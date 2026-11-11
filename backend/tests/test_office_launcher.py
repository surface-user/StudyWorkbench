import os
import subprocess
import sys
from types import SimpleNamespace

import pytest
from study_workbench import office_runtime
from test_office_previews import package

pytestmark = pytest.mark.skipif(os.name != 'nt', reason='Windows external DLL boundary')


def task(tmp_path, prepared=True):
    directory = tmp_path / 'task'
    directory.mkdir()
    if prepared:
        (directory / 'profile/user').mkdir(parents=True)
        (directory / 'profile/user/registrymodifications.xcu').write_text(office_runtime.PROFILE, encoding='utf-8')
        for name in ['output', 'tmp']:
            (directory / name).mkdir()
    source = directory / 'source.docx'
    source.write_bytes(package())
    runtime = object.__new__(office_runtime.OfficeRuntime)
    runtime.root = tmp_path / 'runtime'
    runtime.java_home = None
    runtime.executable = runtime.root / 'program/soffice.com'
    return runtime, directory, source


def test_frozen_backend_launches_owned_helper_without_mutating_its_dll_directory(tmp_path, monkeypatch):
    runtime, directory, source = task(tmp_path, prepared=False)
    runtime.verify = lambda check: check()
    calls = []
    class Process:
        returncode = 0
        def poll(self):
            return 0
        def wait(self, timeout):
            calls.append('wait')
        def close(self):
            calls.append('process-close')
    class Job:
        def start(self, command, cwd, environment):
            calls.append((command, cwd, environment))
            return Process()
        def close(self):
            calls.append('job-close')
    def forbidden(*args, **kwargs):
        raise AssertionError('The backend must not change its DLL search state')
    monkeypatch.setattr(sys, 'frozen', True, raising=False)
    monkeypatch.setattr(office_runtime, 'WindowsProcessJob', Job)
    monkeypatch.setattr(office_runtime.ctypes, 'WinDLL', forbidden)
    result = runtime.convert(source, directory, lambda: None)
    command, cwd, environment = calls[0]
    assert command == [sys.executable, '--launch-office', str(runtime.root), str(directory), '.docx']
    assert cwd == directory and '_internal' not in environment['PATH']
    assert result == directory / 'output/source.pdf'
    assert calls[1:] == ['job-close', 'wait', 'process-close']


@pytest.mark.parametrize('clear_succeeds', [True, False])
def test_only_disposable_helper_clears_dll_before_fixed_external_command(tmp_path, monkeypatch, clear_succeeds):
    runtime, directory, _ = task(tmp_path)
    calls = []
    def clear(value):
        assert value is None
        calls.append('clear')
        return int(clear_succeeds)
    kernel = SimpleNamespace(SetDllDirectoryW=clear)
    def run(command, **options):
        assert calls == ['clear']
        assert command[0] == str(runtime.executable)
        assert command[-1] == str(directory / 'source.docx')
        assert 'pdf:writer_pdf_Export' in command
        assert options['creationflags'] == subprocess.CREATE_NO_WINDOW
        assert options['stdin'] == options['stdout'] == options['stderr'] == subprocess.DEVNULL
        assert options['env'] == runtime.environment(directory)
        calls.append('run')
        return SimpleNamespace(returncode=7)
    monkeypatch.setattr(sys, 'frozen', True, raising=False)
    monkeypatch.setattr(office_runtime, 'OfficeRuntime', lambda root: runtime)
    monkeypatch.setattr(office_runtime, 'native_directory', lambda path: path)
    monkeypatch.setattr(office_runtime.ctypes, 'WinDLL', lambda *args, **kwargs: kernel)
    monkeypatch.setattr(office_runtime.subprocess, 'run', run)
    if clear_succeeds:
        assert office_runtime.launch_office(runtime.root, directory, '.docx') == 7
        assert calls == ['clear', 'run']
    else:
        with pytest.raises(OSError):
            office_runtime.launch_office(runtime.root, directory, '.docx')
        assert calls == ['clear']


def test_helper_refuses_unfrozen_unknown_suffix_or_unsafe_package_before_launch(tmp_path, monkeypatch):
    runtime, directory, source = task(tmp_path)
    monkeypatch.setattr(office_runtime, 'OfficeRuntime', lambda root: runtime)
    with pytest.raises(ValueError, match='内部Office'):
        office_runtime.launch_office(runtime.root, directory, '.docx')
    monkeypatch.setattr(sys, 'frozen', True, raising=False)
    with pytest.raises(ValueError, match='内部Office'):
        office_runtime.launch_office(runtime.root, directory, '.exe')
    def forbidden(*args, **kwargs):
        raise AssertionError('Invalid input must not launch or change DLL state')
    monkeypatch.setattr(office_runtime.ctypes, 'WinDLL', forbidden)
    monkeypatch.setattr(office_runtime.subprocess, 'run', forbidden)
    configuration = directory / 'profile/user/registrymodifications.xcu'
    configuration.write_text('changed configuration', encoding='utf-8')
    with pytest.raises(ValueError, match='配置已变化'):
        office_runtime.launch_office(runtime.root, directory, '.docx')
    configuration.write_text(office_runtime.PROFILE, encoding='utf-8')
    source.write_bytes(package(extras={'word/vbaProject.bin': b'untrusted'}))
    with pytest.raises(ValueError):
        office_runtime.launch_office(runtime.root, directory, '.docx')


@pytest.mark.parametrize('mode', ['same', 'unavailable', 'oversize', 'other'])
def test_native_directory_checks_identity_and_never_uses_truncated_alias(tmp_path, monkeypatch, mode):
    directory = tmp_path / 'task'
    directory.mkdir()
    other = tmp_path / 'other'
    other.mkdir()
    def query(path, buffer, capacity):
        assert path == str(directory)
        if mode == 'unavailable':
            return 0
        if mode == 'oversize':
            return capacity + 1
        buffer.value = str(other if mode == 'other' else directory)
        return len(buffer.value)
    monkeypatch.setattr(office_runtime.ctypes, 'WinDLL', lambda *args, **kwargs: SimpleNamespace(GetShortPathNameW=query))
    if mode == 'other':
        with pytest.raises(ValueError, match='同一任务目录'):
            office_runtime.native_directory(directory)
    else:
        assert office_runtime.native_directory(directory) == directory
