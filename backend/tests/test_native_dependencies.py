import hashlib
import importlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest


@pytest.fixture
def native(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).parents[2] / 'tools'))
    return importlib.import_module('native_dependencies')


def node(path, imports=(), *, machine=0x8664, digest='same'):
    return dict(path=path, machine=machine, magic=0x20B, sha256=digest, edges=list(imports),
                characteristics=0x0002, clr_rva=0)


@pytest.mark.parametrize('kind', ['import', 'delay'])
@pytest.mark.parametrize('root,other', [('program', 'java/bin'), ('java/bin', 'program'),
                                     ('backend/_internal', '.'), ('.', 'backend/_internal')])
def test_crt_in_other_process_domain_or_system_cannot_fill_missing_private_crt(native, tmp_path, kind, root, other):
    path = (Path(root) / 'entry.exe').as_posix()
    foreign = (Path(other) / 'VCRUNTIME140.dll').as_posix()
    nodes = {path.casefold(): node(path, [('vcruntime140.dll', kind)]), foreign.casefold(): node(foreign)}
    (tmp_path / 'vcruntime140.dll').write_bytes(b'host CRT must not count')
    with pytest.raises(ValueError, match=f'Unresolved {kind}.*system CRT'):
        native.closure(nodes, [path], [root, other], [root], tmp_path)


def test_delayed_bridge_requires_reachable_java_root_not_global_name(native, tmp_path):
    nodes = {'program/officebean.dll': node('program/officebean.dll', [('jawt.dll', 'delay')]),
             'java/bin/jawt.dll': node('java/bin/jawt.dll')}
    with pytest.raises(ValueError, match='Unresolved delay.*jawt.dll'):
        native.closure(nodes, ['program/officebean.dll'], ['program'], ['program'], tmp_path)
    result = native.closure(nodes, ['program/officebean.dll'], ['program', 'java/bin'], ['program'], tmp_path)
    assert result['edges'][0]['target'] == 'java/bin/jawt.dll'


def test_api_set_and_system_leaves_are_distinct_and_do_not_claim_minimum_os(native, tmp_path):
    (tmp_path / 'kernel32.dll').write_bytes(b'self-authored host presence fixture')
    nodes = {'main.exe': node('main.exe', [('kernel32.dll', 'import'), ('api-ms-win-core-file-l1-1-0.dll', 'delay')])}
    result = native.closure(nodes, ['main.exe'], ['.'], ['.'], tmp_path)
    assert [e['resolution'] for e in result['edges']] == ['host-system-file', 'api-set-contract']
    nodes['main.exe']['edges'].append(('api-ms-made-up.dll', 'import'))
    with pytest.raises(ValueError, match='Unresolved import'):
        native.closure(nodes, ['main.exe'], ['.'], ['.'], tmp_path)


def test_casefold_cycle_and_resolved_architecture_are_checked(native, tmp_path):
    nodes = {'program/main.exe': node('program/Main.EXE', [('mixed.dll', 'import')]),
             'program/mixed.dll': node('program/MiXeD.dll', [('main.exe', 'import')])}
    result = native.closure(nodes, ['program/main.exe'], ['program'], ['program'], tmp_path)
    assert len(result['nodes']) == 2 and result['edges'][0]['target'] == 'program/MiXeD.dll'
    nodes['program/mixed.dll']['machine'] = 0x14c
    with pytest.raises(ValueError, match='x64 PE32'):
        native.closure(nodes, ['program/main.exe'], ['program'], ['program'], tmp_path)


@pytest.mark.parametrize('different', [False, True])
def test_unordered_registered_directory_collision_requires_identical_bytes(native, tmp_path, different):
    name = 'msvcp140-' + 'a' * 32 + '.dll'
    nodes = {'pkg/mod.pyd': node('pkg/mod.pyd', [(name, 'import')]),
             'one.libs/' + name: node('one.libs/' + name),
             'two.libs/' + name: node('two.libs/' + name, digest='changed' if different else 'same')}
    if different:
        with pytest.raises(ValueError, match='Ambiguous registered DLL'):
            native.closure(nodes, ['pkg/mod.pyd'], ['pkg'], ['_internal'], tmp_path,
                           registrations=['one.libs', 'two.libs'])
    else:
        assert len(native.closure(nodes, ['pkg/mod.pyd'], ['pkg'], ['_internal'], tmp_path,
                                  registrations=['one.libs', 'two.libs'])['nodes']) == 2


def test_late_registered_directory_cannot_rescue_bootstrap_crt(native, tmp_path):
    nodes = {'backend.exe': node('backend.exe', [('vcruntime140.dll', 'import')]),
             'late.libs/vcruntime140.dll': node('late.libs/vcruntime140.dll')}
    with pytest.raises(ValueError, match='Unresolved import'):
        native.closure(nodes, ['backend.exe'], ['.'], ['_internal'], tmp_path, registrations=['late.libs'])


@pytest.mark.parametrize('different', [False, True])
def test_process_loaded_dll_identity_cannot_depend_on_plugin_import_order(native, tmp_path, monkeypatch, different):
    nodes = {}
    for package in ['one', 'two']:
        directory = f'backend/_internal/{package}'
        entry, dependency = directory + '/entry.pyd', directory + '/shared.dll'
        nodes[entry] = node(entry, [('shared.dll', 'import')])
        nodes[dependency] = node(dependency, digest='different' if different and package == 'two' else 'same')
    monkeypatch.setattr(native, 'pe_nodes', lambda _: nodes)
    monkeypatch.setattr(native, 'registered_directories', lambda _: [])
    if different:
        with pytest.raises(ValueError, match='Ambiguous process-local backend DLL identity'):
            native.inspect_dependencies({}, tmp_path)
    else:
        result = native.inspect_dependencies({}, tmp_path)
        assert len(result['domains']['backend']['nodes']) == 4
        assert len(result['domains']['backend']['edges']) == 2
        assert not result['unproven_runtime_candidates']


