import copy
import importlib
import importlib.util
import json
import marshal
import struct
import subprocess
import sys
import zipfile
import zlib
from pathlib import Path

import pytest
import yaml


@pytest.fixture
def collector(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).parents[2] / 'tools'))
    return importlib.import_module('frozen_sbom')


def make_exe(collector, source, damage=None):
    source_bytes = (source / 'backend/study_workbench/__init__.py').read_bytes()
    code = compile(source_bytes, 'fixture.py', 'exec', dont_inherit=True)
    compressed = zlib.compress(marshal.dumps(code))
    pyz = b'PYZ\0' + importlib.util.MAGIC_NUMBER + b'\0' * 4
    entries = [('study_workbench', (1, 12, len(compressed))),
               ('vendor.dynamic-data', (0, 12 + len(compressed), len(compressed))),
               ('vendor.namespace', (3, 12 + 2 * len(compressed), 0))]
    pyz += compressed * 2
    if damage == 'duplicate':
        entries.append(entries[0])
    elif damage == 'traversal':
        entries[1] = ('../outside', entries[1][1])
    elif damage == 'member_bounds':
        entries[1] = ('vendor.dynamic-data', (0, len(pyz) + 10000, 100))
    elif damage == 'overlap':
        entries[1] = ('vendor.dynamic-data', entries[0][1])
    elif damage == 'namespace_data':
        entries[2] = ('vendor.namespace', (3, 12, 1))
    elif damage == 'missing_business':
        entries.pop(0)
    elif damage == 'wrong_magic':
        pyz = pyz[:4] + b'bad!' + pyz[8:]
    pyz = pyz[:8] + struct.pack('!i', len(pyz)) + pyz[12:] + marshal.dumps(entries)
    if damage == 'toc_bounds':
        pyz = pyz[:8] + struct.pack('!i', len(pyz) + 1) + pyz[12:]
    reader = collector.CArchiveReader
    name = b'PYZ.pyz\0'
    toc = struct.pack(reader._TOC_ENTRY_FORMAT, reader._TOC_ENTRY_LENGTH + len(name), 0, len(pyz), len(pyz), 0, b'z') + name
    if damage == 'carchive_duplicate':
        toc += toc
    option = b'pyi-contents-directory _internal\0'
    toc += struct.pack(reader._TOC_ENTRY_FORMAT, reader._TOC_ENTRY_LENGTH + len(option), 0, 0, 0, 0, b'o') + option
    pyversion = sys.version_info.major * 100 + sys.version_info.minor + (1 if damage == 'python_version' else 0)
    cookie = struct.pack(reader._COOKIE_FORMAT, reader._COOKIE_MAGIC_PATTERN,
                         len(pyz) + len(toc) + reader._COOKIE_LENGTH, len(pyz) + (1 if damage == 'carchive_bounds' else 0),
                         len(toc), pyversion, b'python.dll')
    return b'MZ self-authored fixture, never executable' + pyz + toc + cookie


