"""Collect local license texts for distributions with verified members in a frozen backend."""
import argparse
import hashlib
import io
import json
import re
import shutil
import stat
import tempfile
import zipfile
from pathlib import Path

from frozen_sbom import inventory
from source_licenses import python_evidence
from source_sbom import no_links, sha256

MAX_BUNDLE_BYTES = 16 * 1024 * 1024
MAX_BUNDLE_ENTRIES = 4096
MAX_BUNDLE_EXPANDED = 32 * 1024 * 1024
MAX_LICENSE_BYTES = 4 * 1024 * 1024
MAX_INDEX_BYTES = 8 * 1024 * 1024
MAX_LICENSE_REFERENCES = 8192
BUNDLE_PATH = 'licenses/_python/frozen-members.zip'


def bundle_bytes(path):
    path = path.absolute()
    no_links(path)
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_BUNDLE_BYTES:
        raise ValueError('License bundle must be a bounded regular file')
    with path.open('rb') as stream:
        raw = stream.read(MAX_BUNDLE_BYTES + 1)
    if len(raw) > MAX_BUNDLE_BYTES:
        raise ValueError('License bundle grew beyond budget')
    return raw


def verify_bundle(payload, path, expected_sha256):
    """Verify a caller-pinned local bundle; do not authenticate upstream licensing."""
    from source_vulnerabilities import unique_object

    if not isinstance(expected_sha256, str) or not re.fullmatch('[0-9a-f]{64}', expected_sha256):
        raise ValueError('Expected license bundle SHA256 is required')
    raw = bundle_bytes(path)
    if sha256(raw) != expected_sha256:
        raise ValueError('License bundle differs from expected SHA256')
    files = inventory(payload)
    fingerprint = sha256(json.dumps(files, sort_keys=True).encode())
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        entries = archive.infolist()
        if not 1 <= len(entries) <= MAX_BUNDLE_ENTRIES:
            raise ValueError('License ZIP entry budget exceeded')
        declared, names = 0, set()
        for item in entries:
            name = item.orig_filename
            mode = item.external_attr >> 16
            if (name != item.filename or name in names
                    or not (name == 'index.json' or re.fullmatch('texts/[0-9a-f]{64}', name))
                    or item.is_dir() or stat.S_IFMT(mode) not in (0, stat.S_IFREG)
                    or item.flag_bits & 1 or item.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED)):
                raise ValueError('Unsafe or duplicated license ZIP member')
            names.add(name)
            limit = MAX_INDEX_BYTES if name == 'index.json' else MAX_LICENSE_BYTES
            declared += item.file_size
            if not 0 < item.file_size <= limit or declared > MAX_BUNDLE_EXPANDED:
                raise ValueError('License ZIP expanded byte budget exceeded')
        if 'index.json' not in names:
            raise ValueError('License ZIP index is missing')
        actual, texts, index = 0, {}, None
        for item in entries:
            limit = min(MAX_INDEX_BYTES if item.filename == 'index.json' else MAX_LICENSE_BYTES,
                        MAX_BUNDLE_EXPANDED - actual)
            with archive.open(item) as stream:
                data = stream.read(limit + 1)
            actual += len(data)
            if len(data) != item.file_size or len(data) > limit or actual > MAX_BUNDLE_EXPANDED:
                raise ValueError('License ZIP actual byte budget or member length exceeded')
            if item.filename == 'index.json':
                index = json.loads(data.decode('utf-8'), object_pairs_hook=unique_object)
            else:
                if sha256(data) != item.filename.removeprefix('texts/'):
                    raise ValueError('License text differs from its content address')
                texts[item.filename] = {'bytes': len(data), 'sha256': sha256(data)}
    if (not isinstance(index, dict) or index.get('scope') != 'mapped frozen PyPI distributions'
            or index.get('payload_fingerprint') != fingerprint
            or index.get('distribution_obligations_reviewed') is not False
            or (index.get('source_head') is not None and
                (not isinstance(index['source_head'], str) or not re.fullmatch('[0-9a-f]{40}', index['source_head'])))):
        raise ValueError('License index is not bound to this frozen backend')
    packages = index.get('packages')
    if not isinstance(packages, dict) or not 1 <= len(packages) <= 1024:
        raise ValueError('Missing or oversized license package set')
    selected, references, issues = set(), 0, 0
    for purl, package in packages.items():
        if (not re.fullmatch(r'pkg:pypi/[a-z0-9][a-z0-9.-]*@[a-zA-Z0-9.+-]+', purl)
                or not isinstance(package, dict)
                or any(not isinstance(package.get(k), str) or not re.fullmatch('[0-9a-f]{64}', package[k])
                       for k in ('metadata_sha256', 'record_sha256'))
                or not isinstance(package.get('issues'), list)
                or any(not isinstance(issue, str) for issue in package['issues'])
                or not isinstance(package.get('files'), list) or not package['files']):
            raise ValueError('Invalid license package identity or evidence')
        issues += bool(package['issues'])
        for item in package['files']:
            references += 1
            if references > MAX_LICENSE_REFERENCES:
                raise ValueError('License reference budget exceeded')
            if (not isinstance(item, dict) or not isinstance(item.get('text_path'), str)
                    or item['text_path'] not in texts or type(item.get('bytes')) is not int
                    or item['bytes'] != texts[item['text_path']]['bytes']
                    or item.get('sha256') != texts[item['text_path']]['sha256']):
                raise ValueError('License reference bytes differ from archived text')
            selected.add(item['text_path'])
    if selected != set(texts):
        raise ValueError('License ZIP contains unreferenced texts')
    if inventory(payload) != files or bundle_bytes(path) != raw:
        raise ValueError('Backend or license bundle changed during verification')
    return {'scope': 'mapped-frozen-python-license-texts', 'applied': True,
            'path': BUNDLE_PATH, 'bytes': len(raw), 'sha256': expected_sha256,
            'payload_fingerprint': fingerprint, 'source_head': index.get('source_head'),
            'packages': len(packages), 'unique_texts': len(texts), 'text_references': references,
            'packages_with_issues': issues, 'distribution_obligations_reviewed': False,
            'upstream_provenance_verified': False, 'product_licenses_complete': False, 'release_ready': False}


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
    files = inventory(payload)
    fingerprint = sha256(json.dumps(files, sort_keys=True).encode())
    inputs, locks, archive, observations = {}, {}, None, None
    if origins is None:
        from frozen_python_members import bounded_file, classify, local_matches
        from frozen_sbom import embedded, metadata
        from source_sbom import LOCKS, lock_inventory, read_lock

        locks = {name: read_lock(source / name) for name in LOCKS}
        expected, _, _ = lock_inventory(locks)
        metadata(payload, files, expected)
        archive = embedded(payload / 'study_backend.exe', source)
        modules, physical, proofs, inputs, _, _ = local_matches(payload, archive, files, expected)
        module_rows = classify(set(archive['pyz']) - {
            name for name, row in archive['pyz'].items() if row['package_identity'] == 'application_source_compared'}, modules)
        file_rows = classify(files, physical)
        observations = {'source': 'local locked RECORD and static member comparison', 'member_mapping_complete': False,
                        **{kind + '_' + status: sum(row['status'] == status for row in rows.values())
                           for kind, rows in (('modules', module_rows), ('files', file_rows))
                           for status in ('matched', 'ambiguous', 'unmapped')}}
        classified = [*module_rows.values(), *file_rows.values()]
        package_ids = sorted({row['candidates'][0]['purl'] for row in classified if row['status'] == 'matched'})
        if not package_ids:
            raise ValueError('No uniquely matched frozen Python packages')
        source_head = None  # No caller-authenticated Git identity is available in an ordinary local build.
    else:
        origin = json.loads((origins / 'origins.json').read_bytes())
        member_raw = (origins / 'local-members/members.json').read_bytes()
        members = json.loads(member_raw)
        if (origin['base_members_sha256'] != sha256(member_raw) or origin['payload_fingerprint'] != fingerprint
                or members['payload_fingerprint'] != fingerprint or members['source_head_assertion'] != origin['source_head_assertion']):
            raise ValueError('License inputs do not match the same frozen backend')
        package_ids, proofs = members['member_packages'], members['build_packages']
        verified = {key for key, value in proofs.items() if value['status'] == 'has_verified_local_members'}
        if not verified or verified != set(package_ids) or len(package_ids) != len(verified):
            raise ValueError('Missing or duplicated verified package')
        source_head = origin['source_head_assertion']
    index = {'scope': 'mapped frozen PyPI distributions', 'payload_fingerprint': fingerprint,
             'source_head': source_head, 'distribution_obligations_reviewed': False, 'packages': {}}
    if observations is not None:
        index['member_matching'] = observations
    hashes = set()
    with tempfile.TemporaryDirectory(dir=output.parent) as work:
        temp = Path(work)
        (temp / 'texts').mkdir()
        for purl in sorted(package_ids):
            match = re.fullmatch(r'pkg:pypi/([a-z0-9.-]+)@([a-zA-Z0-9.+-]+)', purl)
            if not match:
                raise ValueError('Unsupported package identity')
            entry = python_evidence(dict(name=match[1], version=match[2]), temp, source)
            proof = proofs[purl]
            if any(entry.get(k) != proof[k] for k in ('metadata_sha256', 'record_sha256')):
                raise ValueError('License source differs from verified frozen member evidence')
            index['packages'][purl] = entry
            hashes.update(row['sha256'] for row in entry['files'])
        if inventory(payload) != files:
            raise ValueError('Frozen backend changed during license collection')
        if origins is None and (locks != {name: read_lock(source / name) for name in LOCKS}
                                or archive != embedded(payload / 'study_backend.exe', source)
                                or any(sha256(bounded_file(path, row['limit'])) != row['sha256'] for path, row in inputs.items())):
            raise ValueError('Matched build inputs changed during license collection')
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
    parser.add_argument('--payload', type=Path, required=True)
    for flag in ('origins', 'output', 'verify-bundle'):
        parser.add_argument('--' + flag, type=Path)
    parser.add_argument('--sha256')
    parser.add_argument('--source', type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    if args.verify_bundle:
        if args.output or args.origins or not args.sha256:
            parser.error('Verification requires --sha256 and excludes collection inputs')
        print(json.dumps(verify_bundle(args.payload, args.verify_bundle, args.sha256)))
    else:
        if not args.output or args.sha256:
            parser.error('Collection requires --output and excludes --sha256')
        print(json.dumps(collect(args.payload, args.origins, args.source, args.output)))
