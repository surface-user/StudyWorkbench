"""Export package identities and every shipped file without exporting build-host metadata."""
import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'tools'))
from frozen_sbom import inventory  # noqa: E402
from source_sbom import no_links  # noqa: E402


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def export(payload, coverage_file, origins_dir, output, native_profile=None):
    no_links(output.parent)
    if output.resolve().is_relative_to(payload.resolve()):
        raise ValueError('Keep the SBOM outside the payload')
    coverage_raw = coverage_file.read_bytes()
    coverage = json.loads(coverage_raw)
    origins = json.loads((origins_dir / 'origins.json').read_bytes())
    bom_raw = (origins_dir / 'python-origins.cdx.json').read_bytes()
    files = inventory(payload)
    fingerprint = digest(json.dumps(files, sort_keys=True).encode())
    if (files != coverage['physical_files'] or fingerprint != coverage['input_fingerprint']
            or fingerprint != origins['payload_fingerprint'] or digest(coverage_raw) != origins['coverage_sha256']
            or digest(bom_raw) != origins['bom_sha256'] or origins['source_head_assertion'] != coverage['source_head_assertion']):
        raise ValueError('Package mapping, file coverage and payload must refer to the same build')
    head = origins['source_head_assertion']
    if not re.fullmatch('[0-9a-f]{40}', head):
        raise ValueError('Malformed source commit')
    components = []
    for item in json.loads(bom_raw)['components']:
        if item['bom-ref'] == 'application-source:' + head:
            continue
        purl = item['purl']
        identity = f"{item['name']}@{item['version']}"
        if (purl != item['bom-ref'] or purl not in {'pkg:pypi/' + identity, 'pkg:nuget/' + identity}
                or not re.fullmatch(r'pkg:(pypi|nuget)/[a-z0-9.-]+@[a-zA-Z0-9.+-]+', purl)):
            raise ValueError('Unexpected package identity in origin evidence')
        components.append({'type': 'library', 'bom-ref': purl, 'purl': purl,
                           'name': item['name'], 'version': item['version']})
    if native_profile is not None:
        raw = native_profile.read_bytes()
        if digest(raw) != 'bf378e5a38ae40dc6b3961ebda842d5ee6bcec963605ce3c45436dfc991c20e3':
            raise ValueError('Native provenance differs from the verified REL-01i profile')
        for archive in json.loads(raw)['binary_archives']:
            name, version = archive['name'], archive['recipe_declared_version']
            purl = f'pkg:generic/{name}@{version}'
            locations = []
            for member in archive['members']:
                if 'payload_path' in member:
                    path = member['payload_path']
                    if files.get(path) != {'bytes': member['bytes'], 'sha256': member['sha256']}:
                        raise ValueError('Native file no longer matches provenance')
                    locations.append({'location': path})
            components.append({'type': 'library', 'name': name, 'version': version, 'purl': purl,
                               'bom-ref': purl, 'evidence': {'occurrences': locations}})
    for name, record in sorted(files.items()):
        components.append({'type': 'file', 'name': name, 'bom-ref': 'file:' + name,
                           'hashes': [{'alg': 'SHA-256', 'content': record['sha256']}]})
    if len({c['bom-ref'] for c in components}) != len(components):
        raise ValueError('Duplicate component reference')
    app = {'type': 'application', 'name': 'StudyWorkbench-backend', 'version': head, 'bom-ref': 'application-source:' + head}
    result = {'bomFormat': 'CycloneDX', 'specVersion': '1.6', 'version': 1,
              'metadata': {'component': app, 'properties': [
                  {'name': 'studyworkbench:payload-fingerprint-sha256', 'value': fingerprint},
                  {'name': 'studyworkbench:scope', 'value': 'frozen backend files and source-mapped package identities'}]},
              'components': components, 'compositions': [{'aggregate': 'incomplete', 'assemblies': [app['bom-ref']]}]}
    if inventory(payload) != files:
        raise ValueError('Payload changed during export')
    # Serialize completely before creating the exclusively owned output.
    raw = (json.dumps(result, separators=(',', ':'), ensure_ascii=True) + '\n').encode()
    with output.open('xb') as stream:
        stream.write(raw)
    return {'files': len(files), 'libraries': len(components) - len(files), 'bytes': len(raw), 'sha256': digest(raw)}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for flag in ('payload', 'coverage', 'origins', 'output'):
        parser.add_argument('--' + flag, type=Path, required=True)
    parser.add_argument('--native-profile', type=Path, help='Exact REL-01i provenance.json from PR 88')
    args = parser.parse_args()
    print(json.dumps(export(args.payload, args.coverage, args.origins, args.output, args.native_profile)))
