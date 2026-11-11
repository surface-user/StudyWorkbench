"""Pinned optional LibreOffice runtime; each conversion owns a fresh profile and process job."""
import ctypes
import hashlib
import json
import os
import re
import stat
import subprocess
import sys
import time
from pathlib import Path, PurePosixPath

from fastapi import HTTPException

from .imports import resource_path
from .office_inputs import MAX_SOURCE, validate_office

VERSION = '26.8.1'
PACKAGE_SHA256 = 'c6298b10cfa1748bcbedad94c62ce771e240e5021bfd6d7a967cd571b04b5312'
OFFICE_LOCK_SHA256 = '147d21f38890236a51ac3b079d4632690ce7ae12f1470d6896aaef3597a0f8ca'
JAVA_LOCK_SHA256 = '159433e3a2fc9f2a9c4f633a613d3db5aaca29d1b52caa64e3a63755ac8e1907'
JAVA = {'version': '21.0.13+9', 'directory': 'java',
        'package_sha256': '2332c0b4cff6bed722da3567c91d5e47568bcba863fa4945d0a8d6fc76158628'}
APP_LOCAL_CRT = ('msvcp140.dll', 'msvcp140_1.dll', 'msvcp140_2.dll', 'msvcp140_atomic_wait.dll',
                 'msvcp140_codecvt_ids.dll', 'vcruntime140.dll', 'vcruntime140_1.dll', 'vcruntime140_threads.dll')
OPTIONS = 'pdf-static-v3-no-macros-no-external-links-internal-charts-math'
PROFILE = '''<?xml version="1.0" encoding="UTF-8"?>
<oor:items xmlns:oor="http://openoffice.org/2001/registry">
<item oor:path="/org.openoffice.Office.Common/Security/Scripting">
<prop oor:name="MacroSecurityLevel" oor:op="fuse"><value>3</value></prop>
<prop oor:name="DisableMacrosExecution" oor:op="fuse"><value>true</value></prop>
<prop oor:name="DisableActiveContent" oor:op="fuse"><value>true</value></prop>
<prop oor:name="DisablePythonRuntime" oor:op="fuse"><value>true</value></prop>
<prop oor:name="DisableOLEAutomation" oor:op="fuse"><value>true</value></prop>
<prop oor:name="BlockUntrustedRefererLinks" oor:op="fuse"><value>true</value></prop>
</item>
<item oor:path="/org.openoffice.Office.Writer/Content/Update">
<prop oor:name="Link" oor:op="fuse"><value>2</value></prop>
<prop oor:name="Field" oor:op="fuse"><value>false</value></prop>
<prop oor:name="Chart" oor:op="fuse"><value>false</value></prop>
</item>
</oor:items>'''


class ConversionStopped(Exception):
    pass


def profile_configuration(internal_rendering):
    # Internal charts/OMML are active content; only input-gated packages enable their rendering.
    return PROFILE.replace(
        '<prop oor:name="DisableActiveContent" oor:op="fuse"><value>true</value></prop>',
        '<prop oor:name="DisableActiveContent" oor:op="fuse"><value>false</value></prop>'
    ) if internal_rendering else PROFILE


def native_directory(directory):
    # Some Office profile services still fail on deep paths; the alias must name the same directory.
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.GetShortPathNameW.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint32]
    kernel.GetShortPathNameW.restype = ctypes.c_uint32
    buffer = ctypes.create_unicode_buffer(32768)
    length = kernel.GetShortPathNameW(str(directory), buffer, len(buffer))
    if not length or length >= len(buffer):
        return directory
    native = Path(buffer.value)
    if not native.is_absolute() or not os.path.samefile(directory, native):
        raise ValueError('Office短路径不再指向同一任务目录')
    return native


class OfficeProcess:
    def __init__(self, handle, pid, command):
        self.handle, self.pid, self.command = handle, pid, command
        self.returncode = None

    def poll(self):
        import _winapi
        if self.returncode is None and _winapi.WaitForSingleObject(self.handle, 0) == 0:
            self.returncode = _winapi.GetExitCodeProcess(self.handle)
        return self.returncode

    def wait(self, timeout):
        import _winapi
        if _winapi.WaitForSingleObject(self.handle, int(timeout * 1000)) == 258:
            raise subprocess.TimeoutExpired(self.command, timeout)
        self.returncode = _winapi.GetExitCodeProcess(self.handle)
        return self.returncode

    def close(self):
        import _winapi
        if self.handle is not None:
            _winapi.CloseHandle(self.handle)
            self.handle = None


