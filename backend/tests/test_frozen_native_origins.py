import base64
import importlib
import importlib.metadata
import json
import struct
import sys
import zipfile

import pytest
import test_frozen_python_members

collector = test_frozen_python_members.collector


def program(timestamp=11, resource=False):
    raw = bytearray(2048 if resource else 1536)
    raw[:2] = b'MZ'
    struct.pack_into('<I', raw, 0x3c, 0x80)
    raw[0x80:0x84] = b'PE\0\0'
    struct.pack_into('<HHIIIHH', raw, 0x84, 0x8664, 3 if resource else 2, timestamp, 0, 0, 240, 0x22)
    optional = 0x98
    struct.pack_into('<H', raw, optional, 0x20b)
    struct.pack_into('<IIQII', raw, optional + 16, 0x1000, 0x1000, 0x140000000, 0x1000, 0x200)
    struct.pack_into('<II', raw, optional + 56, 0x4000, 0x200)
    struct.pack_into('<H', raw, optional + 68, 3)
    struct.pack_into('<I', raw, optional + 108, 16)
    struct.pack_into('<II', raw, optional + 112 + 6 * 8, 0x2000, 28)
    for index, (name, start, rva, flags) in enumerate([
        (b'.text', 512, 0x1000, 0x60000020), (b'.rdata', 1024, 0x2000, 0x40000040),
    ] + ([(b'.rsrc', 1536, 0x3000, 0x40000040)] if resource else [])):
        struct.pack_into('<8sIIIIIIHHI', raw, 0x188 + index * 40, name, 256, rva, 512, start, 0, 0, 0, 0, flags)
    raw[512:560] = b'Self-authored PE fixture; never executable'.ljust(48, b'.')
    struct.pack_into('<IIHHIIII', raw, 1024, 0, timestamp, 0, 0, 2, 0, 0, 0)
    if resource:
        raw.extend(b'Self-authored overlay; never executed')
    return bytes(raw)


def line(name, raw):
    digest = base64.urlsafe_b64encode(bytes.fromhex(__import__('hashlib').sha256(raw).hexdigest())).decode().rstrip('=')
    return f'{name},sha256={digest},{len(raw)}\n'


