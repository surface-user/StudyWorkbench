import hashlib
import importlib
import importlib.metadata
import importlib.util
import json
import marshal
import stat
import struct
import sys
import zipfile
import zlib

import pytest
import test_frozen_python_members
from test_frozen_python_members import record_line

collector = test_frozen_python_members.collector
fixture = test_frozen_python_members.fixture
matched = test_frozen_python_members.matched


def make_program(collector, modules, startup):
    pyz, records = b'PYZ\0' + importlib.util.MAGIC_NUMBER + b'\0' * 4, []
    for name, kind, source in modules:
        packed = zlib.compress(marshal.dumps(compile(source, name + '.py', 'exec', dont_inherit=True))) if kind != 3 else b''
        records.append((name, (kind, len(pyz), len(packed))))
        pyz += packed
    pyz = pyz[:8] + struct.pack('!i', len(pyz)) + pyz[12:] + marshal.dumps(records)
    blobs = [('PYZ.pyz', 'z', pyz, False)]
    for name, kind, raw in startup:
        blobs.append((name, kind, marshal.dumps(compile(raw, name + '.py', 'exec', dont_inherit=True)), True))
    body, toc = b'', b''
    reader = collector.CArchiveReader
    for name, kind, raw, compressed in blobs:
        packed = zlib.compress(raw) if compressed else raw
        encoded = name.encode() + b'\0'
        toc += struct.pack(reader._TOC_ENTRY_FORMAT, reader._TOC_ENTRY_LENGTH + len(encoded),
                           len(body), len(packed), len(raw), int(compressed), kind.encode()) + encoded
        body += packed
    cookie = struct.pack(reader._COOKIE_FORMAT, reader._COOKIE_MAGIC_PATTERN,
                         len(body) + len(toc) + reader._COOKIE_LENGTH, len(body), len(toc),
                         sys.version_info.major * 100 + sys.version_info.minor, b'python.dll')
    return b'MZ self-authored fixture, never executable' + body + toc + cookie


