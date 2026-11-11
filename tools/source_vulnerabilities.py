"""Query public source-lock identities through OSV v1; never certify product safety."""

import argparse
import json
import re
import sys
from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

import yaml
from packaging.utils import canonicalize_name
from source_sbom import LOCKS, lock_inventory, no_links, read_lock, sha256

VERSION = '1.0'
API = 'https://api.osv.dev/v1/'
MAX_RESPONSE = 8 * 1024 * 1024
MAX_PAGES = 8
LIMITATIONS = [
    'Public PyPI/pub.dev lock identities only; includes development/build/cross-platform packages.',
    'Git and SDK identities are not queried; installed/native/frozen/Office/Java payloads are not covered.',
    'No returned advisory does not prove registry mapping, database coverage or absence of vulnerabilities.',
    'OSV live API has no pinned database snapshot or freshness guarantee; query evidence is a dated observation.',
    'OSV matches are not reachability/exploitability determinations; fixes require separate compatibility tests.',
]


def now():
    return datetime.now(UTC).isoformat()


def unique_object(pairs):
    value = dict(pairs)
    if len(value) != len(pairs):
        raise ValueError('Duplicate response key')
    return value


def timestamp(value):
    if not isinstance(value, str):
        raise ValueError('Missing advisory timestamp')
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        raise ValueError('Timestamp requires timezone')
    return parsed


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError('OSV redirect refused')


def exchange(output, evidence, endpoint, payload=None):
    """Save bounded wire evidence before interpreting it; credentials/proxies are not used."""
    if endpoint != 'querybatch' and not re.fullmatch(r'vulns/[A-Za-z0-9][A-Za-z0-9:_.-]{0,199}', endpoint):
        raise ValueError('Invalid OSV endpoint')
    body = json.dumps(payload, sort_keys=True, separators=(',', ':')).encode() if payload is not None else None
    prefix = f'{len(evidence):04d}'
    row = {'endpoint': endpoint, 'started_at': now(), 'request_sha256': sha256(body or b'')}
    evidence.append(row)
    (output / (prefix + '-request.json')).write_bytes(body or b'')
    request = Request(API + endpoint, data=body, headers={'Content-Type': 'application/json',
                                                       'User-Agent': 'StudyWorkbench-source-vulns/' + VERSION})
    try:
        try:
            response = build_opener(ProxyHandler({}), NoRedirect()).open(request, timeout=30)
        except HTTPError as exc:
            response = exc
        with response:
            raw = response.read(MAX_RESPONSE + 1)
            row.update(http_status=response.status, http_date=response.headers.get('Date'),
                       response_sha256=sha256(raw), response_bytes=len(raw))
        (output / (prefix + '-response.json')).write_bytes(raw)
        if len(raw) > MAX_RESPONSE:
            raise ValueError('Response exceeds budget (saved prefix only)')
        if row['http_status'] != 200:
            raise ValueError('OSV HTTP request failed')
        date = parsedate_to_datetime(row['http_date']) if row['http_date'] else None
        row['response_freshness'] = 'unknown' if date is None else 'current'
        if date is not None and (date.tzinfo is None or not -timedelta(minutes=5) <= datetime.now(UTC) - date <= timedelta(days=1)):
            row['response_freshness'] = 'stale_or_clock_mismatch'
            raise ValueError('OSV response Date is stale or inconsistent')
        value = json.loads(raw, object_pairs_hook=unique_object)
        if not isinstance(value, dict):
            raise ValueError('Expected OSV response object')
        return value
    except (OSError, ValueError, TypeError) as exc:
        row['error_type'] = type(exc).__name__
        raise
    finally:
        row['finished_at'] = now()


def query_packages(components, output, evidence):
    pending = [(item, None) for item in components]
    seen = {item['purl']: set() for item in components}
    for _ in range(MAX_PAGES):
        queries = [{'package': {'name': item['name'], 'ecosystem': item['ecosystem']},
                    'version': item['version'], **({'page_token': token} if token else {})} for item, token in pending]
        value = exchange(output, evidence, 'querybatch', {'queries': queries})
        results = value.get('results')
        if not isinstance(results, list) or len(results) != len(pending):
            raise ValueError('OSV batch count/order cannot be mapped')
        following = []
        for (item, _), result in zip(pending, results, strict=True):
            if not isinstance(result, dict) or set(result) - {'vulns', 'next_page_token'}:
                raise ValueError('Unexpected OSV query result')
            vulns = result.get('vulns', [])
            if not isinstance(vulns, list):
                raise ValueError('Invalid OSV matches')
            for vuln in vulns:
                if (not isinstance(vuln, dict) or not isinstance(vuln.get('id'), str)
                        or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9:_.-]{0,199}', vuln['id'])):
                    raise ValueError('Invalid advisory identifier')
                timestamp(vuln.get('modified'))
                old = item['matches'].get(vuln['id'])
                if old is not None and old != vuln['modified']:
                    raise ValueError('Advisory changed during paginated query')
                item['matches'][vuln['id']] = vuln['modified']
            token = result.get('next_page_token')
            if token is not None and (not isinstance(token, str) or len(token) > 4096):
                raise ValueError('Invalid pagination token')
            if token:
                if token in seen[item['purl']]:
                    raise ValueError('Repeated pagination token')
                seen[item['purl']].add(token)
                following.append((item, token))
            else:
                item['query_status'] = 'matched' if item['matches'] else 'no_advisories_returned_mapping_unconfirmed'
        if not following:
            return
        pending = following
    raise ValueError('OSV pagination budget exhausted')