@pytest.fixture
def native(tmp_path, collector, monkeypatch):
    tool = importlib.import_module('frozen_native_origins')
    source, payload, site, crt = [tmp_path / n for n in ('source', 'payload', 'site', 'crt')]
    for p in (source, payload / '_internal', site, crt):
        p.mkdir(parents=True)
    for name in tool.LOCKS:
        p = source / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b'Fixture lock; unchanged\n')
    (payload / 'study_backend.exe').write_bytes(program(22, resource=True))
    (payload / '_internal/base_library.zip').write_bytes(b'Generated fixture')
    for name in ('api-ms-win-test.dll', 'ucrtbase.dll'):
        raw = b'Self-authored native fixture: ' + name.encode()
        (crt / name).write_bytes(raw)
        (payload / '_internal' / name).write_bytes(raw)
    contents = {tool.BOOT: program(),
                tool.BUILD_SOURCES[1]: b"raise RuntimeError('Never execute wheel helpers')\n",
                tool.BUILD_SOURCES[2]: b"raise RuntimeError('Never execute build source')\n",
                f'pyinstaller-{tool.VERSION}.dist-info/METADATA': f'Name: PyInstaller\nVersion: {tool.VERSION}\n'.encode()}
    record_name = f'pyinstaller-{tool.VERSION}.dist-info/RECORD'
    record = ''.join(line(n, raw) for n, raw in contents.items()) + record_name + ',,\n'
    contents[record_name] = record.encode()
    for name, raw in contents.items():
        p = site / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(raw)
    # An installed console script outside site-packages is indexed but never followed.
    (site / record_name).write_bytes(record.encode() + b'../../Scripts/pyi.exe,sha256=ignored,1\n')
    wheel = tmp_path / 'fixture.whl'
    with zipfile.ZipFile(wheel, 'w') as z:
        for name, raw in contents.items():
            z.writestr(name, raw)
    monkeypatch.setattr(tool, 'WHEEL_SHA256', tool.sha256(wheel.read_bytes()))
    monkeypatch.setattr(tool, 'WHEEL_BYTES', wheel.stat().st_size)
    meta_dir = site / f'pyinstaller-{tool.VERSION}.dist-info'
    monkeypatch.setattr(tool.importlib.metadata, 'distributions', lambda: [importlib.metadata.PathDistribution(meta_dir)])
    entries = [(p.name if p.parent == payload else p.name, str(p), 'EXECUTABLE' if p.parent == payload else 'DATA')
               for p in sorted(payload.rglob('*')) if p.is_file()]
    entries = [(name, str(crt / name), 'BINARY') if name.endswith('.dll') else (name, path, kind)
               for name, path, kind in entries]
    toc = tmp_path / 'COLLECT-00.toc'
    toc.write_text(repr((entries,)), encoding='utf-8')
    paths = {}
    for name in ('coverage', 'python_package', 'source_tree'):
        paths[name] = tmp_path / name
        paths[name].write_bytes(b'Caller input delegated to prior verifier')
    d = {'tool': tool, 'payload': payload, 'source': source, 'site': site, 'crt_root': crt, 'collect_toc': toc,
         'wheel_file': wheel, 'output': tmp_path / 'output', 'contents': contents, **paths}

    def prior(*args):
        assert args[:5] == tuple(d[k] for k in ('payload', 'source', 'coverage', 'python_package', 'source_tree'))
        out = args[-1]
        (out / 'local-members').mkdir(parents=True)
        metadata_raw = (site / f'pyinstaller-{tool.VERSION}.dist-info/METADATA').read_bytes()
        record_raw = (site / record_name).read_bytes()
        package = {'metadata_sha256': tool.sha256(metadata_raw), 'record_sha256': tool.sha256(record_raw)}
        (out / 'local-members/members.json').write_text(json.dumps({'build_packages': {'pkg:pypi/pyinstaller@' + tool.VERSION: package}}))
        base = {'payload_fingerprint': 'fixture-fingerprint', 'exe_sha256': tool.sha256((payload / 'study_backend.exe').read_bytes()),
                'remaining_unmapped_physical': sorted(tool.inventory(payload)),
                'remaining_unmapped_code_modules': ['unknown_fixture'], 'remaining_unmapped_base_library': []}
        bom = {'bomFormat': 'CycloneDX', 'specVersion': '1.6', 'version': 1, 'metadata': {'properties': []},
               'components': [{'type': 'library', 'bom-ref': 'pkg:pypi/pyinstaller@' + tool.VERSION,
                               'purl': 'pkg:pypi/pyinstaller@' + tool.VERSION, 'name': 'pyinstaller', 'version': tool.VERSION,
                               'properties': [{'name': 'upstream-provenance-verified', 'value': 'false'}],
                               'evidence': {'occurrences': [{'location': 'study_backend.exe!startup_fixture'}]}}]}
        (out / 'origins.json').write_text(json.dumps(base))
        (out / 'python-origins.cdx.json').write_text(json.dumps(bom))
        return base

    d['prior'] = prior
    monkeypatch.setattr(tool, 'match_origins', prior)
    return d


def run(d):
    return d['tool'].generate(*(d[k] for k in (
        'payload', 'source', 'coverage', 'python_package', 'source_tree', 'collect_toc', 'wheel_file', 'crt_root', 'output')))


def test_sources_are_bounded_partial_evidence_and_not_executed(native):
    r = run(native)
    assert not r['product_sbom_complete'] and not r['upstream_provenance_verified']
    assert r['collect_entries'] == 4 and not r['collect_authenticated']
    assert len(r['local_crt_sources']) == 2
    for proof in r['local_crt_sources'].values():
        assert proof['component_identity'] is None and proof['component_version'] is None and proof['official_archive'] is None
        assert not proof['license_verified'] and not proof['redistribution_permission_verified']
    b = r['bootloader']
    assert b['executable_sections_identical'] == ['.text'] and b['sections']['.text']['bytes_identical']
    assert b['rdata_equal_except_confirmed_debug_timestamps']
    assert b['debug_timestamp_fields'][0]['changed_byte_offsets'] == [1028]
    assert b['debug_timestamp_fields'][0]['source_value'] == 11 and b['debug_timestamp_fields'][0]['target_value'] == 22
    assert not b['sections']['.rdata']['bytes_identical'] and not b['sections']['.rsrc']['bytes_identical']
    assert not b['whole_bootloader_verified'] and not b['reproducible_build_verified']
    assert not b['overlay_authenticated'] and b['target_pe']['overlay']['bytes'] > 0
    assert len(r['remaining_unmapped_physical']) == 4 and r['remaining_unmapped_code_modules'] == ['unknown_fixture']
    bom = json.loads((native['output'] / 'native-origins.cdx.json').read_text())
    assert len(bom['components']) == 1
    component = bom['components'][0]
    assert component['hashes'][0]['content'] == native['tool'].WHEEL_SHA256
    assert {x['location'] for x in component['evidence']['occurrences']} == {
        'study_backend.exe!startup_fixture', 'study_backend.exe#PE/.text'}
    assert r['pyinstaller_build_sources'][native['tool'].BOOT]['installed_record_sha256'] != r[
        'pyinstaller_build_sources'][native['tool'].BOOT]['wheel_record_sha256']


