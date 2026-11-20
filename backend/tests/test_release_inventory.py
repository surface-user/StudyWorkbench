import hashlib
import importlib
import json
import os
import stat
import subprocess
import sys
import zipfile
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


@pytest.mark.parametrize('raw', [
    b'{"url":"file:///private/build/wheel"}', b'{"url":"git+file:///private/repo"}',
    b'{"url":"C:/private/build/wheel"}', b'{"url":"/private/build/wheel"}',
    b'{"url":42}', b'{}', b'!', b'x' * 65537,
], ids=['file-url', 'git-file', 'drive', 'absolute', 'wrong-type', 'missing', 'invalid-json', 'oversized'])
def test_backend_local_install_metadata_rejected_without_writing(staged, raw):
    stage, checker, _, calls = staged
    relative = 'backend/_internal/pkg.dist-info/direct_url.json'
    path = stage / relative
    path.parent.mkdir(parents=True)
    path.write_bytes(raw)
    data = manifest(stage)
    data['files'][relative] = hashlib.sha256(raw).hexdigest()
    save_manifest(stage, data)
    before = snapshot(stage)
    with pytest.raises(ValueError) as exc:
        checker.main()
    assert 'private' not in str(exc.value)
    assert not calls['opened'] and snapshot(stage) == before


def test_backend_remote_provenance_and_other_payloads_are_preserved(staged):
    stage, checker, _, _ = staged
    data = manifest(stage)
    for relative, url in [('backend/_internal/pkg.dist-info/direct_url.json', 'https://example.test/wheel'),
                          ('component/pkg.dist-info/direct_url.json', 'file:///example')]:
        path = stage / relative
        path.parent.mkdir(parents=True)
        raw = json.dumps({'url': url}).encode()
        path.write_bytes(raw)
        data['files'][relative] = hashlib.sha256(raw).hexdigest()
    save_manifest(stage, data)
    before = snapshot(stage)
    checker.main()
    assert snapshot(stage) == before


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


@pytest.fixture
def native_collection(collection):
    stage, collector, repository, _ = collection
    source = Path(__file__).parents[2] / 'packaging/licenses' / collector.NATIVE_LICENSE_PROFILE
    target = repository / 'packaging/licenses' / collector.NATIVE_LICENSE_PROFILE
    target.mkdir(parents=True)
    profile = json.loads((source / 'provenance.json').read_bytes())
    targets = []
    for archive in profile['binary_archives']:
        for item in archive['members']:
            if 'payload_path' in item:
                # Only inert DLL fixtures are written; the actual provider assets are tested separately.
                raw = ('self-authored inert fixture: ' + item['payload_path']).encode()
                path = stage / 'backend' / item['payload_path']
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(raw)
                item.update(bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())
                targets.append(path)
            else:
                (target / item['license_file']).write_bytes((source / item['license_file']).read_bytes())
    profile_path = target / 'provenance.json'
    profile_path.write_text(json.dumps(profile), encoding='utf-8')
    return stage, collector, repository, profile_path, targets


def test_generic_stage_without_targets_never_reads_profile(collection, monkeypatch):
    stage, collector, _, _ = collection

    def no_native_input(*args):
        raise AssertionError('A generic stage must not access native source profiles')

    monkeypatch.setattr(collector, '_native_input', no_native_input)
    collector.main()
    value = manifest(stage)['native_license_texts']
    assert value['applied'] is False and value['release_ready'] is False
    assert not (stage / 'licenses/_native').exists()
    assert collector.verify_native_license_texts(stage, collector.stage_files(stage), None) == value