@pytest.fixture
def origin(matched, collector, monkeypatch):
    _, payload, source, _, _, site, distributions = matched
    tool = importlib.import_module('frozen_python_origins')
    root = payload.parent
    code = b"raise RuntimeError('Origin scanner must not execute this source')\n"
    stdlib = b"raise RuntimeError('NuGet fixture must never execute')\n"
    runtime = b"raise RuntimeError('PyInstaller runtime fixture must never execute')\n"
    lock = source / tool.LOCKS[0]
    lock.write_bytes(lock.read_bytes() + b'other==1.0.0\npyinstaller==6.22.3\n')
    for name, version in [('other', '1.0.0'), ('pyinstaller', '6.22.3')]:
        meta = site / f'{name}-{version}.dist-info'
        meta.mkdir()
        (meta / 'METADATA').write_text(f'Name: {name}\nVersion: {version}\n', encoding='utf-8')
        (meta / 'RECORD').write_text(record_line(meta.name + '/METADATA', (meta / 'METADATA').read_bytes())
                                   + meta.name + '/RECORD,,\n', encoding='utf-8')
        distributions.append(importlib.metadata.PathDistribution(meta))
    shared = b'Self-authored shared library fixture\n'
    for package in ['sample', 'other']:
        path = site / (package + '.libs/shared.dll')
        path.parent.mkdir()
        path.write_bytes(shared)
        record = site / (package + ('-1.2.3' if package == 'sample' else '-1.0.0') + '.dist-info/RECORD')
        record.write_text(record.read_text() + record_line(path.relative_to(site).as_posix(), shared), encoding='utf-8')
    runtime_path = site / 'PyInstaller/hooks/rthooks/pyi_rth_demo.py'
    runtime_path.parent.mkdir(parents=True)
    runtime_path.write_bytes(runtime)
    record = site / 'pyinstaller-6.22.3.dist-info/RECORD'
    record.write_text(record.read_text() + record_line(runtime_path.relative_to(site).as_posix(), runtime), encoding='utf-8')
    (payload / '_internal/shared.dll').write_bytes(shared)
    sample_record = site / 'sample-1.2.3.dist-info/RECORD'
    (payload / '_internal/sample-1.2.3.dist-info/RECORD').write_bytes(sample_record.read_bytes())
    native = b'Self-authored CPython native fixture\n'
    (payload / '_internal/CPYTHON_FIXTURE.pyd').write_bytes(native)
    for path, raw in {'backend/migrations/env.py': code, 'backend/study_workbench/player.html': b'<p>fixture</p>',
                      'tools/frozen_entry.py': code}.items():
        target = source / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
        if path.startswith('backend/'):
            target = payload / '_internal' / path.removeprefix('backend/')
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(raw)
    business = (source / 'backend/study_workbench/__init__.py').read_bytes()
    vendor = (site / 'vendor/dynamic-data.py').read_bytes()
    modules = [('study_workbench', 1, business), ('vendor.dynamic-data', 0, vendor),
               ('vendor', 3, b''), ('stdlib_fixture', 0, stdlib)]
    startup = [('struct', 'm', stdlib), ('pyi_rth_demo', 's', runtime), ('frozen_entry', 's', code)]
    (payload / 'study_backend.exe').write_bytes(make_program(collector, modules, startup))
    base_code = marshal.dumps(compile(stdlib, 'encodings.py', 'exec', dont_inherit=True))
    with zipfile.ZipFile(payload / '_internal/base_library.zip', 'w') as archive:
        archive.writestr('encodings/__init__.pyc', importlib.util.MAGIC_NUMBER + b'\0' * 12 + base_code)
    python_package = root / 'python.zip'
    version = sys.version.split()[0]
    with zipfile.ZipFile(python_package, 'w') as archive:
        archive.writestr('python.nuspec', '<package><metadata><id>python</id><version>' + version + '</version></metadata></package>')
        archive.writestr('tools/Lib/struct.py', stdlib)
        archive.writestr('tools/Lib/stdlib_fixture.py', stdlib)
        archive.writestr('tools/Lib/encodings/__init__.py', stdlib)
        archive.writestr('tools/DLLs/cpython_fixture.pyd', native)
    monkeypatch.setattr(tool, 'PYTHON_VERSION', version)
    monkeypatch.setattr(tool, 'PYTHON_ARCHIVE_SHA256', hashlib.sha256(python_package.read_bytes()).hexdigest())
    entries = []
    for path in ['backend/study_workbench/__init__.py', 'backend/migrations/env.py',
                 'backend/study_workbench/player.html', 'tools/frozen_entry.py']:
        entries.append({'path': path, 'type': 'blob', 'mode': '100644', 'sha': tool.git_blob((source / path).read_bytes())})
    tree = root / 'source-tree.json'
    tree.write_text(json.dumps({'commit': 'a' * 40, 'tree': 'b' * 40, 'entries': entries}), encoding='utf-8')
    coverage_output = root / 'coverage-origins'
    collector.generate(payload, source, 'a' * 40, collector.sha256((payload / 'study_backend.exe').read_bytes()),
                       root / 'syft.exe', coverage_output)
    return {'tool': tool, 'payload': payload, 'source': source, 'coverage': coverage_output / 'coverage.json',
            'python_package': python_package, 'source_tree': tree, 'output': root / 'origins', 'site': site,
            'collector': collector, 'refresh': 0}


def run(origin):
    d = origin
    return d['tool'].generate(*(d[k] for k in ['payload', 'source', 'coverage', 'python_package', 'source_tree', 'output']))


def refresh_coverage(origin):
    origin['refresh'] += 1
    output = origin['payload'].parent / ('refreshed-' + str(origin['refresh']))
    collector = origin['collector']
    collector.generate(origin['payload'], origin['source'], 'a' * 40,
                       collector.sha256((origin['payload'] / 'study_backend.exe').read_bytes()),
                       origin['payload'].parent / 'syft.exe', output)
    origin['coverage'] = output / 'coverage.json'


