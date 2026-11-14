"""Match actual frozen Python members to local build sources; never authenticate a release."""

import argparse
import base64
import csv
import email.parser
import importlib.metadata
import io
import json
import marshal
import struct
import sys
import zlib
from pathlib import Path, PurePosixPath
from types import CodeType

import yaml
from check_frozen_sources import equivalent
from frozen_sbom import (
    MAX_FILE_BYTES,
    MAX_FILES,
    MAX_MEMBER_BYTES,
    bounded_inflate,
    embedded,
    inventory,
    metadata,
    safe_name,
)
from packaging.utils import canonicalize_name
from source_sbom import LOCKS, lock_inventory, no_links, read_lock, sha256
from source_vulnerabilities import unique_object

MAX_REPORT_BYTES = 16 * 1024 * 1024
MAX_RECORD_BYTES = 4 * 1024 * 1024
MAX_RECORD_ROWS = 100000
MAX_BUILD_BYTES = 1024**3
LIMITATIONS = [
    'Local METADATA/RECORD and code or file equality do not authenticate upstream archives or ownership.',
    'Only actual uniquely matched members establish this subset; other installed packages are not projected into it.',
    'Matching optimization levels are equivalent compilations, not proof of the original compiler option.',
    'Unmapped and ambiguous modules/files, namespaces, stdlib and CArchive runtime scripts remain unverified.',
    'A matched package is not proof that its entire distribution is shipped, imported or reachable at runtime.',
    'The package subset does not establish dependency edges, complete product SBOM, licenses or vulnerability status.',
    'Before/after checks detect observed changes; the inputs are not an atomic filesystem snapshot.',
]


def bounded_file(path, limit):
    no_links(path)
    if not path.is_file() or path.stat().st_size > limit:
        raise ValueError('Input file is absent or exceeds budget')
    raw = path.read_bytes()
    if len(raw) > limit:
        raise ValueError('Input grew beyond budget')
    return raw


def module_name(name):
    path = PurePosixPath(name)
    if path.suffix != '.py' or any(part.endswith(('.dist-info', '.data')) for part in path.parts):
        return None
    parts = list(path.with_suffix('').parts)
    if parts[-1] == '__init__':
        parts.pop()
    return '.'.join(parts)


