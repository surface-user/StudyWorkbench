"""Exercise the packaged UNO client against one native URLTransformer in a temporary Windows job."""
import argparse
import ctypes as c
import hashlib
import json
import os
import re
import secrets
import subprocess
import sys
import time
from pathlib import Path

from check_office_java_pipe import (
    COMPONENTS,
    JAVA_PIPE_MODULES,
    SOURCE,
    checked_output,
    compiled_class_identity,
    fixed_probe_source,
    inspection_kernel,
    observe_modules,
    owned_image,
)

CLIENT_SOURCE = Path(__file__).with_name('office_java_pipe') / 'OfficeUnoClient.java'
CLIENT_SHA256 = '8cb0b934b60380e0f9eb68949e3db8fdbb68bb9eff328cc2d24014c5e8c26b18'
SERVICE = 'com.sun.star.util.URLTransformer'
IMPLEMENTATION = 'com.sun.star.comp.framework.URLTransformer'
OFFICE_MODULES = tuple('program/' + name for name in (
    'sal3.dll', 'cppu3.dll', 'mergedlo.dll', 'iolo.dll', 'binaryurplo.dll', 'vcruntime140.dll'))


def server_command(runtime, directory, pipe_id, instance_id):
    if not all(re.fullmatch('[0-9a-f]{32}', value) for value in (pipe_id, instance_id)) or pipe_id == instance_id:
        raise ValueError('Two distinct single-use identifiers required')
    program = runtime.root / 'program'
    settings = [arg for arg in runtime.command(directory / 'unused.docx', directory) if arg.startswith('-env:')]
    address = f'uno:pipe,name=StudyWorkbench{pipe_id};urp;Probe{instance_id}'
    return [str(program / 'uno.exe'), *settings, '-env:LO_LIB_DIR=' + program.as_uri(),
            '-s', SERVICE, '-u', address, '--singleaccept', '--quiet']


def check_receipt(path, pid):
    expected = f'{pid}\n{IMPLEMENTATION}\nparseStrict\nassemble\n'.encode('ascii')
    with path.open('rb') as stream:
        if stream.read(len(expected) + 1) != expected:
            raise ValueError('Incorrect client PID or remote operation receipt')


def wait_for_pipe(kernel, pipe_id, process, deadline):
    # The fixed LibreOffice Windows implementation prefixes the pipe with the process owner's SID.
    advapi = c.WinDLL('advapi32', use_last_error=True)
    advapi.GetTokenInformation.argtypes = [c.c_void_p, c.c_int, c.c_void_p, c.c_uint32, c.POINTER(c.c_uint32)]
    advapi.ConvertSidToStringSidW.argtypes = [c.c_void_p, c.POINTER(c.c_void_p)]
    kernel.LocalFree.argtypes, kernel.LocalFree.restype = [c.c_void_p], c.c_void_p
    token_user, used, sid_string = c.create_string_buffer(4096), c.c_uint32(), c.c_void_p()
    if not advapi.GetTokenInformation(c.c_void_p(-4), 1, token_user, len(token_user), c.byref(used)):
        raise c.WinError(c.get_last_error())
    if not advapi.ConvertSidToStringSidW(c.c_void_p.from_buffer(token_user), c.byref(sid_string)):
        raise c.WinError(c.get_last_error())
    try:
        pipe = r'\\.\pipe\OSL_PIPE_' + c.wstring_at(sid_string) + '_StudyWorkbench' + pipe_id
    finally:
        kernel.LocalFree(sid_string)
    kernel.WaitNamedPipeW.argtypes = [c.c_wchar_p, c.c_uint32]
    while not kernel.WaitNamedPipeW(pipe, 1):
        if process.poll() is not None or time.monotonic() >= deadline:
            raise RuntimeError('The single-use native listener did not become ready')
        time.sleep(.05)


