"""Inventory one frozen backend and expose SBOM coverage gaps without approving release."""

import argparse
import email.parser
import hashlib
import importlib.util
import io
import json
import marshal
import os
import re
import struct
import subprocess
import sys
import zipfile
import zlib
from pathlib import Path, PurePosixPath
from types import CodeType
from urllib.parse import quote

import yaml
from check_frozen_sources import equivalent
from packaging.utils import canonicalize_name
from packaging.version import Version
from PyInstaller.archive.readers import CArchiveReader
from release_inventory import stage_files
from source_sbom import CONFIG, LOCKS, SYFT_SHA256, SYFT_VERSION, lock_inventory, no_links, read_lock, sha256

MAX_FILES = 20000
MAX_FILE_BYTES = 256 * 1024 * 1024
MAX_TOTAL_BYTES = 3 * 1024**3
MAX_MEMBER_BYTES = 8 * 1024 * 1024
MAX_TOC_BYTES = 4 * 1024 * 1024
SCAN_CONFIG = CONFIG + 'file:\n  metadata:\n    selection: all\n  digests: [sha256]\n'
CATALOGERS = 'python-installed-package-cataloger,pe-binary-package-cataloger,binary-classifier-cataloger'
LIMITATIONS = [
    'Only this frozen backend directory is scanned; other final product and installer components are excluded.',
    'Shipped Python METADATA declares identities; it neither authenticates upstream archives nor lists every frozen package.',
    'PE resource versions, PURLs and CPEs are scanner candidates, not authenticated package or vulnerability identities.',
    'PYZ and base_library.zip entries without a verified source comparison remain unmapped; file hashes are not package identities.',
    'Source head and expected executable hash are caller assertions; remote commit/build provenance must be checked separately.',
    'Dependency edges, embedded libraries, complete licenses, vulnerabilities and signatures are not verified.',
    'latex2mathml project MIT metadata does not settle embedded unimathsymbols.txt LPPL provenance or distribution obligations.',
    'Before/after hashes detect observed changes, but the scan is not an atomic filesystem snapshot.',
]


def safe_name(name):
    if not isinstance(name, str) or not name or '\\' in name or '\x00' in name or ':' in name:
        raise ValueError('Unsafe inventory name')
    path = PurePosixPath(name)
    if path.is_absolute() or path.as_posix() != name or any(p in {'..', '.'} or p.rstrip(' .') != p for p in path.parts):
        raise ValueError('Unsafe inventory path')
    return name


def inventory(payload):
    no_links(payload)
    paths = stage_files(payload)
    # The SBOM inventories even a pre-existing inventory file; it is not its own output.
    if (payload / 'build-inventory.json').is_file():
        paths['build-inventory.json'] = payload / 'build-inventory.json'
    if not paths or len(paths) > MAX_FILES:
        raise ValueError('Payload file count exceeds budget or is empty')
    result, total = {}, 0
    for name, path in sorted(paths.items()):
        safe_name(name)
        size = path.stat().st_size
        total += size
        if size > MAX_FILE_BYTES or total > MAX_TOTAL_BYTES:
            raise ValueError('Payload byte budget exceeded')
        with path.open('rb') as stream:
            digest = hashlib.file_digest(stream, 'sha256').hexdigest()
        result[name] = {'bytes': size, 'sha256': digest}
    return result


def bounded_inflate(data):
    inflater = zlib.decompressobj()
    plain = inflater.decompress(data, MAX_MEMBER_BYTES + 1)
    if len(plain) > MAX_MEMBER_BYTES or not inflater.eof or inflater.unused_data or inflater.unconsumed_tail:
        raise ValueError('Invalid or oversized embedded compressed member')
    return plain


def check_spans(spans):
    ordered = sorted((start, end) for start, end in spans if end > start)
    if any(left[1] > right[0] for left, right in zip(ordered, ordered[1:])):
        raise ValueError('Overlapping archive members')