def test_pinned_sources_cover_real_members_and_keep_shared_and_unverified_roles(origin):
    report = run(origin)
    physical = report['additional_physical_origins']
    assert {x['identity'] for x in physical['_internal/shared.dll']} == {'pkg:pypi/sample@1.2.3', 'pkg:pypi/other@1.0.0'}
    assert physical['_internal/CPYTHON_FIXTURE.pyd'][0]['source_path'] == 'tools/DLLs/cpython_fixture.pyd'
    assert physical['_internal/sample-1.2.3.dist-info/RECORD'][0]['record_self_hash_declared'] is False
    assert physical['_internal/migrations/env.py'][0]['source_git_blob_sha1']
    assert physical['_internal/study_workbench/player.html'][0]['evidence_kind'] == 'project_git_blob_bytes'
    assert report['additional_pyz_origins']['stdlib_fixture'][0]['equivalent_optimization_levels'] == [0, 1, 2]
    assert 'encodings/__init__.pyc' in report['base_library_origins']
    assert report['carchive_origins']['struct']['status'] == 'source_matched'
    runtime = report['carchive_origins']['pyi_rth_demo']['candidates'][0]
    assert runtime['identity'] == 'pkg:pypi/pyinstaller@6.22.3' and runtime['metadata_sha256'] and runtime['record_sha256']
    assert report['carchive_origins']['frozen_entry']['candidates'][0]['identity'] == 'application-source:' + 'a' * 40
    assert report['carchive_origins']['PYZ.pyz']['status'] == 'embedded_container'
    namespace = report['namespace_descriptions']['vendor']
    assert namespace['namespace_version'] is None and namespace['stored_code_bytes'] == 0
    assert namespace['contributing_build_distributions'] == ['pkg:pypi/sample@1.2.3']
    assert not namespace['package_identity_authenticated']
    assert not report['product_sbom_complete'] and not report['upstream_provenance_verified'] and not report['source_tree_authenticated']
    assert 'study_backend.exe' in report['remaining_unmapped_physical']
    assert '_internal/base_library.zip' in report['remaining_unmapped_physical']
    assert not report['remaining_unmapped_code_modules'] and not report['remaining_unmapped_base_library']
    output = origin['output']
    bom_raw = (output / 'python-origins.cdx.json').read_bytes()
    assert report['bom_sha256'] == hashlib.sha256(bom_raw).hexdigest()
    components = {x['bom-ref']: x for x in json.loads(bom_raw)['components']}
    assert set(components) == {'pkg:pypi/sample@1.2.3', 'pkg:pypi/other@1.0.0', 'pkg:pypi/pyinstaller@6.22.3',
                               'pkg:nuget/python@' + sys.version.split()[0], 'application-source:' + 'a' * 40}
    for purl in ['pkg:pypi/sample@1.2.3', 'pkg:pypi/other@1.0.0']:
        assert {'location': '_internal/shared.dll'} in components[purl]['evidence']['occurrences']
        assert 'hashes' not in components[purl]
    assert str(origin['site']) not in json.dumps(report) and str(origin['source']) not in json.dumps(report)


@pytest.mark.parametrize('kind', ['archive_hash', 'interpreter', 'tree_commit', 'tree_duplicate', 'tree_path', 'project_blob', 'project_source', 'existing', 'nested'])
def test_untrusted_input_or_output_boundaries_fail_without_overall_report(origin, monkeypatch, kind):
    tool = origin['tool']
    if kind == 'archive_hash':
        monkeypatch.setattr(tool, 'PYTHON_ARCHIVE_SHA256', '0' * 64)
    elif kind == 'interpreter':
        monkeypatch.setattr(tool, 'PYTHON_VERSION', '0.0.0')
    elif kind in {'tree_commit', 'tree_duplicate', 'tree_path', 'project_blob'}:
        path = origin['source_tree']
        data = json.loads(path.read_bytes())
        if kind == 'tree_commit':
            data['commit'] = 'c' * 40
        elif kind == 'tree_duplicate':
            data['entries'].append(data['entries'][0])
        elif kind == 'tree_path':
            data['entries'][0]['path'] = '../outside'
        else:
            data['entries'][1]['sha'] = '0' * 40
        path.write_text(json.dumps(data), encoding='utf-8')
    elif kind == 'project_source':
        (origin['source'] / 'backend/study_workbench/player.html').write_bytes(b'changed')
    elif kind == 'existing':
        origin['output'].mkdir()
        (origin['output'] / 'keep').write_bytes(b'kept')
    else:
        origin['output'] = origin['payload'] / 'nested'
    with pytest.raises((ValueError, OSError)):
        run(origin)
    assert not (origin['output'] / 'origins.json').exists()
    if kind == 'existing':
        assert (origin['output'] / 'keep').read_bytes() == b'kept'