@pytest.fixture
def fixture(collector, tmp_path, monkeypatch):
    payload, source, syft = tmp_path / 'payload', tmp_path / 'source', tmp_path / 'syft.exe'
    module = source / 'backend/study_workbench/__init__.py'
    module.parent.mkdir(parents=True)
    module.write_bytes(b"raise RuntimeError('Package code must never execute during collection')\n")
    (source / collector.LOCKS[0]).write_bytes(b'sample==1.2.3\nunused==9.0.0\n')
    dart = source / collector.LOCKS[1]
    dart.parent.mkdir(parents=True)
    dart.write_text(yaml.safe_dump({'packages': {'fixture': {'version': '1.0.0', 'source': 'hosted',
                    'description': {'name': 'fixture', 'url': 'https://pub.dev', 'sha256': 'f' * 64}}}}))
    meta = payload / '_internal/sample-1.2.3.dist-info/METADATA'
    meta.parent.mkdir(parents=True)
    meta.write_bytes(b'Name: sample\nVersion: 1.2.3\n')
    (payload / 'study_backend.exe').write_bytes(make_exe(collector, source))
    (payload / '_internal/native.pyd').write_bytes(b'self-authored native fixture')
    with zipfile.ZipFile(payload / '_internal/base_library.zip', 'w') as archive:
        archive.writestr('encodings/__init__.pyc', b'opaque bytes, never loaded')
    syft.write_bytes(b'self-authored scanner stub')
    monkeypatch.setattr(collector, 'SYFT_SHA256', collector.sha256(syft.read_bytes()))
    calls = []

    def run(command, **kwargs):
        calls.append((command, {**kwargs, 'env': {k: v for k, v in kwargs['env'].items() if k.startswith('SYFT_')}}))
        files = collector.inventory(payload)
        python = {'id': 'py1', 'type': 'python', 'name': 'sample', 'version': '1.2.3',
                  'purl': 'pkg:pypi/sample@1.2.3', 'locations': [{'path': '/' + meta.relative_to(payload).as_posix()}]}
        native = {'id': 'native1', 'type': 'binary', 'name': 'fixture', 'version': 'UNKNOWN',
                  'purl': '', 'locations': [{'path': '/study_backend.exe'}]}
        raw = {'descriptor': {'version': collector.SYFT_VERSION}, 'artifacts': [python, native]}
        components = [{'type': 'file', 'bom-ref': name, 'name': '/' + name,
                       'hashes': [{'alg': 'SHA-256', 'content': item['sha256']}]} for name, item in files.items()]
        components += [{'type': 'library', 'bom-ref': 'py1', 'name': 'sample', 'version': '1.2.3', 'purl': python['purl']},
                       {'type': 'application', 'bom-ref': 'native1', 'name': 'fixture', 'version': 'UNKNOWN'}]
        for component, candidate in zip(components[-2:], raw['artifacts']):
            component['properties'] = [{'name': 'syft:location:0:path', 'value': candidate['locations'][0]['path']}]
        bom = {'bomFormat': 'CycloneDX', 'specVersion': '1.6', 'components': components}
        (kwargs['cwd'] / 'backend.cdx.json').write_text(json.dumps(bom))
        (kwargs['cwd'] / 'backend.syft.json').write_text(json.dumps(raw))
    monkeypatch.setattr(collector.subprocess, 'run', run)
    return payload, source, syft, tmp_path / 'output', calls


def generate(collector, fixture):
    payload, source, syft, output, _ = fixture
    return collector.generate(payload, source, 'a' * 40, collector.sha256((payload / 'study_backend.exe').read_bytes()), syft, output)


def test_complete_coverage_keeps_unmapped_entries_and_declared_identity_separate(collector, fixture, monkeypatch):
    payload, _, _, output, calls = fixture
    before = collector.inventory(payload)
    monkeypatch.setenv('SYFT_ENRICH', 'all')
    monkeypatch.setenv('SYFT_CONFIG', 'do-not-read.yaml')
    result = generate(collector, fixture)
    assert result['physical_files'] == before == collector.inventory(payload)
    assert result['product_sbom_complete'] is False and result['source_head_authenticated'] is False
    assert result['source_head_assertion'] == 'a' * 40
    assert result['locked_python_without_shipped_metadata'] == ['pkg:pypi/unused@9.0.0']
    assert result['shipped_python_metadata']['pkg:pypi/sample@1.2.3']['upstream_provenance_verified'] is False
    assert result['embedded']['pyz']['vendor.dynamic-data']['package_identity'] == 'unmapped'
    assert result['embedded']['pyz']['vendor.namespace']['compressed_bytes'] == 0
    assert result['embedded']['pyz']['study_workbench']['package_identity'] == 'application_source_compared'
    assert result['embedded']['runtime_options'] == ['pyi-contents-directory _internal']
    assert result['native_files']['_internal/native.pyd']['candidate_ids'] == []
    assert result['scanner_candidates'][1]['version'] == 'UNKNOWN'
    assert str(payload.parent) not in json.dumps(result)
    assert json.loads((output / 'coverage.json').read_text()) == result
    command, kwargs = calls[0]
    assert kwargs['timeout'] == 180 and kwargs['check'] is True
    assert 'SYFT_CONFIG' not in kwargs['env'] and 'SYFT_ENRICH' not in kwargs['env']
    assert kwargs['env']['SYFT_CHECK_FOR_APP_UPDATE'] == 'false'
    assert command[command.index('--override-default-catalogers') + 1] == collector.CATALOGERS
    assert yaml.safe_load((output / 'syft.yaml').read_text())['file']['digests'] == ['sha256']


