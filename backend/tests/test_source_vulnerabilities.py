import copy
import importlib
import io
import json
from datetime import UTC, datetime, timedelta
from email.utils import format_datetime
from pathlib import Path
from urllib.error import HTTPError

import pytest
import yaml

MODIFIED = '2026-01-02T03:04:05.123456Z'
IDENTIFIER = 'GHSA-aaaa-bbbb-cccc'


@pytest.fixture
def vuln(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).parents[2] / 'tools'))
    return importlib.import_module('source_vulnerabilities')


@pytest.fixture
def source(vuln, tmp_path):
    root = tmp_path / 'source'
    packages = {
        'collection': {'source': 'hosted', 'version': '1.19.1+2',
                       'description': {'name': 'collection', 'url': 'https://pub.dev', 'sha256': 'a' * 64}},
        'glass': {'source': 'git', 'version': '0.1.0',
                  'description': {'url': 'https://example.test/private.git', 'path': '.', 'resolved-ref': 'b' * 40}},
        'flutter': {'source': 'sdk', 'version': '0.0.0', 'description': 'flutter'},
    }
    for name, data in zip(vuln.LOCKS, [b'PyYAML==6.0.3\n', yaml.safe_dump({'packages': packages}).encode()], strict=True):
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    return root


def item():
    return {'purl': 'pkg:pypi/pyyaml@6.0.3', 'name': 'pyyaml', 'ecosystem': 'PyPI', 'version': '6.0.3',
            'matches': {}, 'query_status': 'unknown'}


def advisory():
    return {'id': IDENTIFIER, 'modified': MODIFIED, 'aliases': ['CVE-2026-0000'],
            'affected': [{'package': {'name': 'PyYAML', 'ecosystem': 'PyPI'},
                          'ranges': [{'type': 'ECOSYSTEM', 'events': [{'introduced': '0'}, {'fixed': '7.0.0'}]}]}]}


def fake_exchange(monkeypatch, vuln, responses):
    calls = []
    def exchange(output, evidence, endpoint, payload=None):
        calls.append((endpoint, copy.deepcopy(payload)))
        response = responses[len(calls) - 1]
        if isinstance(response, Exception):
            raise response
        return copy.deepcopy(response)
    monkeypatch.setattr(vuln, 'exchange', exchange)
    return calls


def test_scan_only_sends_public_names_versions_and_keeps_all_unknowns(vuln, source, tmp_path, monkeypatch):
    calls = fake_exchange(monkeypatch, vuln, [{'results': [{}, {}]}])
    result = vuln.scan(source, tmp_path / 'result')
    assert calls == [('querybatch', {'queries': [
        {'package': {'name': 'collection', 'ecosystem': 'Pub'}, 'version': '1.19.1+2'},
        {'package': {'name': 'pyyaml', 'ecosystem': 'PyPI'}, 'version': '6.0.3'}]})]
    assert result['queries_complete'] and result['exit_code'] == 3
    assert not result['product_check_complete'] and result['database_snapshot'] is None
    assert result['database_freshness'] == 'unknown_live_api'
    assert {x['kind'] for x in result['excluded']} == {'sdk', 'git'}
    assert all(x['query_status'] == 'no_advisories_returned_mapping_unconfirmed' for x in result['components'])
    assert result['source_lock_sha256'] == {n: vuln.sha256((source / n).read_bytes()) for n in vuln.LOCKS}
    assert json.loads((tmp_path / 'result/report.json').read_text()) == result


def test_scan_retains_findings_and_fixed_ranges_without_upgrading(vuln, source, tmp_path, monkeypatch):
    before = {n: (source / n).read_bytes() for n in vuln.LOCKS}
    fake_exchange(monkeypatch, vuln, [{'results': [{}, {'vulns': [{'id': IDENTIFIER, 'modified': MODIFIED}]}]}, advisory()])
    result = vuln.scan(source, tmp_path / 'result')
    found = result['components'][1]['advisories'][0]
    assert result['queries_complete'] and result['exit_code'] == 2
    assert found['state'] == 'osv_match_requires_triage'
    assert found['affected'][0]['ranges'][0]['events'][-1] == {'fixed': '7.0.0'}
    assert before == {n: (source / n).read_bytes() for n in vuln.LOCKS}


