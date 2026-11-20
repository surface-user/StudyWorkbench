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
    monkeypatch.setattr(native, 'office_environment_entries', lambda *_: dict(roots=[]))
    monkeypatch.setattr(native, 'office_locale_entries', lambda *_: dict(roots=[]))
    monkeypatch.setattr(native, 'office_textencoding_entries', lambda *_: dict(roots=[]))
    # This earlier fixture exercises UNO only; the complete fixed Python policy has its own fixture below.
    monkeypatch.setattr(native, 'office_python_libraries', lambda *_: dict(extensions={}))
    monkeypatch.setattr(native, 'office_program_entries', lambda *_: dict(roots={}))
    monkeypatch.setattr(native, 'office_venv_entries', lambda *_: dict(roots={}))
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
    monkeypatch.setattr(native, 'office_environment_entries', lambda *_: dict(roots=[]))
    monkeypatch.setattr(native, 'office_locale_entries', lambda *_: dict(roots=[]))
    monkeypatch.setattr(native, 'office_textencoding_entries', lambda *_: dict(roots=[]))
    monkeypatch.setattr(native, 'office_python_libraries', lambda *_: dict(extensions={}))
    monkeypatch.setattr(native, 'office_program_entries', lambda *_: dict(roots={}))
    monkeypatch.setattr(native, 'office_venv_entries', lambda *_: dict(roots={}))
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
    monkeypatch.setattr(native, 'office_environment_entries', lambda *_: dict(roots=[]))
    monkeypatch.setattr(native, 'office_locale_entries', lambda *_: dict(roots=[]))
    monkeypatch.setattr(native, 'office_textencoding_entries', lambda *_: dict(roots=[]))
    monkeypatch.setattr(native, 'office_program_entries', lambda *_: dict(roots={}))
    monkeypatch.setattr(native, 'office_venv_entries', lambda *_: dict(roots={}))
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
    monkeypatch.setattr(native, 'office_environment_entries', lambda *_: dict(roots=[]))
    monkeypatch.setattr(native, 'office_locale_entries', lambda *_: dict(roots=[]))
    monkeypatch.setattr(native, 'office_textencoding_entries', lambda *_: dict(roots=[]))
    monkeypatch.setattr(native, 'office_venv_entries', lambda *_: dict(roots={}))
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
    monkeypatch.setattr(native, 'office_environment_entries', lambda *_: dict(roots=[]))
    monkeypatch.setattr(native, 'office_locale_entries', lambda *_: dict(roots=[]))
    monkeypatch.setattr(native, 'office_textencoding_entries', lambda *_: dict(roots=[]))
    monkeypatch.setattr(native, 'office_venv_entries', lambda *_: dict(roots={}))
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


@pytest.fixture
def venv_registry(native, program_registry, tmp_path, monkeypatch):
    office, payload, nodes, lock = program_registry
    manifest = json.loads(lock.read_bytes())
    directory = 'program/python-core-3.13.15/bin/'
    for name in ('python.exe', 'pythonw.exe', 'venvlauncher.exe'):
        relative = directory + name
        data = ('self-authored inactive Python launcher fixture: ' + relative).encode()
        path = tmp_path / relative
        path.parent.mkdir(exist_ok=True, parents=True)
        path.write_bytes(data)
        payload[office + relative] = path
        manifest['files'][relative] = hashlib.sha256(data).hexdigest()
        nodes[office + relative] = node(office + relative, digest=manifest['files'][relative])
    nodes[office + directory + 'venvlauncher.exe']['edges'] = [
        ('kernel32.dll', 'import'), ('api-ms-win-core-path-l1-1-0.dll', 'import')]
    for name in ('python.exe', 'pythonw.exe'):
        nodes[office + directory + name]['edges'] = [('python313.dll', 'import'), ('vcruntime140.dll', 'import')]
    (tmp_path / 'kernel32.dll').write_bytes(b'self-authored host-presence fixture')
    raw = json.dumps(manifest).encode()
    lock.write_bytes(raw)
    for constant in ('OFFICE_PYTHON_LOCK_SHA256', 'OFFICE_PROGRAM_LOCK_SHA256', 'OFFICE_VENV_LOCK_SHA256'):
        monkeypatch.setattr(native, constant, hashlib.sha256(raw).hexdigest())
    return office, payload, nodes, lock


@pytest.mark.parametrize('damage', ['missing-lock', 'changed-lock', 'big-lock', 'missing-venv', 'missing-console',
    'missing-windowed', 'extra-exe', 'extra-dll', 'moved-venv', 'changed-venv', 'architecture', 'header',
    'dll-flag', 'not-executable', 'managed-clr', 'unknown-flags', 'unknown-clr', 'changed-console', 'console-architecture'])