def embedded(exe, source):
    """Read bounded archive directories and compare business code, never execute it."""
    data = exe.read_bytes()
    cookie_at = data.rfind(CArchiveReader._COOKIE_MAGIC_PATTERN)
    length = CArchiveReader._COOKIE_LENGTH
    if cookie_at < 0 or cookie_at + length > len(data):
        raise ValueError('Missing CArchive cookie')
    _, package_size, toc_offset, toc_size, python_version, _ = struct.unpack(
        CArchiveReader._COOKIE_FORMAT, data[cookie_at:cookie_at + length])
    if python_version != sys.version_info.major * 100 + sys.version_info.minor:
        raise ValueError('Wrong interpreter for CArchive Python version')
    start = cookie_at + length - package_size
    toc_start = start + toc_offset
    if not (0 <= start <= toc_start <= cookie_at and 0 < toc_size <= MAX_TOC_BYTES
            and toc_start + toc_size == cookie_at):
        raise ValueError('Invalid CArchive bounds')
    records, contents, options, spans, cursor = [], {}, [], [], toc_start
    while cursor < cookie_at:
        header = CArchiveReader._TOC_ENTRY_LENGTH
        if cursor + header > cookie_at:
            raise ValueError('Truncated CArchive entry')
        size, offset, stored, unpacked, compressed, kind = struct.unpack(
            CArchiveReader._TOC_ENTRY_FORMAT, data[cursor:cursor + header])
        if size <= header or cursor + size > cookie_at:
            raise ValueError('Invalid CArchive entry size')
        name = data[cursor + header:cursor + size].rstrip(b'\0').decode('utf-8')
        cursor += size
        if kind == b'o':
            if stored or unpacked or len(name) > 4096 or len(options) >= 100:
                raise ValueError('Invalid CArchive runtime option')
            options.append(name)
            continue
        safe_name(name)
        if name in contents or len(contents) >= MAX_FILES or compressed not in (0, 1):
            raise ValueError('Duplicate or unsupported CArchive entry')
        if offset < 0 or start + offset + stored > toc_start or unpacked > MAX_FILE_BYTES:
            raise ValueError('CArchive member escapes container or budget')
        spans.append((offset, offset + stored))
        blob = data[start + offset:start + offset + stored]
        contents[name] = (kind, compressed, blob)
        records.append({'name': name, 'kind': kind.decode('ascii'), 'container': 'study_backend.exe',
                        'offset': start + offset, 'stored_bytes': stored, 'declared_unpacked_bytes': unpacked,
                        'compressed': bool(compressed), 'stored_bytes_sha256': sha256(blob)})
    check_spans(spans)
    pyz_names = [name for name, (kind, _, _) in contents.items() if kind == b'z']
    if len(pyz_names) != 1:
        raise ValueError('Expected exactly one embedded PYZ')
    pyz_name = pyz_names[0]
    _, compressed, pyz = contents[pyz_name]
    if compressed or len(pyz) < 12 or pyz[:4] != b'PYZ\0' or pyz[4:8] != importlib.util.MAGIC_NUMBER:
        raise ValueError('Unsupported PYZ or wrong interpreter bytecode version')
    toc_at = struct.unpack('!i', pyz[8:12])[0]
    if not 12 <= toc_at < len(pyz) or len(pyz) - toc_at > MAX_TOC_BYTES:
        raise ValueError('Invalid PYZ directory bounds')
    stream = io.BytesIO(pyz[toc_at:])
    toc = marshal.load(stream)
    if stream.read(1) or not isinstance(toc, list) or len(toc) > MAX_FILES:
        raise ValueError('Invalid PYZ directory')
    modules, blocks, spans = {}, {}, []
    for name, entry in toc:
        if not isinstance(name, str) or not re.fullmatch(r'[A-Za-z_][A-Za-z_0-9-]*(?:\.[A-Za-z_][A-Za-z_0-9-]*)*', name):
            raise ValueError('Unsafe PYZ module name')
        if name in modules or not isinstance(entry, tuple) or len(entry) != 3:
            raise ValueError('Duplicate or malformed PYZ entry')
        kind, offset, size = entry
        if (any(type(v) is not int for v in entry) or kind not in (0, 1, 3)
                or offset < 0 or size < 0 or offset + size > toc_at or (kind != 3 and offset < 12)
                or (kind == 3 and size)):
            raise ValueError('PYZ member escapes container')
        spans.append((offset, offset + size))
        blob = pyz[offset:offset + size]
        blocks[name] = blob
        modules[name] = {'container': 'study_backend.exe!' + pyz_name, 'offset': offset,
                         'compressed_bytes': size, 'compressed_bytes_sha256': sha256(blob),
                         'kind': kind, 'package_identity': 'unmapped'}
    check_spans(spans)
    sources = source / 'backend/study_workbench'
    paths = {('study_workbench' + ('' if p.stem == '__init__' else '.' + p.stem)): p
             for p in sources.glob('*.py')}
    if not paths or set(paths) != {n for n in modules if n == 'study_workbench' or n.startswith('study_workbench.')}:
        raise ValueError('Frozen business source set differs')
    source_hashes = {}
    for name, path in sorted(paths.items()):
        no_links(path)
        raw = read_lock(path)
        code = marshal.loads(bounded_inflate(blocks[name]))
        if not isinstance(code, CodeType) or not equivalent(
                code, compile(raw.decode('utf-8'), code.co_filename, 'exec', dont_inherit=True)):
            raise ValueError('Frozen business code differs from source: ' + name)
        relative = path.relative_to(source).as_posix()
        source_hashes[relative] = {'sha256': sha256(raw),
                                 'git_blob_sha1': hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()}
        modules[name]['package_identity'] = 'application_source_compared'
    return {'container_sha256': sha256(data), 'python_version_cookie': python_version,
            'carchive': records, 'runtime_options': options, 'pyz': modules, 'business_sources': source_hashes,
            'source_head_authenticated': False}


