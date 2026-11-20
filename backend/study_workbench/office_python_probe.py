"""Disposable fixed-code checker for the two pinned self-contained Python entry images."""
import ctypes
import hashlib
import json
import os
import stat
import sys
import time
from pathlib import Path

from .office_runtime import PYTHON_CORE, OfficeRuntime, WindowsProcessJob

RUNTIME_SHA256 = 'b0a040bd584bb69aeaba44f749996d2320d83707889b8f8ad85d93d44893c9ee'
MAX_RESULT = 65536
DLL_PATHS = {name: 'bin/' + name for name in ('python313.dll', 'python3.dll', 'vcruntime140.dll')}
DLL_PATHS.update({name: 'lib/' + name for name in ('libcrypto-3.dll', 'libssl-3.dll', 'libffi-8.dll', 'sqlite3.dll')})
PROBE_SCRIPT = r"""import json
import os
import sys
import traceback
from pathlib import Path

output, root = Path(sys.argv[1]), Path(sys.argv[2]).resolve()
result = {'pid': os.getpid(), 'version': list(sys.version_info[:3]), 'ok': False}
try:
    import ctypes
    import hashlib
    import sqlite3
    import ssl
    from ctypes import wintypes as w
    assert sys.version_info[:3] == (3, 13, 15)
    assert Path(sys.prefix).samefile(root) and Path(sys.base_prefix).samefile(root)
    assert Path(sys.executable).parent.samefile(root / 'bin')
    for entry in sys.path:
        assert Path(entry).resolve().is_relative_to(root)
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.GetModuleHandleW.argtypes = [w.LPCWSTR]
    kernel.GetModuleHandleW.restype = w.HMODULE
    kernel.GetModuleFileNameW.argtypes = [w.HMODULE, w.LPWSTR, w.DWORD]
    kernel.GetModuleFileNameW.restype = w.DWORD
    abi = ctypes.PyDLL(str(root / 'bin/python3.dll'))
    abi.Py_IsInitialized.argtypes = []
    abi.Py_IsInitialized.restype = ctypes.c_int
    assert abi.Py_IsInitialized() == 1
    expected = {name: 'bin/' + name for name in ('python313.dll', 'python3.dll', 'vcruntime140.dll')}
    expected.update({name: 'lib/' + name for name in ('libcrypto-3.dll', 'libssl-3.dll', 'libffi-8.dll', 'sqlite3.dll')})
    mapped = {}
    for name, relative in expected.items():
        handle = kernel.GetModuleHandleW(name)
        assert handle, 'Required DLL not observed: ' + name
        buffer = ctypes.create_unicode_buffer(32768)
        length = kernel.GetModuleFileNameW(handle, buffer, len(buffer))
        assert 0 < length < len(buffer), 'Cannot identify DLL: ' + name
        actual = Path(buffer.value)
        assert actual.samefile(root / relative), 'Unexpected DLL identity: ' + name
        mapped[name] = {'path': relative, 'sha256': hashlib.sha256(actual.read_bytes()).hexdigest()}
    with sqlite3.connect(':memory:') as connection:
        assert connection.execute('SELECT 6 * 7').fetchone() == (42,)
    assert ctypes.sizeof(ctypes.c_void_p) == 8
    result.update(ok=True, executable='bin/' + Path(sys.executable).name,
        prefix='.', module_paths=mapped, ssl=ssl.OPENSSL_VERSION, sqlite=sqlite3.sqlite_version,
        abi_functions_exercised=['Py_IsInitialized'], all_exports_certified=False,
        all_process_modules_observed=False, dynamic_isolation_certified=False)
except BaseException as error:
    result.update(error_type=type(error).__name__, error=str(error), traceback=traceback.format_exc())
output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
raise SystemExit(0 if result['ok'] else 1)
"""


def environment(task, core):
    result = {key: os.environ[key] for key in ('SystemRoot', 'WINDIR') if key in os.environ}
    result.update(PATH=str(core / 'bin') + os.pathsep + str(Path(os.environ['SystemRoot']) / 'System32'),
        TEMP=str(task / 'tmp'), TMP=str(task / 'tmp'), APPDATA=str(task / 'profile'),
        LOCALAPPDATA=str(task / 'profile'), USERPROFILE=str(task / 'profile'),
        OPENSSL_CONF=str(task / 'profile/openssl-empty.cnf'), OPENSSL_MODULES=str(core / 'lib'))
    return result


