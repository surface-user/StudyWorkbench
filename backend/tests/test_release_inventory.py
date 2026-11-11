import hashlib
import importlib
import json
import os
import stat
import subprocess
import sys
from importlib.metadata import PackagePath
from pathlib import Path
from types import SimpleNamespace

import pytest


def snapshot(stage):
    return {p.relative_to(stage).as_posix(): p.read_bytes() for p in stage.rglob('*') if p.is_file()}


def manifest(stage):
    return json.loads((stage / 'build-inventory.json').read_text(encoding='utf-8'))


def save_manifest(stage, value):
    (stage / 'build-inventory.json').write_text(json.dumps(value), encoding='utf-8')


@pytest.fixture
def staged(tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).parents[2] / 'tools'))
    checker = importlib.import_module('check_release')
    native = importlib.import_module('native_dependencies')
    collector = importlib.import_module('release_inventory')
    stage = tmp_path / 'stage'
    stage.mkdir()
    files = {}
    for relative in ['python313.dll', 'backend/backend.exe', 'data/app.so']:
        path = stage / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        data = ('self-authored fixture ' + relative).encode()
        path.write_bytes(data)
        files[relative] = hashlib.sha256(data).hexdigest()
    save_manifest(stage, {'python': '3.13.17', 'files': files})
    calls = {'opened': [], 'closed': [], 'imports': [], 'headers': {}, 'parsed': []}
    def pe(path, fast_load):
        assert fast_load
        calls['opened'].append(path)
        machine, magic = calls['headers'].get(Path(path).relative_to(stage).as_posix(), (0x8664, 0x20b))
        return SimpleNamespace(
            FILE_HEADER=SimpleNamespace(Machine=machine),
            OPTIONAL_HEADER=SimpleNamespace(Magic=magic),
            parse_data_directories=lambda **kwargs: calls['parsed'].append(path),
            DIRECTORY_ENTRY_IMPORT=[SimpleNamespace(dll=name) for name in calls['imports']],
            close=lambda: calls['closed'].append(path))
    monkeypatch.setattr(native.pefile, 'PE', pe)
    monkeypatch.setenv('SystemRoot', str(tmp_path / 'empty-system'))
    monkeypatch.setattr(sys, 'argv', ['check_release.py', str(stage)])
    return stage, checker, collector, calls


def test_complete_stage_retains_hash_and_pe_checks_without_writes(staged):
    stage, checker, _, calls = staged
    before = snapshot(stage)
    checker.main()
    assert snapshot(stage) == before
    assert {Path(p).name for p in calls['opened']} == {'python313.dll', 'backend.exe'}
    assert calls['opened'] == calls['closed']


@pytest.mark.parametrize('damage', ['extra', 'nested_extra', 'missing'])
def test_actual_payload_must_equal_inventory_before_pe_checks(staged, damage):
    stage, checker, _, calls = staged
    if damage == 'missing':
        (stage / 'data/app.so').unlink()
    else:
        path = stage / ('unexpected.txt' if damage == 'extra' else 'data/unexpected.txt')
        path.write_bytes(b'not in the manifest')
    before = snapshot(stage)
    with pytest.raises((ValueError, AssertionError, FileNotFoundError)):
        checker.main()
    assert not calls['opened'] and snapshot(stage) == before


def test_changed_listed_bytes_still_fail_hash_validation(staged):
    stage, checker, _, calls = staged
    (stage / 'data/app.so').write_bytes(b'changed bytes')
    before = snapshot(stage)
    with pytest.raises(AssertionError):
        checker.main()
    assert not calls['opened'] and snapshot(stage) == before


@pytest.mark.parametrize('kind', ['absolute', 'traversal'])
def test_manifest_cannot_read_a_file_outside_stage(staged, monkeypatch, kind):
    stage, checker, _, calls = staged
    outside = stage.parent / 'outside.txt'
    outside.write_bytes(b'never read by the checker')
    value = manifest(stage)
    reference = str(outside) if kind == 'absolute' else '../outside.txt'
    value['files'][reference] = hashlib.sha256(outside.read_bytes()).hexdigest()
    save_manifest(stage, value)
    before = snapshot(stage)
    original_open = Path.open
    def guarded(path, *args, **kwargs):
        if path.resolve() == outside.resolve():
            raise RuntimeError('Checker attempted to open an outside file')
        return original_open(path, *args, **kwargs)
    with monkeypatch.context() as patch:
        patch.setattr(Path, 'open', guarded)
        with pytest.raises(ValueError):
            checker.main()
    assert not calls['opened'] and snapshot(stage) == before


