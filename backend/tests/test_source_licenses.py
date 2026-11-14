import base64
import hashlib
import importlib
import importlib.metadata
import json
from pathlib import Path

import pytest
import yaml


@pytest.fixture
def example(tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).parents[2] / 'tools'))
    tool = importlib.import_module('source_licenses')
    source = tmp_path / 'source'
    (source / 'backend').mkdir(parents=True)
    (source / 'apps/desktop').mkdir(parents=True)
    (source / tool.LOCKS[0]).write_text('example==1.0.0\n', encoding='utf-8')
    hosted = {'source': 'hosted', 'version': '2.0.0',
              'description': {'name': 'sample', 'url': 'https://pub.dev', 'sha256': 'a' * 64}}
    (source / tool.LOCKS[1]).write_text(yaml.safe_dump({'packages': {
        'sample': hosted, 'flutter': {'source': 'sdk', 'version': '0.0.0', 'description': 'flutter'}}}),
        encoding='utf-8')
    site = tmp_path / 'site'
    metadata = site / 'example-1.0.0.dist-info'
    (metadata / 'licenses').mkdir(parents=True)
    (metadata / 'METADATA').write_text('Metadata-Version: 2.4\nName: example\nVersion: 1.0.0\n'
                                     'License-Expression: MIT\nLicense-File: LICENSE\n', encoding='utf-8')
    license_text = b'Self-authored Python license fixture\n'
    (metadata / 'licenses/LICENSE').write_bytes(license_text)
    digest = base64.urlsafe_b64encode(hashlib.sha256(license_text).digest()).decode().rstrip('=')
    (metadata / 'RECORD').write_text('example-1.0.0.dist-info/METADATA,,\n'
                                   f'example-1.0.0.dist-info/licenses/LICENSE,sha256={digest},{len(license_text)}\n',
                                   encoding='utf-8')
    dist = importlib.metadata.PathDistribution(metadata)
    monkeypatch.setattr(tool.importlib.metadata, 'distributions', lambda: [dist])
    dart = tmp_path / 'dart'
    (dart / 'LICENSES/vendor').mkdir(parents=True)
    (dart / 'pubspec.yaml').write_text('name: sample\nversion: 2.0.0\n', encoding='utf-8')
    (dart / 'LICENSE').write_bytes(b'Self-authored Dart license fixture\n')
    (dart / 'LICENSES/vendor/custom.txt').write_bytes(b'Self-authored third-party fixture\n')
    config = tmp_path / 'package_config.json'
    config.write_text(json.dumps({'packages': [{'name': 'sample', 'rootUri': dart.as_uri()}]}), encoding='utf-8')
    return tool, source, config, tmp_path / 'output', metadata, dart


def test_exact_locks_copy_original_texts_and_preserve_unknowns(example):
    tool, source, config, output, _, _ = example
    report = tool.collect(source, config, output)
    assert len(report['components']) == 2
    assert report['packages_with_issues'] == 0
    assert len(report['excluded_sdk_components']) == 1
    assert not report['product_licenses_complete']
    assert not report['distribution_obligations_reviewed']
    assert not report['archive_provenance_verified']
    files = [f for p in report['components'].values() for f in p['files']]
    assert len(files) == 3
    for file in files:
        data = (output / file['text_path']).read_bytes()
        assert len(data) == file['bytes']
        assert tool.sha256(data) == file['sha256']
    assert report['components']['pkg:pypi/example@1.0.0']['files'][0]['installed_record_sha256_matches']
    assert str(source.parent) not in (output / 'report.json').read_text(encoding='utf-8')


@pytest.mark.parametrize('kind', ['missing_python', 'wrong_python', 'duplicate_python', 'wrong_dart',
                                  'missing_dart', 'no_text', 'declared_text', 'unhashed'])