def validate_result(path, pid, entry, files):
    info = path.lstat()
    if (not stat.S_ISREG(info.st_mode) or getattr(info, 'st_file_attributes', 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT
            or not 0 < info.st_size <= MAX_RESULT):
        raise ValueError('Python探针输出类型或预算无效')
    data = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(data, dict):
        raise ValueError('Python探针输出结构无效')
    if (data.get('ok') is not True or data.get('pid') != pid or data.get('version') != [3, 13, 15]
            or data.get('executable') != 'bin/' + entry or data.get('prefix') != '.'
            or data.get('abi_functions_exercised') != ['Py_IsInitialized']
            or data.get('all_exports_certified') is not False or data.get('dynamic_isolation_certified') is not False
            or data.get('all_process_modules_observed') is not False):
        raise ValueError('Python探针进程、版本或有限证据范围不符')
    modules = data.get('module_paths')
    if not isinstance(modules, dict) or set(modules) != set(DLL_PATHS):
        raise ValueError('Python探针缺少固定DLL身份')
    for name, relative in DLL_PATHS.items():
        row = modules[name]
        if (not isinstance(row, dict) or row.get('path') != relative
                or row.get('sha256') != files[PYTHON_CORE + relative]):
            raise ValueError('Python探针DLL路径或hash不符: ' + name)
    return data


def _new_output(directory, runtime_root):
    if (not directory.is_absolute() or str(directory).startswith(('\\\\', '//'))
            or directory.exists() or directory.is_symlink()):
        raise ValueError('Python探针输出必须为全新本地绝对目录')
    for parent in (directory.parent, *directory.parent.parents):
        info = parent.lstat()
        if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT:
            raise ValueError('Python探针输出路径含重解析点')
    if directory.resolve().is_relative_to(runtime_root.resolve()):
        raise ValueError('Python探针输出不得位于组件内')
    directory.mkdir()


def probe(runtime_root, directory):
    if os.name != 'nt' or len(sys.argv) != 4 or sys.argv[1] != '--probe-office-python':
        raise ValueError('Python探针只支持一次性Windows内部helper')
    runtime = OfficeRuntime(runtime_root)
    if not runtime.python_launchers or runtime.fingerprint != RUNTIME_SHA256:
        raise ValueError('Python探针需要精确自包含组合')
    _new_output(directory, runtime.root)
    deadline = time.monotonic() + 540

    def checkpoint():
        if time.monotonic() >= deadline:
            raise ValueError('Python组合校验超过受控时间预算')

    try:
        runtime.verify(checkpoint)
        core = runtime.root / PYTHON_CORE
        script = directory / 'fixed-probe.py'
        script.write_text(PROBE_SCRIPT, encoding='utf-8', newline='\n')
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.SetDllDirectoryW.argtypes = [ctypes.c_wchar_p]
        kernel.SetDllDirectoryW.restype = ctypes.c_int
        # This mode is a disposable helper, never the threaded HTTP server.
        if not kernel.SetDllDirectoryW(None):
            raise ctypes.WinError(ctypes.get_last_error())
        kernel.SetErrorMode.argtypes = [ctypes.c_uint]
        kernel.SetErrorMode.restype = ctypes.c_uint
        previous_error_mode = kernel.SetErrorMode(0x8003)
        entries = []
        try:
            for name in ('python.exe', 'pythonw.exe'):
                checkpoint()
                task = directory / name.removesuffix('.exe')
                for part in ('cwd', 'tmp', 'profile'):
                    (task / part).mkdir(parents=True, exist_ok=True)
                (task / 'profile/openssl-empty.cnf').write_bytes(b'')
                output = task / 'result.json'
                command = [str(core / 'bin' / name), '-I', '-S', '-B', str(script), str(output), str(core)]
                job, process = WindowsProcessJob(), None
                try:
                    process = job.start(command, task / 'cwd', environment(task, core))
                    code = process.wait(20)
                    if code != 0:
                        raise ValueError('固定Python入口探针退出失败: ' + name + ' / ' + str(code))
                    data = validate_result(output, process.pid, name, runtime.files)
                    entries.append(dict(image=name, pid=process.pid, exit_code=code, result=data))
                finally:
                    job.close()
                    if process is not None:
                        try:
                            process.wait(10)
                        finally:
                            process.close()
        finally:
            kernel.SetErrorMode(previous_error_mode)
        runtime.verify(checkpoint)
        with (runtime.root / 'runtime-lock.json').open('rb') as stream:
            if hashlib.file_digest(stream, 'sha256').hexdigest() != runtime.fingerprint:
                raise ValueError('Python组合清单在探针中变化')
        if script.read_text(encoding='utf-8') != PROBE_SCRIPT:
            raise ValueError('固定Python探针脚本在运行中变化')
        result = dict(component_inventory_sha256=runtime.fingerprint,
            mode='frozen' if getattr(sys, 'frozen', False) else 'source',
            probe_script_sha256=hashlib.sha256(PROBE_SCRIPT.encode('utf-8')).hexdigest(),
            entries=entries, component_bytes_preserved=True, full_export_interface_certified=False,
            dynamic_isolation_certified=False, product_release_ready=False)
        (directory / 'report.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n',
                                              encoding='utf-8', newline='\n')
        return result
    except BaseException as error:
        (directory / 'failure.json').write_text(json.dumps(dict(type=type(error).__name__, message=str(error)),
            ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
        raise
