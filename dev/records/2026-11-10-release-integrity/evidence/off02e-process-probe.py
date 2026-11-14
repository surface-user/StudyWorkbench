"""Read only this probe's Office descendants; Windows x64 diagnostic, not product code."""
import argparse
import ctypes as c
from ctypes import wintypes as w
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'backend'))
from study_workbench.office_runtime import OfficeRuntime

assert os.name == 'nt' and struct.calcsize('P') == 8
kernel = c.WinDLL('kernel32', use_last_error=True)
native = c.WinDLL('ntdll')

class Entry(c.Structure):
    _fields_ = [('size', w.DWORD), ('usage', w.DWORD), ('pid', w.DWORD), ('heap', c.c_size_t),
                ('module', w.DWORD), ('threads', w.DWORD), ('parent', w.DWORD), ('priority', w.LONG),
                ('flags', w.DWORD), ('name', w.WCHAR * 260)]

class Basic(c.Structure):
    _fields_ = [('exit', w.LONG), ('peb', c.c_void_p), ('affinity', c.c_size_t), ('priority', w.LONG),
                ('pid', c.c_size_t), ('parent', c.c_size_t)]

class Region(c.Structure):
    _fields_ = [('base', c.c_void_p), ('allocation', c.c_void_p), ('allocation_protect', w.DWORD),
                ('partition', w.WORD), ('size', c.c_size_t), ('state', w.DWORD),
                ('protect', w.DWORD), ('type', w.DWORD)]

kernel.CreateToolhelp32Snapshot.argtypes = [w.DWORD, w.DWORD]
kernel.CreateToolhelp32Snapshot.restype = w.HANDLE
kernel.Process32FirstW.argtypes = [w.HANDLE, c.POINTER(Entry)]
kernel.Process32NextW.argtypes = [w.HANDLE, c.POINTER(Entry)]
kernel.CloseHandle.argtypes = [w.HANDLE]
kernel.OpenProcess.argtypes = [w.DWORD, w.BOOL, w.DWORD]
kernel.OpenProcess.restype = w.HANDLE
kernel.ReadProcessMemory.argtypes = [w.HANDLE, c.c_void_p, c.c_void_p, c.c_size_t, c.POINTER(c.c_size_t)]
kernel.VirtualQueryEx.argtypes = [w.HANDLE, c.c_void_p, c.POINTER(Region), c.c_size_t]
kernel.VirtualQueryEx.restype = c.c_size_t
native.NtQueryInformationProcess.argtypes = [w.HANDLE, c.c_int, c.c_void_p, w.ULONG, c.c_void_p]
native.NtQueryInformationProcess.restype = w.LONG
shell = c.WinDLL('shell32')
shell.CommandLineToArgvW.argtypes = [w.LPCWSTR, c.POINTER(c.c_int)]
shell.CommandLineToArgvW.restype = c.POINTER(w.LPWSTR)
kernel.LocalFree.argtypes = [c.c_void_p]

def descendants(root_pid):
    snapshot = kernel.CreateToolhelp32Snapshot(2, 0)
    if snapshot == c.c_void_p(-1).value:
        raise c.WinError(c.get_last_error())
    entries = {}
    try:
        item = Entry(size=c.sizeof(Entry))
        more = kernel.Process32FirstW(snapshot, c.byref(item))
        while more:
            entries[item.pid] = (item.parent, item.name)
            more = kernel.Process32NextW(snapshot, c.byref(item))
    finally:
        kernel.CloseHandle(snapshot)
    owned = {root_pid}
    for _ in range(12):
        expanded = owned | {pid for pid, (parent, _) in entries.items() if parent in owned}
        if expanded == owned:
            break
        owned = expanded
    return {pid: entries[pid] for pid in owned - {root_pid} if pid in entries}