@pytest.mark.parametrize('guard', ['database', 'python_version'])
def test_original_database_and_python_version_guards_remain(staged, guard):
    stage, checker, _, _ = staged
    value = manifest(stage)
    if guard == 'database':
        data = b'self-authored database fixture, no personal content'
        (stage / 'study.db').write_bytes(data)
        value['files']['study.db'] = hashlib.sha256(data).hexdigest()
    else:
        value['python'] = '3.12.7'
    save_manifest(stage, value)
    before = snapshot(stage)
    with pytest.raises(AssertionError):
        checker.main()
    assert snapshot(stage) == before


@pytest.mark.parametrize('dependency', [b'vcruntime140.dll', b'not_a_windows_dependency.dll'])
def test_original_crt_and_pe_dependency_guards_remain_and_close_handles(staged, dependency):
    stage, checker, _, calls = staged
    calls['imports'] = [dependency]
    before = snapshot(stage)
    with pytest.raises(ValueError, match='Unresolved import'):
        checker.main()
    assert calls['opened'] and calls['closed'] == calls['opened']
    assert snapshot(stage) == before


def test_child_reparse_directory_is_refused_and_external_bytes_preserved(staged):
    stage, checker, _, calls = staged
    external = stage.parent / 'external'
    external.mkdir()
    (external / 'keep.txt').write_bytes(b'external fixture must stay unchanged')
    link = stage / 'linked'
    if os.name == 'nt':
        created = subprocess.run(['cmd', '/c', 'mklink', '/J', str(link), str(external)],
                                 capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
        assert created.returncode == 0, created.stderr
    else:
        link.symlink_to(external, target_is_directory=True)
    with pytest.raises(ValueError, match='reparse'):
        checker.main()
    assert not calls['opened']
    assert (external / 'keep.txt').read_bytes() == b'external fixture must stay unchanged'


def test_non_regular_payload_is_refused_before_reading(staged, monkeypatch):
    stage, checker, _, calls = staged
    special = stage / 'special'
    special.write_bytes(b'never read as a regular payload')
    original = Path.lstat
    def reported_type(path):
        if path == special:
            return SimpleNamespace(st_mode=stat.S_IFIFO, st_file_attributes=0)
        return original(path)
    monkeypatch.setattr(Path, 'lstat', reported_type)
    with pytest.raises(ValueError, match='regular'):
        checker.main()
    assert not calls['opened']


def test_manifest_link_is_rejected_before_reading_its_contents(staged, monkeypatch):
    stage, checker, _, calls = staged
    inventory = stage / 'build-inventory.json'
    original_stat, original_open = Path.lstat, Path.open
    def reported_link(path):
        if path == inventory:
            return SimpleNamespace(st_mode=stat.S_IFREG, st_file_attributes=stat.FILE_ATTRIBUTE_REPARSE_POINT)
        return original_stat(path)
    def guarded(path, *args, **kwargs):
        if path == inventory:
            raise RuntimeError('Manifest was read before rejecting its link attribute')
        return original_open(path, *args, **kwargs)
    with monkeypatch.context() as patch:
        patch.setattr(Path, 'lstat', reported_link)
        patch.setattr(Path, 'open', guarded)
        with pytest.raises(ValueError, match='reparse'):
            checker.main()
    assert not calls['opened']


def test_collector_refuses_license_directory_junction_before_copying(staged, monkeypatch):
    stage, _, collector, _ = staged
    external = stage.parent / 'external-licenses'
    external.mkdir()
    (external / 'keep').write_bytes(b'external fixture')
    if os.name == 'nt':
        linked = subprocess.run(['cmd', '/c', 'mklink', '/J', str(stage / 'licenses'), str(external)],
                                capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
        assert linked.returncode == 0, linked.stderr
    else:
        (stage / 'licenses').symlink_to(external, target_is_directory=True)
    before = snapshot(external)
    monkeypatch.setattr(sys, 'argv', ['release_inventory.py', '--stage', str(stage)])
    with pytest.raises(ValueError, match='reparse'):
        collector.main()
    assert snapshot(external) == before


@pytest.fixture
def collection(staged, tmp_path, monkeypatch):
    stage, _, collector, _ = staged
    repository = tmp_path / 'fixture-repository'
    sdk = tmp_path / 'fixture-sdk'
    sdk.mkdir()
    (sdk / 'LICENSE').write_text('self-authored license fixture', encoding='utf-8')
    config = repository / 'apps/desktop/.dart_tool/package_config.json'
    config.parent.mkdir(parents=True)
    config.write_text(json.dumps({'packages': [], 'flutterRoot': sdk.as_uri(), 'flutterVersion': 'fixture'}), encoding='utf-8')
    (repository / 'apps/desktop/build/windows/x64/packages').mkdir(parents=True)
    license_path = repository / '.local/release-tools/nlohmann-json-3.11.2-LICENSE.MIT'
    license_path.parent.mkdir(parents=True)
    license_path.write_text('self-authored MIT fixture', encoding='utf-8')
    monkeypatch.setattr(collector, '__file__', str(repository / 'tools/release_inventory.py'))
    monkeypatch.setattr(collector.importlib.metadata, 'distributions', lambda: [])
    monkeypatch.setattr(sys, 'argv', ['release_inventory.py', '--stage', str(stage)])
    return stage, collector, repository, config


def test_collection_includes_nested_inventory_but_excludes_only_root_manifest(collection):
    stage, collector, _, _ = collection
    nested = stage / 'data/build-inventory.json'
    nested.write_bytes(b'legitimate nested payload')
    collector.main()
    files = manifest(stage)['files']
    assert 'build-inventory.json' not in files
    assert files['data/build-inventory.json'] == hashlib.sha256(nested.read_bytes()).hexdigest()
    assert set(files) == set(snapshot(stage)) - {'build-inventory.json'}


X64_TARGETS = [
    'study_workbench.exe', 'flutter_windows.dll', 'python313.dll',
    'backend/study_backend.exe', 'backend/_internal/pkg/native.pyd',
    'backend/_internal/pkg/dependency.dll',
]


@pytest.mark.parametrize('relative', X64_TARGETS)
@pytest.mark.parametrize('header', [(0x14c, 0x10b), (0xaa64, 0x20b), (0x8664, 0x10b)],
                         ids=['x86', 'arm64', 'wrong-magic'])
def test_wrong_architecture_is_refused_before_imports_without_writes(staged, relative, header):
    stage, checker, _, calls = staged
    path = stage / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b'self-authored PE stub fixture')
    value = manifest(stage)
    value['files'][relative] = hashlib.sha256(path.read_bytes()).hexdigest()
    save_manifest(stage, value)
    calls['headers'][relative] = header
    before = snapshot(stage)
    with pytest.raises(ValueError, match='x64 PE32'):
        checker.main()
    assert snapshot(stage) == before
    assert calls['opened'] == calls['closed']
    assert str(path) not in calls['parsed']


@pytest.mark.parametrize('ecosystem', ['python', 'dart'])
@pytest.mark.parametrize('damage', ['parent', 'absolute', 'nested', 'backslash', 'dot'])
def test_license_package_name_cannot_choose_another_directory(collection, tmp_path, monkeypatch, ecosystem, damage):
    stage, collector, _, config = collection
    source = tmp_path / 'dependency-source'
    source.mkdir()
    (source / 'LICENSE').write_bytes(b'self-authored license')
    escaped = tmp_path / 'escaped'
    escaped.mkdir()
    (escaped / 'LICENSE').write_bytes(b'fixture sentinel must never be overwritten')
    name = {'parent': '../../escaped', 'absolute': str(escaped), 'nested': 'nested/package',
            'backslash': 'nested\\package', 'dot': '.'}[damage]
    if ecosystem == 'python':
        dist = SimpleNamespace(metadata={'Name': name}, version='1.0', files=[PackagePath('LICENSE')],
                               locate_file=lambda file: source / file)
        monkeypatch.setattr(collector.importlib.metadata, 'distributions', lambda: [dist])
    else:
        value = json.loads(config.read_text(encoding='utf-8'))
        value['packages'] = [{'name': name, 'rootUri': source.as_uri()}]
        config.write_text(json.dumps(value), encoding='utf-8')
    before = snapshot(tmp_path)
    with pytest.raises(ValueError, match='license'):
        collector.main()
    after = snapshot(tmp_path)
    assert all(after[path] == data for path, data in before.items())
    assert {p: data for p, data in after.items() if not p.startswith('stage/')} == {
        p: data for p, data in before.items() if not p.startswith('stage/')}


@pytest.mark.parametrize('location', ['outside', 'inside'])
def test_absolute_license_record_is_rejected_without_overwriting(collection, tmp_path, monkeypatch, location):
    stage, collector, _, _ = collection
    source = tmp_path / 'license-source'
    source.write_bytes(b'self-authored license bytes')
    target = (tmp_path if location == 'outside' else stage / 'licenses/sample') / 'LICENSE'
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(b'fixture sentinel must never be overwritten')
    dist = SimpleNamespace(metadata={'Name': 'sample'}, version='1.0', files=[PackagePath(target.as_posix())],
                           locate_file=lambda file: source)
    monkeypatch.setattr(collector.importlib.metadata, 'distributions', lambda: [dist])
    before = snapshot(tmp_path)
    with pytest.raises(ValueError, match='license'):
        collector.main()
    assert snapshot(tmp_path) == before


def test_valid_nested_python_dart_and_native_licenses_remain_collected(collection, tmp_path, monkeypatch):
    stage, collector, repository, config = collection
    source = tmp_path / 'dependency-source'
    relative = PackagePath('sample-1.0.dist-info/licenses/LICENSE')
    (source / relative).parent.mkdir(parents=True)
    (source / relative).write_bytes(b'self-authored Python license')
    dist = SimpleNamespace(metadata={'Name': 'sample-pkg_1'}, version='1.0', files=[relative],
                           locate_file=lambda file: source / file)
    monkeypatch.setattr(collector.importlib.metadata, 'distributions', lambda: [dist])
    dart = tmp_path / 'dart-source'
    dart.mkdir()
    (dart / 'NOTICE').write_bytes(b'self-authored Dart notice')
    value = json.loads(config.read_text(encoding='utf-8'))
    value['packages'] = [{'name': 'dart_pkg', 'rootUri': dart.as_uri()}]
    config.write_text(json.dumps(value), encoding='utf-8')
    native = repository / 'apps/desktop/build/windows/x64/packages/Sample.Native.1.0'
    native.mkdir()
    (native / 'LICENSE.txt').write_bytes(b'self-authored native license')
    before = [snapshot(directory) for directory in [source, dart, repository]]
    collector.main()
    assert [snapshot(directory) for directory in [source, dart, repository]] == before
    assert (stage / 'licenses/sample-pkg_1' / relative).read_bytes() == (source / relative).read_bytes()
    assert (stage / 'licenses/dart/dart_pkg/NOTICE').read_bytes() == (dart / 'NOTICE').read_bytes()
    assert (stage / 'licenses/native/Sample.Native.1.0/LICENSE.txt').read_bytes() == (native / 'LICENSE.txt').read_bytes()
    for relative, digest in manifest(stage)['files'].items():
        assert hashlib.sha256((stage / relative).read_bytes()).hexdigest() == digest


@pytest.mark.parametrize('relative', ['LICENSE:stream', 'ambiguous. /LICENSE', 'LICENSE.'])
def test_ambiguous_windows_license_paths_are_rejected_before_copy(collection, tmp_path, monkeypatch, relative):
    stage, collector, _, _ = collection
    source = tmp_path / 'license-source'
    source.write_bytes(b'self-authored license bytes')
    dist = SimpleNamespace(metadata={'Name': 'sample'}, version='1.0', files=[PackagePath(relative)],
                           locate_file=lambda file: source)
    monkeypatch.setattr(collector.importlib.metadata, 'distributions', lambda: [dist])
    before = snapshot(tmp_path)
    with pytest.raises(ValueError, match='license'):
        collector.main()
    assert snapshot(tmp_path) == before


def test_x64_pe32_plus_targets_remain_accepted(staged):
    stage, checker, _, calls = staged
    value = manifest(stage)
    for relative in X64_TARGETS:
        path = stage / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b'self-authored x64 PE stub fixture')
        value['files'][relative] = hashlib.sha256(path.read_bytes()).hexdigest()
    save_manifest(stage, value)
    before = snapshot(stage)
    checker.main()
    assert snapshot(stage) == before
    assert calls['opened'] == calls['closed'] == calls['parsed']


