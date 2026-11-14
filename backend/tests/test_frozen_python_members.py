import base64
import hashlib
import importlib
import importlib.metadata
import json

import pytest
import test_frozen_sbom

collector = test_frozen_sbom.collector
fixture = test_frozen_sbom.fixture


def record_line(name, raw):
    digest = base64.urlsafe_b64encode(hashlib.sha256(raw).digest()).decode().rstrip('=')
    return f'{name},sha256={digest},{len(raw)}\n'


@pytest.fixture
def matched(collector, fixture, monkeypatch):
    payload, source, syft, old_output, _ = fixture
    tool = importlib.import_module('frozen_python_members')
    site = payload.parent / 'site'
    meta = site / 'sample-1.2.3.dist-info'
    meta.mkdir(parents=True)
    metadata = (payload / '_internal/sample-1.2.3.dist-info/METADATA').read_bytes()
    (meta / 'METADATA').write_bytes(metadata)
    vendor = site / 'vendor/dynamic-data.py'
    vendor.parent.mkdir()
    vendor.write_bytes((source / 'backend/study_workbench/__init__.py').read_bytes())
    native = (payload / '_internal/native.pyd').read_bytes()
    (site / 'native.pyd').write_bytes(native)
    data = b'Self-authored opaque package data\n'
    (site / 'data.bin').write_bytes(data)
    (payload / '_internal/data.bin').write_bytes(data)
    (meta / 'RECORD').write_text(record_line('sample-1.2.3.dist-info/METADATA', metadata)
                               + record_line('vendor/dynamic-data.py', vendor.read_bytes())
                               + record_line('native.pyd', native) + record_line('data.bin', data)
                               + 'sample-1.2.3.dist-info/RECORD,,\n', encoding='utf-8')
    unused = site / 'unused-9.0.0.dist-info'
    unused.mkdir()
    (unused / 'METADATA').write_bytes(b'Name: unused\nVersion: 9.0.0\n')
    (unused / 'RECORD').write_text(record_line('unused-9.0.0.dist-info/METADATA',
                                              (unused / 'METADATA').read_bytes()), encoding='utf-8')
    distributions = [importlib.metadata.PathDistribution(p) for p in (meta, unused)]
    monkeypatch.setattr(tool.importlib.metadata, 'distributions', lambda: distributions)
    collector.generate(payload, source, 'a' * 40, collector.sha256((payload / 'study_backend.exe').read_bytes()), syft, old_output)
    return tool, payload, source, old_output / 'coverage.json', payload.parent / 'members', site, distributions


def run(matched):
    tool, payload, source, coverage, output, *_ = matched
    return tool.generate(payload, source, coverage, output)


def test_actual_members_have_source_evidence_without_executing_package_code(matched):
    tool, payload, source, _, output, site, _ = matched
    before = tool.inventory(payload)
    report = run(matched)
    assert report['member_packages'] == ['pkg:pypi/sample@1.2.3']
    assert report['build_packages']['pkg:pypi/unused@9.0.0']['status'] == 'local_metadata_only'
    module = report['modules']['vendor.dynamic-data']
    assert module['status'] == 'matched' and len(module['candidates']) == 1
    evidence = module['candidates'][0]
    assert evidence['source_sha256'] == tool.sha256((site / 'vendor/dynamic-data.py').read_bytes())
    assert evidence['metadata_sha256'] == tool.sha256((site / 'sample-1.2.3.dist-info/METADATA').read_bytes())
    assert evidence['record_sha256'] == tool.sha256((site / 'sample-1.2.3.dist-info/RECORD').read_bytes())
    assert evidence['equivalent_optimization_levels'] == [0, 1, 2]
    assert report['modules']['vendor.namespace'] == {'status': 'unmapped', 'candidates': []}
    assert report['physical_files']['_internal/native.pyd']['status'] == 'matched'
    assert report['physical_files']['_internal/data.bin']['status'] == 'matched'
    assert report['physical_files']['study_backend.exe']['status'] == 'unmapped'
    assert len(report['application_source_compared']) == 1
    assert len(report['unmapped_base_library_zip']) == 1
    assert not report['product_sbom_complete'] and not report['upstream_provenance_verified']
    assert not report['source_head_authenticated'] and before == tool.inventory(payload)
    assert str(site) not in json.dumps(report) and str(source) not in json.dumps(report)
    bom_raw = (output / 'python-members.cdx.json').read_bytes()
    assert report['bom_sha256'] == tool.sha256(bom_raw)
    bom = json.loads(bom_raw)
    assert bom['specVersion'] == '1.6' and len(bom['components']) == 1
    component = bom['components'][0]
    assert component['purl'] == 'pkg:pypi/sample@1.2.3'
    assert {'location': 'study_backend.exe!PYZ.pyz/vendor.dynamic-data'} in component['evidence']['occurrences']
    assert {'location': '_internal/native.pyd'} in component['evidence']['occurrences']
    assert 'hashes' not in component  # A metadata hash is not a whole-package archive hash.
    assert json.loads((output / 'members.json').read_bytes()) == report