def test_com_bin_and_delay_scanning_closes_handles_and_preserves_non_pe_data(native, tmp_path, monkeypatch):
    payload, parsed, closed = {}, [], []
    for name, raw in [('run.com', b'MZcom'), ('run.bin', b'MZbin'), ('data.bin', b'plain data'), ('plugin.dll', b'MZdll')]:
        path = tmp_path / name
        path.write_bytes(raw)
        payload[name] = path
    def pe(path, fast_load):
        assert fast_load
        return SimpleNamespace(FILE_HEADER=SimpleNamespace(Machine=0x8664, Characteristics=0x0002),
                               OPTIONAL_HEADER=SimpleNamespace(Magic=0x20b, DATA_DIRECTORY=[
                                   SimpleNamespace(VirtualAddress=1234 if index == 14 else 0) for index in range(16)]),
                               parse_data_directories=lambda directories: parsed.append((Path(path).name, directories)),
                               DIRECTORY_ENTRY_IMPORT=[SimpleNamespace(dll=b'pyuno.pyd')],
                               DIRECTORY_ENTRY_DELAY_IMPORT=[SimpleNamespace(dll=b'ole32.dll')],
                               close=lambda: closed.append(Path(path).name))
    monkeypatch.setattr(native.pefile, 'PE', pe)
    nodes = native.pe_nodes(payload)
    assert set(nodes) == {'run.com', 'run.bin', 'plugin.dll'}
    assert all(directories == [1, 13] for _, directories in parsed)
    assert closed == [name for name, _ in parsed]
    assert all(n['edges'] == [('pyuno.pyd', 'import'), ('ole32.dll', 'delay')] for n in nodes.values())
    assert all(n['characteristics'] == 0x0002 and n['clr_rva'] == 1234 for n in nodes.values())
    assert payload['data.bin'].read_bytes() == b'plain data'


@pytest.mark.parametrize('damage', ['unknown', 'changed', 'missing_exe'])
def test_frozen_registration_requires_pinned_complete_initializer(native, tmp_path, monkeypatch, damage):
    from PyInstaller.archive import readers
    code = compile('import os\nos.add_dll_directory("sample.libs")', 'build-machine-path', 'exec')
    fingerprint = native.code_fingerprint(code)
    monkeypatch.setattr(native, 'DLL_REGISTRATIONS', {'sample': dict(version='fixture', code_sha256=fingerprint)})
    pyz = SimpleNamespace(extract=lambda name: code)
    archive = SimpleNamespace(toc={'PYZ.pyz': (0, 0, 0, 0, 'z')}, open_embedded_archive=lambda name: pyz)
    monkeypatch.setattr(readers, 'CArchiveReader', lambda path: archive)
    payload = {'backend/study_backend.exe': tmp_path / 'fixture.exe',
               'backend/_internal/sample.libs/one.dll': tmp_path / 'one.dll'}
    assert native.registered_directories(payload) == ['backend/_internal/sample.libs']
    if damage == 'unknown':
        payload['backend/_internal/unproven.libs/other.dll'] = tmp_path / 'other.dll'
    elif damage == 'changed':
        pyz.extract = lambda name: compile('pass', 'same-name', 'exec')
    else:
        del payload['backend/study_backend.exe']
    with pytest.raises(ValueError, match='registration'):
        native.registered_directories(payload)


def test_code_fingerprint_ignores_build_paths_but_not_nested_behavior(native):
    source = 'def f():\n return {"one", "two"}\n'
    one = compile(source, 'machine-one', 'exec')
    two = compile('\n\n' + source, 'machine-two', 'exec')
    assert native.code_fingerprint(one) == native.code_fingerprint(two)
    assert native.code_fingerprint(one) != native.code_fingerprint(compile(source.replace('two', 'three'), 'machine-one', 'exec'))


@pytest.mark.parametrize('damage', ['changed', 'extra', 'missing', 'traversal', 'version', 'build_inventory'])
def test_component_cli_verifies_actual_inventory_without_writing(native, tmp_path, damage):
    from check_native_dependencies import component_payload
    data = b'self-authored component fixture'
    source = tmp_path / 'NOTICE'
    source.write_bytes(data)
    lock = tmp_path / 'runtime-lock.json'
    metadata = dict(version='26.8.1', java=dict(version='21.0.13+9'),
                    files={'NOTICE': hashlib.sha256(data).hexdigest()})
    lock.write_text(json.dumps(metadata), encoding='utf-8')
    files, _ = component_payload(tmp_path)
    assert set(files) == {'NOTICE', 'runtime-lock.json'}
    if damage == 'changed':
        source.write_bytes(b'changed')
    elif damage == 'extra':
        (tmp_path / 'unlisted').write_bytes(b'extra')
    elif damage == 'missing':
        source.unlink()
    elif damage == 'traversal':
        metadata['files'] = {'../outside': hashlib.sha256(data).hexdigest()}
        lock.write_text(json.dumps(metadata), encoding='utf-8')
    elif damage == 'version':
        metadata['version'] = 'future'
        lock.write_text(json.dumps(metadata), encoding='utf-8')
    else:
        (tmp_path / 'build-inventory.json').write_bytes(b'must not be silently excluded')
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    with pytest.raises(ValueError):
        component_payload(tmp_path)
    assert {p.name: p.read_bytes() for p in tmp_path.iterdir()} == before


