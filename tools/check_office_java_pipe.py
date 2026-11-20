"""Developer-only fixed Java UNO pipe diagnostic; never changes native/release policy.

An existing javac compiles this repository's pinned diagnostic. The packaged JRE
loads only the fixed Office jar with a parentless URLClassLoader and attempts an
OPEN-only connection to a new UUID pipe name. Expected native failure is success
for this finite diagnostic; ordinary Office/fallback/isolation remain unproven.
"""
import argparse
import ctypes as c
import hashlib
import json
import os
import stat
import subprocess
import sys
import time
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[1]
PROBE_SOURCE = Path(__file__).with_name('office_java_pipe') / 'PipeDiagnostic.java'
PROBE_SHA256 = '3845c5d1ebe2e164c5eaaab3a446857409fb83fd94d16afc7eb1a88abb66edb0'
COMPONENTS = {'156b4421aeb8eaadb565d6d33234bf69c58d22b5e46b78c9de81548dfe7b9bc9',
    'b0a040bd584bb69aeaba44f749996d2320d83707889b8f8ad85d93d44893c9ee'}


def checked_output(component, output):
    component = component.resolve(strict=True)
    candidate = output.absolute()
    if candidate.exists() or candidate.is_symlink():
        raise ValueError('Choose a new output directory; previous evidence is never overwritten')
    for ancestor in candidate.parents:
        if ancestor.exists():
            info = ancestor.lstat()
            if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
                raise ValueError('Output directory cannot traverse a reparse point')
    candidate = candidate.resolve()
    if candidate.is_relative_to(component) or component.is_relative_to(candidate):
        raise ValueError('Diagnostic output must be separate from the immutable component')
    if not candidate.parent.is_dir():
        raise ValueError('Output parent directory must already exist')
    return candidate


def fixed_probe_source(path=PROBE_SOURCE):
    with path.open('rb') as stream:
        raw = stream.read(16385)
    if len(raw) > 16384 or hashlib.sha256(raw).hexdigest() != PROBE_SHA256:
        raise ValueError('Fixed Java diagnostic source changed')
    return raw


def compiled_class_identity(path):
    with path.open('rb') as stream:
        raw = stream.read(65537)
    if not 8 <= len(raw) <= 65536 or raw[:8] != bytes.fromhex('cafebabe00000037'):
        raise ValueError('Expected bounded Java 11 diagnostic class')
    return hashlib.sha256(raw).hexdigest()


def checked_java_result(path, pid):
    with path.open('rb') as stream:
        raw = stream.read(65537)
    if not 0 < len(raw) <= 65536:
        raise ValueError('Java diagnostic result exceeds budget')
    result = json.loads(raw)
    if not isinstance(result, dict):
        raise ValueError('Expected Java diagnostic result object')
    flags = ('ok', 'expected_missing_pipe_ioexception', 'classloader_parent_null', 'packaged_resource_matches_fixed_jpipe')
    if (type(result.get('pid')) is not int or result['pid'] != pid
            or any(result.get(key) is not True for key in flags)
            or result.get('office_host_execution_verified') is not False):
        raise ValueError('Java result does not prove the owned finite diagnostic')
    return result


def module_identity(root, files, path, canonical, pid):
    if not path.samefile(root / canonical):
        raise ValueError('Actual module came from a different loading domain')
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != files[canonical]:
        raise ValueError('Actual module bytes changed')
    return dict(path=path.relative_to(root).as_posix(), canonical_path=canonical, sha256=digest, observed_pid=pid)