def local_matches(payload, archive, files, expected):
    installed = list(importlib.metadata.distributions())
    inputs, packages, modules, physical = {}, {}, {}, {}
    raw_exe = bounded_file(payload / 'study_backend.exe', MAX_FILE_BYTES)
    pyz_at = next(x['offset'] for x in archive['carchive'] if x['kind'] == 'z')
    rows_total, bytes_total = 0, 0

    def remember(path, limit):
        nonlocal bytes_total
        no_links(path)
        if path not in inputs and (len(inputs) >= MAX_FILES or bytes_total + path.stat().st_size > MAX_BUILD_BYTES):
            raise ValueError('Build source file or byte budget exceeded')
        raw = bounded_file(path, limit)
        if path not in inputs:
            bytes_total += len(raw)
        if bytes_total > MAX_BUILD_BYTES:
            raise ValueError('Build source byte budget exceeded')
        digest = sha256(raw)
        if path in inputs and inputs[path]['sha256'] != digest:
            raise ValueError('Build source changed during matching')
        inputs[path] = {'sha256': digest, 'limit': min(limit, inputs.get(path, {}).get('limit', limit))}
        return raw

    for purl, identity in sorted(expected.items()):
        if not purl.startswith('pkg:pypi/'):
            continue
        matches = [d for d in installed if canonicalize_name(d.metadata.get('Name', '')) == identity['name']
                   and d.version == identity['version']]
        if len(matches) != 1:
            packages[purl] = {'status': 'missing_or_ambiguous_exact_installed_version'}
            continue
        dist = matches[0]
        site = Path(dist.locate_file('')).absolute()
        no_links(site)
        meta = [p for p in dist.files or [] if len(p.parts) == 2 and str(p).endswith('.dist-info/METADATA')]
        if len(meta) != 1:
            raise ValueError('Missing or ambiguous build METADATA')
        metadata_name = PurePosixPath(safe_name(str(meta[0])))
        raw_metadata = remember(site.joinpath(*metadata_name.parts), MAX_RECORD_BYTES)
        declared = email.parser.BytesParser().parsebytes(raw_metadata)
        if (len(declared.get_all('Name', [])) != 1 or len(declared.get_all('Version', [])) != 1
                or canonicalize_name(declared['Name']) != identity['name'] or declared['Version'] != identity['version']):
            raise ValueError('Build METADATA identity changed or is ambiguous')
        record_name = metadata_name.parent / 'RECORD'
        raw_record = remember(site.joinpath(*record_name.parts), MAX_RECORD_BYTES)
        rows = list(csv.reader(io.StringIO(raw_record.decode('utf-8'))))
        rows_total += len(rows)
        if rows_total > MAX_RECORD_ROWS or any(len(row) != 3 for row in rows):
            raise ValueError('Malformed or oversized build RECORD')
        if len({row[0].casefold() for row in rows}) != len(rows):
            raise ValueError('Duplicate build RECORD entry')
        package = {'status': 'local_metadata_only', 'metadata_path': metadata_name.as_posix(),
                   'metadata_sha256': sha256(raw_metadata), 'record_path': record_name.as_posix(),
                   'record_sha256': sha256(raw_record), 'record_entries': len(rows),
                   'ignored_unsafe_paths': 0, 'unhashed_candidate_paths': []}
        packages[purl] = package
        for name, digest, length in rows:
            path = PurePosixPath(name)
            # Windows wheel console scripts legitimately use ../Scripts; never read outside site-packages.
            if (not name or path.is_absolute() or path.as_posix() != name or '..' in path.parts
                    or ':' in name or '\\' in name or any(x.rstrip(' .') != x for x in path.parts)):
                package['ignored_unsafe_paths'] += 1
                continue
            module = module_name(name)
            entry = archive['pyz'].get(module)
            target = '_internal/' + name
            if target not in files and (entry is None or entry['kind'] == 3):
                continue
            if not digest.startswith('sha256='):
                package['unhashed_candidate_paths'].append(name)
                continue
            candidate = site.joinpath(*path.parts)
            raw = remember(candidate, MAX_MEMBER_BYTES if module and entry else MAX_FILE_BYTES)
            source_hash = sha256(raw)
            actual_digest = base64.urlsafe_b64encode(bytes.fromhex(source_hash)).decode().rstrip('=')
            if digest != 'sha256=' + actual_digest or (length and (not length.isdecimal() or int(length) != len(raw))):
                raise ValueError('Build bytes differ from RECORD hash or length')
            evidence = {'purl': purl, 'source_path': name, 'source_sha256': source_hash,
                        'metadata_sha256': package['metadata_sha256'], 'record_sha256': package['record_sha256']}
            if target in files and files[target]['sha256'] == source_hash:
                physical.setdefault(target, []).append(evidence)
            if entry is not None and entry['kind'] != 3:
                start = pyz_at + entry['offset']
                plain = bounded_inflate(raw_exe[start:start + entry['compressed_bytes']])
                actual = marshal.loads(plain)
                if not isinstance(actual, CodeType):
                    raise ValueError('PYZ member is not a code object')
                levels = [level for level in (0, 1, 2) if equivalent(
                    actual, compile(raw, actual.co_filename, 'exec', dont_inherit=True, optimize=level))]
                if levels:
                    modules.setdefault(module, []).append({**evidence, 'equivalent_optimization_levels': levels})
    return modules, physical, packages, inputs, rows_total, bytes_total


def classify(all_names, matches):
    return {name: {'status': 'matched' if len(matches.get(name, [])) == 1 else
                  'ambiguous' if matches.get(name) else 'unmapped',
                  'candidates': matches.get(name, [])} for name in sorted(all_names)}