def test_venv_policy_rejects_unproven_bin_images(native, venv_registry, damage):
    office, payload, nodes, lock = venv_registry
    directory = office + 'program/python-core-3.13.15/bin/'
    if damage == 'missing-lock':
        del payload[office + 'runtime-lock.json']
    elif damage in {'changed-lock', 'big-lock'}:
        lock.write_bytes(b'changed' if damage == 'changed-lock' else b'x' * (4 * 1024 * 1024 + 1))
    elif damage.startswith('missing-'):
        del nodes[directory + {'missing-venv': 'venvlauncher.exe', 'missing-console': 'python.exe',
                               'missing-windowed': 'pythonw.exe'}[damage]]
    elif damage in {'extra-exe', 'extra-dll'}:
        name = directory + ('extra.exe' if damage == 'extra-exe' else 'vcruntime140.dll')
        nodes[name] = node(name)
    elif damage == 'moved-venv':
        nodes[office + 'program/venvlauncher.exe'] = nodes.pop(directory + 'venvlauncher.exe')
    else:
        image = nodes[directory + ('python.exe' if 'console' in damage else 'venvlauncher.exe')]
        field, value = {'changed-venv': ('sha256', 'changed'), 'architecture': ('machine', 0x14c),
            'header': ('magic', 0x10B), 'dll-flag': ('characteristics', 0x2002),
            'not-executable': ('characteristics', 0), 'managed-clr': ('clr_rva', 4096),
            'unknown-flags': ('characteristics', None), 'unknown-clr': ('clr_rva', None),
            'changed-console': ('sha256', 'changed'), 'console-architecture': ('machine', 0x14c)}[damage]
        image[field] = value
    before = {name: path.read_bytes() for name, path in payload.items()}
    with pytest.raises(ValueError, match='Office venv'):
        native.office_venv_entries(payload, nodes, office)
    assert {name: path.read_bytes() for name, path in payload.items()} == before


def test_venv_domain_is_only_its_native_main_image_not_python_children(native, venv_registry, tmp_path, monkeypatch):
    monkeypatch.setattr(native, 'office_environment_entries', lambda *_: dict(roots=[]))
    monkeypatch.setattr(native, 'office_locale_entries', lambda *_: dict(roots=[]))
    monkeypatch.setattr(native, 'office_textencoding_entries', lambda *_: dict(roots=[]))
    office, payload, nodes, _ = venv_registry
    directory = office + 'program/python-core-3.13.15/bin/'
    monkeypatch.setattr(native, 'pe_nodes', lambda _: nodes)
    before = {name: path.read_bytes() for name, path in payload.items()}
    report = native.inspect_dependencies(payload, tmp_path)
    domain = report['domains']['office_venv']
    assert domain['roots'] == domain['nodes'] == [directory + 'venvlauncher.exe']
    assert domain['directories'] == domain['crt_directories'] == [directory.rstrip('/')]
    assert len(domain['edges']) == 2
    assert {row['path'] for row in report['unproven_runtime_candidates']} == {
        directory + 'python.exe', directory + 'pythonw.exe', office + 'program/twain32shim.exe'}
    assert set(domain['pinned_inputs']['unclassified_images']) == {directory + 'python.exe', directory + 'pythonw.exe'}
    assert report['pe_coverage'] == 'partial'
    assert {name: path.read_bytes() for name, path in payload.items()} == before


@pytest.mark.parametrize('kind', ['import', 'delay'])
@pytest.mark.parametrize('dependency', ['vcruntime140.dll', 'python313.dll'])
def test_venv_domain_never_borrows_program_crt_or_python(native, venv_registry, tmp_path, monkeypatch, kind, dependency):
    monkeypatch.setattr(native, 'office_environment_entries', lambda *_: dict(roots=[]))
    monkeypatch.setattr(native, 'office_locale_entries', lambda *_: dict(roots=[]))
    monkeypatch.setattr(native, 'office_textencoding_entries', lambda *_: dict(roots=[]))
    office, payload, nodes, _ = venv_registry
    directory = office + 'program/python-core-3.13.15/bin/'
    monkeypatch.setattr(native, 'pe_nodes', lambda _: nodes)
    domain = native.inspect_dependencies(payload, tmp_path)['domains']['office_venv']
    nodes[directory + 'venvlauncher.exe']['edges'] = [(dependency, kind)]
    with pytest.raises(ValueError, match=f'Unresolved {kind}.*{dependency}'):
        native.closure(nodes, domain['roots'], domain['directories'], domain['crt_directories'], tmp_path)