def test_missing_or_ambiguous_evidence_is_reported_not_passed(example, monkeypatch, kind):
    tool, source, config, output, metadata, dart = example
    if kind == 'missing_python':
        monkeypatch.setattr(tool.importlib.metadata, 'distributions', lambda: [])
    elif kind == 'duplicate_python':
        dist = importlib.metadata.PathDistribution(metadata)
        monkeypatch.setattr(tool.importlib.metadata, 'distributions', lambda: [dist, dist])
    elif kind == 'wrong_python':
        p = metadata / 'METADATA'
        p.write_text(p.read_text().replace('Version: 1.0.0', 'Version: 1.0.1'), encoding='utf-8')
    elif kind == 'wrong_dart':
        (dart / 'pubspec.yaml').write_text('name: sample\nversion: 9.0.0\n', encoding='utf-8')
    elif kind == 'missing_dart':
        config.write_text('{"packages": []}', encoding='utf-8')
    elif kind == 'no_text':
        (metadata / 'RECORD').write_text('example-1.0.0.dist-info/METADATA,,\n', encoding='utf-8')
    elif kind == 'declared_text':
        p = metadata / 'METADATA'
        p.write_text(p.read_text() + 'License-File: custom.txt\n', encoding='utf-8')
    elif kind == 'unhashed':
        (metadata / 'RECORD').write_text('example-1.0.0.dist-info/METADATA,,\n'
                                       'example-1.0.0.dist-info/licenses/LICENSE,,\n', encoding='utf-8')
    report = tool.collect(source, config, output)
    assert report['packages_with_issues'] == 1
    assert any(p['issues'] for p in report['components'].values())
    assert not report['product_licenses_complete']


@pytest.mark.parametrize('kind', ['changed_text', 'size', 'traversal', 'duplicate_config', 'remote_uri',
                                  'empty_text', 'big_text', 'existing_output', 'unsafe_declaration'])
def test_invalid_input_fails_without_success_report(example, kind):
    tool, source, config, output, metadata, dart = example
    if kind == 'changed_text':
        (metadata / 'licenses/LICENSE').write_bytes(b'changed')
    elif kind == 'size':
        p = metadata / 'RECORD'
        rows = p.read_text().splitlines()
        rows[-1] = rows[-1].rsplit(',', 1)[0] + ',999'
        p.write_text('\n'.join(rows) + '\n', encoding='utf-8')
    elif kind == 'traversal':
        (metadata / 'RECORD').write_text('example-1.0.0.dist-info/METADATA,,\n../LICENSE,,\n', encoding='utf-8')
    elif kind == 'duplicate_config':
        package = {'name': 'sample', 'rootUri': dart.as_uri()}
        config.write_text(json.dumps({'packages': [package, package]}), encoding='utf-8')
    elif kind == 'remote_uri':
        config.write_text('{"packages": [{"name": "sample", "rootUri": "https://example.test/"}]}', encoding='utf-8')
    elif kind == 'empty_text':
        (dart / 'LICENSE').write_bytes(b'')
    elif kind == 'big_text':
        (dart / 'LICENSE').write_bytes(b'x' * (4 * 1024 * 1024 + 1))
    elif kind == 'existing_output':
        output.mkdir()
        (output / 'retained').write_bytes(b'keep')
    elif kind == 'unsafe_declaration':
        p = metadata / 'METADATA'
        p.write_text(p.read_text() + 'License-File: ../outside\n', encoding='utf-8')
    with pytest.raises((ValueError, FileExistsError)):
        tool.collect(source, config, output)
    assert not (output / 'report.json').exists()
    if kind == 'existing_output':
        assert (output / 'retained').read_bytes() == b'keep'


def test_declared_custom_filename_is_retained(example):
    tool, source, config, output, metadata, _ = example
    p = metadata / 'METADATA'
    p.write_text(p.read_text().replace('License-File: LICENSE', 'License-File: custom.txt'), encoding='utf-8')
    (metadata / 'licenses/LICENSE').rename(metadata / 'licenses/custom.txt')
    p = metadata / 'RECORD'
    p.write_text(p.read_text().replace('licenses/LICENSE', 'licenses/custom.txt'), encoding='utf-8')
    result = tool.collect(source, config, output)
    assert result['packages_with_issues'] == 0
    assert result['components']['pkg:pypi/example@1.0.0']['files'][0]['source_path'].endswith('custom.txt')