def test_complete_native_stage_copies_originals_and_repeated_run_is_stable(native_collection):
    stage, collector, repository, _, targets = native_collection
    originals, sources = {p: p.read_bytes() for p in targets}, snapshot(repository)
    collector.main()
    value = manifest(stage)
    evidence = value['native_license_texts']
    assert evidence['applied'] and len(evidence['dlls']) == 3 and len(evidence['license_files']) == 2
    assert evidence['product_licenses_complete'] is evidence['vulnerabilities_verified'] is evidence['release_ready'] is False
    for item in evidence['license_files']:
        raw = (stage / item['path']).read_bytes()
        assert raw == (repository / item['source']).read_bytes()
        assert value['files'][item['path']] == item['sha256'] == hashlib.sha256(raw).hexdigest()
    assert {p: p.read_bytes() for p in targets} == originals and snapshot(repository) == sources
    assert collector.verify_native_license_texts(stage, collector.stage_files(stage), evidence) == evidence
    before = snapshot(stage)
    collector.main()
    assert snapshot(stage) == before and snapshot(repository) == sources


@pytest.mark.parametrize('remaining', [1, 2])
@pytest.mark.parametrize('offset', range(3))
def test_partial_native_components_fail_before_any_license_write(native_collection, remaining, offset):
    stage, collector, _, _, targets = native_collection
    keep = {targets[(offset + n) % 3] for n in range(remaining)}
    for path in targets:
        if path not in keep:
            path.unlink()
    before = snapshot(stage)
    with pytest.raises(ValueError, match='Partial'):
        collector.main()
    assert snapshot(stage) == before


@pytest.mark.parametrize('damage', ['dll', 'missing_profile', 'profile_duplicate', 'source_changed', 'source_missing', 'destination_changed', 'destination_directory', 'parent_file',
                                  'producer_url', 'producer_commit', 'archive_hash', 'unknown_target', 'license_path', 'license_id'])
def test_bad_native_inputs_preserve_existing_stage(native_collection, damage):
    stage, collector, _, profile, targets = native_collection
    directory = profile.parent
    destination = stage / 'licenses/_native' / collector.NATIVE_LICENSE_PROFILE / 'OpenSSL-LICENSE.txt'
    if damage == 'dll':
        targets[0].write_bytes(b'changed native version')
    elif damage == 'missing_profile':
        profile.unlink()
    elif damage == 'profile_duplicate':
        profile.write_text('{"schema_version":1,"schema_version":1}', encoding='utf-8')
    elif damage == 'source_changed':
        (directory / 'OpenSSL-LICENSE.txt').write_bytes(b'changed original')
    elif damage == 'source_missing':
        (directory / 'OpenSSL-LICENSE.txt').unlink()
    elif damage == 'destination_changed':
        destination.parent.mkdir(parents=True)
        destination.write_bytes(b'existing bytes must never be overwritten')
    elif damage == 'destination_directory':
        destination.mkdir(parents=True)
    elif damage == 'parent_file':
        (stage / 'licenses').mkdir()
        (stage / 'licenses/_native').write_bytes(b'existing file blocks destination')
    else:
        value = json.loads(profile.read_bytes())
        archive = value['binary_archives'][0]
        if damage == 'producer_url':
            archive['url'] = 'https://example.invalid/not-the-fixed-producer'
        elif damage == 'producer_commit':
            archive['commit'] = 'not-a-Git-commit'
        elif damage == 'archive_hash':
            archive['sha256'] = 'not-an-archive-digest'
        elif damage == 'unknown_target':
            item = dict(next(x for x in archive['members'] if 'payload_path' in x))
            item['payload_path'] = '../outside.dll'
            archive['members'].append(item)
        else:
            item = next(x for x in archive['members'] if 'license_file' in x)
            item['license_file' if damage == 'license_path' else 'declared_spdx_id'] = '../outside' if damage == 'license_path' else 'unverified-license'
        profile.write_text(json.dumps(value), encoding='utf-8')
    before, source_before = snapshot(stage), snapshot(directory)
    with pytest.raises((ValueError, OSError)):
        collector.main()
    assert snapshot(stage) == before and snapshot(directory) == source_before