@pytest.mark.parametrize('import_name', [b'../outside.dll', b'C:\\private.dll', b'bad\x00.dll'])
def test_import_names_cannot_select_paths_outside_loading_roots(native, tmp_path, monkeypatch, import_name):
    path = tmp_path / 'main.exe'
    path.write_bytes(b'self-authored PE fixture')
    closed = []
    pe = SimpleNamespace(FILE_HEADER=SimpleNamespace(Machine=0x8664), OPTIONAL_HEADER=SimpleNamespace(Magic=0x20b),
                         parse_data_directories=lambda **_: None,
                         DIRECTORY_ENTRY_IMPORT=[SimpleNamespace(dll=import_name)], close=lambda: closed.append(True))
    monkeypatch.setattr(native.pefile, 'PE', lambda *_args, **_kwargs: pe)
    with pytest.raises(ValueError, match='Invalid PE import name'):
        native.pe_nodes({'main.exe': path})
    assert closed == [True]


@pytest.fixture
def uno_registry(native, tmp_path, monkeypatch):
    office = 'converters/libreoffice/'
    raw = ('<components xmlns="http://openoffice.org/2010/uno-components">'
           '<component loader="com.sun.star.loader.SharedLibrary" '
           'uri="vnd.sun.star.expand:$URE_INTERNAL_LIB_DIR/Plugin.dll"/>'
           '<component loader="com.sun.star.loader.Java2" uri="vnd.sun.star.expand:$LO_JAVA_DIR/script.jar"/>'
           '<component loader="com.sun.star.loader.Python" uri="script.py"/>'
           '</components>').encode()
    files = {'program/uno.ini': b'self-authored fixed startup',
             'program/fundamental.ini': b'self-authored fixed bootstrap',
             'program/services.rdb': raw,
             'program/services/extra.rdb': raw.replace(b'URE_INTERNAL_LIB_DIR', b'LO_LIB_DIR')}
    policy, payload = {}, {}
    for name, data in files.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        payload[office + name] = path
        policy[name] = hashlib.sha256(data).hexdigest()
    monkeypatch.setattr(native, 'OFFICE_UNO_FILES', policy)
    return office, payload, policy


def test_uno_registration_records_all_sources_but_not_script_loaders(native, uno_registry):
    office, payload, _ = uno_registry
    before = {name: path.read_bytes() for name, path in payload.items()}
    assert native.office_uno_entries(payload, office) == {
        office + 'program/plugin.dll': [office + 'program/services.rdb', office + 'program/services/extra.rdb']}
    assert {name: path.read_bytes() for name, path in payload.items()} == before


@pytest.mark.parametrize('damage', ['startup', 'bootstrap', 'registry', 'missing', 'extra', 'budget'])
def test_uno_registration_rejects_changed_input_even_with_same_component_version(native, uno_registry, damage):
    office, payload, _ = uno_registry
    selected = office + {'startup': 'program/uno.ini', 'bootstrap': 'program/fundamental.ini'}.get(
        damage, 'program/services.rdb')
    if damage == 'missing':
        del payload[selected]
    elif damage == 'extra':
        payload[office + 'program/services/unproven.rdb'] = payload[selected]
    else:
        payload[selected].write_bytes(b'changed' if damage != 'budget' else b'X' * (1024 * 1024 + 1))
    before = {name: path.read_bytes() for name, path in payload.items()}
    with pytest.raises(ValueError, match='Office UNO'):
        native.office_uno_entries(payload, office)
    assert {name: path.read_bytes() for name, path in payload.items()} == before


@pytest.mark.parametrize('uri', ['file:///C:/outside.dll', 'vnd.sun.star.expand:$ORIGIN/plugin.dll',
                               'vnd.sun.star.expand:$LO_LIB_DIR/../outside.dll',
                               'vnd.sun.star.expand:$LO_LIB_DIR/sub/plugin.dll',
                               'vnd.sun.star.expand:$LO_LIB_DIR/plugin%2edll',
                               'vnd.sun.star.expand:$LO_LIB_DIR/plugin.exe'])
def test_pinned_registry_still_requires_supported_native_uri(native, uno_registry, uri):
    office, payload, policy = uno_registry
    path = payload[office + 'program/services.rdb']
    data = path.read_bytes().replace(b'vnd.sun.star.expand:$URE_INTERNAL_LIB_DIR/Plugin.dll', uri.encode())
    path.write_bytes(data)
    policy['program/services.rdb'] = hashlib.sha256(data).hexdigest()
    with pytest.raises(ValueError, match='library URI'):
        native.office_uno_entries(payload, office)


def test_untrusted_xml_is_rejected_before_parsing(native, uno_registry, monkeypatch):
    office, payload, _ = uno_registry
    payload[office + 'program/services.rdb'].write_bytes(b'<!DOCTYPE x [<!ENTITY a "untrusted">]><x>&a;</x>')
    def must_not_parse(_):
        raise AssertionError('Unverified XML reached parser')
    monkeypatch.setattr(native.ET, 'fromstring', must_not_parse)
    with pytest.raises(ValueError, match='configuration changed'):
        native.office_uno_entries(payload, office)


