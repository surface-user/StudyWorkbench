"""Compare three identified backend DLLs with upstream versions and public advisories."""
import argparse
import json
import re
import stat
from pathlib import Path
from urllib.request import Request, urlopen

from lxml import etree, html
from source_sbom import no_links, sha256
from source_vulnerabilities import exchange, now, timestamp, unique_object

PROFILE = Path(__file__).resolve().parents[1] / 'packaging/licenses/cpython-native-3.13.17/provenance.json'
PROFILE_SHA256 = 'bf378e5a38ae40dc6b3961ebda842d5ee6bcec963605ce3c45436dfc991c20e3'
VENDOR = 'https://openssl-library.org/news/vulnerabilities-3.5/'
UPSTREAM = {
    'openssl': ('3.5.9', 'openssl/openssl', 'openssl-3.5.9', '45e844fa2a14ec92d146bd8f5778ac130b6625fb'),
    'libffi': ('3.4.4', 'libffi/libffi', 'v3.4.4', 'f24180be1367f942824365b131ae894b9c769c7d'),
}


def inventory(backend):
    raw = PROFILE.read_bytes()
    if sha256(raw) != PROFILE_SHA256:
        raise ValueError('Native provenance profile changed')
    files = {}
    for archive in json.loads(raw)['binary_archives']:
        name = archive['name']
        if archive['recipe_declared_version'] != UPSTREAM[name][0]:
            raise ValueError('Upstream version mismatch')
        for member in archive['members']:
            if 'payload_path' not in member:
                continue
            relative = member['payload_path']
            path = backend / relative
            no_links(path)
            info = path.stat()
            if not stat.S_ISREG(info.st_mode) or info.st_size != member['bytes']:
                raise ValueError('Native binary type or size changed')
            with path.open('rb') as stream:
                digest = sha256(stream.read(member['bytes'] + 1))
            if digest != member['sha256']:
                raise ValueError('Native binary SHA256 changed')
            files[relative] = digest
    return files


def vendor_matches(raw, version):
    document = html.fromstring(raw, parser=html.HTMLParser(no_network=True))
    headings = document.xpath('//h2[starts-with(@id,"CVE-")]')
    anchors = document.xpath('//a[starts-with(@href,"#CVE-")]/@href')
    ids = {h.get('id') for h in headings}
    if not ids or len(ids) != len(headings) or ids != {a[1:] for a in anchors}:
        raise ValueError('Incomplete or ambiguous OpenSSL advisory index')
    matches = {}
    current = tuple(map(int, version.split('.')))
    if current[:2] != (3, 5):
        raise ValueError('Expected OpenSSL 3.5.x')
    for heading in headings:
        identifier = heading.get('id')
        if not re.fullmatch(r'CVE-\d{4}-\d{4,}', identifier) or heading.text_content().strip() != identifier:
            raise ValueError('Invalid OpenSSL advisory identity')
        section = heading.xpath('../following-sibling::*[1]')[0]
        field = './div[span[normalize-space(.)=$label]]/following-sibling::div[1]'
        ranges = section.xpath(field + '/ul/li', label='Affected')
        severity = section.xpath(field, label='Severity')
        relevant = [r.text_content().strip() for r in ranges if '3.5.' in r.text_content()]
        if not relevant or len(severity) != 1:
            raise ValueError('OpenSSL branch range or severity missing')
        for row in relevant:
            bounds = re.fullmatch(r'from (3\.5\.\d+) before (3\.5\.\d+)', row)
            if not bounds:
                raise ValueError('Unknown OpenSSL version range')
            low, high = (tuple(map(int, v.split('.'))) for v in bounds.groups())
            if low >= high:
                raise ValueError('Invalid OpenSSL version range')
            if low <= current < high:
                matches[identifier] = dict(affected_from=bounds[1], affected_before=bounds[2],
                                           severity=severity[0].text_content().strip())
    return len(ids), matches


def osv_queries():
    queries = []
    for _, repo, tag, commit in UPSTREAM.values():
        queries.extend([{'commit': commit}, {'package': {'ecosystem': 'GIT', 'name': f'https://github.com/{repo}.git'},
                                             'version': tag}])
    return {'queries': queries}


def osv_matches(output, evidence):
    return interpret_osv(exchange(output, evidence, 'querybatch', osv_queries()))


