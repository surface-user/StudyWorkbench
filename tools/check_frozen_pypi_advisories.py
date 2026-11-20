"""Check the mapped PyPI members of the archived REL-01h frozen backend against OSV."""
import argparse
import json
from pathlib import Path

from frozen_sbom import inventory
from packaging.utils import canonicalize_name
from source_sbom import no_links, sha256
from source_vulnerabilities import now, query_packages, unique_object

EVIDENCE = Path(__file__).resolve().parents[1] / 'dev/records/2026-11-10-release-integrity/evidence'


def read_members(payload):
    summary = json.loads((EVIDENCE / 'current-backend-sources-summary.json').read_bytes(), object_pairs_hook=unique_object)
    raw = (EVIDENCE / 'current-backend-subset.cdx.json').read_bytes()
    if sha256(raw) != summary['selected_cdx']['sha256']:
        raise ValueError('CycloneDX evidence digest mismatch')
    files = inventory(payload)
    fingerprint = sha256(json.dumps(files, sort_keys=True).encode())
    if fingerprint != summary['payload']['fingerprint'] or len(files) != summary['payload']['files']:
        raise ValueError('Payload does not match the mapped frozen backend')
    members = summary['local_members']['packages']
    bom = json.loads(raw, object_pairs_hook=unique_object)
    grouped = {}
    for component in bom['components']:
        purl = component.get('purl')
        if purl in members:
            name, version = component['name'], component['version']
            if purl != f'pkg:pypi/{canonicalize_name(name)}@{version}' or purl in grouped:
                raise ValueError('Ambiguous PyPI identity')
            grouped[purl] = dict(name=canonicalize_name(name), version=version, purl=purl,
                                 ecosystem='PyPI', matches={})
    if not 1 <= len(grouped) == len(members) <= 1000 or set(grouped) != set(members):
        raise ValueError('Missing or duplicate mapped PyPI member')
    return fingerprint, [grouped[purl] for purl in sorted(grouped)]


def scan(payload, output):
    payload = payload.absolute()
    output = output.absolute()
    no_links(output.parent)
    if output.resolve().is_relative_to(payload.resolve()):
        raise ValueError('Keep query evidence outside the payload')
    fingerprint, members = read_members(payload)
    expected = [item['purl'] for item in members]
    output.mkdir(exist_ok=False)
    report = dict(payload_fingerprint=fingerprint, started_at=now(), evidence=[], members=members,
                  queries_complete=False, product_check_complete=False, database_snapshot=None)
    try:
        query_packages(members, output, report['evidence'])
        final, after = read_members(payload)
        if final != fingerprint or expected != [item['purl'] for item in after]:
            raise ValueError('Frozen backend or selected identities changed during lookup')
        report['queries_complete'] = True
        status = 2 if any(item['matches'] for item in members) else 3
    except (OSError, ValueError, TypeError, KeyError) as exc:
        report['error_type'] = type(exc).__name__
        status = 1
    report.update(exit_code=status, finished_at=now())
    (output / 'report.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    return status


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--payload', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    try:
        parser.exit(scan(args.payload, args.output))
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.exit(1, f'Cannot verify release evidence: {error}\n')