@pytest.mark.parametrize('response', [{}, {'results': []}, {'results': [None]}, {'results': [{'error': 'unsupported'}]},
                                      {'results': [{'vulns': {}}]}, {'results': [{'vulns': [{'id': '../escape'}]}]},
                                      {'results': [{'vulns': [{'id': IDENTIFIER, 'modified': 'bad'}]}]},
                                      {'results': [{'next_page_token': 123}]}])
def test_malformed_batch_is_not_a_clean_result(vuln, tmp_path, monkeypatch, response):
    fake_exchange(monkeypatch, vuln, [response])
    with pytest.raises(ValueError):
        vuln.query_packages([item()], tmp_path, [])


def test_pagination_queries_only_pending_identities(vuln, tmp_path, monkeypatch):
    first, second = item(), {**item(), 'purl': 'other', 'name': 'other'}
    calls = fake_exchange(monkeypatch, vuln, [{'results': [{'next_page_token': 'opaque'}, {}]},
                                             {'results': [{'vulns': [{'id': IDENTIFIER, 'modified': MODIFIED}]}]}])
    vuln.query_packages([first, second], tmp_path, [])
    assert len(calls[1][1]['queries']) == 1 and calls[1][1]['queries'][0]['page_token'] == 'opaque'
    assert first['matches'] == {IDENTIFIER: MODIFIED} and second['matches'] == {}


@pytest.mark.parametrize('limit', [False, True])
def test_repeated_or_excessive_pagination_fails(vuln, tmp_path, monkeypatch, limit):
    fake_exchange(monkeypatch, vuln, [{'results': [{'next_page_token': 'same'}]}] * 2)
    if limit:
        monkeypatch.setattr(vuln, 'MAX_PAGES', 1)
    with pytest.raises(ValueError, match='pagination'):
        vuln.query_packages([item()], tmp_path, [])


def test_duplicate_advisory_revision_change_is_unknown(vuln, tmp_path, monkeypatch):
    fake_exchange(monkeypatch, vuln, [
        {'results': [{'vulns': [{'id': IDENTIFIER, 'modified': MODIFIED}], 'next_page_token': 'next'}]},
        {'results': [{'vulns': [{'id': IDENTIFIER, 'modified': '2026-01-03T00:00:00Z'}]}]}])
    with pytest.raises(ValueError, match='changed'):
        vuln.query_packages([item()], tmp_path, [])


@pytest.mark.parametrize('change,state', [('none', 'osv_match_requires_triage'), ('nanos', 'osv_match_requires_triage'),
                                         ('modified', 'changed_since_query_unknown'), ('package', 'package_mapping_missing'),
                                         ('ecosystem', 'package_mapping_missing'), ('withdrawn', 'withdrawn')])
def test_detail_mapping_revision_precision_and_withdrawal(vuln, change, state):
    value = advisory()
    if change == 'nanos':
        value['modified'] = MODIFIED.replace('456Z', '456789Z')
    elif change == 'modified':
        value['modified'] = '2026-01-03T00:00:00Z'
    elif change in {'package', 'ecosystem'}:
        value['affected'][0]['package']['name' if change == 'package' else 'ecosystem'] = 'wrong'
    elif change == 'withdrawn':
        value['withdrawn'] = '2026-01-03T00:00:00Z'
    result = vuln.advisory_for({**item(), 'matches': {IDENTIFIER: MODIFIED}}, IDENTIFIER, value)
    assert result['state'] == state and result['modified'] == value['modified']
    assert result['query_modified'] == MODIFIED and result['modified_comparison_precision'] == 'microseconds'


@pytest.mark.parametrize('value', [{'id': 'wrong'}, {'id': IDENTIFIER, 'modified': '2026-01-01'},
                                  {'id': IDENTIFIER, 'modified': MODIFIED, 'affected': None},
                                  {'id': IDENTIFIER, 'modified': MODIFIED, 'affected': [None]}])
def test_invalid_detail_cannot_confirm_match(vuln, value):
    with pytest.raises(ValueError):
        vuln.advisory_for({**item(), 'matches': {IDENTIFIER: MODIFIED}}, IDENTIFIER, value)


@pytest.mark.parametrize('failure', ['network', 'malformed', 'source_changed'])
def test_failed_scan_preserves_evidence_and_incomplete_report(vuln, source, tmp_path, monkeypatch, failure):
    if failure == 'source_changed':
        def change(output, evidence, endpoint, payload):
            (source / vuln.LOCKS[0]).write_bytes(b'PyYAML==6.0.2\n')
            return {'results': [{}, {}]}
        monkeypatch.setattr(vuln, 'exchange', change)
    else:
        fake_exchange(monkeypatch, vuln, [OSError('offline') if failure == 'network' else {}])
    result = vuln.scan(source, tmp_path / 'result')
    assert result['exit_code'] == 1 and not result['queries_complete'] and result['error']
    assert (tmp_path / 'result/report.json').exists()