@pytest.mark.parametrize('raw', [b"(__import__('os').system('never execute'),)", b"([('../escape','/source','DATA')],)",
    b"([('x','/source','BAD')],)", b"([('x','relative','DATA')],)", b"([('x','/source/../escape','DATA')],)",
    b"([('x','/source','DATA'),('X','/source','DATA')],)", b"([('x','/source','DATA',1)],)",
    b"([('x','/source','DATA')],[],)", b'(' * 12 + b"'deep'" + b',)' * 12])
def test_collect_rejects_code_paths_duplicates_and_unsupported_shapes(collector, raw):
    tool = importlib.import_module('frozen_native_origins')
    with pytest.raises((ValueError, SyntaxError)):
        tool.collect_entries(raw)


def test_collect_byte_and_node_budgets(collector, monkeypatch):
    tool = importlib.import_module('frozen_native_origins')
    monkeypatch.setattr(tool, 'MAX_TOC_BYTES', 1)
    with pytest.raises(ValueError, match='byte budget'):
        tool.collect_entries(b'([], )')
    monkeypatch.setattr(tool, 'MAX_TOC_BYTES', 100)
    monkeypatch.setattr(tool, 'MAX_TOC_NODES', 1)
    with pytest.raises(ValueError, match='node/depth'):
        tool.collect_entries(b'([], )')


def test_collect_duplicate_target_is_rejected_with_real_absolute_windows_source(native):
    d = native
    raw = repr(([('ucrtbase.dll', str(d['crt_root'] / 'ucrtbase.dll'), 'BINARY'),
                 ('UCRTBASE.DLL', str(d['crt_root'] / 'ucrtbase.dll'), 'BINARY')],)).encode()
    with pytest.raises(ValueError, match='Duplicate COLLECT target'):
        d['tool'].collect_entries(raw)


@pytest.mark.parametrize('where', ['code', 'architecture', 'overlap', 'duplicate'])
def test_bootloader_rejects_code_architecture_and_structural_changes(collector, where):
    tool = importlib.import_module('frozen_native_origins')
    raw = bytearray(program(22, True))
    if where == 'code':
        raw[520] ^= 1
    elif where == 'architecture':
        struct.pack_into('<H', raw, 0x84, 0x14c)
    elif where == 'overlap':
        struct.pack_into('<I', raw, 0x188 + 40 + 20, 512)
    else:
        raw[0x188 + 40:0x188 + 48] = b'.text\0\0\0'
    with pytest.raises(ValueError):
        tool.compare_bootloader(program(), bytes(raw))


@pytest.mark.parametrize('where', ['other-rdata-byte', 'debug-is-not-coff'])
def test_rdata_differences_are_not_generically_ignored(collector, where):
    tool = importlib.import_module('frozen_native_origins')
    raw = bytearray(program(22, True))
    if where == 'other-rdata-byte':
        raw[1080] ^= 1
    else:
        struct.pack_into('<I', raw, 1028, 33)
    r = tool.compare_bootloader(program(), bytes(raw))
    assert not r['rdata_equal_except_confirmed_debug_timestamps'] and not r['whole_bootloader_verified']


@pytest.mark.parametrize('where', ['wheel', 'metadata', 'record', 'bootloader', 'helper', 'collect-target', 'crt-bytes', 'crt-root'])
def test_wrong_archives_build_records_and_local_sources_fail_without_final_report(native, where):
    d = native
    if where in ('wheel', 'metadata', 'record', 'bootloader', 'helper', 'crt-bytes'):
        path = {'wheel': d['wheel_file'], 'metadata': d['site'] / f"pyinstaller-{d['tool'].VERSION}.dist-info/METADATA",
                'record': d['site'] / f"pyinstaller-{d['tool'].VERSION}.dist-info/RECORD",
                'bootloader': d['site'] / d['tool'].BOOT, 'helper': d['site'] / d['tool'].BUILD_SOURCES[1],
                'crt-bytes': d['crt_root'] / 'ucrtbase.dll'}[where]
        path.write_bytes(path.read_bytes() + b'changed')
    elif where == 'collect-target':
        d['collect_toc'].write_text(repr(([('other', str(d['wheel_file']), 'DATA')],)))
    else:
        d['crt_root'] = d['source']
    with pytest.raises((ValueError, KeyError)):
        run(d)
    assert not (d['output'] / 'native-origins.json').exists()
    assert not (d['output'] / 'native-origins.cdx.json').exists()