def test_native_profile_cannot_swap_dll_producers(native_collection):
    stage, collector, _, path, _ = native_collection
    value = json.loads(path.read_bytes())
    openssl, libffi = value['binary_archives']
    crypto = next(x for x in openssl['members'] if x.get('payload_path') == '_internal/libcrypto-3.dll')
    ffi = next(x for x in libffi['members'] if 'payload_path' in x)
    openssl['members'].remove(crypto)
    libffi['members'].remove(ffi)
    openssl['members'].append(ffi)
    libffi['members'].append(crypto)
    path.write_text(json.dumps(value), encoding='utf-8')
    before = snapshot(stage)
    with pytest.raises(ValueError, match='native license DLL'):
        collector.main()
    assert snapshot(stage) == before


@pytest.mark.parametrize('part', ['profile', 'source', 'destination'])
def test_native_license_reparse_points_refused_before_open(native_collection, monkeypatch, part):
    stage, collector, _, profile, _ = native_collection
    destination = stage / 'licenses/_native' / collector.NATIVE_LICENSE_PROFILE / 'OpenSSL-LICENSE.txt'
    destination.parent.mkdir(parents=True)
    destination.write_bytes((profile.parent / 'OpenSSL-LICENSE.txt').read_bytes())
    target = {'profile': profile, 'source': profile.parent / 'OpenSSL-LICENSE.txt', 'destination': destination}[part]
    original_stat, original_open = Path.lstat, Path.open

    def reparse(path):
        result = original_stat(path)
        if path == target:
            return SimpleNamespace(st_mode=result.st_mode, st_file_attributes=stat.FILE_ATTRIBUTE_REPARSE_POINT)
        return result

    def no_target_read(path, *args, **kwargs):
        if path == target:
            raise AssertionError('Reparse input was opened')
        return original_open(path, *args, **kwargs)

    before = snapshot(stage)
    with monkeypatch.context() as patch:
        patch.setattr(Path, 'lstat', reparse)
        patch.setattr(Path, 'open', no_target_read)
        with pytest.raises(ValueError, match='reparse'):
            collector.main()
    assert snapshot(stage) == before


def test_change_after_native_preflight_refuses_copy(native_collection):
    stage, collector, _, _, targets = native_collection
    plan = collector.native_license_plan(stage, collector.stage_files(stage))
    targets[-1].write_bytes(b'changed between plan and copy')
    before = snapshot(stage)
    with pytest.raises(ValueError, match='changed'):
        collector.stage_native_license_texts(stage, plan)
    assert snapshot(stage) == before


def test_partial_copy_failure_is_kept_and_retry_reuses_correct_first_file(native_collection, monkeypatch):
    stage, collector, _, _, _ = native_collection
    plan = collector.native_license_plan(stage, collector.stage_files(stage))
    first, second = [x[1] for x in plan['writes']]
    original = Path.open

    def fail_second(path, *args, **kwargs):
        if path == second and args and args[0] == 'xb':
            raise OSError('self-authored copy failure')
        return original(path, *args, **kwargs)

    original_manifest = (stage / 'build-inventory.json').read_bytes()
    with monkeypatch.context() as patch:
        patch.setattr(Path, 'open', fail_second)
        with pytest.raises(OSError, match='copy failure'):
            collector.stage_native_license_texts(stage, plan)
    assert first.read_bytes() == plan['writes'][0][2] and not second.exists()
    assert (stage / 'build-inventory.json').read_bytes() == original_manifest
    stamp = first.stat().st_mtime_ns
    collector.stage_native_license_texts(stage, collector.native_license_plan(stage, collector.stage_files(stage)))
    assert first.stat().st_mtime_ns == stamp and second.read_bytes() == plan['writes'][1][2]