class WindowsProcessJob:
    """Kill only this conversion's descendants if cancelled or if the backend exits."""
    def __init__(self):
        from ctypes import wintypes as w

        class Limits(ctypes.Structure):
            _fields_ = [('process_time', ctypes.c_longlong), ('job_time', ctypes.c_longlong),
                        ('flags', w.DWORD), ('min_ws', ctypes.c_size_t), ('max_ws', ctypes.c_size_t),
                        ('processes', w.DWORD), ('affinity', ctypes.c_size_t),
                        ('priority', w.DWORD), ('scheduling', w.DWORD)]

        class Counters(ctypes.Structure):
            _fields_ = [(name, ctypes.c_ulonglong) for name in
                        ('read_ops', 'write_ops', 'other_ops', 'read_bytes', 'write_bytes', 'other_bytes')]

        class Extended(ctypes.Structure):
            _fields_ = [('basic', Limits), ('io', Counters), ('process_memory', ctypes.c_size_t),
                        ('job_memory', ctypes.c_size_t), ('peak_process', ctypes.c_size_t),
                        ('peak_job', ctypes.c_size_t)]

        self.kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        self.kernel.CreateJobObjectW.argtypes = [ctypes.c_void_p, w.LPCWSTR]
        self.kernel.CreateJobObjectW.restype = w.HANDLE
        self.kernel.SetInformationJobObject.argtypes = [w.HANDLE, ctypes.c_int, ctypes.c_void_p, w.DWORD]
        self.kernel.SetInformationJobObject.restype = w.BOOL
        self.kernel.AssignProcessToJobObject.argtypes = [w.HANDLE, w.HANDLE]
        self.kernel.AssignProcessToJobObject.restype = w.BOOL
        self.kernel.ResumeThread.argtypes = [w.HANDLE]
        self.kernel.ResumeThread.restype = w.DWORD
        self.kernel.CloseHandle.argtypes = [w.HANDLE]
        self.kernel.CloseHandle.restype = w.BOOL
        self.handle = self.kernel.CreateJobObjectW(None, None)
        if not self.handle:
            raise ctypes.WinError(ctypes.get_last_error())
        limits = Extended()
        limits.basic.flags = 0x2000 | 0x200 | 0x8  # Kill-on-close, aggregate memory, active process count.
        limits.basic.processes = 4
        limits.job_memory = 1024 * 1024 * 1024
        if not self.kernel.SetInformationJobObject(self.handle, 9, ctypes.byref(limits), ctypes.sizeof(limits)):
            self.close()
            raise OSError('无法限制转换进程资源')

    def start(self, command, directory, environment):
        import _winapi
        startup = subprocess.STARTUPINFO()
        startup.dwFlags = subprocess.STARTF_USESHOWWINDOW
        startup.wShowWindow = 0
        # Attach while suspended: soffice.com must not spawn an unowned child first.
        handle, thread, pid, _ = _winapi.CreateProcess(
            command[0], subprocess.list2cmdline(command), None, None, False,
            subprocess.CREATE_NO_WINDOW | 0x4, environment, str(directory), startup)
        try:
            if not self.kernel.AssignProcessToJobObject(self.handle, handle):
                raise OSError('无法隔离本次转换进程')
            if self.kernel.ResumeThread(thread) == 0xFFFFFFFF:
                raise OSError('无法启动本次转换进程')
        except BaseException:
            _winapi.TerminateProcess(handle, 1)
            _winapi.CloseHandle(handle)
            raise
        finally:
            _winapi.CloseHandle(thread)
        return OfficeProcess(handle, pid, command)

    def close(self):
        if self.handle:
            self.kernel.CloseHandle(self.handle)
            self.handle = None