@pytest.mark.parametrize('kind', ['traversal', 'duplicate_case', 'symlink', 'version', 'entities',
                                  'utf16_entities', 'duplicate_identity'])
def test_pinned_zip_structure_and_metadata_are_validated_without_extraction(origin, monkeypatch, kind):
    path, tool = origin['python_package'], origin['tool']
    with zipfile.ZipFile(path) as archive:
        original = [(x.filename, archive.read(x)) for x in archive.infolist()]
    with zipfile.ZipFile(path, 'w') as archive:
        for name, raw in original:
            if name == 'python.nuspec' and kind == 'version':
                raw = b'<package><metadata><id>python</id><version>0.0.0</version></metadata></package>'
            elif name == 'python.nuspec' and kind == 'entities':
                raw = b'<!DOCTYPE package [<!ENTITY value "python">]><package><metadata><id>&value;</id></metadata></package>'
            elif name == 'python.nuspec' and kind == 'utf16_entities':
                raw = ('<!DOCTYPE package [<!ENTITY value "python">]><package><metadata><id>&value;</id><version>'
                       + sys.version.split()[0] + '</version></metadata></package>').encode('utf-16')
            elif name == 'python.nuspec' and kind == 'duplicate_identity':
                raw = ('<package><metadata><id>python</id><id>python</id><version>'
                       + sys.version.split()[0] + '</version></metadata></package>').encode()
            archive.writestr(name, raw)
        if kind == 'traversal':
            archive.writestr('../outside.py', b'not extracted')
        elif kind == 'duplicate_case':
            archive.writestr('TOOLS/lib/STRUCT.py', b'duplicate')
        elif kind == 'symlink':
            link = zipfile.ZipInfo('tools/link.py')
            link.external_attr = (stat.S_IFLNK | 0o777) << 16
            archive.writestr(link, b'outside')
    monkeypatch.setattr(tool, 'PYTHON_ARCHIVE_SHA256', hashlib.sha256(path.read_bytes()).hexdigest())
    with pytest.raises(ValueError):
        run(origin)
    assert not (origin['output'] / 'origins.json').exists()
    assert not (path.parent / 'outside.py').exists()


@pytest.mark.parametrize('constant', ['MAX_ARCHIVE_BYTES', 'MAX_ZIP_BYTES', 'MAX_ZIP_MEMBER_BYTES', 'MAX_FILES',
                                     'MAX_BUILD_BYTES', 'MAX_MEMBER_BYTES', 'MAX_RECORD_BYTES', 'MAX_REPORT_BYTES', 'MAX_RECORD_ROWS'])
def test_source_and_archive_budgets_refuse_partial_success(origin, monkeypatch, constant):
    monkeypatch.setattr(origin['tool'], constant, 1)
    with pytest.raises(ValueError, match='budget|oversized'):
        run(origin)
    assert not (origin['output'] / 'origins.json').exists()


@pytest.mark.parametrize('kind', ['archive', 'tree', 'coverage', 'project', 'build', 'member_report', 'member_bom'])
def test_inputs_changed_after_member_matching_are_not_audited_as_stable(origin, monkeypatch, kind):
    tool = origin['tool']
    paths = {'archive': origin['python_package'], 'tree': origin['source_tree'], 'coverage': origin['coverage'],
             'project': origin['source'] / 'backend/study_workbench/player.html',
             'build': origin['site'] / 'PyInstaller/hooks/rthooks/pyi_rth_demo.py',
             'member_report': origin['output'] / 'local-members/members.json',
             'member_bom': origin['output'] / 'local-members/python-members.cdx.json'}
    original = tool.zip_members

    def changed(*args):
        result = original(*args)
        path = paths[kind]
        path.write_bytes(path.read_bytes() + b'\n')
        return result

    monkeypatch.setattr(tool, 'zip_members', changed)
    with pytest.raises(ValueError, match='changed|differs'):
        run(origin)
    assert not (origin['output'] / 'origins.json').exists() and not (origin['output'] / 'python-origins.cdx.json').exists()