@pytest.mark.parametrize('damage', ['duplicate', 'traversal', 'member_bounds', 'missing_business',
                                  'wrong_magic', 'toc_bounds', 'python_version', 'overlap',
                                  'carchive_duplicate', 'carchive_bounds', 'namespace_data'])
def test_malformed_or_wrong_version_embedded_directories_fail_before_scan(collector, fixture, damage):
    payload, source, _, output, calls = fixture
    (payload / 'study_backend.exe').write_bytes(make_exe(collector, source, damage))
    with pytest.raises(ValueError):
        generate(collector, fixture)
    assert not calls and not output.exists()


def test_changed_business_source_is_not_attributed_to_frozen_code(collector, fixture):
    _, source, _, output, calls = fixture
    (source / 'backend/study_workbench/__init__.py').write_text('changed = True\n')
    with pytest.raises(ValueError, match='differs'):
        generate(collector, fixture)
    assert not calls and not output.exists()


@pytest.mark.parametrize('damage', ['wrong_version', 'duplicate_name', 'duplicate_version', 'missing_name', 'duplicate_package'])
def test_shipped_metadata_must_be_unique_and_match_exact_source_lock(collector, fixture, damage):
    payload, _, _, output, calls = fixture
    path = payload / '_internal/sample-1.2.3.dist-info/METADATA'
    if damage == 'duplicate_package':
        other = payload / '_internal/another.dist-info/METADATA'
        other.parent.mkdir()
        other.write_bytes(path.read_bytes())
    else:
        path.write_text({'wrong_version': 'Name: sample\nVersion: 2.0\n',
                         'duplicate_name': 'Name: sample\nName: other\nVersion: 1.2.3\n',
                         'duplicate_version': 'Name: sample\nVersion: 1.2.3\nVersion: 1.2.3\n',
                         'missing_name': 'Version: 1.2.3\n'}[damage])
    with pytest.raises(ValueError):
        generate(collector, fixture)
    assert not calls and not output.exists()


@pytest.mark.parametrize('damage', ['missing_file', 'extra_file', 'file_hash', 'file_path', 'duplicate_ref',
                                  'version', 'missing_package', 'raw_location', 'raw_version', 'scanner_version',
                                  'candidate_location', 'format'])
def test_scan_disagreements_never_create_coverage_receipt(collector, fixture, monkeypatch, damage):
    *_, output, _ = fixture
    original = collector.subprocess.run
    def run(command, **kwargs):
        original(command, **kwargs)
        bom_path, raw_path = output / 'backend.cdx.json', output / 'backend.syft.json'
        bom, raw = json.loads(bom_path.read_text()), json.loads(raw_path.read_text())
        if damage == 'missing_file':
            del bom['components'][0]
        elif damage == 'extra_file':
            extra = copy.deepcopy(bom['components'][0])
            extra.update(name='/extra', **{'bom-ref': 'extra'})
            bom['components'].append(extra)
        elif damage == 'file_hash':
            bom['components'][0]['hashes'][0]['content'] = '0' * 64
        elif damage == 'file_path':
            bom['components'][0]['name'] = '/../outside'
        elif damage == 'duplicate_ref':
            bom['components'].append(copy.deepcopy(bom['components'][0]))
        elif damage == 'version':
            bom['components'][-2]['version'] = '9.0'
        elif damage == 'missing_package':
            bom['components'].pop()
        elif damage == 'raw_location':
            raw['artifacts'][0]['locations'] = [{'path': '/outside'}]
        elif damage == 'raw_version':
            raw['artifacts'][0]['version'] = '9.0'
        elif damage == 'scanner_version':
            raw['descriptor']['version'] = 'wrong'
        elif damage == 'candidate_location':
            bom['components'][-1]['properties'][0]['value'] = '/unrelated'
        else:
            bom['specVersion'] = '1.5'
        bom_path.write_text(json.dumps(bom))
        raw_path.write_text(json.dumps(raw))
    monkeypatch.setattr(collector.subprocess, 'run', run)
    with pytest.raises(ValueError):
        generate(collector, fixture)
    assert not (output / 'coverage.json').exists() and (output / 'syft.log').exists()