def parameters(pid, expected_parent):
    handle = kernel.OpenProcess(0x410, False, pid)
    if not handle:
        raise c.WinError(c.get_last_error())
    try:
        def read(address, size):
            assert address and 0 < size <= 65536
            value, count = c.create_string_buffer(size), c.c_size_t()
            if not kernel.ReadProcessMemory(handle, address, value, size, c.byref(count)) or count.value != size:
                raise c.WinError(c.get_last_error())
            return value.raw

        basic = Basic()
        assert native.NtQueryInformationProcess(handle, 0, c.byref(basic), c.sizeof(basic), None) == 0
        assert basic.pid == pid and basic.parent == expected_parent
        params = struct.unpack('<Q', read(basic.peb + 0x20, 8))[0]
        # PEB/command layout follows Windows SDK; environment offset is a locally checked x64 diagnostic ABI.
        raw = read(params + 0x60, 40)
        def text_at(offset):
            length, maximum, pointer = struct.unpack_from('<HH4xQ', raw, offset)
            assert length % 2 == 0 and 0 < length <= maximum <= 65534
            return read(pointer, length).decode('utf-16-le')
        image, command = text_at(0), text_at(16)
        pointer = struct.unpack_from('<Q', raw, 32)[0]
        region = Region()
        assert kernel.VirtualQueryEx(handle, pointer, c.byref(region), c.sizeof(region)) == c.sizeof(region)
        budget = min(65536, region.size - (pointer - region.base))
        snapshot = read(pointer, budget)
        assert struct.unpack('<Q', read(params + 0x80, 8))[0] == pointer, 'environment changed during snapshot'
        strings, segment = [], bytearray()
        for offset in range(0, len(snapshot) - 1, 2):
            pair = snapshot[offset:offset + 2]
            if pair == b'\0\0':
                if not segment:
                    break
                strings.append(segment.decode('utf-16-le'))
                segment.clear()
            else:
                segment.extend(pair)
        else:
            raise AssertionError('Environment exceeds diagnostic budget')
        assert all('=' in value for value in strings), 'environment changed during parse'
        environment = dict(value.split('=', 1) for value in strings if not value.startswith('='))
        count = c.c_int()
        argv = shell.CommandLineToArgvW(command, c.byref(count))
        assert argv
        try:
            arguments = [argv[index] for index in range(count.value)]
        finally:
            kernel.LocalFree(argv)
        return image, arguments, environment
    finally:
        kernel.CloseHandle(handle)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--mode', choices=['source', 'frozen'], required=True)
    parser.add_argument('--test-root', type=Path, required=True)
    args = parser.parse_args()
    runtime = OfficeRuntime(Path(r'D:\computer_work\project\StudyWorkbench\.local\release-tools\libreoffice-java-26.8.1-21.0.13'))
    samples = Path(r'D:\computer_work\project\StudyWorkbench\.local\goal-20261112\formats\.local\fmt-samples01')
    test_root = args.test_root.resolve()
    forbidden = ('URE_BOOTSTRAP', 'INIFILENAME', 'CONFIGURATION_LAYERS', 'UserInstallation', 'UNO_SERVICES',
                 'UNO_TYPES', 'URE_MORE_JAVA_TYPES', 'URE_MORE_SERVICES', 'URE_MORE_TYPES', 'UNO_PATH',
                 'SAL_CONFIG_STATICIZE', 'SAL_CONFIG_WINREG_RETAIN_TMP')
    environment = dict(os.environ, PYTHONPATH=str(ROOT / 'backend'), PYTHONUTF8='1', PYTHONDONTWRITEBYTECODE='1')
    environment.update({name: 'foreign-bootstrap-sentinel' for name in forbidden})
    command = [sys.executable, str(ROOT / 'tools/check_office_previews.py'), '--test-root', str(test_root),
               '--runtime', str(runtime.root), '--docx', str(samples / '复杂分节.docx'), '--pptx', str(samples / '复杂图表.pptx')]
    if args.mode == 'frozen':
        command += ['--exe', str(ROOT / 'dist/study_backend/study_backend.exe')]
    observed, errors = {}, []
    log_path = ROOT / f'artifacts/off02e/{test_root.name}.log'
    with log_path.open('w', encoding='utf-8') as log:
        process = subprocess.Popen(command, cwd=ROOT, env=environment, stdout=log, stderr=subprocess.STDOUT,
                                   creationflags=subprocess.CREATE_NO_WINDOW)
        # Covers the existing probe's two independent 600s waits, startup and restart; engine timeout remains 90s.
        deadline = time.monotonic() + 1800
        try:
            while process.poll() is None:
                assert time.monotonic() < deadline, 'conversion observation deadline'
                for pid, (parent, name) in descendants(process.pid).items():
                    if name.lower() != 'soffice.bin' or pid in observed:
                        continue
                    try:
                        image, actual, child_env = parameters(pid, parent)
                        assert os.path.samefile(image, runtime.root / 'program/soffice.bin')
                        assert actual[-2].endswith(('.docx', '.pptx')), 'conversion command not ready'
                        source = Path(actual[-2])
                        expected = runtime.command(source, source.parent)
                        assert actual[1:-1] == expected[1:], 'Office argument mismatch'
                        cwd = str(source.parent).replace('\\', '\\\\').replace('$', '\\$')
                        assert actual[-1] == '-env:OOO_CWD=2' + cwd, 'Office internal cwd argument mismatch'
                        expected_env = runtime.environment(source.parent)
                        child_upper = {k.upper(): v for k, v in child_env.items()}
                        assert all(child_upper.get(k.upper()) == v for k, v in expected_env.items()), 'Office environment mismatch'
                        assert child_upper.get('ATTACHED_PARENT_PROCESSID') == str(parent)
                        assert set(child_upper) == {key.upper() for key in expected_env} | {'ATTACHED_PARENT_PROCESSID'}
                        assert all(name.upper() not in child_upper for name in forbidden), 'inherited bootstrap variable'
                        observed[pid] = {'format': source.suffix, 'arguments': actual[1:],
                                         'environment': {key: child_upper[key.upper()] for key in expected_env},
                                         'no_inherited_bootstrap': True}
                        print(json.dumps({'observed': source.suffix, 'pid': pid}), flush=True)
                    except (OSError, AssertionError, ValueError, UnicodeError) as error:
                        errors.append({'pid': pid, 'error': str(error)})
                time.sleep(.03)
        finally:
            if process.poll() is None:
                process.kill()
            process.wait(10)
    result = {'mode': args.mode, 'returncode': process.returncode, 'observations': list(observed.values()),
              'observation_errors': errors, 'windows': sys.getwindowsversion()[:3]}
    output = ROOT / f'artifacts/off02e/{test_root.name}-processes.json'
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'mode': args.mode, 'returncode': process.returncode, 'observed': len(observed), 'errors': len(errors)}))
    assert process.returncode == 0
    assert {value['format'] for value in observed.values()} == {'.docx', '.pptx'}, 'missed actual Office format process'


if __name__ == "__main__":
    main()
