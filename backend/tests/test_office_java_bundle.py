import hashlib
import importlib
import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest
from study_workbench import office_runtime


@pytest.fixture
def components(tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).parents[2] / 'tools'))
    compose = importlib.import_module('compose_office_runtime')
    java = importlib.import_module('prepare_java_runtime')
    from test_java_runtime_preparation import fixture_files
    office_root, java_root = tmp_path / 'office', tmp_path / 'java'
    office_files = {name: ('original ' + name).encode() for name in
                    ['program/soffice.com', 'program/soffice.bin', 'program/officebean.dll', 'license.txt', 'NOTICE',
                     *('System64/' + name for name in office_runtime.APP_LOCAL_CRT)]}

    def write(root, files, lock_name, version, package):
        checksums = {}
        for name, raw in files.items():
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
            checksums[name] = hashlib.sha256(raw).hexdigest()
        lock = root / lock_name
        lock.write_text(json.dumps({'version': version, 'package_sha256': package, 'files': checksums}), encoding='utf-8')
        return hashlib.sha256(lock.read_bytes()).hexdigest()

    office_hash = write(office_root, office_files, 'runtime-lock.json', office_runtime.VERSION, office_runtime.PACKAGE_SHA256)
    java_hash = write(java_root, fixture_files(java), java.LOCK_NAME, java.VERSION, java.PACKAGE_SHA256)
    for module in [office_runtime, compose]:
        monkeypatch.setattr(module, 'OFFICE_LOCK_SHA256', office_hash)
        monkeypatch.setattr(module, 'JAVA_LOCK_SHA256', java_hash)
    monkeypatch.setattr(java.pefile, 'PE', lambda *a, **kw: SimpleNamespace(
        FILE_HEADER=SimpleNamespace(Machine=0x8664), OPTIONAL_HEADER=SimpleNamespace(Magic=0x20B), close=lambda: None))
    monkeypatch.setenv('SystemRoot', str(tmp_path / 'system'))
    return compose, office_root, java_root, tmp_path / 'combined'


def test_composition_preserves_originals_and_pins_child_environment(components, monkeypatch, tmp_path):
    compose, original, java, target = components
    original_bytes = {p.relative_to(original): p.read_bytes() for p in original.rglob('*') if p.is_file()}
    java_bytes = {p.relative_to(java): p.read_bytes() for p in java.rglob('*') if p.is_file()}
    monkeypatch.setenv('JAVA_HOME', 'host Java must not be borrowed')
    monkeypatch.setenv('JAVA_TOOL_OPTIONS', '-Duntrusted=true')
    monkeypatch.setenv('UNO_JAVA_JFW_PARAMETER_2', '-Duntrusted=true')
    bundled = compose.compose(original, java, target)
    bundled.verify(lambda: None)
    assert all((original / p).read_bytes() == raw for p, raw in original_bytes.items())
    assert all((java / p).read_bytes() == raw for p, raw in java_bytes.items())
    assert (target / 'office-runtime-lock.json').read_bytes() == original_bytes[Path('runtime-lock.json')]
    assert all((target / 'java' / p).read_bytes() == raw for p, raw in java_bytes.items())
    for name in office_runtime.APP_LOCAL_CRT:
        assert (target / 'program' / name).read_bytes() == original_bytes[Path('System64') / name]
    env = bundled.environment(tmp_path / 'task')
    assert env['JAVA_HOME'] == str(target / 'java')
    assert env['UNO_JAVA_JFW_JREHOME'] == (target / 'java').as_uri()
    assert env['UNO_JAVA_JFW_PARAMETER_1'] == '-Djava.awt.headless=true'
    assert 'JAVA_TOOL_OPTIONS' not in env and 'UNO_JAVA_JFW_PARAMETER_2' not in env
    assert env['PATH'].split(os.pathsep)[:3] == [str(target / 'program'), str(target / 'java/bin'), str(target / 'java/bin/server')]
    assert os.environ['JAVA_HOME'] == 'host Java must not be borrowed'
    legacy = office_runtime.OfficeRuntime(original)
    assert legacy.java_home is None and 'JAVA_HOME' not in legacy.environment(tmp_path / 'task')


@pytest.mark.parametrize('damage', ['source_file', 'source_lock', 'java_file', 'java_lock', 'extra_java'])
def test_changed_source_is_rejected_before_destination_creation(components, damage):
    compose, original, java, target = components
    paths = {'source_file': original / 'NOTICE', 'source_lock': original / 'runtime-lock.json',
             'java_file': java / 'NOTICE', 'java_lock': java / 'java-runtime-lock.json', 'extra_java': java / 'extra.dll'}
    paths[damage].write_bytes(b'tampered')
    with pytest.raises(ValueError):
        compose.compose(original, java, target)
    assert not target.exists()


@pytest.mark.parametrize('location', ['existing', 'office', 'java', 'aliased_office'])
def test_destination_never_overwrites_or_mutates_inputs(components, location, tmp_path):
    compose, original, java, target = components
    if location == 'existing':
        target.mkdir()
        (target / 'keep').write_bytes(b'keep')
    elif location == 'office':
        target = original / 'new'
    elif location == 'java':
        target = java / 'new'
    else:
        (tmp_path / 'intermediate').mkdir()
        target = tmp_path / 'intermediate/../office/new'
    with pytest.raises(ValueError):
        compose.compose(original, java, target)
    if location == 'existing':
        assert (target / 'keep').read_bytes() == b'keep'
    else:
        assert not target.exists()


@pytest.mark.parametrize('damage', ['java_version', 'missing_marker', 'missing_crt', 'original_hash', 'extra', 'java_lock'])
def test_composite_inventory_cannot_relabel_or_omit_fixed_payload(components, damage):
    compose, original, java, target = components
    compose.compose(original, java, target)
    lock = target / 'runtime-lock.json'
    manifest = json.loads(lock.read_text())
    if damage == 'java_version':
        manifest['java']['version'] = 'other'
    elif damage == 'missing_marker':
        del manifest['java']
    elif damage == 'missing_crt':
        del manifest['files']['program/vcruntime140.dll']
    elif damage == 'original_hash':
        manifest['files']['NOTICE'] = '0' * 64
    elif damage == 'extra':
        manifest['files']['program/extra.dll'] = '0' * 64
    else:
        (target / 'java/java-runtime-lock.json').write_text('{}')
    lock.write_text(json.dumps(manifest))
    with pytest.raises(ValueError):
        office_runtime.OfficeRuntime(target)


def test_changed_payload_still_fails_full_runtime_verification(components):
    compose, original, java, target = components
    runtime = compose.compose(original, java, target)
    (target / 'java/bin/jawt.dll').write_bytes(b'changed after composition')
    with pytest.raises(ValueError, match='变化'):
        runtime.verify(lambda: None)