def test_runtime_hook_name_alone_does_not_assign_pyinstaller_identity(origin):
    path = origin['site'] / 'PyInstaller/hooks/rthooks/pyi_rth_demo.py'
    before = path.read_bytes()
    path.write_bytes(b'changed = True\n')
    record = origin['site'] / 'pyinstaller-6.22.3.dist-info/RECORD'
    record.write_text(record.read_text().replace(record_line(path.relative_to(origin['site']).as_posix(), before),
                                                record_line(path.relative_to(origin['site']).as_posix(), path.read_bytes())), encoding='utf-8')
    report = run(origin)
    assert report['carchive_origins']['pyi_rth_demo']['status'] == 'unmapped'
    assert report['carchive_origins']['pyi_rth_demo']['candidates'] == []
    bom = json.loads((origin['output'] / 'python-origins.cdx.json').read_bytes())
    assert 'pkg:pypi/pyinstaller@6.22.3' not in {x.get('purl') for x in bom['components']}


@pytest.mark.parametrize('kind', ['header', 'different_code'])
def test_base_zip_code_identity_is_checked_independently_of_its_name(origin, kind):
    raw = importlib.util.MAGIC_NUMBER + b'\0' * 12 + marshal.dumps(compile('different = True', 'base.py', 'exec', dont_inherit=True))
    if kind == 'header':
        raw = b'bad!' + raw[4:]
    with zipfile.ZipFile(origin['payload'] / '_internal/base_library.zip', 'w') as archive:
        archive.writestr('encodings/__init__.pyc', raw)
    refresh_coverage(origin)
    if kind == 'header':
        with pytest.raises(ValueError, match='pyc'):
            run(origin)
        assert not (origin['output'] / 'origins.json').exists()
    else:
        report = run(origin)
        assert report['remaining_unmapped_base_library'] == ['encodings/__init__.pyc']
        assert report['base_library_origins'] == {}


def test_record_self_metadata_is_not_filled_with_a_fake_declared_hash(origin):
    record = origin['site'] / 'sample-1.2.3.dist-info/RECORD'
    record.write_text(record.read_text().replace('sample-1.2.3.dist-info/RECORD,,', 'sample-1.2.3.dist-info/RECORD,sha256=unverified,'), encoding='utf-8')
    (origin['payload'] / '_internal/sample-1.2.3.dist-info/RECORD').write_bytes(record.read_bytes())
    refresh_coverage(origin)
    with pytest.raises(ValueError, match='RECORD'):
        run(origin)
    assert not (origin['output'] / 'origins.json').exists()


def test_cli_origin_subset_never_returns_release_success(origin, monkeypatch, capsys):
    tool = origin['tool']
    monkeypatch.setattr('sys.argv', ['frozen_python_origins', '--payload', str(origin['payload']), '--source', str(origin['source']),
                                   '--coverage', str(origin['coverage']), '--python-package', str(origin['python_package']),
                                   '--source-tree', str(origin['source_tree']), '--output', str(origin['output'])])
    assert tool.main() == 2
    assert 'remain incomplete' in capsys.readouterr().out


def test_unmatched_build_inputs_are_also_kept_stable_until_the_end(origin, monkeypatch):
    data = origin['site'] / 'data.bin'
    before = data.read_bytes()
    data.write_bytes(b'valid source differs from frozen file\n')
    record = origin['site'] / 'sample-1.2.3.dist-info/RECORD'
    record.write_text(record.read_text().replace(record_line('data.bin', before),
                                                record_line('data.bin', data.read_bytes())), encoding='utf-8')
    original = origin['tool'].zip_members

    def changed(*args):
        result = original(*args)
        data.write_bytes(b'changed again after the first source check')
        return result

    monkeypatch.setattr(origin['tool'], 'zip_members', changed)
    with pytest.raises(ValueError, match='changed'):
        run(origin)
    assert not (origin['output'] / 'origins.json').exists()