@pytest.fixture
def selfcontained_registry(native, venv_registry, tmp_path, monkeypatch):
    office, payload, nodes, lock = venv_registry
    manifest = json.loads(lock.read_bytes())
    program, directory = office + 'program/', office + 'program/python-core-3.13.15/bin/'
    data = b'distinct self-authored ABI library fixture'
    path = tmp_path / 'program/python3.dll'
    path.write_bytes(data)
    digest = hashlib.sha256(data).hexdigest()
    payload[program + 'python3.dll'] = path
    manifest['files']['program/python3.dll'] = digest
    nodes[program + 'python3.dll'] = node(program + 'python3.dll', digest=digest)
    nodes[program + 'python3.dll']['characteristics'] = 0x2002
    for name in ('python313.dll', 'python3.dll', 'vcruntime140.dll'):
        source_path = payload[program + name]
        target = tmp_path / 'program/python-core-3.13.15/bin' / name
        target.write_bytes(source_path.read_bytes())
        payload[directory + name] = target
        manifest['files']['program/python-core-3.13.15/bin/' + name] = manifest['files']['program/' + name]
        nodes[directory + name] = node(directory + name, digest=manifest['files']['program/' + name])
        nodes[directory + name]['characteristics'] = 0x2002
    manifest['python_launchers'] = dict(layout='bin-local-v1', version='3.13.15',
                                      directory='program/python-core-3.13.15/bin')
    raw = json.dumps(manifest).encode()
    lock.write_bytes(raw)
    monkeypatch.setattr(native, 'OFFICE_SELFCONTAINED_LOCK_SHA256', hashlib.sha256(raw).hexdigest())
    return office, payload, nodes, lock


def test_child_python_and_extensions_use_bin_crt_while_office_host_keeps_program(
        native, selfcontained_registry, tmp_path, monkeypatch):
    monkeypatch.setattr(native, 'office_environment_entries', lambda *_: dict(roots=[]))
    monkeypatch.setattr(native, 'office_locale_entries', lambda *_: dict(roots=[]))
    monkeypatch.setattr(native, 'office_textencoding_entries', lambda *_: dict(roots=[]))
    office, payload, nodes, _ = selfcontained_registry
    program = office + 'program'
    bin_dir, library = program + '/python-core-3.13.15/bin', program + '/python-core-3.13.15/lib'
    monkeypatch.setattr(native, 'pe_nodes', lambda _: nodes)
    result = native.inspect_dependencies(payload, tmp_path)
    entries = result['domains']['office_python_launchers']
    assert entries['roots'] == [bin_dir + '/python.exe', bin_dir + '/pythonw.exe']
    assert entries['directories'] == entries['crt_directories'] == [bin_dir]
    assert set(entries['nodes']) == {bin_dir + '/' + name for name in
                                    ('python.exe', 'pythonw.exe', 'python313.dll', 'vcruntime140.dll')}
    child = result['domains']['office_python_child_extensions']
    host = result['domains']['office_python']
    assert len(child['roots']) == 19 and child['directories'] == [library, bin_dir]
    assert child['crt_directories'] == [bin_dir]
    assert host['directories'] == [library, program] and host['crt_directories'] == [program]
    for domain, expected in [(child, bin_dir), (host, program)]:
        assert {edge['target'] for edge in domain['edges'] if edge['name'] == 'vcruntime140.dll'} == {
            expected + '/vcruntime140.dll'}
    assert {row['path'] for row in result['unproven_runtime_candidates']} == {
        program + '/twain32shim.exe', program + '/python3.dll', bin_dir + '/python3.dll'}
    assert result['pe_coverage'] == 'partial'


@pytest.mark.parametrize('damage', ['unknown-lock', 'missing-python', 'missing-abi', 'missing-crt', 'extra-dll',
    'moved-crt', 'changed-copy', 'x86-copy', 'not-dll-copy', 'clr-copy'])
def test_selfcontained_bin_policy_requires_exact_native_companion_set(native, selfcontained_registry, damage):
    office, payload, nodes, lock = selfcontained_registry
    directory = office + 'program/python-core-3.13.15/bin/'
    if damage == 'unknown-lock':
        lock.write_bytes(lock.read_bytes() + b' ')
    elif damage.startswith('missing-'):
        del nodes[directory + {'missing-python': 'python313.dll', 'missing-abi': 'python3.dll',
                               'missing-crt': 'vcruntime140.dll'}[damage]]
    elif damage == 'extra-dll':
        nodes[directory + 'extra.dll'] = node(directory + 'extra.dll')
    elif damage == 'moved-crt':
        nodes[office + 'elsewhere/vcruntime140.dll'] = nodes.pop(directory + 'vcruntime140.dll')
    else:
        field, value = {'changed-copy': ('sha256', 'changed'), 'x86-copy': ('machine', 0x14c),
                        'not-dll-copy': ('characteristics', 0x0002), 'clr-copy': ('clr_rva', 4096)}[damage]
        nodes[directory + 'vcruntime140.dll'][field] = value
    with pytest.raises(ValueError, match='Office venv'):
        native.office_venv_entries(payload, nodes, office)


