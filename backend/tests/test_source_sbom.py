import copy
import importlib
import json
import subprocess
from pathlib import Path

import pytest
import yaml


@pytest.fixture
def sbom(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).parents[2] / 'tools'))
    return importlib.import_module('source_sbom')


@pytest.fixture
def locks(sbom):
    packages = {
        'collection': {'source': 'hosted', 'version': '1.19.1+2', 'dependency': 'transitive',
                       'description': {'name': 'collection', 'url': 'https://pub.dev', 'sha256': 'a' * 64}},
        'glass': {'source': 'git', 'version': '0.1.0', 'dependency': 'direct main',
                  'description': {'url': 'https://github.com/example/glass.git', 'path': '.',
                                  'resolved-ref': 'b' * 40, 'ref': 'main'}},
        'flutter': {'source': 'sdk', 'version': '0.0.0', 'description': 'flutter'},
    }
    return {sbom.LOCKS[0]: b'PyYAML==6.0.3\npytest==9.0.1\n',
            sbom.LOCKS[1]: yaml.safe_dump({'packages': packages, 'sdks': {'flutter': '>=3.44.0'}}).encode()}


def bom_for(sbom, expected, projected):
    return {'bomFormat': 'CycloneDX', 'specVersion': '1.6', 'components': [
        {'type': 'library', 'bom-ref': purl, 'purl': purl, 'name': item['name'], 'version': item['version'],
         'properties': [{'name': 'syft:location:0:path', 'value': '/' + item['lock']}]}
        for purl, item in expected.items()
    ] + [{'type': 'file', 'bom-ref': name, 'name': '/' + name,
          'hashes': [{'alg': 'SHA-256', 'content': sbom.sha256(data)}]} for name, data in projected.items()]}


def test_inventory_preserves_source_identity_and_excludes_unresolved_sdk(sbom, locks):
    before = copy.deepcopy(locks)
    expected, excluded, projected = sbom.lock_inventory(locks)
    assert locks == before
    assert len(expected) == 4
    assert 'pkg:pypi/pyyaml@6.0.3' in expected
    assert 'pkg:pub/collection@1.19.1%2B2?hosted_url=pub.dev' in expected
    assert any('vcs_url=https%3A%2F%2Fgithub.com%2Fexample%2Fglass.git%40' + 'b' * 40 in key for key in expected)
    assert excluded == [{'name': 'flutter', 'locked_version': '0.0.0', 'sdk': 'flutter',
                         'reason': 'SDK constraint is not an installed SDK version'}]
    assert 'flutter' not in yaml.safe_load(projected[sbom.LOCKS[1]])['packages']
    assert sbom.compare_bom(bom_for(sbom, expected, projected), expected, projected) == 4


@pytest.mark.parametrize('text', ['thing>=1.0', 'thing==1.0; os_name == "nt"', '-r other.txt',
                                 'thing @ https://example.test/file.whl', 'thing==1.0\nThing==2.0', ''])
def test_python_lock_rejects_ambiguous_inventory(sbom, locks, text):
    locks[sbom.LOCKS[0]] = text.encode()
    with pytest.raises(ValueError):
        sbom.lock_inventory(locks)


@pytest.mark.parametrize('change', ['path', 'unpinned_git', 'credential', 'custom_host', 'bad_hash', 'bad_version'])
def test_dart_lock_rejects_unverified_sources(sbom, locks, change):
    value = yaml.safe_load(locks[sbom.LOCKS[1]])
    if change == 'path':
        value['packages']['glass']['source'] = 'path'
    elif change == 'unpinned_git':
        value['packages']['glass']['description']['resolved-ref'] = 'main'
    elif change == 'credential':
        value['packages']['glass']['description']['url'] = 'https://secret@example.test/repo.git'
    elif change == 'custom_host':
        value['packages']['collection']['description']['url'] = 'https://example.test'
    elif change == 'bad_hash':
        value['packages']['collection']['description']['sha256'] = 'missing'
    else:
        value['packages']['glass']['version'] = None
    locks[sbom.LOCKS[1]] = yaml.safe_dump(value).encode()
    with pytest.raises(ValueError):
        sbom.lock_inventory(locks)


def test_duplicate_yaml_keys_fail_instead_of_overwriting_inventory(sbom, locks):
    locks[sbom.LOCKS[1]] = b'packages: {}\npackages: {}\n'
    with pytest.raises(ValueError, match='Duplicate'):
        sbom.lock_inventory(locks)


@pytest.mark.parametrize('malformed', [[], {'bomFormat': 'CycloneDX', 'specVersion': '1.6', 'components': [None]}])
def test_malformed_bom_is_rejected(sbom, locks, malformed):
    expected, _, projected = sbom.lock_inventory(locks)
    with pytest.raises(ValueError):
        sbom.compare_bom(malformed, expected, projected)


@pytest.mark.parametrize('damage', ['missing', 'extra', 'duplicate', 'name', 'version', 'git_commit',
                                  'lock_hash', 'file_missing', 'origin', 'format'])