@pytest.mark.parametrize('relative', ['converters/libreoffice/program/helper.exe', 'backend/_internal/pkg/helper.exe'])
def test_separate_helper_architecture_is_outside_main_process_gate(staged, relative):
    stage, checker, _, calls = staged
    path = stage / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b'self-authored separate helper fixture')
    value = manifest(stage)
    value['files'][relative] = hashlib.sha256(path.read_bytes()).hexdigest()
    save_manifest(stage, value)
    calls['headers'][relative] = (0x14c, 0x10b)
    before = snapshot(stage)
    with pytest.raises(ValueError, match='coverage incomplete.*unclassified PE'):
        checker.main()
    assert snapshot(stage) == before
    assert str(path) in calls['parsed']
    assert calls['opened'] == calls['closed']


def test_unknown_helper_is_reported_without_claiming_whole_package_x64(staged, capsys):
    stage, checker, _, calls = staged
    path = stage / 'templates/arm.exe'
    path.parent.mkdir()
    path.write_bytes(b'self-authored non-runtime template')
    value = manifest(stage)
    value['files']['templates/arm.exe'] = hashlib.sha256(path.read_bytes()).hexdigest()
    save_manifest(stage, value)
    calls['headers']['templates/arm.exe'] = (0xaa64, 0x20b)
    before = snapshot(stage)
    with pytest.raises(ValueError, match='coverage incomplete.*unclassified PE'):
        checker.main()
    report = json.loads(capsys.readouterr().out.splitlines()[0])
    assert report['pe_coverage'] == 'partial'
    assert report['unproven_runtime_candidates'] == [dict(path='templates/arm.exe', machine='0xaa64')]
    assert report['limitations']
    assert snapshot(stage) == before