@pytest.mark.parametrize('kind', ['import', 'delay'])
def test_child_context_does_not_fall_back_to_host_crt(native, selfcontained_registry, tmp_path, monkeypatch, kind):
    monkeypatch.setattr(native, 'office_environment_entries', lambda *_: dict(roots=[]))
    monkeypatch.setattr(native, 'office_locale_entries', lambda *_: dict(roots=[]))
    monkeypatch.setattr(native, 'office_textencoding_entries', lambda *_: dict(roots=[]))
    office, payload, nodes, _ = selfcontained_registry
    monkeypatch.setattr(native, 'pe_nodes', lambda _: nodes)
    domain = native.inspect_dependencies(payload, tmp_path)['domains']['office_python_launchers']
    directory = office + 'program/python-core-3.13.15/bin/'
    for name in ('python.exe', 'pythonw.exe'):
        nodes[directory + name]['edges'] = [('vcruntime140.dll', kind)]
    del nodes[directory + 'vcruntime140.dll']
    (tmp_path / 'vcruntime140.dll').write_bytes(b'host CRT cannot replace child private CRT')
    with pytest.raises(ValueError, match=f'Unresolved {kind}.*system CRT'):
        native.closure(nodes, domain['roots'], domain['directories'], domain['crt_directories'], tmp_path)


@pytest.fixture(params=['legacy', 'selfcontained'])
def textencoding_registry(native, request, tmp_path, monkeypatch):
    office, payload, nodes, lock = request.getfixturevalue(
        'venv_registry' if request.param == 'legacy' else 'selfcontained_registry')
    manifest = json.loads(lock.read_bytes())
    images = {}
    for name in ('sal3.dll', 'sal_textenclo.dll'):
        raw = ('independent fixed text encoding fixture ' + name).encode()
        path = tmp_path / 'program' / name
        path.write_bytes(raw)
        digest = hashlib.sha256(raw).hexdigest()
        images[name] = digest
        relative = 'program/' + name
        payload[office + relative] = path
        manifest['files'][relative] = digest
        nodes[office + relative] = node(office + relative, digest=digest)
        nodes[office + relative]['characteristics'] = 0x2002
    nodes[office + 'program/soffice.bin']['edges'].append(('sal3.dll', 'import'))
    nodes[office + 'program/sal3.dll']['edges'] = [('vcruntime140.dll', 'import')]
    nodes[office + 'program/sal_textenclo.dll']['edges'] = [('sal3.dll', 'import'), ('vcruntime140.dll', 'delay')]
    raw = json.dumps(manifest).encode()
    lock.write_bytes(raw)
    digest = hashlib.sha256(raw).hexdigest()
    monkeypatch.setattr(native, 'OFFICE_TEXTENC_IMAGES', images)
    monkeypatch.setattr(native, 'OFFICE_TEXTENC_LOCK_SHA256', digest)
    if request.param == 'selfcontained':
        monkeypatch.setattr(native, 'OFFICE_SELFCONTAINED_LOCK_SHA256', digest)
    else:
        for constant in ('OFFICE_PYTHON_LOCK_SHA256', 'OFFICE_PROGRAM_LOCK_SHA256', 'OFFICE_VENV_LOCK_SHA256'):
            monkeypatch.setattr(native, constant, digest)
    monkeypatch.setattr(native, 'pe_nodes', lambda _: nodes)
    return office, payload, nodes, lock


def test_fixed_textencoding_adds_one_potential_root_without_new_search_or_other_domain_changes(
        native, textencoding_registry, tmp_path, monkeypatch):
    monkeypatch.setattr(native, 'office_environment_entries', lambda *_: dict(roots=[]))
    monkeypatch.setattr(native, 'office_locale_entries', lambda *_: dict(roots=[]))
    office, payload, nodes, _ = textencoding_registry
    target = office + 'program/sal_textenclo.dll'
    before_bytes = {name: path.read_bytes() for name, path in payload.items()}
    with monkeypatch.context() as earlier:
        earlier.setattr(native, 'office_textencoding_entries', lambda *_: dict(roots=[]))
        before = native.inspect_dependencies(payload, tmp_path)
    after = native.inspect_dependencies(payload, tmp_path)
    old_domain, domain = before['domains']['office'], after['domains']['office']
    assert set(domain['roots']) == set(old_domain['roots']) | {target}
    assert set(domain['nodes']) == set(old_domain['nodes']) | {target}
    for key in ('directories', 'crt_directories', 'registered_directories', 'uno_entries', 'uno_configuration_sha256'):
        assert domain[key] == old_domain[key]
    assert {name: value for name, value in after['domains'].items() if name != 'office'} == {
        name: value for name, value in before['domains'].items() if name != 'office'}
    assert {row['path'] for row in after['unproven_runtime_candidates']} == {
        row['path'] for row in before['unproven_runtime_candidates']} - {target}
    assert after['pe_coverage'] == 'partial'
    assert domain['text_encoding_entries']['caller'] == office + 'program/sal3.dll'
    assert {name: path.read_bytes() for name, path in payload.items()} == before_bytes