def generate(payload, source, coverage_file, output):
    payload, source, coverage_file, output = [p.absolute() for p in (payload, source, coverage_file, output)]
    no_links(output.parent)
    for path in (payload, source, coverage_file):
        no_links(path)
    if output.is_relative_to(payload) or payload.is_relative_to(output):
        raise ValueError('Output must be separate from payload')
    coverage_raw = bounded_file(coverage_file, MAX_REPORT_BYTES)
    coverage = json.loads(coverage_raw, object_pairs_hook=unique_object)
    if coverage['scope'] != 'one-frozen-backend-coverage' or coverage['python_version'] != sys.version.split()[0]:
        raise ValueError('Wrong coverage scope or build interpreter version')
    locks = {name: read_lock(source / name) for name in LOCKS}
    if {n: sha256(b) for n, b in locks.items()} != coverage['source_lock_sha256']:
        raise ValueError('Source locks differ from coverage')
    files = inventory(payload)
    if files != coverage['physical_files']:
        raise ValueError('Payload differs from coverage')
    archive = embedded(payload / 'study_backend.exe', source)
    if archive != coverage['embedded']:
        raise ValueError('Frozen directory or business sources differ from coverage')
    expected, _, _ = lock_inventory(locks)
    if metadata(payload, files, expected) != coverage['shipped_python_metadata']:
        raise ValueError('Shipped metadata differs from coverage')
    output.mkdir(exist_ok=False)
    modules, physical, packages, inputs, rows, byte_count = local_matches(payload, archive, files, expected)
    classified_modules = classify(set(archive['pyz']) - {
        n for n, v in archive['pyz'].items() if v['package_identity'] == 'application_source_compared'}, modules)
    classified_files = classify(files, physical)
    occurrences = {}
    pyz_name = next(x['name'] for x in archive['carchive'] if x['kind'] == 'z')
    for mapping, prefix in ((classified_modules, 'study_backend.exe!' + pyz_name + '/'), (classified_files, '')):
        for name, entry in mapping.items():
            if entry['status'] == 'matched':
                occurrences.setdefault(entry['candidates'][0]['purl'], []).append(prefix + name)
    components = []
    for purl, locations in sorted(occurrences.items()):
        identity, build = expected[purl], packages[purl]
        build['status'] = 'has_verified_local_members'
        components.append({'type': 'library', 'bom-ref': purl, 'purl': purl,
                           'name': identity['name'], 'version': identity['version'],
                           'evidence': {'occurrences': [{'location': x} for x in sorted(locations)]},
                           'properties': [{'name': 'studyworkbench:identity-evidence', 'value': 'local-build-record-and-static-comparison'},
                                          {'name': 'studyworkbench:metadata-sha256', 'value': build['metadata_sha256']},
                                          {'name': 'studyworkbench:record-sha256', 'value': build['record_sha256']},
                                          {'name': 'studyworkbench:upstream-provenance-verified', 'value': 'false'}]})
    if (files != inventory(payload) or locks != {name: read_lock(source / name) for name in LOCKS}
            or archive != embedded(payload / 'study_backend.exe', source)
            or coverage_raw != bounded_file(coverage_file, MAX_REPORT_BYTES)):
        raise ValueError('Payload, coverage or source changed during matching')
    for path, proof in inputs.items():
        if sha256(bounded_file(path, proof['limit'])) != proof['sha256']:
            raise ValueError('Build source changed during matching')
    bom = {'bomFormat': 'CycloneDX', 'specVersion': '1.6', 'version': 1,
           'metadata': {'properties': [{'name': 'studyworkbench:scope', 'value': 'local-frozen-Python-member-subset'},
                                       {'name': 'studyworkbench:product-sbom-complete', 'value': 'false'},
                                       {'name': 'studyworkbench:coverage-sha256', 'value': sha256(coverage_raw)}]},
           'components': components}
    bom_raw = (json.dumps(bom, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
    (output / 'python-members.cdx.json').write_bytes(bom_raw)
    report = {'schema_version': 1, 'scope': 'local-frozen-Python-member-matches',
              'product_sbom_complete': False, 'upstream_provenance_verified': False,
              'source_head_authenticated': False, 'source_head_assertion': coverage['source_head_assertion'],
              'collector_sha256': sha256(Path(__file__).read_bytes()), 'coverage_sha256': sha256(coverage_raw),
              'source_lock_sha256': coverage['source_lock_sha256'], 'payload_fingerprint': coverage['input_fingerprint'],
              'exe_sha256': archive['container_sha256'], 'python_version': sys.version.split()[0],
              'record_rows_inspected': rows, 'build_source_files_checked': len(inputs), 'build_source_bytes': byte_count,
              'build_packages': packages, 'member_packages': sorted(occurrences),
              'modules': classified_modules, 'physical_files': classified_files,
              'application_source_compared': archive['business_sources'],
              'unmapped_base_library_zip': coverage['base_library_zip'],
              'bom_sha256': sha256(bom_raw), 'limitations': LIMITATIONS}
    (output / 'members.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--payload', type=Path, required=True)
    parser.add_argument('--source', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--coverage', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True, help='New separate directory; parent must exist')
    args = parser.parse_args()
    try:
        report = generate(args.payload, args.source, args.coverage, args.output)
    except (OSError, ValueError, TypeError, KeyError, EOFError, SyntaxError, struct.error, zlib.error, yaml.YAMLError) as exc:
        parser.exit(1, f'Frozen Python matching failed: {exc}\n')
    print(f"Matched {len(report['member_packages'])} local build package identities; upstream and product coverage remain incomplete.")
    return 2


if __name__ == '__main__':
    raise SystemExit(main())
