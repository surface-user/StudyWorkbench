import copy
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from study_workbench import office_python_probe as probe
from study_workbench.office_runtime import PYTHON_CORE
from test_office_java_bundle import components as components
from test_office_java_bundle import python_components as python_components


@pytest.fixture
def observed(tmp_path):
    # Independent contract fixture; these bytes are never executable.
    paths = {'python313.dll': 'bin/python313.dll', 'python3.dll': 'bin/python3.dll',
             'vcruntime140.dll': 'bin/vcruntime140.dll', 'libcrypto-3.dll': 'lib/libcrypto-3.dll',
             'libssl-3.dll': 'lib/libssl-3.dll', 'libffi-8.dll': 'lib/libffi-8.dll', 'sqlite3.dll': 'lib/sqlite3.dll'}
    checksums = {relative: hashlib.sha256(('self-authored fixture ' + relative).encode()).hexdigest()
                 for relative in paths.values()}
    files = {PYTHON_CORE + relative: digest for relative, digest in checksums.items()}
    data = dict(ok=True, pid=123, version=[3, 13, 15], executable='bin/python.exe', prefix='.',
        abi_functions_exercised=['Py_IsInitialized'], all_exports_certified=False,
        dynamic_isolation_certified=False, all_process_modules_observed=False,
        module_paths={name: dict(path=relative, sha256=checksums[relative]) for name, relative in paths.items()})
    return tmp_path / 'result.json', data, files


def test_expected_observed_private_modules_are_accepted(observed):
    path, data, files = observed
    path.write_text(json.dumps(data), encoding='utf-8')
    assert probe.validate_result(path, 123, 'python.exe', files) == data


@pytest.mark.parametrize('damage', ['pid', 'host-version', 'other-entry', 'failed', 'outside-prefix',
    'missing-dll', 'extra-dll', 'foreign-path', 'changed-hash', 'full-exports', 'dynamic-certification',
    'all-modules', 'extra-abi-call', 'missing-modules', 'bad-row', 'list-output'])
def test_observed_identity_or_scope_mismatch_is_rejected(observed, damage):
    path, original, files = observed
    data = copy.deepcopy(original)
    if damage == 'pid':
        data['pid'] = 124
    elif damage == 'host-version':
        data['version'] = [3, 13, 17]
    elif damage == 'other-entry':
        data['executable'] = 'bin/pythonw.exe'
    elif damage == 'failed':
        data['ok'] = False
    elif damage == 'outside-prefix':
        data['prefix'] = '..'
    elif damage == 'missing-dll':
        del data['module_paths']['libssl-3.dll']
    elif damage == 'extra-dll':
        data['module_paths']['foreign.dll'] = dict(path='../../foreign.dll', sha256='0' * 64)
    elif damage == 'foreign-path':
        data['module_paths']['vcruntime140.dll']['path'] = 'program/vcruntime140.dll'
    elif damage == 'changed-hash':
        data['module_paths']['python313.dll']['sha256'] = '0' * 64
    elif damage == 'full-exports':
        data['all_exports_certified'] = True
    elif damage == 'dynamic-certification':
        data['dynamic_isolation_certified'] = True
    elif damage == 'all-modules':
        data['all_process_modules_observed'] = True
    elif damage == 'extra-abi-call':
        data['abi_functions_exercised'].append('_Py_RefTotal')
    elif damage == 'missing-modules':
        data['module_paths'] = None
    elif damage == 'bad-row':
        data['module_paths']['python3.dll'] = 'not an identity record'
    else:
        data = []
    path.write_text(json.dumps(data), encoding='utf-8')
    with pytest.raises(ValueError):
        probe.validate_result(path, 123, 'python.exe', files)


@pytest.mark.parametrize('empty', [False, True])
def test_output_budget_is_checked_before_parsing(observed, empty):
    path, data, files = observed
    data['padding'] = 'x' * 65537
    path.write_text('' if empty else json.dumps(data), encoding='utf-8')
    with pytest.raises(ValueError, match='预算'):
        probe.validate_result(path, 123, 'python.exe', files)


@pytest.mark.parametrize('location', ['existing', 'inside-component', 'relative'])
def test_output_never_overwrites_or_writes_into_component(tmp_path, location):
    runtime = tmp_path / 'runtime'
    runtime.mkdir()
    if location == 'existing':
        output = tmp_path / 'retained'
        output.mkdir()
        (output / 'keep').write_bytes(b'keep')
    elif location == 'inside-component':
        output = runtime / 'child-output'
    else:
        output = Path('relative-probe-output')
    with pytest.raises(ValueError):
        probe._new_output(output, runtime)
    assert not (runtime / 'child-output').exists()
    if location == 'existing':
        assert (output / 'keep').read_bytes() == b'keep'