@pytest.mark.parametrize('damage', ['payload', 'source', 'lock', 'timeout'])
def test_changing_inputs_or_failed_scan_leave_only_failure_artifacts(collector, fixture, monkeypatch, damage):
    payload, source, _, output, _ = fixture
    original = collector.subprocess.run
    def run(command, **kwargs):
        if damage == 'timeout':
            raise subprocess.TimeoutExpired(command, 180)
        original(command, **kwargs)
        if damage == 'payload':
            (payload / '_internal/native.pyd').write_bytes(b'changed')
        elif damage == 'source':
            (source / 'backend/study_workbench/__init__.py').write_text('changed = True')
        else:
            (source / collector.LOCKS[0]).write_text('sample==9.0\n')
    monkeypatch.setattr(collector.subprocess, 'run', run)
    with pytest.raises((ValueError, subprocess.SubprocessError)):
        generate(collector, fixture)
    assert not (output / 'coverage.json').exists()


@pytest.mark.parametrize('limit', ['MAX_FILES', 'MAX_FILE_BYTES', 'MAX_TOTAL_BYTES', 'MAX_TOC_BYTES', 'MAX_MEMBER_BYTES'])
def test_payload_and_archive_budgets_are_enforced(collector, fixture, monkeypatch, limit):
    monkeypatch.setattr(collector, limit, 1)
    with pytest.raises(ValueError):
        generate(collector, fixture)
    assert not fixture[-1]


def test_root_inventory_is_payload_too(collector, fixture):
    payload = fixture[0]
    (payload / 'build-inventory.json').write_bytes(b'previous inventory is still a shipped file')
    assert 'build-inventory.json' in generate(collector, fixture)['physical_files']


@pytest.mark.parametrize('damage', ['scanner_hash', 'expected_exe', 'existing_output', 'nested_output'])
def test_wrong_hash_or_unsafe_output_does_not_run_scanner(collector, fixture, damage):
    payload, source, syft, output, calls = fixture
    expected = collector.sha256((payload / 'study_backend.exe').read_bytes())
    if damage == 'scanner_hash':
        syft.write_bytes(b'tampered scanner')
    elif damage == 'expected_exe':
        expected = '0' * 64
    elif damage == 'existing_output':
        output.mkdir()
        (output / 'keep').write_bytes(b'preserve')
    else:
        output = payload / '..' / payload.name / 'new-output'
    with pytest.raises((ValueError, FileExistsError)):
        collector.generate(payload, source, 'a' * 40, expected, syft, output)
    assert not calls
    if damage == 'existing_output':
        assert (output / 'keep').read_bytes() == b'preserve'


@pytest.mark.parametrize('name', ['../outside', '/absolute', 'bad\\path', 'drive:name', 'bad. /name'])
def test_zip_members_cannot_escape_or_create_files(collector, fixture, name):
    payload, _, _, output, calls = fixture
    with zipfile.ZipFile(payload / '_internal/base_library.zip', 'w') as archive:
        info = zipfile.ZipInfo(name)
        info.filename = name
        archive.writestr(info, b'no extraction')
    with pytest.raises(ValueError):
        generate(collector, fixture)
    assert not calls and not output.exists()


def test_duplicate_zip_entries_are_rejected(collector, fixture):
    path = fixture[0] / '_internal/base_library.zip'
    with zipfile.ZipFile(path, 'w') as archive:
        archive.writestr('same', b'first')
        with pytest.warns(UserWarning, match='Duplicate'):
            archive.writestr('same', b'second')
    with pytest.raises(ValueError, match='Duplicate'):
        collector.zip_directory(path)


def test_zip_expansion_budget_does_not_depend_on_compressed_size(collector, fixture, monkeypatch):
    path = fixture[0] / '_internal/base_library.zip'
    with zipfile.ZipFile(path, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('small-compressed-large-plain', b'x' * 1000)
    monkeypatch.setattr(collector, 'MAX_MEMBER_BYTES', 100)
    with pytest.raises(ValueError, match='oversized'):
        collector.zip_directory(path)


def test_payload_root_reparse_is_rejected_before_reading(collector, fixture, monkeypatch):
    import stat
    from types import SimpleNamespace
    payload, _, _, output, calls = fixture
    original = Path.lstat
    def lstat(path):
        info = original(path)
        return SimpleNamespace(st_mode=info.st_mode, st_file_attributes=stat.FILE_ATTRIBUTE_REPARSE_POINT) if path == payload else info
    monkeypatch.setattr(Path, 'lstat', lstat)
    with pytest.raises(ValueError, match='reparse'):
        generate(collector, fixture)
    assert not calls and not output.exists()