def test_comparison_fails_closed_for_incomplete_or_wrong_evidence(sbom, locks, damage):
    expected, _, projected = sbom.lock_inventory(locks)
    bom = bom_for(sbom, expected, projected)
    if damage == 'missing':
        del bom['components'][0]
    elif damage == 'extra':
        bom['components'].append({'type': 'library', 'bom-ref': 'extra', 'purl': 'pkg:pypi/extra@1'})
    elif damage == 'duplicate':
        bom['components'].append(copy.deepcopy(bom['components'][0]))
    elif damage in {'name', 'version'}:
        bom['components'][0][damage] = 'wrong'
    elif damage == 'git_commit':
        next(x for x in bom['components'] if x.get('name') == 'glass')['purl'] += 'bad'
    elif damage == 'lock_hash':
        bom['components'][-1]['hashes'][0]['content'] = 'f' * 64
    elif damage == 'file_missing':
        bom['components'].pop()
    elif damage == 'origin':
        bom['components'][0]['properties'] = []
    else:
        bom['specVersion'] = '1.5'
    with pytest.raises(ValueError):
        sbom.compare_bom(bom, expected, projected)


@pytest.fixture
def runner(sbom, locks, tmp_path, monkeypatch):
    source = tmp_path / 'source'
    for name, data in locks.items():
        path = source / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    exe = tmp_path / 'syft.exe'
    exe.write_bytes(b'self-authored mock binary')
    monkeypatch.setattr(sbom, 'SYFT_SHA256', sbom.sha256(exe.read_bytes()))
    calls = []

    def run(command, **kwargs):
        calls.append((command, kwargs))
        root = kwargs['cwd']
        expected, _, projected = sbom.lock_inventory(locks)
        assert {p.relative_to(root / 'inputs').as_posix() for p in (root / 'inputs').rglob('*') if p.is_file()} == set(sbom.LOCKS)
        (root / 'source.cdx.json').write_text(json.dumps(bom_for(sbom, expected, projected)))

    monkeypatch.setattr(sbom.subprocess, 'run', run)
    return source, exe, tmp_path / 'output', calls


def test_generation_uses_only_isolated_inputs_and_explicit_config(sbom, runner, monkeypatch):
    source, exe, output, calls = runner
    monkeypatch.setenv('SYFT_ENRICH', 'all')
    monkeypatch.setenv('SYFT_CONFIG', 'untrusted.yaml')
    (source / 'unrelated-secret.txt').write_text('never catalog this')
    result = sbom.generate(source, exe, output)
    assert result['matched_components'] == 4
    assert result['product_sbom_complete'] is False
    assert result['scope'] == 'source-locks-only'
    assert len(result['excluded_sdk_components']) == 1
    assert result['source_lock_sha256'][sbom.LOCKS[1]] != result['scan_input_sha256'][sbom.LOCKS[1]]
    assert result['bom_sha256'] == sbom.sha256((output / 'source.cdx.json').read_bytes())
    assert (output / 'comparison.json').is_file()
    command, kwargs = calls[0]
    assert command[2] == 'dir:inputs'
    assert command[-1] == 'cyclonedx-json@1.6=source.cdx.json'
    assert kwargs['env']['SYFT_CHECK_FOR_APP_UPDATE'] == 'false'
    assert 'SYFT_ENRICH' not in kwargs['env'] and 'SYFT_CONFIG' not in kwargs['env']
    assert kwargs['timeout'] == 120 and kwargs['check'] is True
    assert 'enrich: []' in (output / 'syft.yaml').read_text()


def test_existing_output_is_never_overwritten(sbom, runner):
    source, exe, output, calls = runner
    output.mkdir()
    (output / 'comparison.json').write_text('preserve')
    with pytest.raises(FileExistsError):
        sbom.generate(source, exe, output)
    assert not calls
    assert (output / 'comparison.json').read_text() == 'preserve'


def test_wrong_tool_hash_fails_before_executing_or_creating_output(sbom, runner):
    source, exe, output, calls = runner
    exe.write_bytes(b'tampered')
    with pytest.raises(ValueError, match='pinned'):
        sbom.generate(source, exe, output)
    assert not calls and not output.exists()


@pytest.mark.parametrize('failure', ['timeout', 'exit', 'invalid_bom', 'changed_lock'])
def test_failed_scan_never_writes_success_receipt(sbom, runner, monkeypatch, failure):
    source, exe, output, _ = runner
    original = sbom.subprocess.run

    def run(command, **kwargs):
        if failure == 'timeout':
            raise subprocess.TimeoutExpired(command, 120)
        if failure == 'exit':
            raise subprocess.CalledProcessError(2, command)
        original(command, **kwargs)
        if failure == 'invalid_bom':
            (output / 'source.cdx.json').write_text('{}')
        else:
            (source / sbom.LOCKS[0]).write_text('pytest==1.0\n')
    monkeypatch.setattr(sbom.subprocess, 'run', run)
    with pytest.raises((ValueError, subprocess.SubprocessError)):
        sbom.generate(source, exe, output)
    assert not (output / 'comparison.json').exists()
    assert (output / 'syft.log').exists()


def test_oversized_lock_is_rejected_before_scan(sbom, runner):
    source, exe, output, calls = runner
    (source / sbom.LOCKS[0]).write_bytes(b'x' * (1024 * 1024 + 1))
    with pytest.raises(ValueError, match='1 MiB'):
        sbom.generate(source, exe, output)
    assert not calls and not output.exists()


def test_linked_lock_is_rejected_before_reading(sbom, runner, monkeypatch):
    source, exe, output, calls = runner
    original = Path.lstat

    def lstat(path):
        info = original(path)
        if path == source / sbom.LOCKS[0]:
            from types import SimpleNamespace
            return SimpleNamespace(st_mode=info.st_mode, st_file_attributes=sbom.stat.FILE_ATTRIBUTE_REPARSE_POINT)
        return info
    monkeypatch.setattr(Path, 'lstat', lstat)
    with pytest.raises(ValueError, match='reparse'):
        sbom.generate(source, exe, output)
    assert not calls and not output.exists()
