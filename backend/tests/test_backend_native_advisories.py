import hashlib
import json
from pathlib import Path

import pytest


@pytest.fixture
def checker(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).parents[2] / 'tools'))
    import check_backend_native_advisories
    return check_backend_native_advisories


def entry(number, low, high):
    cve = f'CVE-2026-{number}'
    return f'''<a href="#{cve}"><h2 id="{cve}">{cve}</h2></a><div>
    <div><span>Severity</span></div><div>Low</div>
    <div><span>Affected</span></div><div><ul><li>from {low} before {high}</li></ul></div></div>'''


def test_vendor_index_numeric_exclusive_ranges_and_unknown_schema(checker):
    raw = '<main>' + entry(1000, '3.5.0', '3.5.9') + entry(1001, '3.5.9', '3.5.10') + '</main>'
    count, matches = checker.vendor_matches(raw.encode(), '3.5.9')
    assert count == 2 and matches == {'CVE-2026-1001': {
        'affected_from': '3.5.9', 'affected_before': '3.5.10', 'severity': 'Low'}}
    for invalid in [raw.replace('3.5.10','unknown'), raw.replace('>Affected<','>Other<'),
                    raw.replace('1001','1000'), raw.replace('from 3.5.0','after 3.5.0')]:
        with pytest.raises(ValueError):
            checker.vendor_matches(invalid.encode(), '3.5.9')


def test_osv_records_tag_and_commit_independently_and_rejects_partial_pages(checker, monkeypatch, tmp_path):
    match = {'id': 'CVE-2026-1000', 'modified': '2026-11-17T12:00:00Z'}
    results = [{'vulns': [match]}, {}, {}, {}]
    def exchange(output, evidence, method, payload):
        assert output == tmp_path and method == 'querybatch'
        assert payload['queries'][0] == {'commit': checker.UPSTREAM['openssl'][3]}
        assert payload['queries'][1]['version'] == 'openssl-3.5.9'
        return {'results': results}
    monkeypatch.setattr(checker, 'exchange', exchange)
    got = checker.osv_matches(tmp_path, [])
    assert got['openssl'] == {'commit': {match['id']: match['modified']}, 'tag': {}}
    assert got['libffi'] == {'commit': {}, 'tag': {}}
    results[0] = {'next_page_token': 'more'}
    with pytest.raises(ValueError):
        checker.osv_matches(tmp_path, [])
    results.pop()
    with pytest.raises(ValueError):
        checker.osv_matches(tmp_path, [])


def test_changed_binary_fails_before_network_and_prior_evidence_is_preserved(checker, tmp_path, monkeypatch):
    backend = tmp_path / 'backend'
    backend.mkdir()
    fixture = b'synthetic binary fixture'
    path = backend / 'sample.dll'
    path.write_bytes(fixture)
    digest = hashlib.sha256(fixture).hexdigest()
    member = dict(payload_path=path.name, bytes=len(fixture), sha256=digest)
    raw = json.dumps({'binary_archives': [dict(name='openssl', recipe_declared_version='3.5.9',
                                                members=[member])]}).encode()
    profile = tmp_path / 'profile.json'
    profile.write_bytes(raw)
    monkeypatch.setattr(checker, 'PROFILE', profile)
    monkeypatch.setattr(checker, 'PROFILE_SHA256', hashlib.sha256(raw).hexdigest())
    assert checker.inventory(backend) == {'sample.dll': digest}
    monkeypatch.setattr(checker, 'osv_matches', lambda *_: pytest.fail('queried before checking binary'))
    path.write_bytes(fixture[:-1] + b'?')
    output = tmp_path / 'report'
    assert checker.scan(backend, output) == 1
    original = (output / 'report.json').read_bytes()
    assert not json.loads(original)['queries_complete']
    with pytest.raises(FileExistsError):
        checker.scan(backend, output)
    with pytest.raises(ValueError):
        checker.scan(backend, backend / 'report')
    assert (output / 'report.json').read_bytes() == original


def test_offline_replay_keeps_vendor_and_osv_distinct(checker, tmp_path, monkeypatch):
    snapshot = tmp_path / 'snapshot'
    snapshot.mkdir()
    (snapshot / '0000-request.json').write_text(json.dumps(checker.osv_queries()), encoding='utf8')
    (snapshot / '0000-response.json').write_bytes(b'{"results":[{},{},{},{}]}')
    (snapshot / 'openssl-3.5.html').write_text(entry(1001, '3.5.0', '3.5.10'), encoding='utf8')
    monkeypatch.setattr(checker, 'inventory', lambda _: {'synthetic': 'test'})
    monkeypatch.setattr(checker, 'exchange', lambda *_: pytest.fail('unexpected OSV network access'))
    monkeypatch.setattr(checker, 'urlopen', lambda *_: pytest.fail('unexpected OpenSSL network access'))
    backend = tmp_path / 'backend'
    backend.mkdir()
    output = tmp_path / 'output'
    assert checker.scan(backend, output, snapshot) == 2
    report = json.loads((output / 'report.json').read_bytes())
    assert report['queries_complete'] and report['observation'] == 'caller_supplied_snapshots'
    assert report['vendor']['matching'].keys() == {'CVE-2026-1001'}
    assert report['osv']['openssl'] == {'commit': {}, 'tag': {}}
    assert not report['product_check_complete'] and not report['product_reachability_verified']
    (snapshot / '0000-request.json').write_bytes(b'{"queries":[]}')
    assert checker.scan(backend, tmp_path / 'failed', snapshot) == 1