def test_existing_output_is_not_overwritten(vuln, source, tmp_path, monkeypatch):
    calls = fake_exchange(monkeypatch, vuln, [])
    output = tmp_path / 'result'
    output.mkdir()
    (output / 'keep').write_bytes(b'keep')
    with pytest.raises(FileExistsError):
        vuln.scan(source, output)
    assert (output / 'keep').read_bytes() == b'keep' and calls == []


def test_private_python_url_rejected_before_network(vuln, source, tmp_path, monkeypatch):
    calls = fake_exchange(monkeypatch, vuln, [])
    (source / vuln.LOCKS[0]).write_bytes(b'private @ https://user:secret@example.test/file.whl\n')
    with pytest.raises(ValueError):
        vuln.scan(source, tmp_path / 'result')
    assert calls == [] and not (tmp_path / 'result').exists()


def response_opener(monkeypatch, vuln, raw, status=200, date=None, error=False):
    class Response(io.BytesIO):
        pass
    response = Response(raw)
    response.status = status
    response.headers = {'Date': date}
    calls = []
    class Opener:
        def open(self, request, timeout):
            calls.append((request, timeout))
            if error:
                raise HTTPError(request.full_url, status, 'test', response.headers, response)
            return response
    def build(*handlers):
        assert handlers[0].proxies == {} and isinstance(handlers[1], vuln.NoRedirect)
        return Opener()
    monkeypatch.setattr(vuln, 'build_opener', build)
    return calls


def test_wire_evidence_hashes_endpoint_and_unknown_date(vuln, tmp_path, monkeypatch):
    calls = response_opener(monkeypatch, vuln, b'{"results": []}')
    evidence = []
    assert vuln.exchange(tmp_path, evidence, 'querybatch', {'queries': []}) == {'results': []}
    request, timeout = calls[0]
    assert request.full_url == 'https://api.osv.dev/v1/querybatch' and timeout == 30
    assert set(dict(request.header_items())) == {'Content-type', 'User-agent'}
    row = evidence[0]
    assert row['request_sha256'] == vuln.sha256((tmp_path / '0000-request.json').read_bytes())
    assert row['response_sha256'] == vuln.sha256((tmp_path / '0000-response.json').read_bytes())
    assert row['response_freshness'] == 'unknown' and row['finished_at']


@pytest.mark.parametrize('mode', ['http', 'oversize', 'duplicate', 'invalid_json', 'wrong_type', 'stale', 'future'])
def test_untrusted_http_fails_and_preserves_raw_evidence(vuln, tmp_path, monkeypatch, mode):
    raw = {'duplicate': b'{"results": [], "results": []}', 'invalid_json': b'not-json',
           'wrong_type': b'[]'}.get(mode, b'{"results": []}')
    date = format_datetime(datetime.now(UTC) + timedelta(days=-2 if mode == 'stale' else 2 if mode == 'future' else 0))
    if mode == 'oversize':
        monkeypatch.setattr(vuln, 'MAX_RESPONSE', 5)
    response_opener(monkeypatch, vuln, raw, 503 if mode == 'http' else 200, date, error=mode == 'http')
    evidence = []
    with pytest.raises(ValueError):
        vuln.exchange(tmp_path, evidence, 'querybatch', {'queries': []})
    assert evidence[0]['error_type'] and evidence[0]['finished_at']
    assert (tmp_path / '0000-response.json').exists()


@pytest.mark.parametrize('endpoint', ['https://evil.test', '../escape', 'vulns/../../escape', 'vulns/name?secret'])
def test_endpoint_injection_never_reaches_network(vuln, tmp_path, monkeypatch, endpoint):
    calls = response_opener(monkeypatch, vuln, b'{}')
    with pytest.raises(ValueError):
        vuln.exchange(tmp_path, [], endpoint)
    assert calls == [] and list(tmp_path.iterdir()) == []


def test_redirect_is_refused(vuln):
    with pytest.raises(ValueError, match='redirect'):
        vuln.NoRedirect().redirect_request(None, None, 302, '', {}, 'https://elsewhere.test')