@pytest.mark.parametrize('name', ['sal3.dll', 'sal_textenclo.dll'])
@pytest.mark.parametrize('damage', ['missing', 'changed', 'x86', 'pe32', 'not-dll', 'non-executable', 'clr', 'relocated'])
def test_textencoding_rejects_missing_changed_or_non_native_fixed_images(native, textencoding_registry, name, damage):
    office, payload, nodes, _ = textencoding_registry
    key = office + 'program/' + name
    if damage == 'missing':
        del nodes[key]
    elif damage == 'relocated':
        nodes[office + 'java/bin/' + name] = nodes.pop(key)
    else:
        field, value = {'changed': ('sha256', 'changed'), 'x86': ('machine', 0x14c), 'pe32': ('magic', 0x10b),
            'not-dll': ('characteristics', 0x0002), 'non-executable': ('characteristics', 0x2000), 'clr': ('clr_rva', 4096)}[damage]
        nodes[key][field] = value
    with pytest.raises(ValueError, match='Office text encoding'):
        native.office_textencoding_entries(payload, nodes, office)


@pytest.mark.parametrize('damage', ['missing-lock', 'changed-lock', 'changed-manifest'])
def test_textencoding_requires_exact_component_and_source_hashes(native, textencoding_registry, monkeypatch, damage):
    office, payload, nodes, lock = textencoding_registry
    if damage == 'missing-lock':
        del payload[office + 'runtime-lock.json']
    elif damage == 'changed-lock':
        lock.write_bytes(lock.read_bytes() + b' ')
    else:
        manifest = json.loads(lock.read_bytes())
        manifest['files']['program/sal_textenclo.dll'] = '0' * 64
        raw = json.dumps(manifest).encode()
        lock.write_bytes(raw)
        monkeypatch.setattr(native, 'OFFICE_TEXTENC_LOCK_SHA256', hashlib.sha256(raw).hexdigest())
    with pytest.raises(ValueError, match='Office text encoding'):
        native.office_textencoding_entries(payload, nodes, office)


@pytest.mark.parametrize('kind', ['import', 'delay'])
def test_textencoding_cannot_borrow_java_or_system_crt(native, textencoding_registry, tmp_path, monkeypatch, kind):
    monkeypatch.setattr(native, 'office_environment_entries', lambda *_: dict(roots=[]))
    monkeypatch.setattr(native, 'office_locale_entries', lambda *_: dict(roots=[]))
    office, payload, nodes, _ = textencoding_registry
    domain = native.inspect_dependencies(payload, tmp_path)['domains']['office']
    nodes[office + 'program/sal_textenclo.dll']['edges'] = [('vcruntime140.dll', kind)]
    nodes[office + 'java/bin/vcruntime140.dll'] = nodes.pop(office + 'program/vcruntime140.dll')
    (tmp_path / 'vcruntime140.dll').write_bytes(b'Host CRT must not satisfy private dependency')
    with pytest.raises(ValueError, match=f'Unresolved {kind}.*system CRT'):
        native.closure(nodes, [office + 'program/sal_textenclo.dll'],
            domain['directories'], domain['crt_directories'], tmp_path)


@pytest.fixture
def locale_registry(native, textencoding_registry, tmp_path, monkeypatch):
    office, payload, nodes, lock = textencoding_registry
    manifest = json.loads(lock.read_bytes())
    registry_raw = (b'<components xmlns="http://openoffice.org/2010/uno-components">'
        b'<component loader="com.sun.star.loader.SharedLibrary" '
        b'uri="vnd.sun.star.expand:$LO_LIB_DIR/mergedlo.dll">'
        b'<implementation name="com.sun.star.i18n.LocaleDataImpl" '
        b'constructor="com_sun_star_i18n_LocaleDataImpl_get_implementation"/>'
        b'</component></components>')
    registry = 'program/services/services.rdb'
    path = tmp_path / registry
    path.write_bytes(registry_raw)
    digest = hashlib.sha256(registry_raw).hexdigest()
    payload[office + registry] = path
    manifest['files'][registry] = digest
    monkeypatch.setattr(native, 'OFFICE_UNO_FILES', {**native.OFFICE_UNO_FILES, registry: digest})
    images = {}
    for name in ('mergedlo.dll', 'localedata_en.dll', 'localedata_es.dll', 'localedata_euro.dll', 'localedata_others.dll'):
        raw = ('independent registered locale provider fixture ' + name).encode()
        path = tmp_path / 'program' / name
        path.write_bytes(raw)
        digest = hashlib.sha256(raw).hexdigest()
        images[name] = digest
        payload[office + 'program/' + name] = path
        manifest['files']['program/' + name] = digest
        nodes[office + 'program/' + name] = node(office + 'program/' + name,
            [('vcruntime140.dll', 'import')] if name == 'mergedlo.dll' else [('sal3.dll', 'import')], digest=digest)
        nodes[office + 'program/' + name]['characteristics'] = 0x2002
    raw = json.dumps(manifest).encode()
    lock.write_bytes(raw)
    digest = hashlib.sha256(raw).hexdigest()
    monkeypatch.setattr(native, 'OFFICE_LOCALE_IMAGES', images)
    for constant in ('OFFICE_TEXTENC_LOCK_SHA256', 'OFFICE_LOCALE_LOCK_SHA256'):
        monkeypatch.setattr(native, constant, digest)
    if 'python_launchers' in manifest:
        monkeypatch.setattr(native, 'OFFICE_SELFCONTAINED_LOCK_SHA256', digest)
    else:
        for constant in ('OFFICE_PYTHON_LOCK_SHA256', 'OFFICE_PROGRAM_LOCK_SHA256', 'OFFICE_VENV_LOCK_SHA256'):
            monkeypatch.setattr(native, constant, digest)
    return office, payload, nodes, lock