@pytest.mark.parametrize('damage', ['none', 'missing-entry', 'missing-transitive', 'architecture'])
def test_registered_office_entries_share_the_existing_loading_domain_and_unknown_gate(
        native, uno_registry, tmp_path, monkeypatch, damage):
    # This earlier fixture exercises UNO only; the complete fixed Python policy has its own fixture below.
    monkeypatch.setattr(native, 'office_python_libraries', lambda *_: dict(extensions={}))
    monkeypatch.setattr(native, 'office_program_entries', lambda *_: dict(roots={}))
    office, payload, policy = uno_registry
    program = office + 'program/'
    roots = ['soffice.com', 'soffice.bin', 'officebean.dll', 'javavmlo.dll', 'jvmfwklo.dll',
             'jvmaccesslo.dll', 'javaloaderlo.dll', 'juh.dll', 'juhx.dll', 'java_uno.dll']
    nodes = {program + name: node(program + name) for name in roots}
    nodes[program + 'plugin.dll'] = node(program + 'plugin.dll', [('private.dll', 'delay')])
    nodes[program + 'private.dll'] = node(program + 'private.dll')
    unknown = program + 'twain32shim.exe'
    nodes[unknown] = node(unknown, machine=0x14c)
    lock = tmp_path / 'runtime-lock.json'
    lock.write_text(json.dumps(dict(version='26.8.1',
        package_sha256='c6298b10cfa1748bcbedad94c62ce771e240e5021bfd6d7a967cd571b04b5312',
        java=dict(version='21.0.13+9', directory='java',
                  package_sha256='2332c0b4cff6bed722da3567c91d5e47568bcba863fa4945d0a8d6fc76158628'))), encoding='utf-8')
    payload[office + 'runtime-lock.json'] = lock
    monkeypatch.setattr(native, 'pe_nodes', lambda _: nodes)
    if damage == 'missing-entry':
        del nodes[program + 'plugin.dll']
    elif damage == 'missing-transitive':
        del nodes[program + 'private.dll']
        nodes[office + 'foreign/private.dll'] = node(office + 'foreign/private.dll')
    elif damage == 'architecture':
        nodes[program + 'plugin.dll']['machine'] = 0x14c
    if damage != 'none':
        with pytest.raises(ValueError, match='Missing declared PE|Unresolved delay|Expected x64'):
            native.inspect_dependencies(payload, tmp_path)
        return
    report = native.inspect_dependencies(payload, tmp_path)
    domain = report['domains']['office']
    assert program + 'plugin.dll' in domain['roots'] and program + 'private.dll' in domain['nodes']
    assert domain['uno_entries'] == native.office_uno_entries(payload, office)
    assert domain['uno_configuration_sha256'] == {office + name: digest for name, digest in policy.items()}
    assert domain['directories'] == [office + 'program', office + 'java/bin', office + 'java/bin/server']
    assert report['unproven_runtime_candidates'] == [dict(path=unknown, machine='0x14c')]
    assert report['pe_coverage'] == 'partial'


@pytest.fixture
def java_registry(native, uno_registry, tmp_path, monkeypatch):
    office, payload, _ = uno_registry
    files = {'release': b'Self-authored Java release fixture\n',
             'bin/java.dll': b'Self-authored Java core fixture',
             'bin/optional.dll': b'Self-authored optional JNI fixture',
             'bin/vcruntime140.dll': b'Self-authored Java CRT fixture',
             'bin/server/jvm.dll': b'Self-authored VM fixture',
             'bin/java.exe': b'Self-authored Java launcher fixture',
             'bin/other.exe': b'Self-authored auxiliary launcher fixture'}
    nodes = {}
    for name, data in files.items():
        path = tmp_path / 'java' / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        payload[office + 'java/' + name] = path
        if name != 'release':
            nodes[office + 'java/' + name] = node(office + 'java/' + name, digest=hashlib.sha256(data).hexdigest())
    nodes[office + 'java/bin/optional.dll']['edges'] = [('vcruntime140.dll', 'delay')]
    inventory = dict(version='21.0.13+9', package_sha256='fixture',
                     files={name: hashlib.sha256(data).hexdigest() for name, data in files.items()})
    raw = json.dumps(inventory).encode()
    lock = tmp_path / 'java/java-runtime-lock.json'
    lock.write_bytes(raw)
    payload[office + 'java/java-runtime-lock.json'] = lock
    monkeypatch.setattr(native, 'OFFICE_JAVA_LOCK_SHA256', hashlib.sha256(raw).hexdigest())
    return office, payload, nodes, lock, inventory