class OfficeRuntime:
    def __init__(self, directory):
        self.root = Path(directory)
        if not self.root.is_absolute() or str(self.root).startswith(('\\\\', '//')):
            raise ValueError('转换运行时必须为本地绝对路径')
        for parent in [self.root, *self.root.parents]:
            info = parent.lstat()
            if getattr(info, 'st_file_attributes', 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT:
                raise ValueError('转换运行时路径含重解析点')
        manifest_path = resource_path(self.root, 'runtime-lock.json')
        with manifest_path.open('rb') as handle:
            raw = handle.read(4 * 1024 * 1024 + 1)
        if len(raw) > 4 * 1024 * 1024:
            raise ValueError('运行时清单超限')
        manifest = json.loads(raw)
        if not isinstance(manifest, dict) or manifest.get('version') != VERSION or manifest.get('package_sha256') != PACKAGE_SHA256:
            raise ValueError('转换器版本未锁定')
        self.files = manifest['files']
        if not isinstance(self.files, dict) or not 1 <= len(self.files) <= 20000:
            raise ValueError('转换器文件清单无效')
        for relative, checksum in self.files.items():
            if (not isinstance(relative, str) or not isinstance(checksum, str)
                    or not re.fullmatch('[a-f0-9]{64}', checksum)):
                raise ValueError('转换器校验清单无效')
            if (relative.startswith('/') or '\\' in relative or
                    any(part in {'.', '..'} or ':' in part for part in PurePosixPath(relative).parts)):
                raise ValueError('转换器清单路径无效')
        if not {'program/soffice.com', 'program/soffice.bin', 'license.txt', 'NOTICE'} <= self.files.keys():
            raise ValueError('转换器或许可文件缺失')
        self.java_home = None
        if 'java' not in manifest and ('office-runtime-lock.json' in self.files or
                                       any(name.startswith('java/') for name in self.files)):
            raise ValueError('Office配套Java缺少组合清单声明')
        if 'java' in manifest:
            if manifest['java'] != JAVA:
                raise ValueError('Office配套Java版本未锁定')
            components = []
            for name, checksum in [('office-runtime-lock.json', OFFICE_LOCK_SHA256),
                                   ('java/java-runtime-lock.json', JAVA_LOCK_SHA256)]:
                with resource_path(self.root, name).open('rb') as handle:
                    component = handle.read(4 * 1024 * 1024 + 1)
                if hashlib.sha256(component).hexdigest() != checksum:
                    raise ValueError('Office配套组件原始清单已变化')
                components.append(json.loads(component))
            original, java = components
            expected = dict(original['files'])
            expected.update({'java/' + name: checksum for name, checksum in java['files'].items()})
            expected.update({'office-runtime-lock.json': OFFICE_LOCK_SHA256,
                             'java/java-runtime-lock.json': JAVA_LOCK_SHA256})
            expected.update({'program/' + name: original['files']['System64/' + name] for name in APP_LOCAL_CRT})
            if self.files != expected:
                raise ValueError('Office组合清单未完整保留固定组件或CRT')
            self.java_home = resource_path(self.root, 'java')
        self.executable = resource_path(self.root, 'program/soffice.com')
        for name in ['program/soffice.com', 'program/soffice.bin']:
            with resource_path(self.root, name).open('rb') as handle:
                if hashlib.file_digest(handle, 'sha256').hexdigest() != self.files[name]:
                    raise ValueError('转换器入口校验失败')
        self.fingerprint = hashlib.sha256(raw).hexdigest()

    def verify(self, checkpoint):
        found = set()
        directories = [self.root]
        while directories:
            with os.scandir(directories.pop()) as entries:
                for entry in entries:
                    checkpoint()
                    info = entry.stat(follow_symlinks=False)
                    if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT:
                        raise ValueError('离线转换包含重解析点')
                    path = Path(entry.path)
                    if entry.is_dir(follow_symlinks=False):
                        directories.append(path)
                        continue
                    relative = path.relative_to(self.root).as_posix()
                    if relative == 'runtime-lock.json' or path.suffix.lower() == '.msi':
                        continue
                    expected = self.files.get(relative)
                    if expected is None:
                        raise ValueError('离线转换包含未登记文件，请重新准备已核版本')
                    digest = hashlib.sha256()
                    with path.open('rb') as handle:
                        while chunk := handle.read(1024 * 1024):
                            checkpoint()
                            digest.update(chunk)
                    if digest.hexdigest() != expected:
                        raise ValueError('离线转换包缺失或已变化，请重新准备已核版本')
                    found.add(relative)
        if found != self.files.keys():
            raise ValueError('离线转换包文件缺失')

    def environment(self, directory):
        profile, temporary = directory / 'profile', directory / 'tmp'
        environment = {key: os.environ[key] for key in ('SystemRoot', 'WINDIR') if key in os.environ}
        environment.update(PATH=str(self.executable.parent) + os.pathsep +
                           str(Path(os.environ['SystemRoot']) / 'System32'),
                           TEMP=str(temporary), TMP=str(temporary), APPDATA=str(profile),
                           LOCALAPPDATA=str(profile), USERPROFILE=str(profile),
                           SAL_DISABLESKIA='1', SAL_DISABLE_OPENCL='1')
        if self.java_home is not None:
            environment.update(JAVA_HOME=str(self.java_home), UNO_JAVA_JFW_JREHOME=self.java_home.as_uri(),
                               UNO_JAVA_JFW_PARAMETER_1='-Djava.awt.headless=true')
            environment['PATH'] = os.pathsep.join((str(self.executable.parent), str(self.java_home / 'bin'),
                                                   str(self.java_home / 'bin/server'),
                                                   str(Path(os.environ['SystemRoot']) / 'System32')))
        return environment

    def command(self, source, directory):
        filter_name = 'writer_pdf_Export' if source.suffix == '.docx' else 'impress_pdf_Export'
        return [str(self.executable), '-env:UserInstallation=' + (directory / 'profile').as_uri(),
                '--headless', '--nologo', '--nodefault', '--norestore', '--quickstart=no',
                '--convert-to', 'pdf:' + filter_name, '--outdir', str(directory / 'output'), str(source)]

    def convert(self, source, directory, checkpoint, timeout=90):
        internal_rendering = validate_office(source.read_bytes(), source.suffix)
        self.verify(checkpoint)
        profile = directory / 'profile'
        (profile / 'user').mkdir(parents=True)
        configuration = profile_configuration(internal_rendering)
        (profile / 'user/registrymodifications.xcu').write_text(configuration, encoding='utf-8')
        output = directory / 'output'
        output.mkdir()
        temporary = directory / 'tmp'
        temporary.mkdir()
        native = directory
        if getattr(sys, 'frozen', False):
            if source != directory / ('source' + source.suffix):
                raise ValueError('冻结转换只读取本任务固定source文件')
            command = [sys.executable, '--launch-office', str(self.root), str(directory), source.suffix]
        else:
            native = native_directory(directory)
            command = self.command(native / source.name, native)
        environment = self.environment(native)
        job = WindowsProcessJob()
        process = None
        try:
            checkpoint()
            process = job.start(command, native, environment)
            deadline = time.monotonic() + timeout
            while process.poll() is None:
                checkpoint()
                if time.monotonic() >= deadline:
                    raise ValueError('转换超过90秒，进程已停止；原件与任务保留')
                time.sleep(.1)
            checkpoint()
            if process.returncode != 0:
                raise ValueError('转换未完成，可能损坏、加密或超过资源限制；原件保留')
        finally:
            job.close()
            if process is not None:
                try:
                    process.wait(timeout=10)
                finally:
                    process.close()
        return output / (source.stem + '.pdf')


def launch_office(runtime_root, directory, suffix):
    """Only the disposable helper clears its inherited DLL directory, never the threaded backend."""
    if os.name != 'nt' or not getattr(sys, 'frozen', False) or suffix not in {'.docx', '.pptx'}:
        raise ValueError('只支持冻结Windows内部Office入口')
    if not directory.is_absolute() or str(directory).startswith(('\\\\', '//')):
        raise ValueError('转换任务必须为本地绝对目录')
    instance = OfficeRuntime(runtime_root)
    source = resource_path(directory, 'source' + suffix)
    for name in ['profile/user/registrymodifications.xcu', 'output', 'tmp']:
        if not resource_path(directory, name).exists():
            raise ValueError('转换任务配置不完整')
    with source.open('rb') as handle:
        raw = handle.read(MAX_SOURCE + 1)
    internal_rendering = validate_office(raw, suffix)
    expected_profile = profile_configuration(internal_rendering)
    with resource_path(directory, 'profile/user/registrymodifications.xcu').open('r', encoding='utf-8') as handle:
        if handle.read(len(expected_profile) + 1) != expected_profile:
            raise ValueError('转换配置已变化，拒绝启动外部组件')
    native = native_directory(directory)
    command, environment = instance.command(native / source.name, native), instance.environment(native)
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.SetDllDirectoryW.argtypes = [ctypes.c_wchar_p]
    kernel.SetDllDirectoryW.restype = ctypes.c_int
    if not kernel.SetDllDirectoryW(None):
        raise ctypes.WinError(ctypes.get_last_error())
    return subprocess.run(command, cwd=native, env=environment, stdin=subprocess.DEVNULL,
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                          creationflags=subprocess.CREATE_NO_WINDOW).returncode


def runtime():
    if os.name != 'nt':
        raise ValueError('当前分页转换包仅验证Windows x64')
    directory = os.environ.get('STUDY_OFFICE_RUNTIME')
    if directory is None:
        directory = (Path(sys.executable).resolve().parent.parent / 'converters/libreoffice'
                     if getattr(sys, 'frozen', False) else
                     Path(__file__).resolve().parents[2] / '.local/release-tools/libreoffice-26.8.1')
    return OfficeRuntime(directory)


def capability():
    try:
        instance = runtime()
        return dict(available=True, converter='LibreOffice', version=VERSION,
                    fingerprint=instance.fingerprint, options=OPTIONS)
    except (OSError, ValueError, KeyError, TypeError, HTTPException):
        return dict(available=False, converter='LibreOffice', version=VERSION,
                    reason='未找到已核验的离线转换包；可先使用Word结构预览，或在外部转PDF后添加')