def zip_directory(path):
    result, total = {}, 0
    with zipfile.ZipFile(path) as archive:
        members = archive.infolist()
        if len(members) > MAX_FILES:
            raise ValueError('ZIP member budget exceeded')
        for item in members:
            name = safe_name(item.orig_filename)
            if name != item.filename:
                raise ValueError('ZIP member name was normalized')
            total += item.file_size
            if name in result or item.is_dir() or item.file_size > MAX_MEMBER_BYTES or total > MAX_FILE_BYTES:
                raise ValueError('Duplicate, directory or oversized ZIP member')
            # No extraction paths are created, and no bytecode is loaded or run.
            with archive.open(item) as stream:
                data = stream.read(MAX_MEMBER_BYTES + 1)
            if len(data) != item.file_size or len(data) > MAX_MEMBER_BYTES:
                raise ValueError('ZIP member length differs')
            result[name] = {'container': '_internal/base_library.zip', 'bytes': len(data),
                            'uncompressed_bytes_sha256': sha256(data), 'package_identity': 'unmapped'}
    return result


def metadata(payload, files, expected):
    result, names = {}, set()
    for relative in files:
        if not relative.endswith('.dist-info/METADATA'):
            continue
        raw = read_lock(payload / relative)
        msg = email.parser.BytesParser().parsebytes(raw)
        if len(msg.get_all('Name', [])) != 1 or len(msg.get_all('Version', [])) != 1:
            raise ValueError('Missing or duplicate Python metadata identity')
        name, version = canonicalize_name(msg['Name']), msg['Version']
        Version(version)
        purl = 'pkg:pypi/' + name + '@' + quote(version, safe='')
        if name in names or purl not in expected:
            raise ValueError('Duplicate metadata package or identity differs from source lock')
        names.add(name)
        result[purl] = {'name': name, 'version': version, 'path': relative, 'sha256': sha256(raw),
                        'identity_evidence': 'shipped_metadata_declaration', 'upstream_provenance_verified': False}
    return result