def test_fixed_java_images_keep_launchers_out_of_the_office_dll_domain(
        native, java_registry, tmp_path, monkeypatch):
    monkeypatch.setattr(native, 'office_python_libraries', lambda *_: dict(extensions={}))
    monkeypatch.setattr(native, 'office_program_entries', lambda *_: dict(roots={}))
    office, payload, nodes, _, _ = java_registry
    program = office + 'program/'
    for name in ['soffice.com', 'soffice.bin', 'officebean.dll', 'javavmlo.dll', 'jvmfwklo.dll',
                 'jvmaccesslo.dll', 'javaloaderlo.dll', 'juh.dll', 'juhx.dll', 'java_uno.dll',
                 'plugin.dll', 'vcruntime140.dll']:
        nodes[program + name] = node(program + name)
    nodes[program + 'twain32shim.exe'] = node(program + 'twain32shim.exe', machine=0x14c)
    lock = tmp_path / 'runtime-lock.json'
    lock.write_text(json.dumps(dict(version='26.8.1',
        package_sha256='c6298b10cfa1748bcbedad94c62ce771e240e5021bfd6d7a967cd571b04b5312',
        java=dict(version='21.0.13+9', directory='java',
                  package_sha256='2332c0b4cff6bed722da3567c91d5e47568bcba863fa4945d0a8d6fc76158628'))), encoding='utf-8')
    payload[office + 'runtime-lock.json'] = lock
    monkeypatch.setattr(native, 'pe_nodes', lambda _: nodes)
    before = {name: path.read_bytes() for name, path in payload.items()}
    report = native.inspect_dependencies(payload, tmp_path)
    assert len(report['pinned_java_libraries']['dlls']) == 4
    optional = office + 'java/bin/optional.dll'
    for name, crt in [('java', office + 'java/bin'), ('office', office + 'program')]:
        domain = report['domains'][name]
        assert optional in domain['roots'] and domain['crt_directories'] == [crt]
        edge = next(row for row in domain['edges'] if row['source'] == optional)
        assert edge == dict(source=optional, name='vcruntime140.dll', kind='delay',
                            resolution='private-crt', target=crt + '/vcruntime140.dll')
    assert report['domains']['java']['directories'] == [office + 'java/bin', office + 'java/bin/server']
    assert report['domains']['office']['directories'] == [office + 'program', office + 'java/bin', office + 'java/bin/server']
    launchers = {office + 'java/bin/java.exe', office + 'java/bin/other.exe'}
    assert set(report['pinned_java_libraries']['executables']) == launchers
    assert launchers <= set(report['domains']['java']['roots'])
    assert launchers.isdisjoint(report['domains']['office']['roots'])
    assert {row['path'] for row in report['unproven_runtime_candidates']} == {program + 'twain32shim.exe'}
    assert report['pe_coverage'] == 'partial'
    assert {name: path.read_bytes() for name, path in payload.items()} == before
    del nodes[program + 'vcruntime140.dll']
    with pytest.raises(ValueError, match='Unresolved delay.*system CRT'):
        native.inspect_dependencies(payload, tmp_path)


@pytest.mark.parametrize('damage', ['missing-lock', 'changed-lock', 'big-lock', 'missing-dll', 'extra-dll',
                                   'moved-dll', 'changed-dll', 'architecture', 'header', 'release', 'missing-release'])
def test_fixed_java_library_policy_rejects_missing_changed_or_relocated_inputs(
        native, java_registry, damage):
    office, payload, nodes, lock, _ = java_registry
    selected = office + 'java/bin/optional.dll'
    if damage == 'missing-lock':
        del payload[office + 'java/java-runtime-lock.json']
    elif damage in {'changed-lock', 'big-lock'}:
        lock.write_bytes(b'changed' if damage == 'changed-lock' else b'x' * (1024 * 1024 + 1))
    elif damage == 'missing-dll':
        del nodes[selected]
    elif damage == 'extra-dll':
        nodes[office + 'java/bin/unproven.dll'] = node(office + 'java/bin/unproven.dll')
    elif damage == 'moved-dll':
        nodes[office + 'program/optional.dll'] = nodes.pop(selected)
    elif damage == 'changed-dll':
        nodes[selected]['sha256'] = 'changed'
    elif damage == 'architecture':
        nodes[selected]['machine'] = 0x14c
    elif damage == 'header':
        nodes[selected]['magic'] = 0x10B
    elif damage == 'release':
        payload[office + 'java/release'].write_bytes(b'changed')
    else:
        del payload[office + 'java/release']
    before = {name: path.read_bytes() for name, path in payload.items()}
    with pytest.raises(ValueError, match='Java'):
        native.office_java_libraries(payload, nodes, office)
    assert {name: path.read_bytes() for name, path in payload.items()} == before


def test_fixed_java_dll_roots_do_not_add_new_search_directories(native, java_registry, monkeypatch):
    office, payload, nodes, lock, inventory = java_registry
    original = 'bin/optional.dll'
    moved = 'bin/foreign/optional.dll'
    inventory['files'][moved] = inventory['files'].pop(original)
    nodes[office + 'java/' + moved] = nodes.pop(office + 'java/' + original)
    raw = json.dumps(inventory).encode()
    lock.write_bytes(raw)
    monkeypatch.setattr(native, 'OFFICE_JAVA_LOCK_SHA256', hashlib.sha256(raw).hexdigest())
    with pytest.raises(ValueError, match='Java DLL path'):
        native.office_java_libraries(payload, nodes, office)


@pytest.mark.parametrize('damage', ['missing', 'extra', 'moved', 'changed', 'architecture', 'header'])
def test_fixed_java_launcher_policy_rejects_unproven_images(native, java_registry, damage):
    office, payload, nodes, _, _ = java_registry
    name = office + 'java/bin/other.exe'
    if damage == 'missing':
        del nodes[name]
    elif damage == 'extra':
        nodes[office + 'java/bin/unproven.exe'] = node(office + 'java/bin/unproven.exe')
    elif damage == 'moved':
        nodes[office + 'java/bin/server/other.exe'] = nodes.pop(name)
    elif damage == 'changed':
        nodes[name]['sha256'] = 'changed'
    elif damage == 'architecture':
        nodes[name]['machine'] = 0x14c
    else:
        nodes[name]['magic'] = 0x10B
    before = {name: path.read_bytes() for name, path in payload.items()}
    with pytest.raises(ValueError, match='Java EXE'):
        native.office_java_libraries(payload, nodes, office)
    assert {name: path.read_bytes() for name, path in payload.items()} == before


