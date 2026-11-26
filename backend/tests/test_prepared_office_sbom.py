import importlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest


@pytest.fixture
def tools(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).parents[2] / 'tools'))
    return importlib.import_module('prepared_office_sbom'), importlib.import_module('office_msi_members')


def test_cabinet_allows_only_observed_target_bytes(tools, tmp_path):
    _, msi = tools
    rows = [['a', 'c', 'short|actual.bin', '3'], ['b', 'c', 'actual.bin', '3']]
    files = msi.source_files(rows, {'c': 'child'}, {'child': ('INSTALLLOCATION', 'short|nested:source')})
    assert files == {'a': ('nested/actual.bin', 3), 'b': ('nested/actual.bin', 3)}
    (tmp_path / 'a').write_bytes(b'one')
    (tmp_path / 'b').write_bytes(b'two')
    chosen = {'nested/actual.bin': msi.file_sha(tmp_path / 'b')}
    assert msi.check_cabinet_files(tmp_path, files, chosen) == 2
    with pytest.raises(ValueError):
        msi.check_cabinet_files(tmp_path, files, {'nested/actual.bin': '0' * 64})
    (tmp_path / 'b').write_bytes(b'extra')
    with pytest.raises(ValueError):
        msi.check_cabinet_files(tmp_path, files, chosen)
    (tmp_path / 'b').unlink()
    with pytest.raises(ValueError):
        msi.check_cabinet_files(tmp_path, files, chosen)


@pytest.mark.parametrize('key,field,dir_record', [
    ('A.exe', 'name', ('INSTALLLOCATION', 'dir')), ('../x', 'name', ('INSTALLLOCATION', 'dir')),
    ('CON.bin', 'name', ('INSTALLLOCATION', 'dir')), ('dot.', 'name', ('INSTALLLOCATION', 'dir')),
    ('b', 'short|../wrong', ('INSTALLLOCATION', 'dir')), ('b', 'name', ('cycle', '.')),
    ('b', 'name', ('INSTALLLOCATION', 'dir/escape'))])
def test_msi_rejects_unsafe_or_ambiguous_rows(tools, key, field, dir_record):
    _, msi = tools
    with pytest.raises(ValueError):
        msi.source_files([['a.exe', 'c', 'first', '1'], [key, 'c', field, '1']], {'c': 'cycle'}, {'cycle': dir_record})


def test_base_only_comparison_hash_and_membership(tools, tmp_path):
    mod, _ = tools
    setup = tmp_path / 'setup'
    setup.write_bytes(b'my synthetic setup')
    digest = mod.file_sha(setup)
    bom = tmp_path / 'base.json'
    data = {'bomFormat': 'CycloneDX', 'specVersion': '1.6', 'metadata': {'component': {
        'bom-ref': 'setup:' + digest, 'hashes': mod.hashes(digest)}}, 'components': [{'bom-ref': 'file:app/build-inventory.json'}]}
    bom.write_text(json.dumps(data))
    original = mod.file_sha(bom)
    assert mod.compare_base(bom, setup, original)[-1]['value'] == 'absent'
    data['components'].append({'bom-ref': 'file:app/Converters/LibreOffice/one'})
    bom.write_text(json.dumps(data))
    with pytest.raises(ValueError, match='receipt'):
        mod.compare_base(bom, setup, original)
    with pytest.raises(ValueError, match='already'):
        mod.compare_base(bom, setup, mod.file_sha(bom))
    setup.write_bytes(b'other')
    with pytest.raises(ValueError, match='differ'):
        mod.compare_base(bom, setup, mod.file_sha(bom))


@pytest.fixture
def sample(tools, tmp_path, monkeypatch):
    mod, _ = tools
    crt = 'System64/msvcp140.dll'
    names = {'program/soffice.bin': b'office', 'java/release': b'java', crt: b'crt', 'program/msvcp140.dll': b'crt',
             'runtime-lock.json': b'combined', 'office-runtime-lock.json': b'office lock', 'java/' + mod.LOCK_NAME: b'java lock'}
    paths, digests = {}, {}
    for name, raw in names.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
        paths[name], digests[name] = path, mod.file_sha(path)
    monkeypatch.setattr(mod, 'pe_version', lambda *args: ('1.2.3.4', '0x8664'))
    manifest = SimpleNamespace(fingerprint=digests.pop('runtime-lock.json'), files=digests, python_launchers=False)
    source, target = mod.MOUNT + 'program/soffice.bin', mod.MOUNT + 'program/msvcp140.dll'
    graph = {'unproven_runtime_candidates': [{'path': mod.MOUNT + crt}], 'pe_images': 3, 'domains': {
        'office': {'edges': [{'source': source, 'target': target, 'resolution': 'private-crt'},
                             {'source': source, 'target': target, 'resolution': 'package'},
                             {'source': source, 'name': 'kernel32.dll', 'resolution': 'system'}]}}}
    return mod, [paths, manifest, {name: digests[name] for name in (crt, 'program/soffice.bin')},
                 {'release': digests['java/release']}, graph, 3, []]


def test_layers_keep_prepared_files_separate_from_base_and_unproven_loading(sample):
    mod, args = sample
    result = mod.assemble(*args)
    layers = {c['name']: c for c in result['components']}
    assert len(layers['LibreOffice']['components']) == 2 and len(layers['Eclipse Temurin JRE']['components']) == 1
    assert len(layers['msvcp140.dll']['evidence']['occurrences']) == 2
    copy = layers['app/' + mod.MOUNT + 'program/msvcp140.dll']
    assert copy['properties'] == [mod.prop('copied-from', 'app/' + mod.MOUNT + 'System64/msvcp140.dll')]
    unknown = next(f for f in layers['LibreOffice']['components'] if f['name'].endswith('msvcp140.dll'))
    assert unknown['properties'] == [mod.prop('native-loading-domain', 'unproven')]
    assert result['dependencies'][1] == {'ref': 'file:app/' + mod.MOUNT + 'program/soffice.bin', 'dependsOn': [copy['bom-ref']]}
    assert result['metadata']['component']['bom-ref'].startswith('prepared:')
    assert result['compositions'][0]['aggregate'] == 'incomplete'


@pytest.mark.parametrize('fault', ['office', 'jre', 'copy', 'path', 'unknown', 'edge'])
def test_wrong_file_or_edge_attribution_fails(sample, fault):
    mod, args = sample
    paths, manifest, office, java, graph, _, _ = args
    if fault == 'office':
        office['program/soffice.bin'] = '0' * 64
    elif fault == 'jre':
        java['release'] = '0' * 64
    elif fault == 'copy':
        manifest.files['program/msvcp140.dll'] = '0' * 64
    elif fault == 'path':
        paths['unlisted'] = paths['java/release']
        manifest.files['unlisted'] = manifest.files['java/release']
    elif fault == 'unknown':
        graph['unproven_runtime_candidates'][0]['path'] = mod.MOUNT + 'missing'
    else:
        graph['domains']['office']['edges'][0]['target'] = mod.MOUNT + 'missing'
    with pytest.raises(ValueError):
        mod.assemble(*args)