def run(component, output, javac):
    if os.name != 'nt' or c.sizeof(c.c_void_p) != 8:
        raise ValueError('This diagnostic requires 64-bit Windows')
    sys.path.insert(0, str(SOURCE / 'backend'))
    from study_workbench.office_runtime import OfficeRuntime, WindowsProcessJob, profile_configuration

    runtime = OfficeRuntime(Path(os.path.abspath(component)))
    if runtime.fingerprint not in COMPONENTS:
        raise ValueError('Unsupported Office-Java component')
    out = checked_output(runtime.root, output)
    compiler = javac.resolve(strict=True)
    source = fixed_probe_source(CLIENT_SOURCE, CLIENT_SHA256)
    compiler_hash = hashlib.sha256(compiler.read_bytes()).hexdigest()
    scripts = (Path(__file__), Path(__file__).with_name('check_office_java_pipe.py'))
    script_hashes = {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in scripts}
    deadline = time.monotonic() + 540
    def checkpoint():
        if time.monotonic() >= deadline:
            raise TimeoutError('Component verification exceeded its budget')
    runtime.verify(checkpoint)
    out.mkdir()
    for name in ('profile/user', 'tmp', 'classes', 'cwd'):
        (out / name).mkdir(parents=True)
    (out / 'profile/user/registrymodifications.xcu').write_text(profile_configuration(False), encoding='utf-8')
    env = runtime.environment(out)
    system32 = str(Path(os.environ['SystemRoot']) / 'System32')
    program = runtime.root / 'program'
    jar = program / 'classes/libreoffice.jar'
    cls = out / 'classes/OfficeUnoClient.class'
    with (out / 'javac.log').open('xb') as log:
        subprocess.run([str(compiler), '-proc:none', '--release', '11', '-classpath', str(jar),
                        '-d', str(cls.parent), str(CLIENT_SOURCE)], cwd=out / 'cwd',
                       env=dict(env, PATH=str(compiler.parent) + os.pathsep + system32), stdout=log,
                       stderr=subprocess.STDOUT, timeout=20, check=True, creationflags=subprocess.CREATE_NO_WINDOW)
    class_hash = compiled_class_identity(cls)
    pipe_id, instance_id = secrets.token_hex(16), secrets.token_hex(16)
    kernel, job = inspection_kernel(), WindowsProcessJob()
    host = client = None
    report = dict(component_inventory_sha256=runtime.fingerprint, source_sha256=CLIENT_SHA256,
                  class_sha256=class_hash, compiler_sha256=compiler_hash, controller_sha256=script_hashes,
                  service=SERVICE, ok=False)
    try:
        host = job.start(server_command(runtime, out, pipe_id, instance_id), out / 'cwd', env)
        report['native_host'] = owned_image(kernel, runtime, job, host, 'program/uno.exe')
        limit = time.monotonic() + 30
        wait_for_pipe(kernel, pipe_id, host, limit)
        command = [str(runtime.root / 'java/bin/java.exe'), '-Xmx128m', '-Djava.awt.headless=true',
                   '-Djava.io.tmpdir=' + str(out / 'tmp'), '-Duser.home=' + str(out / 'profile'),
                   '-Djava.library.path=' + str(program), '-classpath', os.pathsep.join([str(cls.parent), str(jar)]),
                   'OfficeUnoClient', pipe_id, instance_id, str(out)]
        client = job.start(command, out / 'cwd', dict(env, PATH=str(runtime.root / 'java/bin') + os.pathsep + system32))
        report['java_client'] = owned_image(kernel, runtime, job, client, 'java/bin/java.exe')
        while not (out / 'ready').exists():
            if client.poll() is not None or host.poll() is not None or time.monotonic() >= limit:
                raise RuntimeError('Native UNO call did not complete; inspect the local client failure file')
            time.sleep(.02)
        check_receipt(out / 'ready', client.pid)
        for proc, paths, key in ((client, JAVA_PIPE_MODULES, 'java_modules'), (host, OFFICE_MODULES, 'native_modules')):
            modules, errors = {}, set()
            observe_modules(kernel, runtime, proc, paths, modules, errors)
            if errors:
                raise ValueError('Incomplete module snapshot of the connected processes')
            report[key] = modules
        (out / 'observer.done').write_bytes(b'ok')
        if client.wait(8) != 0 or host.wait(8) != 0:
            raise RuntimeError('The single-use connection failed to shut down cleanly')
        report['ok'] = True
    except Exception as error:
        # Command lines and connection identifiers are private to this run.
        report['failure_type'] = type(error).__name__
    finally:
        job.close()
        for proc in (client, host):
            if proc is not None:
                try:
                    proc.wait(8)
                finally:
                    proc.close()
    runtime.verify(checkpoint)
    if (fixed_probe_source(CLIENT_SOURCE, CLIENT_SHA256) != source or compiled_class_identity(cls) != class_hash
            or hashlib.sha256(compiler.read_bytes()).hexdigest() != compiler_hash
            or any(hashlib.sha256(path.read_bytes()).hexdigest() != script_hashes[path.name] for path in scripts)):
        raise ValueError('Diagnostic inputs changed during execution')
    (out / 'report.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    if not report['ok']:
        raise RuntimeError('Bounded UNO client diagnostic failed; local evidence preserved')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--component', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--javac', required=True, type=Path)
    args = parser.parse_args()
    run(args.component, args.output, args.javac)
    print('Verified native URLTransformer and the packaged Java client')