def test_fixed_java_launcher_never_adds_a_search_directory(native, java_registry, monkeypatch):
    office, payload, nodes, lock, inventory = java_registry
    moved = 'bin/server/other.exe'
    inventory['files'][moved] = inventory['files'].pop('bin/other.exe')
    nodes[office + 'java/' + moved] = nodes.pop(office + 'java/bin/other.exe')
    raw = json.dumps(inventory).encode()
    lock.write_bytes(raw)
    monkeypatch.setattr(native, 'OFFICE_JAVA_LOCK_SHA256', hashlib.sha256(raw).hexdigest())
    with pytest.raises(ValueError, match='Java EXE path'):
        native.office_java_libraries(payload, nodes, office)


def test_fixed_java_policy_requires_its_primary_launcher(native, java_registry, monkeypatch):
    office, payload, nodes, lock, inventory = java_registry
    del inventory['files']['bin/java.exe']
    del nodes[office + 'java/bin/java.exe']
    raw = json.dumps(inventory).encode()
    lock.write_bytes(raw)
    monkeypatch.setattr(native, 'OFFICE_JAVA_LOCK_SHA256', hashlib.sha256(raw).hexdigest())
    with pytest.raises(ValueError, match='primary Java launcher'):
        native.office_java_libraries(payload, nodes, office)


@pytest.fixture
def python_registry(native, uno_registry, tmp_path, monkeypatch):
    office, payload, _ = uno_registry
    directory = 'program/python-core-3.13.15/lib/'
    names = [directory + name + '.pyd' for name in native.OFFICE_PYTHON_PYDS]
    names += [directory + name for name in native.OFFICE_PYTHON_DLLS]
    names += ['program/python313.dll', 'program/vcruntime140.dll', 'program/pythonloader.uno.ini']
    nodes, files = {}, {}
    for name in names:
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        data = ('self-authored inactive Python fixture: ' + name).encode()
        path.write_bytes(data)
        payload[office + name] = path
        files[name] = hashlib.sha256(data).hexdigest()
        if not name.endswith('.ini'):
            nodes[office + name] = node(office + name, digest=files[name])
    for name in native.OFFICE_PYTHON_PYDS:
        nodes[office + directory + name + '.pyd']['edges'] = [('python313.dll', 'import'),
                                                            ('vcruntime140.dll', 'delay')]
    for name, dependency in [('_ctypes', 'libffi-8.dll'), ('_hashlib', 'libcrypto-3.dll'),
                             ('_ssl', 'libssl-3.dll'), ('_sqlite3', 'sqlite3.dll')]:
        nodes[office + directory + name + '.pyd']['edges'].append((dependency, 'import'))
    raw = json.dumps(dict(version='26.8.1', files=files,
        package_sha256='c6298b10cfa1748bcbedad94c62ce771e240e5021bfd6d7a967cd571b04b5312',
        java=dict(version='21.0.13+9', directory='java',
                  package_sha256='2332c0b4cff6bed722da3567c91d5e47568bcba863fa4945d0a8d6fc76158628'))).encode()
    lock = tmp_path / 'runtime-lock.json'
    lock.write_bytes(raw)
    payload[office + 'runtime-lock.json'] = lock
    monkeypatch.setattr(native, 'OFFICE_PYTHON_LOCK_SHA256', hashlib.sha256(raw).hexdigest())
    return office, payload, nodes, lock


@pytest.mark.parametrize('damage', ['missing-lock', 'changed-lock', 'big-lock', 'missing-pyd', 'extra-pyd',
                                   'extra-exe', 'nested-dll', 'moved-dll', 'changed-pyd', 'architecture',
                                   'header', 'python313', 'crt', 'missing-ini', 'changed-ini', 'big-ini'])
def test_fixed_python_policy_rejects_unproven_inputs(native, python_registry, damage):
    office, payload, nodes, lock = python_registry
    prefix = office + 'program/python-core-3.13.15/lib/'
    if damage == 'missing-lock':
        del payload[office + 'runtime-lock.json']
    elif damage in {'changed-lock', 'big-lock'}:
        lock.write_bytes(b'changed' if damage == 'changed-lock' else b'x' * (4 * 1024 * 1024 + 1))
    elif damage == 'missing-pyd':
        del nodes[prefix + '_ssl.pyd']
    elif damage in {'extra-pyd', 'extra-exe', 'nested-dll'}:
        name = prefix + {'extra-pyd': 'unproven.pyd', 'extra-exe': 'unproven.exe',
                         'nested-dll': 'foreign/extra.dll'}[damage]
        nodes[name] = node(name)
    elif damage == 'moved-dll':
        nodes[office + 'java/bin/libffi-8.dll'] = nodes.pop(prefix + 'libffi-8.dll')
    elif damage == 'changed-pyd':
        nodes[prefix + '_ssl.pyd']['sha256'] = 'changed'
    elif damage == 'architecture':
        nodes[prefix + '_ssl.pyd']['machine'] = 0x14c
    elif damage == 'header':
        nodes[prefix + '_ssl.pyd']['magic'] = 0x10B
    elif damage in {'python313', 'crt'}:
        name = office + 'program/' + ('python313.dll' if damage == 'python313' else 'vcruntime140.dll')
        nodes[name]['sha256'] = 'changed'
    elif damage == 'missing-ini':
        del payload[office + 'program/pythonloader.uno.ini']
    else:
        payload[office + 'program/pythonloader.uno.ini'].write_bytes(
            b'changed' if damage == 'changed-ini' else b'x' * 65537)
    before = {name: path.read_bytes() for name, path in payload.items()}
    with pytest.raises(ValueError, match='Office Python'):
        native.office_python_libraries(payload, nodes, office)
    assert {name: path.read_bytes() for name, path in payload.items()} == before