def interpret_osv(response):
    results = response.get('results')
    queries = osv_queries()['queries']
    if not isinstance(results, list) or len(results) != len(queries):
        raise ValueError('Incomplete OSV query batch')
    observed = {}
    for (name, mode), result in zip(((n, m) for n in UPSTREAM for m in ('commit', 'tag')), results, strict=True):
        if not isinstance(result, dict) or set(result) - {'vulns'} or not isinstance(result.get('vulns', []), list):
            raise ValueError('Unexpected or paginated OSV response; incomplete check')
        matches = {}
        for item in result.get('vulns', []):
            identifier = item['id']
            if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9:_.-]{0,199}', identifier) or identifier in matches:
                raise ValueError('Invalid OSV match identity')
            timestamp(item['modified'])
            matches[identifier] = item['modified']
        observed.setdefault(name, {})[mode] = matches
    return observed


def saved_bytes(directory, filename, limit):
    path = directory / filename
    no_links(path)
    if not stat.S_ISREG(path.stat().st_mode):
        raise ValueError('Expected a regular evidence file')
    with path.open('rb') as stream:
        raw = stream.read(limit + 1)
    if len(raw) > limit:
        raise ValueError('Evidence exceeds size limit')
    return raw


def scan(backend, output, snapshot=None):
    backend, output = backend.absolute(), output.absolute()
    no_links(backend)
    no_links(output.parent)
    if output.resolve().is_relative_to(backend.resolve()):
        raise ValueError('Output must be outside the backend')
    output.mkdir()
    report = dict(started_at=now(), profile_sha256=PROFILE_SHA256, transport=[], queries_complete=False,
                  observation='caller_supplied_snapshots' if snapshot else 'live',
                  product_check_complete=False, product_reachability_verified=False, database_snapshot_pinned=False)
    code = 1
    try:
        report['files'] = inventory(backend)
        report['upstream'] = {name: dict(version=version, repository=repo, tag=tag, commit=commit)
                              for name, (version, repo, tag, commit) in UPSTREAM.items()}
        if snapshot is None:
            report['osv'] = osv_matches(output, report['transport'])
            with urlopen(Request(VENDOR, headers={'User-Agent': 'StudyWorkbench-release-check'}), timeout=30) as response:
                if response.status != 200 or response.geturl() != VENDOR:
                    raise ValueError('Unexpected OpenSSL response')
                raw = response.read(2 * 1024 * 1024 + 1)
                if len(raw) > 2 * 1024 * 1024:
                    raise ValueError('OpenSSL index too large')
                report['vendor_http_date'] = response.headers.get('Date')
            (output / 'openssl-3.5.html').write_bytes(raw)
        else:
            query = saved_bytes(snapshot, '0000-request.json', 4096)
            if json.loads(query, object_pairs_hook=unique_object) != osv_queries():
                raise ValueError('Snapshot queries do not match the pinned components')
            response = saved_bytes(snapshot, '0000-response.json', 8 * 1024 * 1024)
            report['transport'].append(dict(endpoint='querybatch', request_sha256=sha256(query),
                                            response_sha256=sha256(response)))
            report['osv'] = interpret_osv(json.loads(response, object_pairs_hook=unique_object))
            raw = saved_bytes(snapshot, 'openssl-3.5.html', 2 * 1024 * 1024)
        count, matches = vendor_matches(raw, UPSTREAM['openssl'][0])
        report['vendor'] = dict(url=VENDOR, sha256=sha256(raw), entries=count, matching=matches)
        if inventory(backend) != report['files']:
            raise ValueError('Backend changed during check')
        report['queries_complete'] = True
        code = 2 if matches or any(m for group in report['osv'].values() for m in group.values()) else 3
    except (OSError, ValueError, IndexError, KeyError, TypeError, etree.ParserError) as error:
        report['error_type'] = type(error).__name__
    report.update(exit_code=code, finished_at=now())
    (output / 'report.json').write_text(json.dumps(report, indent=2, sort_keys=True) + '\n', encoding='utf8')
    return code


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--backend', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--snapshot', type=Path, help='Recompute from saved OSV request/response and OpenSSL index; offline')
    args = parser.parse_args()
    raise SystemExit(scan(args.backend, args.output, args.snapshot))
