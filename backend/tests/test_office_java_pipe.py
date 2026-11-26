"""Trust boundaries for the developer Java checker; real JVM evidence stays local."""
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest


@pytest.fixture
def checker():
    path = Path(__file__).resolve().parents[2] / 'tools/check_office_java_pipe.py'
    spec = importlib.util.spec_from_file_location('office_java_pipe_checker', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_fixed_self_authored_probe_is_pinned(checker, tmp_path):
    original = checker.fixed_probe_source()
    changed = tmp_path / 'Probe.java'
    changed.write_bytes(original + b'\n')
    with pytest.raises(ValueError, match='source changed'):
        checker.fixed_probe_source(changed)


@pytest.mark.parametrize('location', ['existing', 'inside', 'ancestor'])
def test_output_cannot_overwrite_evidence_or_component(checker, tmp_path, location):
    component = tmp_path / 'immutable/component'
    component.mkdir(parents=True)
    output = {'existing': tmp_path / 'existing', 'inside': component / 'probe', 'ancestor': component.parent}[location]
    if location == 'existing':
        output.mkdir()
        (output / 'report.json').write_bytes(b'old failed evidence')
    with pytest.raises(ValueError):
        checker.checked_output(component, output)
    if location == 'existing':
        assert (output / 'report.json').read_bytes() == b'old failed evidence'
    assert list(component.iterdir()) == []


def test_new_separate_output_requires_existing_parent(checker, tmp_path):
    component = tmp_path / 'component'
    component.mkdir()
    assert checker.checked_output(component, tmp_path / 'fresh') == tmp_path / 'fresh'
    assert not (tmp_path / 'fresh').exists()
    with pytest.raises(ValueError, match='parent'):
        checker.checked_output(component, tmp_path / 'missing/fresh')


@pytest.mark.parametrize('raw', [b'', b'cafebabe', bytes.fromhex('cafebabe00000034'),
    bytes.fromhex('cafebabe00000037') + b'x' * 65536], ids=['empty', 'not-class', 'old-version', 'oversized'])
def test_wrong_or_oversized_class_is_rejected(checker, tmp_path, raw):
    path = tmp_path / 'Probe.class'
    path.write_bytes(raw)
    with pytest.raises(ValueError, match='bounded Java 11'):
        checker.compiled_class_identity(path)


@pytest.fixture
def diagnostic_result():
    return dict(ok=True, pid=12345, expected_missing_pipe_ioexception=True, classloader_parent_null=True,
        packaged_resource_matches_fixed_jpipe=True, office_host_execution_verified=False)


@pytest.mark.parametrize('damage', ['pid', 'bool-pid', 'false-result', 'integer-flag', 'missing-flag', 'host-claim', 'oversized'])
def test_unowned_or_overclaimed_results_are_rejected(checker, tmp_path, diagnostic_result, damage):
    result = dict(diagnostic_result)
    if damage == 'pid':
        result['pid'] += 1
    elif damage == 'bool-pid':
        result['pid'] = True
    elif damage == 'false-result':
        result['ok'] = False
    elif damage == 'integer-flag':
        result['classloader_parent_null'] = 1
    elif damage == 'missing-flag':
        del result['expected_missing_pipe_ioexception']
    elif damage == 'host-claim':
        result['office_host_execution_verified'] = True
    path = tmp_path / 'result.json'
    path.write_text(json.dumps(result) if damage != 'oversized' else 'x' * 65537, encoding='utf-8')
    with pytest.raises(ValueError):
        checker.checked_java_result(path, 12345)


def test_owned_finite_result_is_accepted(checker, tmp_path, diagnostic_result):
    path = tmp_path / 'result.json'
    path.write_text(json.dumps(diagnostic_result), encoding='utf-8')
    assert checker.checked_java_result(path, 12345) == diagnostic_result


@pytest.mark.parametrize('raw', [b'', b'[]', b'null'])
def test_incomplete_or_nonobject_result_is_rejected(checker, tmp_path, raw):
    path = tmp_path / 'result.json'
    path.write_bytes(raw)
    with pytest.raises(ValueError):
        checker.checked_java_result(path, 12345)


def test_same_bytes_in_foreign_domain_do_not_prove_actual_module(checker, tmp_path):
    root = tmp_path / 'component'
    java, program = root / 'java/bin/vcruntime140.dll', root / 'program/vcruntime140.dll'
    for path in (java, program):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b'controlled byte-identical CRT fixture')
    canonical = 'java/bin/vcruntime140.dll'
    files = {canonical: hashlib.sha256(java.read_bytes()).hexdigest()}
    with pytest.raises(ValueError, match='different loading domain'):
        checker.module_identity(root, files, program, canonical, 12345)
    observed = checker.module_identity(root, files, java, canonical, 12345)
    assert observed['canonical_path'] == canonical and observed['observed_pid'] == 12345
    java.write_bytes(b'changed')
    with pytest.raises(ValueError, match='bytes changed'):
        checker.module_identity(root, files, java, canonical, 12345)