def test_python_domain_preserves_other_domains_and_unknown_images(native, python_registry, tmp_path, monkeypatch):
    monkeypatch.setattr(native, 'office_program_entries', lambda *_: dict(roots={}))
    office, payload, nodes, _ = python_registry
    program = office + 'program/'
    for name in ['soffice.com', 'soffice.bin', 'officebean.dll', 'javavmlo.dll', 'jvmfwklo.dll',
                 'jvmaccesslo.dll', 'javaloaderlo.dll', 'juh.dll', 'juhx.dll', 'java_uno.dll', 'plugin.dll']:
        nodes[program + name] = node(program + name)
    unknown = ['python3.dll', 'python.exe', 'python-core-3.13.15/bin/python.exe',
               'templates/template.exe', 'managed.dll', 'twain32shim.exe']
    for name in unknown:
        nodes[program + name] = node(program + name, machine=0x14c if name == 'twain32shim.exe' else 0x8664)
    monkeypatch.setattr(native, 'pe_nodes', lambda _: nodes)
    before = {name: path.read_bytes() for name, path in payload.items()}
    report = native.inspect_dependencies(payload, tmp_path)
    domain = report['domains']['office_python']
    assert len(domain['roots']) == 19 and len(domain['nodes']) == 25
    assert domain['directories'] == [program + 'python-core-3.13.15/lib', program.rstrip('/')]
    assert domain['crt_directories'] == [program.rstrip('/')]
    assert {row['path'] for row in report['unproven_runtime_candidates']} == {program + name for name in unknown}
    assert report['pe_coverage'] == 'partial'
    assert set(domain['pinned_inputs']['libraries']) == {
        program + 'python-core-3.13.15/lib/' + name for name in native.OFFICE_PYTHON_DLLS}
    assert {edge['target'] for edge in domain['edges'] if edge['name'] == 'vcruntime140.dll'} == {
        program + 'vcruntime140.dll'}
    assert {name: path.read_bytes() for name, path in payload.items()} == before


def test_authenticated_nested_template_is_never_a_python_root(native, python_registry, monkeypatch):
    office, payload, nodes, lock = python_registry
    name = 'program/python-core-3.13.15/lib/site-packages/fixture/raw.exe'
    manifest = json.loads(lock.read_bytes())
    manifest['files'][name] = 'self-authored-template-identity'
    nodes[office + name] = node(office + name, digest=manifest['files'][name], machine=0x14c)
    raw = json.dumps(manifest).encode()
    lock.write_bytes(raw)
    monkeypatch.setattr(native, 'OFFICE_PYTHON_LOCK_SHA256', hashlib.sha256(raw).hexdigest())
    policy = native.office_python_libraries(payload, nodes, office)
    assert policy['unclassified_images'] == {office + name: 'self-authored-template-identity'}
    assert office + name not in policy['extensions'] and office + name not in policy['libraries']
    nodes[office + name]['sha256'] = 'tampered'
    with pytest.raises(ValueError, match='nested PE bytes changed'):
        native.office_python_libraries(payload, nodes, office)


@pytest.mark.parametrize('kind', ['import', 'delay'])
@pytest.mark.parametrize('foreign', ['java/bin', 'program/python-core-3.13.15/lib'])
def test_python_domain_never_borrows_foreign_crt(native, python_registry, tmp_path, kind, foreign):
    office, payload, nodes, _ = python_registry
    native.office_python_libraries(payload, nodes, office)
    program = office + 'program'
    library = program + '/python-core-3.13.15/lib'
    nodes[library + '/_ssl.pyd']['edges'] = [('vcruntime140.dll', kind)]
    nodes[office + foreign + '/vcruntime140.dll'] = nodes.pop(program + '/vcruntime140.dll')
    (tmp_path / 'vcruntime140.dll').write_bytes(b'host CRT cannot rescue Python')
    with pytest.raises(ValueError, match=f'Unresolved {kind}.*system CRT'):
        native.closure(nodes, [library + '/_ssl.pyd'], [library, program], [program], tmp_path)


@pytest.fixture
def program_registry(native, python_registry, tmp_path, monkeypatch):
    office, payload, nodes, lock = python_registry
    manifest = json.loads(lock.read_bytes())
    for name in [*native.OFFICE_PROGRAM_ENTRIES, 'twain32shim.exe']:
        relative = 'program/' + name
        data = ('self-authored inactive program main-image fixture: ' + relative).encode()
        path = tmp_path / relative
        path.write_bytes(data)
        payload[office + relative] = path
        manifest['files'][relative] = hashlib.sha256(data).hexdigest()
        nodes[office + relative] = node(office + relative, digest=manifest['files'][relative])
    nodes[office + 'program/twain32shim.exe'].update(machine=0x14c, magic=0x10B)
    for name in ['officebean.dll', 'javavmlo.dll', 'jvmfwklo.dll', 'jvmaccesslo.dll', 'javaloaderlo.dll',
                 'juh.dll', 'juhx.dll', 'java_uno.dll', 'plugin.dll', 'unopkgapp.dll']:
        nodes[office + 'program/' + name] = node(office + 'program/' + name)
    nodes[office + 'program/unopkg.bin']['edges'] = [('unopkgapp.dll', 'import'), ('vcruntime140.dll', 'delay')]
    raw = json.dumps(manifest).encode()
    lock.write_bytes(raw)
    for constant in ('OFFICE_PYTHON_LOCK_SHA256', 'OFFICE_PROGRAM_LOCK_SHA256'):
        monkeypatch.setattr(native, constant, hashlib.sha256(raw).hexdigest())
    return office, payload, nodes, lock


