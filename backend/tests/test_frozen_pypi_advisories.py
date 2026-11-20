import importlib
import json
from pathlib import Path

import pytest


@pytest.fixture
def scan(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).parents[2] / 'tools'))
    return importlib.import_module('check_frozen_pypi_advisories')


def test_mapped_inventory_is_bound_to_package_files_and_cdx(scan, tmp_path, monkeypatch):
    payload = tmp_path / 'backend'
    payload.mkdir()
    (payload / 'sample').write_bytes(b'fixed')
    evidence = tmp_path / 'evidence'
    evidence.mkdir()
    monkeypatch.setattr(scan, 'EVIDENCE', evidence)
    member = 'pkg:pypi/sample@1'
    cdx = json.dumps({'components': [dict(purl=member, name='sample', version='1'),
                                     dict(purl='pkg:pypi/tool@2', name='tool', version='2')]}).encode()
    (evidence / 'current-backend-subset.cdx.json').write_bytes(cdx)
    fingerprint = scan.sha256(json.dumps(scan.inventory(payload), sort_keys=True).encode())
    summary = dict(payload=dict(fingerprint=fingerprint, files=1), selected_cdx=dict(sha256=scan.sha256(cdx)),
                   local_members=dict(packages=[member]))
    source = evidence / 'current-backend-sources-summary.json'
    source.write_text(json.dumps(summary))
    digest, members = scan.read_members(payload)
    assert digest == fingerprint and [item['purl'] for item in members] == [member]
    summary['local_members']['packages'].append(member)
    source.write_text(json.dumps(summary))
    with pytest.raises(ValueError, match='duplicate'):
        scan.read_members(payload)
    (payload / 'sample').write_bytes(b'changed')
    with pytest.raises(ValueError, match='Payload'):
        scan.read_members(payload)
    (evidence / 'current-backend-subset.cdx.json').write_bytes(b'{}')
    with pytest.raises(ValueError, match='CycloneDX'):
        scan.read_members(payload)


@pytest.mark.parametrize('case,expected', [('empty', 3), ('match', 2), ('changed', 1), ('unavailable', 1)])
def test_query_exit_codes_and_recorded_failures(scan, tmp_path, monkeypatch, case, expected):
    payload = tmp_path / 'backend'
    payload.mkdir()
    output = tmp_path / 'query'
    current = ['initial']
    monkeypatch.setattr(scan, 'read_members', lambda path: (current[0], [dict(purl='pkg:pypi/sample@1', matches={})]))

    def lookup(rows, output, evidence):
        if case == 'match':
            rows[0]['matches']['GHSA-example'] = 'modified'
        if case == 'changed':
            current[0] = 'changed'
        if case == 'unavailable':
            raise OSError('unavailable')

    monkeypatch.setattr(scan, 'query_packages', lookup)
    assert scan.scan(payload, output) == expected
    saved = json.loads((output / 'report.json').read_bytes())
    assert saved['queries_complete'] is (expected != 1)
    assert saved['product_check_complete'] is False
    with pytest.raises(FileExistsError):
        scan.scan(payload, output)
    with pytest.raises(ValueError, match='outside'):
        scan.scan(payload, payload / 'output')
