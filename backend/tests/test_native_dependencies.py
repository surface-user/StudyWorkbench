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
    return dict(path=path, machine=machine, magic=0x20B, sha256=digest, edges=list(imports))


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
        return SimpleNamespace(FILE_HEADER=SimpleNamespace(Machine=0x8664), OPTIONAL_HEADER=SimpleNamespace(Magic=0x20b),
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