@pytest.mark.parametrize('where', ['collect_toc', 'wheel_file', 'coverage', 'source_tree', 'python_package', 'crt', 'helper', 'lock'])
def test_all_selected_inputs_are_rechecked_after_prior_verification(native, monkeypatch, where):
    def mutate(*args):
        r = native['prior'](*args)
        p = {'crt': native['crt_root'] / 'ucrtbase.dll', 'helper': native['site'] / native['tool'].BUILD_SOURCES[1],
             'lock': native['source'] / native['tool'].LOCKS[0]}.get(where, native.get(where))
        p.write_bytes(p.read_bytes() + b'changed at end')
        return r
    monkeypatch.setattr(native['tool'], 'match_origins', mutate)
    with pytest.raises(ValueError, match='changed'):
        run(native)
    assert (native['output'] / 'python-origins/origins.json').exists()
    assert not (native['output'] / 'native-origins.json').exists()


@pytest.mark.parametrize('limit', ['MAX_NEW_FILES', 'MAX_NEW_BYTES'])
def test_native_input_budgets_fail_closed(native, monkeypatch, limit):
    monkeypatch.setattr(native['tool'], limit, 1)
    with pytest.raises(ValueError, match='budget'):
        run(native)
    assert not (native['output'] / 'native-origins.json').exists()


@pytest.mark.parametrize('kind', ['unsafe', 'duplicate', 'wheel-record', 'duplicate-record'])
def test_rejected_wheel_entries_and_record_claims_are_not_accepted_via_a_new_hash(native, monkeypatch, kind):
    d, tool = native, native['tool']
    contents = dict(d['contents'])
    record_name = f'pyinstaller-{tool.VERSION}.dist-info/RECORD'
    if kind == 'wheel-record':
        contents[record_name] = contents[record_name].replace(b'sha256=', b'sha512=', 1)
    elif kind == 'duplicate-record':
        contents[record_name] += contents[record_name].splitlines(keepends=True)[0]
    with zipfile.ZipFile(d['wheel_file'], 'w') as z:
        for name, raw in contents.items():
            z.writestr(name, raw)
        if kind in ('unsafe', 'duplicate'):
            z.writestr('../outside' if kind == 'unsafe' else tool.BOOT.upper(), b'fixture')
    monkeypatch.setattr(tool, 'WHEEL_SHA256', tool.sha256(d['wheel_file'].read_bytes()))
    monkeypatch.setattr(tool, 'WHEEL_BYTES', d['wheel_file'].stat().st_size)
    with pytest.raises(ValueError):
        run(d)
    assert not (d['output'] / 'native-origins.json').exists()


@pytest.mark.parametrize('duplicate', [False, True])
def test_metadata_name_uses_canonical_identity_and_rejects_multiple_declarations(native, monkeypatch, duplicate):
    d, tool = native, native['tool']
    contents = dict(d['contents'])
    meta_name = f'pyinstaller-{tool.VERSION}.dist-info/METADATA'
    record_name = f'pyinstaller-{tool.VERSION}.dist-info/RECORD'
    contents[meta_name] = contents[meta_name].replace(b'Name: PyInstaller', b'Name: pyinstaller')
    if duplicate:
        contents[meta_name] += b'Name: pyinstaller\n'
    contents[record_name] = (''.join(line(n, raw) for n, raw in contents.items() if n != record_name)
                             + record_name + ',,\n').encode()
    for name in (meta_name, record_name):
        (d['site'] / name).write_bytes(contents[name])
    with zipfile.ZipFile(d['wheel_file'], 'w') as z:
        for name, raw in contents.items():
            z.writestr(name, raw)
    monkeypatch.setattr(tool, 'WHEEL_SHA256', tool.sha256(d['wheel_file'].read_bytes()))
    monkeypatch.setattr(tool, 'WHEEL_BYTES', d['wheel_file'].stat().st_size)
    if duplicate:
        with pytest.raises(ValueError, match='METADATA identity'):
            run(d)
    else:
        assert run(d)['pyinstaller_wheel_sha256'] == tool.WHEEL_SHA256


def test_cli_uses_incomplete_exit_and_never_a_release_success(native, monkeypatch):
    d = native
    argv = ['tool']
    for flag, key in [('payload', 'payload'), ('source', 'source'), ('coverage', 'coverage'),
                      ('python-package', 'python_package'), ('source-tree', 'source_tree'), ('collect-toc', 'collect_toc'),
                      ('pyinstaller-wheel', 'wheel_file'), ('crt-source-root', 'crt_root'), ('output', 'output')]:
        argv += ['--' + flag, str(d[key])]
    monkeypatch.setattr(sys, 'argv', argv)
    assert d['tool'].main() == 2
    with pytest.raises(SystemExit) as exc:
        d['tool'].main()
    assert exc.value.code == 1