@pytest.mark.parametrize('damage', ['record_missing', 'record_changed', 'license_missing', 'license_changed', 'dll_changed'])
def test_release_checker_rejects_native_license_tampering_without_writes(native_collection, staged, monkeypatch, damage):
    stage, collector, _, _, targets = native_collection
    checker, calls = staged[1], staged[3]
    collector.main()
    value = manifest(stage)
    value['python'] = '3.13.17'  # Synthetic release metadata; the actual collector still records its interpreter.
    evidence = value['native_license_texts']
    license_path = stage / evidence['license_files'][0]['path']
    if damage == 'record_missing':
        del value['native_license_texts']
    elif damage == 'record_changed':
        evidence['dlls'][0]['sha256'] = '0' * 64
    elif damage == 'license_missing':
        license_path.unlink()
        del value['files'][license_path.relative_to(stage).as_posix()]
    elif damage == 'license_changed':
        license_path.write_bytes(b'forged license with updated outer manifest')
        value['files'][license_path.relative_to(stage).as_posix()] = hashlib.sha256(license_path.read_bytes()).hexdigest()
    else:
        targets[0].write_bytes(b'forged DLL with updated outer manifest')
        value['files'][targets[0].relative_to(stage).as_posix()] = hashlib.sha256(targets[0].read_bytes()).hexdigest()
    save_manifest(stage, value)
    monkeypatch.setattr(sys, 'argv', ['check_release.py', str(stage)])
    before = snapshot(stage)
    with pytest.raises((ValueError, OSError)):
        checker.main()
    assert snapshot(stage) == before and not calls['opened']


@pytest.mark.parametrize('case', ['local-install', 'remote-install', 'remote-missing-license'])
def test_native_license_and_install_metadata_guards_coexist(native_collection, staged, monkeypatch, case):
    stage, collector, _, _, _ = native_collection
    checker, calls = staged[1], staged[3]
    collector.main()
    value = manifest(stage)
    value['python'] = '3.13.17'
    relative = 'backend/_internal/example.dist-info/direct_url.json'
    metadata = stage / relative
    metadata.parent.mkdir()
    url = 'file:///private/wheel' if case == 'local-install' else 'https://example.test/wheel'
    metadata.write_bytes(json.dumps({'url': url}).encode())
    value['files'][relative] = hashlib.sha256(metadata.read_bytes()).hexdigest()
    if case == 'remote-missing-license':
        relative = value['native_license_texts']['license_files'][0]['path']
        (stage / relative).unlink()
        del value['files'][relative]
    save_manifest(stage, value)
    monkeypatch.setattr(sys, 'argv', ['check_release.py', str(stage)])
    before = snapshot(stage)
    if case == 'remote-install':
        checker.main()
        assert calls['opened'] and calls['opened'] == calls['closed']
    else:
        match = 'local installation path' if case == 'local-install' else 'original is missing'
        with pytest.raises(ValueError, match=match):
            checker.main()
        assert not calls['opened']
    assert snapshot(stage) == before


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
    licenses = importlib.import_module('frozen_member_licenses')
    raw = b'Self-authored architecture-test license fixture.'
    digest = hashlib.sha256(raw).hexdigest()
    index = {'scope': 'mapped frozen PyPI distributions', 'source_head': None,
             'payload_fingerprint': hashlib.sha256(json.dumps(licenses.inventory(stage / 'backend'), sort_keys=True).encode()).hexdigest(),
             'distribution_obligations_reviewed': False,
             'packages': {'pkg:pypi/example@1': {'metadata_sha256': 'a' * 64, 'record_sha256': 'b' * 64, 'issues': [],
                          'files': [{'text_path': 'texts/' + digest, 'sha256': digest, 'bytes': len(raw)}]}}}
    target = stage / licenses.BUNDLE_PATH
    target.parent.mkdir(parents=True)
    with zipfile.ZipFile(target, 'x') as archive:
        licenses.write_entry(archive, 'index.json', json.dumps(index).encode())
        licenses.write_entry(archive, 'texts/' + digest, raw)
    expected = hashlib.sha256(target.read_bytes()).hexdigest()
    value['python_license_bundle'] = licenses.verify_bundle(stage / 'backend', target, expected)
    value['files'][licenses.BUNDLE_PATH] = expected
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