@pytest.mark.parametrize('kind', ['code', 'data'])
def test_valid_record_but_different_frozen_bytes_are_not_attributed(matched, kind):
    _, _, _, _, _, site, _ = matched
    path = site / ('vendor/dynamic-data.py' if kind == 'code' else 'data.bin')
    old = path.read_bytes()
    path.write_bytes(b'changed = True\n')
    record = site / 'sample-1.2.3.dist-info/RECORD'
    name = path.relative_to(site).as_posix()
    record.write_text(record.read_text().replace(record_line(name, old), record_line(name, path.read_bytes())), encoding='utf-8')
    report = run(matched)
    entry = report['modules']['vendor.dynamic-data'] if kind == 'code' else report['physical_files']['_internal/data.bin']
    assert entry == {'status': 'unmapped', 'candidates': []}


def test_shared_source_keeps_all_candidates_without_choosing_an_owner(matched):
    tool, payload, source, coverage, _, site, distributions = matched
    lock = source / tool.LOCKS[0]
    lock.write_bytes(lock.read_bytes() + b'other==1.0.0\n')
    original = json.loads(coverage.read_bytes())
    original['source_lock_sha256'][tool.LOCKS[0]] = tool.sha256(lock.read_bytes())
    coverage.write_text(json.dumps(original), encoding='utf-8')
    other = site / 'other-1.0.0.dist-info'
    other.mkdir()
    (other / 'METADATA').write_bytes(b'Name: other\nVersion: 1.0.0\n')
    (other / 'RECORD').write_text(record_line('other-1.0.0.dist-info/METADATA', (other / 'METADATA').read_bytes())
                                + record_line('vendor/dynamic-data.py', (site / 'vendor/dynamic-data.py').read_bytes()), encoding='utf-8')
    distributions.append(importlib.metadata.PathDistribution(other))
    report = run(matched)
    module = report['modules']['vendor.dynamic-data']
    assert module['status'] == 'ambiguous'
    assert {x['purl'] for x in module['candidates']} == {'pkg:pypi/sample@1.2.3', 'pkg:pypi/other@1.0.0'}
    assert 'pkg:pypi/other@1.0.0' not in report['member_packages']
    assert report['physical_files']['_internal/native.pyd']['status'] == 'matched'


@pytest.mark.parametrize('kind', ['hash', 'length', 'duplicate', 'malformed', 'missing', 'duplicate_metadata'])
def test_invalid_build_evidence_never_writes_success(matched, kind):
    _, _, _, _, output, site, _ = matched
    record = site / 'sample-1.2.3.dist-info/RECORD'
    if kind == 'hash':
        (site / 'data.bin').write_bytes(b'tampered')
    elif kind == 'length':
        lines = record.read_text().splitlines()
        lines = [line.rsplit(',', 1)[0] + ',999' if line.startswith('data.bin,') else line for line in lines]
        record.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    elif kind == 'duplicate':
        record.write_text(record.read_text() + record.read_text().splitlines()[0] + '\n', encoding='utf-8')
    elif kind == 'malformed':
        record.write_text('invalid,row\n', encoding='utf-8')
    elif kind == 'missing':
        (site / 'native.pyd').unlink()
    else:
        meta = site / 'sample-1.2.3.dist-info/METADATA'
        meta.write_bytes(meta.read_bytes() + b'Name: sample\n')
    with pytest.raises((ValueError, OSError)):
        run(matched)
    assert not (output / 'members.json').exists() and not (output / 'python-members.cdx.json').exists()


def test_unhashed_and_unsafe_record_paths_are_not_read_or_used(matched):
    _, _, _, _, _, site, _ = matched
    record = site / 'sample-1.2.3.dist-info/RECORD'
    lines = [line for line in record.read_text().splitlines() if not line.startswith('native.pyd,')]
    record.write_text('\n'.join(lines) + '\nnative.pyd,,\n../outside.py,sha256=do-not-read,1\n', encoding='utf-8')
    report = run(matched)
    package = report['build_packages']['pkg:pypi/sample@1.2.3']
    assert package['ignored_unsafe_paths'] == 1 and package['unhashed_candidate_paths'] == ['native.pyd']
    assert report['physical_files']['_internal/native.pyd']['status'] == 'unmapped'


@pytest.mark.parametrize('kind', ['missing', 'wrong_version', 'ambiguous'])
def test_exact_installed_identity_is_required_but_not_projected_to_product(matched, kind):
    _, _, _, _, _, site, distributions = matched
    if kind == 'missing':
        distributions.pop(0)
    elif kind == 'ambiguous':
        distributions.append(distributions[0])
    else:
        meta = site / 'sample-1.2.3.dist-info/METADATA'
        meta.write_text('Name: sample\nVersion: 1.2.4\n', encoding='utf-8')
    report = run(matched)
    assert report['member_packages'] == []
    assert report['build_packages']['pkg:pypi/sample@1.2.3']['status'] == 'missing_or_ambiguous_exact_installed_version'
    assert report['modules']['vendor.dynamic-data']['status'] == 'unmapped'


