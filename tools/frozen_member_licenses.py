"""Collect local license texts for distributions with verified members in a frozen backend."""
import argparse
import hashlib
import json
import re
import shutil
import tempfile
import zipfile
from pathlib import Path

from frozen_sbom import inventory
from source_licenses import python_evidence
from source_sbom import no_links, sha256


def write_entry(archive, name, raw):
    info = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0))
    info.compress_type = zipfile.ZIP_DEFLATED
    info.create_system = 3
    info.external_attr = 0o100644 << 16
    archive.writestr(info, raw)


def collect(payload, origins, source, output):
    no_links(output.parent)
    if output.resolve().is_relative_to(payload.resolve()):
        raise ValueError('Keep the license bundle outside the frozen payload')
    if output.exists():
        raise FileExistsError(output)
    origin = json.loads((origins / 'origins.json').read_bytes())
    member_raw = (origins / 'local-members/members.json').read_bytes()
    members = json.loads(member_raw)
    files = inventory(payload)
    fingerprint = sha256(json.dumps(files, sort_keys=True).encode())
    if (origin['base_members_sha256'] != sha256(member_raw) or origin['payload_fingerprint'] != fingerprint
            or members['payload_fingerprint'] != fingerprint or members['source_head_assertion'] != origin['source_head_assertion']):
        raise ValueError('License inputs do not match the same frozen backend')
    package_ids = members['member_packages']
    verified = {key for key, value in members['build_packages'].items() if value['status'] == 'has_verified_local_members'}
    if not verified or verified != set(package_ids) or len(package_ids) != len(verified):
        raise ValueError('Missing or duplicated verified package')
    index = {'scope': 'mapped frozen PyPI distributions', 'payload_fingerprint': fingerprint,
             'source_head': origin['source_head_assertion'], 'distribution_obligations_reviewed': False, 'packages': {}}
    hashes = set()
    with tempfile.TemporaryDirectory(dir=output.parent) as work:
        temp = Path(work)
        (temp / 'texts').mkdir()
        for purl in sorted(package_ids):
            match = re.fullmatch(r'pkg:pypi/([a-z0-9.-]+)@([a-zA-Z0-9.+-]+)', purl)
            if not match:
                raise ValueError('Unsupported package identity')
            entry = python_evidence(dict(name=match[1], version=match[2]), temp, source)
            proof = members['build_packages'][purl]
            if any(entry.get(k) != proof[k] for k in ('metadata_sha256', 'record_sha256')):
                raise ValueError('License source differs from verified frozen member evidence')
            index['packages'][purl] = entry
            hashes.update(row['sha256'] for row in entry['files'])
        if inventory(payload) != files:
            raise ValueError('Frozen backend changed during license collection')
        with zipfile.ZipFile(temp / 'bundle.zip', 'x') as archive:
            write_entry(archive, 'index.json', (json.dumps(index, ensure_ascii=False, indent=2) + '\n').encode())
            for digest in sorted(hashes):
                raw = (temp / 'texts' / digest).read_bytes()
                if sha256(raw) != digest:
                    raise ValueError('Selected license bytes changed')
                write_entry(archive, 'texts/' + digest, raw)
        with (temp / 'bundle.zip').open('rb') as archive:
            result_hash = hashlib.file_digest(archive, 'sha256').hexdigest()
            archive.seek(0)
            with output.open('xb') as target:
                shutil.copyfileobj(archive, target)
    return {'packages': len(package_ids), 'unique_texts': len(hashes),
            'text_references': sum(len(x['files']) for x in index['packages'].values()),
            'packages_with_issues': sum(bool(x['issues']) for x in index['packages'].values()),
            'sha256': result_hash}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for flag in ('payload', 'origins', 'output'):
        parser.add_argument('--' + flag, type=Path, required=True)
    parser.add_argument('--source', type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    print(json.dumps(collect(args.payload, args.origins, args.source, args.output)))