def test_bundled_metadata_does_not_replace_distribution_identity(example):
    tool, source, config, output, metadata, _ = example
    nested = metadata.parent / 'example/vendor/other.dist-info'
    nested.mkdir(parents=True)
    (nested / 'METADATA').write_bytes(b'Name: other\nVersion: 8.0.0\n')
    (nested / 'LICENSE').write_bytes(b'Self-authored bundled license fixture\n')
    record = metadata / 'RECORD'
    record.write_text(record.read_text() + 'example/vendor/other.dist-info/METADATA,,\n'
                      'example/vendor/other.dist-info/LICENSE,,\n', encoding='utf-8')
    result = tool.collect(source, config, output)
    evidence = result['components']['pkg:pypi/example@1.0.0']
    assert len(evidence['files']) == 2
    assert evidence['version'] == '1.0.0'
    assert evidence['issues'] == ['license_record_hash_unverified:example/vendor/other.dist-info/LICENSE']


def test_changed_lock_during_collection_is_rejected(example, monkeypatch):
    tool, source, config, output, _, _ = example
    original = tool.dart_evidence

    def changed(*args):
        result = original(*args)
        (source / tool.LOCKS[0]).write_text('example==2.0.0\n', encoding='utf-8')
        return result

    monkeypatch.setattr(tool, 'dart_evidence', changed)
    with pytest.raises(ValueError, match='changed'):
        tool.collect(source, config, output)
    assert not (output / 'report.json').exists()


def test_cli_missing_evidence_is_nonzero(example, monkeypatch, capsys):
    tool, source, config, output, _, _ = example
    monkeypatch.setattr(tool.importlib.metadata, 'distributions', lambda: [])
    monkeypatch.setattr('sys.argv', ['source_licenses', '--source', str(source), '--package-config', str(config),
                                   '--output', str(output)])
    assert tool.main() == 2
    assert 'remain unverified' in capsys.readouterr().out


@pytest.fixture
def supplemented(example):
    tool, source, config, output, metadata, dart = example
    (source / tool.LOCKS[0]).write_text('latex2mathml==3.81.1\n', encoding='utf-8')
    (metadata / 'METADATA').write_text('Metadata-Version: 2.4\nName: latex2mathml\n'
                                     'Version: 3.81.1\nLicense-Expression: MIT\n', encoding='utf-8')
    (metadata / 'RECORD').write_text('example-1.0.0.dist-info/METADATA,,\n', encoding='utf-8')
    actual = Path(__file__).parents[2] / 'packaging/licenses/latex2mathml-3.81.1'
    profile = json.loads((actual / 'provenance.json').read_text(encoding='utf-8'))
    folder = source / 'packaging/licenses/latex2mathml-3.81.1'
    folder.mkdir(parents=True)
    for name in profile['package_files']:
        data = ('Self-authored source fixture for ' + name + '\n').encode()
        path = metadata.parent / name
        path.parent.mkdir(exist_ok=True)
        path.write_bytes(data)
        profile['package_files'][name] = tool.sha256(data)
    for item in profile['license_texts']:
        data = ('Self-authored license fixture for ' + item['license'] + '\n').encode()
        (folder / item['path']).write_bytes(data)
        item.update(sha256=tool.sha256(data), bytes=len(data))
    (folder / 'provenance.json').write_text(json.dumps(profile), encoding='utf-8')
    return (*example, folder, profile)


def test_pinned_supplement_keeps_mixed_license_scopes_and_unresolved_conditions(supplemented):
    tool, source, config, output, metadata, _, _, _ = supplemented
    original = {p.name: p.read_bytes() for p in metadata.iterdir() if p.is_file()}
    report = tool.collect(source, config, output)
    component = report['components']['pkg:pypi/latex2mathml@3.81.1']
    assert component['declared_license'] == 'MIT' and component['declared_license_files'] == []
    assert {f['license'] for f in component['files']} == {'MIT', 'LPPL-1.3-or-later'}
    assert all(f['evidence_kind'] == 'repository_supplement' for f in component['files'])
    assert all('installed_record_sha256_matches' not in f for f in component['files'])
    assert component['supplement']['pinned_package_files_matched'] == 9
    notice = component['supplement']['embedded_notices']['latex2mathml/unimathsymbols.txt']
    assert notice['copyright'] == 'Copyright 2011 Günter Milde'
    assert notice['declared_license'] == 'LPPL-1.3-or-later'
    assert notice['notice_not_updated_for_vendor_changes']
    assert component['supplement']['upstream_commit'] == 'fb724a91658cf41d2fad0192da0845b05446f208'
    assert 'lppl_original_work_and_vendor_change_conditions_unresolved' in component['issues']
    assert report['packages_with_issues'] == 1 and not report['product_licenses_complete']
    assert not component['supplement']['distribution_obligations_reviewed']
    assert not report['archive_provenance_verified']
    assert original == {p.name: p.read_bytes() for p in metadata.iterdir() if p.is_file()}
    for item in component['files']:
        assert tool.sha256((output / item['text_path']).read_bytes()) == item['sha256']
    assert str(metadata.parent) not in (output / 'report.json').read_text(encoding='utf-8')