def compare(bom, raw, files, declared):
    if bom.get('bomFormat') != 'CycloneDX' or bom.get('specVersion') != '1.6':
        raise ValueError('Expected CycloneDX 1.6')
    if raw.get('descriptor', {}).get('version') != SYFT_VERSION:
        raise ValueError('Wrong scanner version in evidence')
    found_files, refs, packages = set(), set(), []
    for item in bom['components']:
        reference = item.get('bom-ref')
        if not isinstance(reference, str) or reference in refs:
            raise ValueError('Missing or duplicate SBOM reference')
        refs.add(reference)
        if item.get('type') != 'file':
            packages.append(item)
            continue
        name = safe_name(item['name'].removeprefix('/'))
        if (name in found_files or name not in files
                or {'alg': 'SHA-256', 'content': files[name]['sha256']} not in item.get('hashes', [])):
            raise ValueError('Extra, duplicate or changed SBOM file')
        found_files.add(name)
    if found_files != set(files):
        raise ValueError('SBOM is missing physical payload files')
    discovered, python, candidates = {}, set(), []
    for item in raw['artifacts']:
        if item['id'] in discovered:
            raise ValueError('Duplicate scanner candidate')
        discovered[item['id']] = item
        locations = [safe_name(x['path'].removeprefix('/')) for x in item['locations']]
        if not locations or any(x not in files for x in locations):
            raise ValueError('Scanner candidate evidence is outside physical payload')
        if item['type'] == 'python':
            purl = item['purl']
            expected = declared.get(purl)
            if (purl in python or not expected or canonicalize_name(item['name']) != expected['name']
                    or item['version'] != expected['version'] or expected['path'] not in locations):
                raise ValueError('Python scanner identity differs from shipped metadata')
            python.add(purl)
        elif item['type'] != 'binary':
            raise ValueError('Unexpected scanner component type')
        candidates.append({'id': item['id'], 'name': item['name'], 'version': item['version'],
                           'type': item['type'], 'purl_candidate': item.get('purl'),
                           'cpes_candidates': item.get('cpes', []), 'locations': locations,
                           'upstream_provenance_verified': False})
    if python != set(declared) or len(packages) != len(discovered):
        raise ValueError('Missing or extra package candidates')
    matched = set()
    for item in packages:
        if item.get('purl'):
            selected = [x for x in discovered.values() if x.get('purl') == item['purl']]
        else:
            selected = [x for x in discovered.values() if x['id'] == item['bom-ref']]
        if (len(selected) != 1 or selected[0]['id'] in matched or item['name'] != selected[0]['name']
                or item.get('version') != selected[0]['version']):
            raise ValueError('CycloneDX candidate differs from scanner evidence')
        locations = [p['value'] for p in item.get('properties', [])
                     if re.fullmatch(r'syft:location:[0-9]+:path', p.get('name', ''))]
        if locations != [location['path'] for location in selected[0]['locations']]:
            raise ValueError('CycloneDX candidate location differs from scanner evidence')
        matched.add(selected[0]['id'])
    native = {}
    for path in files:
        if Path(path).suffix.lower() in {'.exe', '.dll', '.pyd'}:
            native[path] = {'candidate_ids': [x['id'] for x in candidates if path in x['locations']],
                            'identity_status': 'unverified', 'sha256': files[path]['sha256']}
    return candidates, native