def test_locale_providers_preserve_old_graph_search_crt_and_other_domains(native, locale_registry, tmp_path, monkeypatch):
    monkeypatch.setattr(native, 'office_environment_entries', lambda *_: dict(roots=[]))
    office, payload, nodes, _ = locale_registry
    before_bytes = {name: path.read_bytes() for name, path in payload.items()}
    expected = {office + 'program/localedata_' + lang + '.dll' for lang in ('en', 'es', 'euro', 'others')}
    with monkeypatch.context() as previous:
        previous.setattr(native, 'office_locale_entries', lambda *_: dict(roots=[]))
        before = native.inspect_dependencies(payload, tmp_path)
    after = native.inspect_dependencies(payload, tmp_path)
    old, new = before['domains']['office'], after['domains']['office']
    assert set(new['roots']) == set(old['roots']) | expected
    assert set(new['nodes']) == set(old['nodes']) | expected
    assert office + 'program/mergedlo.dll' in old['nodes']
    for key in ('directories', 'crt_directories', 'registered_directories', 'uno_entries',
        'uno_configuration_sha256', 'text_encoding_entries'):
        assert new[key] == old[key]
    assert {key: value for key, value in after['domains'].items() if key != 'office'} == {
        key: value for key, value in before['domains'].items() if key != 'office'}
    assert {row['path'] for row in after['unproven_runtime_candidates']} == {
        row['path'] for row in before['unproven_runtime_candidates']} - expected
    assert after['pe_coverage'] == 'partial'
    assert new['locale_data_entries']['caller'] == office + 'program/mergedlo.dll'
    assert {name: path.read_bytes() for name, path in payload.items()} == before_bytes


@pytest.mark.parametrize('name', ['mergedlo.dll', 'localedata_en.dll', 'localedata_es.dll',
    'localedata_euro.dll', 'localedata_others.dll'])
@pytest.mark.parametrize('damage', ['missing', 'changed'])
def test_every_fixed_locale_image_must_be_present_and_match_source(native, locale_registry, name, damage):
    office, payload, nodes, _ = locale_registry
    key = office + 'program/' + name
    if damage == 'missing':
        del nodes[key]
    else:
        nodes[key]['sha256'] = 'changed'
    with pytest.raises(ValueError, match='Office locale'):
        native.office_locale_entries(payload, nodes, office)


@pytest.mark.parametrize('name', ['mergedlo.dll', 'localedata_es.dll'])
@pytest.mark.parametrize('field,value', [('machine', 0x14c), ('magic', 0x10b), ('characteristics', 0x0002),
    ('characteristics', 0x2000), ('clr_rva', 4096)])
def test_locale_caller_and_provider_need_native_dll_headers(native, locale_registry, name, field, value):
    office, payload, nodes, _ = locale_registry
    nodes[office + 'program/' + name][field] = value
    with pytest.raises(ValueError, match='Office locale'):
        native.office_locale_entries(payload, nodes, office)


@pytest.mark.parametrize('damage', ['missing-lock', 'changed-lock', 'missing-registry', 'changed-registry', 'registry-budget'])
def test_locale_source_registration_and_component_are_fixed(native, locale_registry, damage):
    office, payload, nodes, lock = locale_registry
    if damage == 'missing-lock':
        del payload[office + 'runtime-lock.json']
    elif damage == 'changed-lock':
        lock.write_bytes(lock.read_bytes() + b' ')
    elif damage == 'missing-registry':
        del payload[office + 'program/services/services.rdb']
    else:
        payload[office + 'program/services/services.rdb'].write_bytes(
            b'changed registration' if damage == 'changed-registry' else b'x' * (1024 * 1024 + 1))
    with pytest.raises(ValueError, match='Office locale'):
        native.office_locale_entries(payload, nodes, office)


def test_same_named_locale_provider_in_java_does_not_replace_fixed_program_image(native, locale_registry):
    office, payload, nodes, _ = locale_registry
    key = office + 'program/localedata_es.dll'
    nodes[office + 'java/bin/localedata_es.dll'] = nodes.pop(key)
    with pytest.raises(ValueError, match='Office locale'):
        native.office_locale_entries(payload, nodes, office)