@pytest.mark.parametrize('kind', ['changed_source', 'missing_source', 'changed_text', 'wrong_length',
                                  'wrong_identity', 'missing_mapping', 'unsafe_source', 'other_package',
                                  'unsafe_text', 'missing_profile'])
def test_supplement_rejects_unmatched_or_unsafe_inputs(supplemented, kind):
    tool, source, config, output, metadata, _, folder, profile = supplemented
    first = next(iter(profile['package_files']))
    if kind == 'changed_source':
        (metadata.parent / first).write_bytes(b'Changed package bytes')
    elif kind == 'missing_source':
        (metadata.parent / first).unlink()
    elif kind == 'changed_text':
        (folder / 'MIT.txt').write_bytes(b'Changed license text')
    elif kind == 'wrong_length':
        profile['license_texts'][0]['bytes'] += 1
    elif kind == 'wrong_identity':
        profile['purl'] = 'pkg:pypi/latex2mathml@3.81.2'
    elif kind == 'missing_mapping':
        profile['package_files'].pop(first)
    elif kind == 'unsafe_source':
        profile['package_files']['latex2mathml/../../outside'] = profile['package_files'].pop(first)
    elif kind == 'other_package':
        profile['package_files']['other/__init__.py'] = profile['package_files'].pop(first)
    elif kind == 'unsafe_text':
        profile['license_texts'][0]['path'] = '../outside'
    (folder / 'provenance.json').write_text(json.dumps(profile), encoding='utf-8')
    if kind == 'missing_profile':
        (folder / 'provenance.json').unlink()
    with pytest.raises((ValueError, OSError)):
        tool.collect(source, config, output)
    assert not (output / 'report.json').exists()


@pytest.mark.parametrize('kind', ['profile', 'source'])
def test_supplement_detects_changes_during_collection(supplemented, monkeypatch, kind):
    tool, source, config, output, metadata, _, folder, profile = supplemented
    original = tool.keep_text

    def changed(*args):
        result = original(*args)
        if kind == 'profile':
            (folder / 'provenance.json').write_text(json.dumps(profile) + '\n', encoding='utf-8')
        else:
            (metadata.parent / next(iter(profile['package_files']))).write_bytes(b'changed')
        return result

    monkeypatch.setattr(tool, 'keep_text', changed)
    with pytest.raises(ValueError, match='changed'):
        tool.collect(source, config, output)
    assert not (output / 'report.json').exists()


def test_supplement_is_not_a_fallback_for_another_version(supplemented):
    tool, source, config, output, metadata, _, _, _ = supplemented
    (source / tool.LOCKS[0]).write_text('latex2mathml==3.81.2\n', encoding='utf-8')
    path = metadata / 'METADATA'
    path.write_text(path.read_text().replace('Version: 3.81.1', 'Version: 3.81.2'), encoding='utf-8')
    report = tool.collect(source, config, output)
    component = report['components']['pkg:pypi/latex2mathml@3.81.2']
    assert component['files'] == [] and component['issues'] == ['license_text_missing']
    assert 'supplement' not in component and report['packages_with_issues'] == 1


def test_supplement_does_not_turn_missing_obligations_into_cli_success(supplemented, monkeypatch):
    tool, source, config, output, *_ = supplemented
    monkeypatch.setattr('sys.argv', ['source_licenses', '--source', str(source), '--package-config', str(config),
                                   '--output', str(output)])
    assert tool.main() == 2