def advisory_for(item, identifier, advisory):
    if advisory.get('id') != identifier:
        raise ValueError('OSV returned the wrong advisory')
    timestamp(advisory.get('modified'))
    affected = advisory.get('affected')
    if not isinstance(affected, list) or not all(isinstance(a, dict) for a in affected):
        raise ValueError('Invalid affected packages')
    matching = []
    for entry in affected:
        package = entry.get('package', {})
        if not isinstance(package, dict):
            raise ValueError('Invalid advisory package')
        name = package.get('name')
        if item['ecosystem'] == 'PyPI' and isinstance(name, str):
            name = canonicalize_name(name)
        if package.get('ecosystem') == item['ecosystem'] and name == item['name']:
            matching.append(entry)
    state = 'osv_match_requires_triage'
    if advisory.get('withdrawn'):
        timestamp(advisory['withdrawn'])
        state = 'withdrawn'
    elif timestamp(advisory['modified']) != timestamp(item['matches'][identifier]):
        state = 'changed_since_query_unknown'
    elif not matching:
        state = 'package_mapping_missing'
    return {'id': identifier, 'state': state, 'modified': advisory['modified'],
            'query_modified': item['matches'][identifier], 'modified_comparison_precision': 'microseconds',
            'aliases': advisory.get('aliases', []), 'summary': advisory.get('summary'),
            'severity': advisory.get('severity', []), 'database_specific': advisory.get('database_specific', {}),
            'affected': matching, 'references': advisory.get('references', []),
            'published': advisory.get('published'), 'withdrawn': advisory.get('withdrawn')}


def scan(source, output):
    source, output = source.absolute(), output.absolute()
    raw = {name: read_lock(source / name) for name in LOCKS}
    inventory, sdk, _ = lock_inventory(raw)
    components, excluded = [], [{'name': x['name'], 'reason': x['reason'], 'kind': 'sdk'} for x in sdk]
    for purl, identity in sorted(inventory.items()):
        if '?vcs_url=' in purl:
            excluded.append({'name': identity['name'], 'purl': purl, 'kind': 'git',
                             'reason': 'Git identity is not a pub.dev release; no repository/commit query is sent'})
        else:
            components.append({**identity, 'purl': purl, 'ecosystem': 'PyPI' if purl.startswith('pkg:pypi/') else 'Pub',
                               'query_status': 'unknown', 'matches': {}, 'advisories': []})
    if not components or len(components) > 1000:
        raise ValueError('Source package count outside query budget')
    no_links(output.parent)
    output.mkdir(exist_ok=False)
    report = {'scope': 'source-locks-only', 'tool_version': VERSION, 'api': API, 'python_version': sys.version,
              'tool_sha256': {name: sha256(Path(__file__).with_name(name).read_bytes())
                              for name in ('source_vulnerabilities.py', 'source_sbom.py')},
              'source_lock_sha256': {name: sha256(data) for name, data in raw.items()},
              'started_at': now(), 'database_snapshot': None, 'database_freshness': 'unknown_live_api',
              'product_check_complete': False, 'queries_complete': False, 'components': components,
              'excluded': excluded, 'evidence': [], 'limitations': LIMITATIONS}
    exit_code = 1
    try:
        query_packages(components, output, report['evidence'])
        advisories = {}
        for item in components:
            for identifier in sorted(item['matches']):
                if identifier not in advisories:
                    if len(advisories) >= 1000:
                        raise ValueError('Advisory budget exhausted')
                    advisories[identifier] = exchange(output, report['evidence'], 'vulns/' + identifier)
                item['advisories'].append(advisory_for(item, identifier, advisories[identifier]))
        if raw != {name: read_lock(source / name) for name in LOCKS}:
            raise ValueError('Source locks changed during query')
        report['queries_complete'] = True
        exit_code = 2 if any(x['matches'] for x in components) else 3
    except (OSError, ValueError, TypeError) as exc:
        report['error'] = str(exc)
    report['finished_at'] = now()
    report['exit_code'] = exit_code
    (output / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--output', type=Path, required=True, help='New directory; parent must exist')
    args = parser.parse_args()
    try:
        report = scan(args.source, args.output)
    except (OSError, ValueError, TypeError, yaml.YAMLError) as exc:
        parser.exit(1, f'Source query failed: {exc}\n')
    print(json.dumps({'queries_complete': report['queries_complete'], 'packages': len(report['components']),
                      'matched_packages': sum(bool(x['matches']) for x in report['components']),
                      'excluded': len(report['excluded']), 'product_check_complete': False,
                      'error': report.get('error'), 'exit_code': report['exit_code']}))
    return report['exit_code']


if __name__ == '__main__':
    sys.exit(main())