@pytest.mark.parametrize('kind', ['import', 'delay'])
def test_locale_provider_cannot_borrow_crt_from_other_domain_or_system(native, locale_registry, tmp_path, monkeypatch, kind):
    monkeypatch.setattr(native, 'office_environment_entries', lambda *_: dict(roots=[]))
    office, payload, nodes, _ = locale_registry
    domain = native.inspect_dependencies(payload, tmp_path)['domains']['office']
    target = office + 'program/localedata_es.dll'
    nodes[target]['edges'] = [('vcruntime140.dll', kind)]
    nodes[office + 'java/bin/vcruntime140.dll'] = nodes.pop(office + 'program/vcruntime140.dll')
    (tmp_path / 'vcruntime140.dll').write_bytes(b'Host CRT must not fill private dependency')
    with pytest.raises(ValueError, match=f'Unresolved {kind}.*system CRT'):
        native.closure(nodes, [target], domain['directories'], domain['crt_directories'], tmp_path)


@pytest.fixture
def environment_registry(native, locale_registry, tmp_path, monkeypatch):
    office, payload, nodes, lock = locale_registry
    manifest = json.loads(lock.read_bytes())
    registry = 'program/services/services.rdb'
    data = (b'<components xmlns="http://openoffice.org/2010/uno-components">'
        b'<component loader="com.sun.star.loader.SharedLibrary" environment="mscx" '
        b'uri="vnd.sun.star.expand:$LO_LIB_DIR/mergedlo.dll">'
        b'<implementation name="com.sun.star.i18n.LocaleDataImpl"/></component>'
        b'<component loader="com.sun.star.loader.SharedLibrary" environment="mscx:affine" '
        b'uri="vnd.sun.star.expand:$LO_LIB_DIR/mergedlo.dll">'
        b'<implementation name="com.sun.star.comp.sdbc.ado.ODriver"/></component></components>')
    payload[office + registry].write_bytes(data)
    digest = hashlib.sha256(data).hexdigest()
    manifest['files'][registry] = digest
    monkeypatch.setattr(native, 'OFFICE_UNO_FILES', {**native.OFFICE_UNO_FILES, registry: digest})
    images = {}
    for name in ('cppu3.dll', 'mscx_uno.dll', 'affine_uno_uno.dll', 'purpenvhelper3MSC.dll',
        'log_uno_uno.dll', 'unsafe_uno_uno.dll'):
        data = ('independent fixed environment fixture ' + name).encode()
        path = tmp_path / 'program' / name
        path.write_bytes(data)
        digest = hashlib.sha256(data).hexdigest()
        payload[office + 'program/' + name] = path
        manifest['files']['program/' + name] = digest
        key = (office + 'program/' + name).casefold()
        nodes[key] = node(office + 'program/' + name, digest=digest)
        nodes[key]['characteristics'] = 0x2002
        if name not in ('log_uno_uno.dll', 'unsafe_uno_uno.dll'):
            images[name] = digest
    program = office + 'program/'
    nodes[program + 'soffice.bin']['edges'].append(('cppu3.dll', 'import'))
    nodes[program + 'cppu3.dll']['edges'] = [('vcruntime140.dll', 'import')]
    nodes[program + 'mscx_uno.dll']['edges'] = [('cppu3.dll', 'import')]
    nodes[program + 'affine_uno_uno.dll']['edges'] = [('purpenvhelper3msc.dll', 'import')]
    nodes[program + 'purpenvhelper3msc.dll']['edges'] = [('cppu3.dll', 'import')]
    raw = json.dumps(manifest).encode()
    lock.write_bytes(raw)
    digest = hashlib.sha256(raw).hexdigest()
    monkeypatch.setattr(native, 'OFFICE_ENVIRONMENT_IMAGES', images)
    for constant in ('OFFICE_TEXTENC_LOCK_SHA256', 'OFFICE_LOCALE_LOCK_SHA256', 'OFFICE_ENVIRONMENT_LOCK_SHA256'):
        monkeypatch.setattr(native, constant, digest)
    if 'python_launchers' in manifest:
        monkeypatch.setattr(native, 'OFFICE_SELFCONTAINED_LOCK_SHA256', digest)
    else:
        for constant in ('OFFICE_PYTHON_LOCK_SHA256', 'OFFICE_PROGRAM_LOCK_SHA256', 'OFFICE_VENV_LOCK_SHA256'):
            monkeypatch.setattr(native, constant, digest)
    return office, payload, nodes, lock