def generate(payload, source, source_head, expected_exe_sha256, syft, output):
    payload, source, syft, output = [p.absolute() for p in (payload, source, syft, output)]
    if not re.fullmatch('[0-9a-f]{40}', source_head) or not re.fullmatch('[0-9a-f]{64}', expected_exe_sha256):
        raise ValueError('Expected full source head and executable SHA256 assertions')
    no_links(output.parent)
    for path in (payload, source, syft):
        no_links(path)
    payload, source, syft = [p.resolve() for p in (payload, source, syft)]
    output = output.parent.resolve() / output.name
    if output.is_relative_to(payload) or payload.is_relative_to(output):
        raise ValueError('Output must be separate from payload')
    no_links(syft)
    with syft.open('rb') as stream:
        if hashlib.file_digest(stream, 'sha256').hexdigest() != SYFT_SHA256:
            raise ValueError('Syft does not match pinned Windows x64 executable')
    files = inventory(payload)
    if files.get('study_backend.exe', {}).get('sha256') != expected_exe_sha256:
        raise ValueError('Executable differs from expected hash')
    locks = {name: read_lock(source / name) for name in LOCKS}
    expected, _, _ = lock_inventory(locks)
    declared = metadata(payload, files, expected)
    archive = embedded(payload / 'study_backend.exe', source)
    base_zip = zip_directory(payload / '_internal/base_library.zip')
    fingerprint = sha256(json.dumps(files, sort_keys=True).encode())
    output.mkdir(exist_ok=False)
    (output / 'syft.yaml').write_text(SCAN_CONFIG, encoding='utf-8')
    env = {key: val for key, val in os.environ.items() if not key.upper().startswith('SYFT_')}
    env['SYFT_CHECK_FOR_APP_UPDATE'] = 'false'
    command = [str(syft), 'scan', 'dir:' + str(payload), '--config', 'syft.yaml',
               '--override-default-catalogers', CATALOGERS, '--source-name', 'StudyWorkbench-frozen-backend',
               '--source-version', fingerprint, '-o', 'cyclonedx-json@1.6=backend.cdx.json',
               '-o', 'syft-json=backend.syft.json']
    with (output / 'syft.log').open('wb') as log:
        subprocess.run(command, cwd=output, env=env, stdout=log, stderr=subprocess.STDOUT, check=True, timeout=180)
    bom_bytes = (output / 'backend.cdx.json').read_bytes()
    syft_bytes = (output / 'backend.syft.json').read_bytes()
    candidates, native = compare(json.loads(bom_bytes), json.loads(syft_bytes), files, declared)
    if files != inventory(payload) or locks != {name: read_lock(source / name) for name in LOCKS}:
        raise ValueError('Payload or source locks changed during scan')
    if archive != embedded(payload / 'study_backend.exe', source):
        raise ValueError('Business sources changed during scan')
    result = {'schema_version': 1, 'scope': 'one-frozen-backend-coverage', 'product_sbom_complete': False,
              'source_head_assertion': source_head, 'expected_executable_sha256_assertion': expected_exe_sha256,
              'source_head_authenticated': False, 'syft_version': SYFT_VERSION,
              'syft_executable_sha256': SYFT_SHA256, 'collector_sha256': sha256(Path(__file__).read_bytes()),
              'scan_config_sha256': sha256(SCAN_CONFIG.encode()), 'python_version': sys.version.split()[0],
              'input_fingerprint': fingerprint, 'source_lock_sha256': {n: sha256(b) for n, b in locks.items()},
              'bom_sha256': sha256(bom_bytes), 'syft_json_sha256': sha256(syft_bytes),
              'physical_files': files, 'embedded': archive, 'base_library_zip': base_zip,
              'shipped_python_metadata': declared, 'scanner_candidates': candidates, 'native_files': native,
              'locked_python_without_shipped_metadata': sorted(p for p in expected if p.startswith('pkg:pypi/') and p not in declared),
              'limitations': LIMITATIONS}
    (output / 'coverage.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--payload', type=Path, required=True)
    parser.add_argument('--source', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--source-head', required=True, help='Caller assertion; authenticate Git/build provenance separately')
    parser.add_argument('--exe-sha256', required=True)
    parser.add_argument('--syft', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True, help='New separate directory; parent must exist')
    args = parser.parse_args()
    try:
        result = generate(args.payload, args.source, args.source_head, args.exe_sha256, args.syft, args.output)
    except (OSError, ValueError, TypeError, KeyError, EOFError, struct.error, zlib.error, yaml.YAMLError,
            zipfile.BadZipFile, subprocess.SubprocessError) as exc:
        parser.exit(1, f'Frozen SBOM failed: {exc}\n')
    print(f"Compared {len(result['physical_files'])} physical files; package identities and product SBOM remain incomplete.")
    return 2


if __name__ == '__main__':
    raise SystemExit(main())