def run_diagnostic(component, output, javac):
    if os.name != 'nt' or c.sizeof(c.c_void_p) != 8:
        raise ValueError('This fixed diagnostic requires 64-bit Windows')
    sys.path.insert(0, str(SOURCE / 'backend'))
    from study_workbench.office_runtime import OfficeRuntime, WindowsProcessJob

    component = Path(os.path.abspath(component))
    out = checked_output(component, output)
    runtime = OfficeRuntime(component)
    if runtime.fingerprint not in COMPONENTS:
        raise ValueError('Use only the fixed Office-Java or self-contained component')
    compiler = javac.resolve(strict=True)
    if not compiler.is_file():
        raise ValueError('Existing javac executable required; no compiler is installed by this tool')
    script_raw = fixed_probe_source()
    out.mkdir()
    for name in ('cwd', 'tmp', 'profile', 'classes'):
        (out / name).mkdir()
    deadline = time.monotonic() + 540
    def checkpoint():
        assert time.monotonic() < deadline, 'Full component verification budget exceeded'
    runtime.verify(checkpoint)
    def sha(path):
        return hashlib.sha256(path.read_bytes()).hexdigest()
    raw_script = Path(__file__).read_bytes()
    java_source = PROBE_SOURCE
    java_class = out / 'classes/PipeDiagnostic.class'
    environment = {key: os.environ[key] for key in ('SystemRoot', 'WINDIR') if key in os.environ}
    environment.update(PATH=str(compiler.parent) + os.pathsep + str(Path(os.environ['SystemRoot']) / 'System32'),
        TEMP=str(out / 'tmp'), TMP=str(out / 'tmp'), APPDATA=str(out / 'profile'),
        LOCALAPPDATA=str(out / 'profile'), USERPROFILE=str(out / 'profile'))
    compiler_hash = sha(compiler)
    version = subprocess.run([str(compiler), '-version'], cwd=out / 'cwd', env=environment,
        capture_output=True, timeout=20, creationflags=subprocess.CREATE_NO_WINDOW)
    if version.returncode != 0:
        raise ValueError('Existing javac version check failed')
    compiled = subprocess.run([str(compiler), '--release', '11', '-d', str(out / 'classes'), str(java_source)],
        cwd=out / 'cwd', env=environment, capture_output=True, timeout=20, creationflags=subprocess.CREATE_NO_WINDOW)
    (out / 'javac.log').write_bytes(compiled.stdout + compiled.stderr)
    if compiled.returncode != 0:
        raise ValueError('Fixed Java diagnostic compilation failed; log retained')
    class_hash = compiled_class_identity(java_class)
    identities = dict(source_sha256=hashlib.sha256(script_raw).hexdigest(), class_sha256=class_hash,
        controller_sha256=hashlib.sha256(raw_script).hexdigest(), compiler_sha256=compiler_hash,
        compiler_version=(version.stdout + version.stderr).decode('utf-8', errors='replace').strip(), release_target=11)
    kernel = c.WinDLL('kernel32', use_last_error=True)
    kernel.IsProcessInJob.argtypes, kernel.IsProcessInJob.restype = [c.c_void_p, c.c_void_p, c.POINTER(c.c_int)], c.c_int
    kernel.QueryFullProcessImageNameW.argtypes = [c.c_void_p, c.c_uint32, c.c_wchar_p, c.POINTER(c.c_uint32)]
    kernel.QueryFullProcessImageNameW.restype = c.c_int
    kernel.K32EnumProcessModulesEx.argtypes = [c.c_void_p, c.c_void_p, c.c_uint32, c.POINTER(c.c_uint32), c.c_uint32]
    kernel.K32EnumProcessModulesEx.restype = c.c_int
    kernel.K32GetModuleFileNameExW.argtypes = [c.c_void_p, c.c_void_p, c.c_wchar_p, c.c_uint32]
    kernel.K32GetModuleFileNameExW.restype = c.c_uint32
    environment = {key: os.environ[key] for key in ('SystemRoot', 'WINDIR') if key in os.environ}
    environment.update(PATH=str(runtime.root / 'java/bin') + os.pathsep + str(Path(os.environ['SystemRoot']) / 'System32'),
        TEMP=str(out / 'tmp'), TMP=str(out / 'tmp'), APPDATA=str(out / 'profile'),
        LOCALAPPDATA=str(out / 'profile'), USERPROFILE=str(out / 'profile'))
    job, process, result, modules, errors = WindowsProcessJob(), None, {}, {}, set()
    folded = {name.casefold(): name for name in runtime.files}
    selected = {'jpipe.dll', 'jpipx.dll', 'sal3.dll', 'vcruntime140.dll', 'msvcp140.dll', 'jvm.dll', 'java.dll'}
    report = dict(scope='Owned fixed-JRE Java UNO missing-pipe diagnostic, not ordinary Office-host proof',
        component_inventory_sha256=runtime.fingerprint, full_component_verified_before_after=False,
        identities=identities, product_release_ready=False, ordinary_office_execution_verified=False,
        native_loader_fallback_controlled_globally=False)
    try:
        process = job.start([str(runtime.root / 'java/bin/java.exe'), '-Xmx128m', '-Djava.awt.headless=true',
            '-Djava.io.tmpdir=' + str(out / 'tmp'), '-Duser.home=' + str(out / 'profile'),
            '-cp', str(java_class.parent), 'PipeDiagnostic', str(runtime.root), str(out / 'result.json'),
            str(out / 'observer.done')], out / 'cwd', environment)
        member = c.c_int()
        assert kernel.IsProcessInJob(process.handle, job.handle, c.byref(member)) and member.value
        buffer, capacity = c.create_unicode_buffer(32768), c.c_uint32(32768)
        assert kernel.QueryFullProcessImageNameW(process.handle, 0, buffer, c.byref(capacity))
        assert Path(buffer.value).samefile(runtime.root / 'java/bin/java.exe')
        assert sha(Path(buffer.value)) == runtime.files['java/bin/java.exe']
        child_deadline = time.monotonic() + 20
        result_path = out / 'result.json'
        while not result_path.exists():
            assert process.poll() is None, 'Diagnostic exited before JNI result'
            assert time.monotonic() < child_deadline, 'Diagnostic exceeded 20s'
            time.sleep(.01)
        assert 0 < result_path.stat().st_size <= 65536
        result = checked_java_result(result_path, process.pid)
        array, needed = (c.c_void_p * 4096)(), c.c_uint32()
        assert kernel.K32EnumProcessModulesEx(process.handle, array, c.sizeof(array), c.byref(needed), 3)
        assert needed.value <= c.sizeof(array)
        for module in array[:needed.value // c.sizeof(c.c_void_p)]:
            length = kernel.K32GetModuleFileNameExW(process.handle, module, buffer, len(buffer))
            if not 0 < length < len(buffer):
                errors.add(('module-name', c.get_last_error()))
                continue
            path = Path(buffer.value)
            name = path.name.casefold()
            if name not in selected:
                continue
            canonical = folded[('java/bin/server/' if name == 'jvm.dll' else 'java/bin/' if name in {
                'java.dll', 'vcruntime140.dll', 'msvcp140.dll'} else 'program/') + name]
            modules[name] = module_identity(runtime.root, runtime.files, path, canonical, process.pid)
        assert selected <= modules.keys(), ('Missing required observed modules', selected - modules.keys())
        (out / 'observer.done').write_bytes(b'owned selected modules verified')
        code = process.wait(max(1, child_deadline - time.monotonic()))
        assert code == 0
        report.update(ok=True, exit_code=code, result=result, module_paths=modules,
            observed_java_image=dict(path='java/bin/java.exe', sha256=runtime.files['java/bin/java.exe'], pid=process.pid))
    except BaseException as error:
        report.update(ok=False, error_type=type(error).__name__, error=str(error), module_paths=modules)
    finally:
        job.close()
        if process is not None:
            try:
                process.wait(10)
            finally:
                process.close()
        report['sampling_errors'] = [dict(stage=stage, code=code) for stage, code in sorted(errors)]
    runtime.verify(checkpoint)
    assert java_source.is_file() and sha(java_source) == identities['source_sha256']
    assert compiled_class_identity(java_class) == identities['class_sha256'] and Path(__file__).read_bytes() == raw_script
    assert fixed_probe_source() == script_raw and sha(compiler) == compiler_hash
    report['full_component_verified_before_after'] = True
    (out / 'report.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    if report['ok'] is not True:
        raise ValueError('Original bounded diagnostic failure retained in report.json')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--component', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--javac', type=Path, required=True, help='Existing developer JDK javac; never installed by this checker')
    args = parser.parse_args()
    report = run_diagnostic(args.component, args.output, args.javac)
    print(json.dumps(dict(ok=report['ok'], report=str(args.output / 'report.json'),
        ordinary_office_execution_verified=False, native_loader_fallback_controlled_globally=False)))


if __name__ == '__main__':
    main()