def test_configured_environments_add_two_roots_three_nodes_and_keep_other_purposes_unknown(
        native, environment_registry, tmp_path, monkeypatch):
    office, payload, nodes, _ = environment_registry
    program = office + 'program/'
    before_bytes = {name: path.read_bytes() for name, path in payload.items()}
    with monkeypatch.context() as old_policy:
        old_policy.setattr(native, 'office_environment_entries', lambda *_: dict(roots=[]))
        before = native.inspect_dependencies(payload, tmp_path)
    after = native.inspect_dependencies(payload, tmp_path)
    old, new = before['domains']['office'], after['domains']['office']
    roots = {program + 'mscx_uno.dll', program + 'affine_uno_uno.dll'}
    newly_covered = roots | {program + 'purpenvhelper3msc.dll'}
    assert set(new['roots']) == set(old['roots']) | roots
    assert set(new['nodes']) == set(old['nodes']) | newly_covered
    for key in ('directories', 'crt_directories', 'registered_directories', 'uno_entries',
        'uno_configuration_sha256', 'text_encoding_entries', 'locale_data_entries'):
        assert new[key] == old[key]
    assert {key: value for key, value in after['domains'].items() if key != 'office'} == {
        key: value for key, value in before['domains'].items() if key != 'office'}
    assert {row['path'].casefold() for row in after['unproven_runtime_candidates']} == {
        row['path'].casefold() for row in before['unproven_runtime_candidates']} - newly_covered
    assert {program + 'log_uno_uno.dll', program + 'unsafe_uno_uno.dll'} <= {
        row['path'] for row in after['unproven_runtime_candidates']}
    assert after['pe_coverage'] == 'partial'
    assert new['environment_binding_entries']['other_descriptors_and_purposes_certified'] is False
    assert {name: path.read_bytes() for name, path in payload.items()} == before_bytes


@pytest.mark.parametrize('name', ['cppu3.dll', 'mscx_uno.dll', 'affine_uno_uno.dll', 'purpenvhelper3MSC.dll'])
@pytest.mark.parametrize('damage', ['missing', 'changed'])
def test_fixed_binding_caller_roots_and_transitive_helper_require_source_identity(
        native, environment_registry, name, damage):
    office, payload, nodes, _ = environment_registry
    key = (office + 'program/' + name).casefold()
    if damage == 'missing':
        del nodes[key]
    else:
        nodes[key]['sha256'] = 'changed'
    with pytest.raises(ValueError, match='Office environment'):
        native.office_environment_entries(payload, nodes, office)


@pytest.mark.parametrize('name', ['cppu3.dll', 'affine_uno_uno.dll'])
@pytest.mark.parametrize('field,value', [('machine', 0x14c), ('magic', 0x10b), ('characteristics', 0x0002),
    ('characteristics', 0x2000), ('clr_rva', 4096)])
def test_environment_native_image_headers_are_required(native, environment_registry, name, field, value):
    office, payload, nodes, _ = environment_registry
    nodes[office + 'program/' + name][field] = value
    with pytest.raises(ValueError, match='Office environment'):
        native.office_environment_entries(payload, nodes, office)


@pytest.mark.parametrize('damage', ['missing-lock', 'changed-lock', 'missing-registry', 'changed-registry', 'registry-budget'])
def test_environment_component_and_fixed_registration_must_match(native, environment_registry, damage):
    office, payload, nodes, lock = environment_registry
    if damage == 'missing-lock':
        del payload[office + 'runtime-lock.json']
    elif damage == 'changed-lock':
        lock.write_bytes(lock.read_bytes() + b' ')
    elif damage == 'missing-registry':
        del payload[office + 'program/services/services.rdb']
    else:
        payload[office + 'program/services/services.rdb'].write_bytes(
            b'changed registration' if damage == 'changed-registry' else b'x' * (1024 * 1024 + 1))
    with pytest.raises(ValueError, match='Office environment'):
        native.office_environment_entries(payload, nodes, office)


def test_transitive_purpose_helper_cannot_be_replaced_by_java_copy(native, environment_registry):
    office, payload, nodes, _ = environment_registry
    key = office + 'program/purpenvhelper3msc.dll'
    nodes[office + 'java/bin/purpenvhelper3msc.dll'] = nodes.pop(key)
    with pytest.raises(ValueError, match='Office environment'):
        native.office_environment_entries(payload, nodes, office)


@pytest.mark.parametrize('kind', ['import', 'delay'])
def test_environment_binding_cannot_borrow_foreign_or_system_crt(native, environment_registry, tmp_path, kind):
    office, payload, nodes, _ = environment_registry
    domain = native.inspect_dependencies(payload, tmp_path)['domains']['office']
    target = office + 'program/mscx_uno.dll'
    nodes[target]['edges'] = [('vcruntime140.dll', kind)]
    nodes[office + 'java/bin/vcruntime140.dll'] = nodes.pop(office + 'program/vcruntime140.dll')
    (tmp_path / 'vcruntime140.dll').write_bytes(b'Host CRT must not replace private binding dependency')
    with pytest.raises(ValueError, match=f'Unresolved {kind}.*system CRT'):
        native.closure(nodes, [target], domain['directories'], domain['crt_directories'], tmp_path)