@pytest.mark.parametrize('kind', ['scope', 'interpreter', 'payload', 'business', 'lock', 'duplicate_json', 'existing', 'nested'])
def test_coverage_and_output_boundaries_are_rechecked(matched, kind):
    tool, payload, source, coverage, output, _, _ = matched
    if kind in {'scope', 'interpreter'}:
        data = json.loads(coverage.read_bytes())
        data['scope' if kind == 'scope' else 'python_version'] = 'wrong'
        coverage.write_text(json.dumps(data), encoding='utf-8')
    elif kind == 'payload':
        (payload / '_internal/data.bin').write_bytes(b'changed')
    elif kind == 'business':
        (source / 'backend/study_workbench/__init__.py').write_bytes(b'changed = True\n')
    elif kind == 'lock':
        path = source / tool.LOCKS[0]
        path.write_bytes(path.read_bytes() + b'changed==1.0\n')
    elif kind == 'duplicate_json':
        coverage.write_text('{"scope":"wrong",' + coverage.read_text()[1:], encoding='utf-8')
    elif kind == 'existing':
        output.mkdir()
        (output / 'kept').write_bytes(b'keep')
    else:
        output = payload / 'nested'
    with pytest.raises((ValueError, OSError)):
        tool.generate(payload, source, coverage, output)
    assert not (output / 'members.json').exists()
    if kind == 'existing':
        assert (output / 'kept').read_bytes() == b'keep'


@pytest.mark.parametrize('constant', ['MAX_RECORD_ROWS', 'MAX_BUILD_BYTES', 'MAX_RECORD_BYTES',
                                     'MAX_REPORT_BYTES', 'MAX_MEMBER_BYTES', 'MAX_FILES'])
def test_input_budgets_refuse_incomplete_success(matched, monkeypatch, constant):
    tool, _, _, _, output, *_ = matched
    monkeypatch.setattr(tool, constant, 1)
    with pytest.raises(ValueError, match='budget|oversized'):
        run(matched)
    assert not (output / 'members.json').exists()


@pytest.mark.parametrize('kind', ['payload', 'coverage', 'lock', 'business', 'build_source', 'build_metadata', 'build_record'])
def test_inputs_changed_during_matching_are_not_reported_as_stable(matched, monkeypatch, kind):
    tool, payload, source, coverage, output, site, _ = matched
    paths = {'payload': payload / '_internal/data.bin', 'coverage': coverage, 'lock': source / tool.LOCKS[0],
             'business': source / 'backend/study_workbench/__init__.py', 'build_source': site / 'vendor/dynamic-data.py',
             'build_metadata': site / 'sample-1.2.3.dist-info/METADATA', 'build_record': site / 'sample-1.2.3.dist-info/RECORD'}
    original = tool.classify

    def changed(*args):
        result = original(*args)
        path = paths[kind]
        path.write_bytes(path.read_bytes() + b'\n')
        return result

    monkeypatch.setattr(tool, 'classify', changed)
    with pytest.raises(ValueError, match='changed'):
        run(matched)
    assert not (output / 'members.json').exists() and not (output / 'python-members.cdx.json').exists()


def test_cli_finite_matching_never_returns_a_release_success_code(matched, monkeypatch, capsys):
    tool, payload, source, coverage, output, *_ = matched
    monkeypatch.setattr('sys.argv', ['frozen_python_members', '--payload', str(payload), '--source', str(source),
                                   '--coverage', str(coverage), '--output', str(output)])
    assert tool.main() == 2
    assert 'remain incomplete' in capsys.readouterr().out


@pytest.mark.parametrize('kind', ['metadata', 'code'])
def test_final_source_recheck_keeps_the_original_input_budget(matched, monkeypatch, kind):
    tool, _, _, _, output, site, _ = matched
    if kind == 'metadata':
        monkeypatch.setattr(tool, 'MAX_RECORD_BYTES', 2048)
        path, size = site / 'sample-1.2.3.dist-info/METADATA', 2049
    else:
        monkeypatch.setattr(tool, 'MAX_MEMBER_BYTES', 512)
        path, size = site / 'vendor/dynamic-data.py', 513
    original = tool.classify

    def grew(*args):
        result = original(*args)
        path.write_bytes(b'x' * size)
        return result

    monkeypatch.setattr(tool, 'classify', grew)
    with pytest.raises(ValueError, match='budget'):
        run(matched)
    assert not (output / 'members.json').exists() and not (output / 'python-members.cdx.json').exists()