def test_probe_environment_never_inherits_python_java_or_openssl_options(tmp_path, monkeypatch):
    for name in ('PYTHONPATH', 'PYTHONHOME', 'PYTHONSTARTUP', 'JAVA_HOME', 'JAVA_TOOL_OPTIONS', 'OPENSSL_CONF', 'PATH'):
        monkeypatch.setenv(name, 'untrusted inherited value')
    monkeypatch.setenv('SystemRoot', str(tmp_path / 'system'))
    environment = probe.environment(tmp_path / 'task', tmp_path / 'core')
    assert environment['PATH'].split(os.pathsep) == [str(tmp_path / 'core/bin'), str(tmp_path / 'system/System32')]
    assert environment['OPENSSL_CONF'] == str(tmp_path / 'task/profile/openssl-empty.cnf')
    assert environment['OPENSSL_MODULES'] == str(tmp_path / 'core/lib')
    assert not {'PYTHONPATH', 'PYTHONHOME', 'PYTHONSTARTUP', 'JAVA_HOME', 'JAVA_TOOL_OPTIONS'} & environment.keys()
    assert os.environ['PYTHONPATH'] == 'untrusted inherited value'


@pytest.mark.skipif(os.name != 'nt', reason='Windows helper prelaunch boundary')
@pytest.mark.parametrize('damage', ['legacy-layout', 'changed-bin-crt', 'changed-abi', 'extra-installer'])
def test_bad_layout_or_payload_is_rejected_before_native_calls(request, tmp_path, monkeypatch, damage):
    compose, original, java, target = request.getfixturevalue('python_components')
    runtime = compose.compose(original, java, target, python_launchers=damage != 'legacy-layout')
    monkeypatch.setattr(probe, 'RUNTIME_SHA256', runtime.fingerprint)
    monkeypatch.setattr(sys, 'argv', ['backend', '--probe-office-python', str(target), str(tmp_path / 'probe')])
    def must_not_call(*args, **kwargs):
        pytest.fail('Native DLL state/process APIs must not run for a rejected component')
    monkeypatch.setattr(probe.ctypes, 'WinDLL', must_not_call)
    monkeypatch.setattr(probe, 'WindowsProcessJob', must_not_call)
    if damage != 'legacy-layout':
        name = {'changed-bin-crt': PYTHON_CORE + 'bin/vcruntime140.dll',
                'changed-abi': PYTHON_CORE + 'bin/python3.dll', 'extra-installer': 'unlisted.msi'}[damage]
        (target / name).write_bytes(b'untrusted bytes')
    with pytest.raises(ValueError):
        probe.probe(target, tmp_path / 'probe')


@pytest.mark.skipif(os.name != 'nt', reason='Windows disposable helper cleanup boundary')
@pytest.mark.parametrize('interruption', ['timeout', 'cancel'])
def test_interrupted_child_closes_job_before_wait_and_retains_failure(tmp_path, monkeypatch, interruption):
    error = subprocess.TimeoutExpired('fixed child', 20) if interruption == 'timeout' else KeyboardInterrupt('controlled interruption')
    runtime = SimpleNamespace(root=tmp_path / 'component', python_launchers=True,
        fingerprint=probe.RUNTIME_SHA256, verify=lambda checkpoint: checkpoint())
    runtime.root.mkdir()
    output, events = tmp_path / 'probe', []
    class Function:
        def __call__(self, *args):
            return 1
    kernel = SimpleNamespace(SetDllDirectoryW=Function(), SetErrorMode=Function())
    class Process:
        def wait(self, timeout):
            events.append(('wait', timeout))
            if timeout == 20:
                raise error
            return 0
        def close(self):
            events.append(('process-close',))
    class Job:
        def start(self, command, cwd, environment):
            events.append(('start',))
            return Process()
        def close(self):
            events.append(('job-close',))
    monkeypatch.setattr(probe, 'OfficeRuntime', lambda root: runtime)
    monkeypatch.setattr(probe.ctypes, 'WinDLL', lambda *args, **kwargs: kernel)
    monkeypatch.setattr(probe, 'WindowsProcessJob', Job)
    monkeypatch.setattr(sys, 'argv', ['backend', '--probe-office-python', str(runtime.root), str(output)])
    with pytest.raises(type(error)):
        probe.probe(runtime.root, output)
    assert events == [('start',), ('wait', 20), ('job-close',), ('wait', 10), ('process-close',)]
    assert json.loads((output / 'failure.json').read_text('utf-8')) == {
        'type': type(error).__name__, 'message': str(error)}
    assert not (output / 'report.json').exists()