@pytest.mark.parametrize('damage', ['missing-lock', 'changed-lock', 'big-lock', 'missing-exe', 'missing-com',
    'missing-bin', 'extra-exe', 'moved-exe', 'changed-exe', 'architecture', 'header', 'dll-flag',
    'not-executable', 'managed-clr', 'unknown-flags', 'unknown-clr', 'missing-excluded',
    'changed-excluded', 'excluded-architecture'])
def test_program_policy_rejects_unproven_main_images(native, program_registry, damage):
    office, payload, nodes, lock = program_registry
    program = office + 'program/'
    if damage == 'missing-lock':
        del payload[office + 'runtime-lock.json']
    elif damage in {'changed-lock', 'big-lock'}:
        lock.write_bytes(b'changed' if damage == 'changed-lock' else b'x' * (4 * 1024 * 1024 + 1))
    elif damage.startswith('missing-'):
        suffix = {'missing-exe': 'soffice.exe', 'missing-com': 'unopkg.com', 'missing-bin': 'unopkg.bin',
                  'missing-excluded': 'twain32shim.exe'}[damage]
        del nodes[program + suffix]
    elif damage == 'extra-exe':
        nodes[program + 'unproven.exe'] = node(program + 'unproven.exe')
    elif damage == 'moved-exe':
        nodes[office + 'java/bin/soffice.exe'] = nodes.pop(program + 'soffice.exe')
    else:
        image = nodes[program + ('twain32shim.exe' if 'excluded' in damage else 'soffice.exe')]
        field, value = {'changed-exe': ('sha256', 'changed'), 'architecture': ('machine', 0x14c),
            'header': ('magic', 0x10B), 'dll-flag': ('characteristics', 0x2002),
            'not-executable': ('characteristics', 0), 'managed-clr': ('clr_rva', 4096),
            'unknown-flags': ('characteristics', None), 'unknown-clr': ('clr_rva', None),
            'changed-excluded': ('sha256', 'changed'), 'excluded-architecture': ('machine', 0x8664)}[damage]
        image[field] = value
    before = {name: path.read_bytes() for name, path in payload.items()}
    with pytest.raises(ValueError, match='Office program'):
        native.office_program_entries(payload, nodes, office)
    assert {name: path.read_bytes() for name, path in payload.items()} == before


def test_program_domain_retains_child_template_managed_and_x86_unknowns(native, program_registry, tmp_path, monkeypatch):
    office, payload, nodes, _ = program_registry
    program = office + 'program/'
    unknown = ['python-core-3.13.15/bin/python.exe', 'templates/raw.exe', 'managed.dll']
    for name in unknown:
        nodes[program + name] = node(program + name)
    nodes[program + 'managed.dll']['clr_rva'] = 4096
    monkeypatch.setattr(native, 'pe_nodes', lambda _: nodes)
    before = {name: path.read_bytes() for name, path in payload.items()}
    report = native.inspect_dependencies(payload, tmp_path)
    domain = report['domains']['office_program']
    assert len(domain['roots']) == 30 and program + 'unopkgapp.dll' in domain['nodes']
    assert domain['directories'] == domain['crt_directories'] == [program.rstrip('/')]
    assert program + 'python.exe' in domain['roots']
    assert program + 'soffice.com' in domain['roots'] and program + 'unopkg.bin' in domain['roots']
    assert domain['pinned_inputs']['excluded_images'].keys() == {program + 'twain32shim.exe'}
    assert {row['path'] for row in report['unproven_runtime_candidates']} == {
        program + name for name in [*unknown, 'twain32shim.exe']}
    assert report['pe_coverage'] == 'partial'
    assert {name: path.read_bytes() for name, path in payload.items()} == before


@pytest.mark.parametrize('kind', ['import', 'delay'])
@pytest.mark.parametrize('foreign', ['java/bin', 'program/python-core-3.13.15/lib'])
def test_program_domain_cannot_borrow_foreign_dependency(native, program_registry, tmp_path, monkeypatch, kind, foreign):
    office, payload, nodes, _ = program_registry
    program = office + 'program/'
    monkeypatch.setattr(native, 'pe_nodes', lambda _: nodes)
    domain = native.inspect_dependencies(payload, tmp_path)['domains']['office_program']
    nodes[program + 'unopkg.bin']['edges'] = [('unopkgapp.dll', kind)]
    nodes[office + foreign + '/unopkgapp.dll'] = nodes.pop(program + 'unopkgapp.dll')
    with pytest.raises(ValueError, match=f'Unresolved {kind}.*unopkgapp.dll'):
        native.closure(nodes, domain['roots'], domain['directories'], domain['crt_directories'], tmp_path)


@pytest.mark.parametrize('kind', ['import', 'delay'])
@pytest.mark.parametrize('foreign', ['java/bin', 'program/python-core-3.13.15/lib'])
def test_program_private_crt_stays_in_program(native, program_registry, tmp_path, kind, foreign):
    office, payload, nodes, _ = program_registry
    policy = native.office_program_entries(payload, nodes, office)
    program = office + 'program'
    nodes[program + '/unopkg.bin']['edges'] = [('vcruntime140.dll', kind)]
    nodes[office + foreign + '/vcruntime140.dll'] = nodes.pop(program + '/vcruntime140.dll')
    (tmp_path / 'vcruntime140.dll').write_bytes(b'host CRT cannot rescue an Office launcher')
    with pytest.raises(ValueError, match=f'Unresolved {kind}.*system CRT'):
        native.closure(nodes, list(policy['roots']), [program], [program], tmp_path)
