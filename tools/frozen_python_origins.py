"""Extend frozen Python member evidence with pinned archive and declared Git sources."""

import argparse
import base64
import copy
import csv
import hashlib
import importlib.metadata
import importlib.util
import io
import json
import marshal
import re
import stat
import struct
import sys
import xml.etree.ElementTree as ET
import zipfile
import zlib
from pathlib import Path, PurePosixPath
from types import CodeType

import yaml
from check_frozen_sources import equivalent
from defusedxml import ElementTree as SafeET
from defusedxml.common import DefusedXmlException
from frozen_python_members import (
    MAX_BUILD_BYTES,
    MAX_RECORD_BYTES,
    MAX_RECORD_ROWS,
    MAX_REPORT_BYTES,
    bounded_file,
    module_name,
)
from frozen_python_members import (
    generate as match_python,
)
from frozen_sbom import (
    MAX_FILE_BYTES,
    MAX_FILES,
    MAX_MEMBER_BYTES,
    bounded_inflate,
    embedded,
    inventory,
    safe_name,
    zip_directory,
)
from packaging.utils import canonicalize_name
from source_sbom import LOCKS, no_links, read_lock, sha256
from source_vulnerabilities import unique_object

PYTHON_VERSION = '3.13.17'
PYTHON_ARCHIVE_SHA256 = 'dce409744b088f94c6e37ba41f8100c384c27e029e843237364c602d30d475e5'
MAX_ARCHIVE_BYTES = 64 * 1024 * 1024
MAX_ZIP_BYTES = 256 * 1024 * 1024
MAX_ZIP_MEMBER_BYTES = 16 * 1024 * 1024
LIMITATIONS = [
    'The CPython archive pin identifies these bytes; publisher signatures and all embedded native libraries are not authenticated here.',
    'Git head/tree values are caller declarations; matching blobs does not authenticate a remote commit or build service.',
    'Local build RECORD/METADATA and relocated byte matches do not authenticate upstream wheels or uniquely assign shared library ownership.',
    'Namespace entries contain no code; contributing child sources do not establish a namespace version or exclusive owner.',
    'The outer PE bootloader, remaining native/CRT identities, generated containers and complete dependencies remain unverified.',
    'This source subset does not certify the full product SBOM, licenses, vulnerabilities, signatures or runtime reachability.',
    'Before/after hashes detect observed changes, not an atomic filesystem snapshot.',
]


def levels(actual, source):
    if not isinstance(actual, CodeType):
        raise ValueError('Expected a static code object')
    return [n for n in (0, 1, 2) if equivalent(
        actual, compile(source, actual.co_filename, 'exec', dont_inherit=True, optimize=n))]


def git_blob(raw):
    return hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()


def zip_members(archive):
    infos, total = {}, 0
    for item in archive.infolist():
        original = item.orig_filename[:-1] if item.is_dir() else item.orig_filename
        name = safe_name(original)
        mode = item.external_attr >> 16
        if (item.orig_filename != item.filename or name.casefold() in infos
                or stat.S_ISLNK(mode) or (stat.S_IFMT(mode) and not (stat.S_ISREG(mode) or stat.S_ISDIR(mode)))):
            raise ValueError('Unsafe, duplicate or special NuGet member')
        total += item.file_size
        if (len(infos) >= MAX_FILES or item.file_size > MAX_ZIP_MEMBER_BYTES
                or total > MAX_ZIP_BYTES or item.flag_bits & 1):
            raise ValueError('NuGet member or expanded byte budget exceeded')
        infos[name.casefold()] = item
    return infos


def generate(payload, source, coverage_file, python_package, source_tree, output):
    payload, source, coverage_file, python_package, source_tree, output = [p.absolute() for p in (
        payload, source, coverage_file, python_package, source_tree, output)]
    no_links(output.parent)
    if output.is_relative_to(payload) or payload.is_relative_to(output):
        raise ValueError('Output must be separate from payload')
    python_raw = bounded_file(python_package, MAX_ARCHIVE_BYTES)
    if sha256(python_raw) != PYTHON_ARCHIVE_SHA256 or sys.version.split()[0] != PYTHON_VERSION:
        raise ValueError('Wrong pinned CPython archive or interpreter')
    tree_raw = bounded_file(source_tree, MAX_REPORT_BYTES)
    tree = json.loads(tree_raw, object_pairs_hook=unique_object)
    if not all(re.fullmatch('[0-9a-f]{40}', tree[k]) for k in ('commit', 'tree')):
        raise ValueError('Expected full declared source commit/tree')
    tree_entries = tree['entries']
    if len(tree_entries) > MAX_FILES:
        raise ValueError('Git source entry budget exceeded')
    source_blobs = {}
    for item in tree_entries:
        name = safe_name(item['path'])
        if (item['type'] != 'blob' or item['mode'] != '100644'
                or name.casefold() in source_blobs or not re.fullmatch('[0-9a-f]{40}', item['sha'])):
            raise ValueError('Malformed or duplicate declared source blob')
        source_blobs[name.casefold()] = item['sha']
    coverage_raw = bounded_file(coverage_file, MAX_REPORT_BYTES)
    coverage = json.loads(coverage_raw, object_pairs_hook=unique_object)
    if tree['commit'] != coverage['source_head_assertion']:
        raise ValueError('Declared Git source differs from frozen source assertion')
    locks = {n: read_lock(source / n) for n in LOCKS}
    output.mkdir(exist_ok=False)
    members = match_python(payload, source, coverage_file, output / 'local-members')
    member_raw = bounded_file(output / 'local-members/members.json', MAX_REPORT_BYTES)
    bom_raw = bounded_file(output / 'local-members/python-members.cdx.json', MAX_REPORT_BYTES)
    files = inventory(payload)
    archive = embedded(payload / 'study_backend.exe', source)
    if zip_directory(payload / '_internal/base_library.zip') != coverage['base_library_zip']:
        raise ValueError('Base-library directory differs from coverage')
    raw_exe = bounded_file(payload / 'study_backend.exe', MAX_FILE_BYTES)
    inputs, logical_bytes = {}, 0

    def read_input(path, limit, expected=None):
        nonlocal logical_bytes
        no_links(path)
        if path not in inputs and (len(inputs) >= MAX_FILES or logical_bytes + path.stat().st_size > MAX_BUILD_BYTES):
            raise ValueError('Source input file or byte budget exceeded')
        raw = bounded_file(path, limit)
        digest = sha256(raw)
        if expected is not None and digest != expected:
            raise ValueError('Source input differs from recorded hash')
        if path in inputs and digest != inputs[path]['sha256']:
            raise ValueError('Source input changed during matching')
        if path not in inputs:
            logical_bytes += len(raw)
        inputs[path] = {'sha256': digest, 'limit': min(limit, inputs.get(path, {}).get('limit', limit))}
        return raw

    distributions = list(importlib.metadata.distributions())
    builds, rows_total = {}, 0
    for purl, build in members['build_packages'].items():
        if 'record_path' not in build:
            continue
        name, version = purl.removeprefix('pkg:pypi/').rsplit('@', 1)
        found = [d for d in distributions if canonicalize_name(d.metadata.get('Name', '')) == name and d.version == version]
        if len(found) != 1:
            raise ValueError('Build distribution changed after member matching')
        site = Path(found[0].locate_file('')).absolute()
        meta_path = site / safe_name(build['metadata_path'])
        record_path = site / safe_name(build['record_path'])
        read_input(meta_path, MAX_RECORD_BYTES, build['metadata_sha256'])
        record = read_input(record_path, MAX_RECORD_BYTES, build['record_sha256'])
        rows = list(csv.reader(io.StringIO(record.decode('utf-8'))))
        rows_total += len(rows)
        if rows_total > MAX_RECORD_ROWS or any(len(row) != 3 for row in rows):
            raise ValueError('Build RECORD row budget or structure changed')
        if len({r[0].casefold() for r in rows}) != len(rows):
            raise ValueError('Duplicate build RECORD entry')
        builds[purl] = {'site': site, 'rows': rows, 'proof': build}
    def build_source(purl, name, digest, size):
        safe_name(name)
        raw = read_input(builds[purl]['site'] / name,
                         MAX_MEMBER_BYTES if name.endswith('.py') else MAX_FILE_BYTES)
        encoded = base64.urlsafe_b64encode(bytes.fromhex(sha256(raw))).decode().rstrip('=')
        if digest != 'sha256=' + encoded or (size and (not size.isdecimal() or len(raw) != int(size))):
            raise ValueError('Additional build source differs from RECORD')
        build = builds[purl]['proof']
        return raw, {'identity': purl, 'source_path': name, 'source_sha256': sha256(raw),
                     'metadata_sha256': build['metadata_sha256'], 'record_sha256': build['record_sha256']}

    # Keep even non-matching build inputs stable across the additional origin checks.
    for purl, data in builds.items():
        for name, digest, size in data['rows']:
            try:
                safe_name(name)
            except ValueError:
                continue
            entry = archive['pyz'].get(module_name(name))
            if digest.startswith('sha256=') and ('_internal/' + name in files or (entry and entry['kind'] != 3)):
                build_source(purl, name, digest, size)

    app_identity = 'application-source:' + tree['commit']

    def project_source(name):
        safe_name(name)
        raw = read_input(source / name, MAX_MEMBER_BYTES)
        blob = git_blob(raw)
        if source_blobs.get(name.casefold()) != blob:
            raise ValueError('Project source differs from declared Git blob')
        return raw, {'identity': app_identity, 'source_path': name, 'source_sha256': sha256(raw),
                     'source_git_blob_sha1': blob, 'source_head_assertion': tree['commit'],
                     'source_tree_authenticated': False}

    physical, pyz, base_zip, startup, namespaces = {}, {}, {}, {}, {}
    occurrences = {}

    def add_occurrence(identity, location):
        occurrences.setdefault(identity, set()).add(location)

    for name, proof in members['application_source_compared'].items():
        _, git_proof = project_source(name)
        if proof['git_blob_sha1'] != git_proof['source_git_blob_sha1']:
            raise ValueError('Application code source differs from Git declaration')
        module = 'study_workbench' + ('' if Path(name).stem == '__init__' else '.' + Path(name).stem)
        add_occurrence(app_identity, 'study_backend.exe!PYZ.pyz/' + module)
    for name, item in members['physical_files'].items():
        if item['status'] != 'unmapped' or not name.startswith(('_internal/migrations/', '_internal/study_workbench/')):
            continue
        relative = 'backend/' + name.removeprefix('_internal/')
        if relative.casefold() not in source_blobs:
            continue
        raw, proof = project_source(relative)
        if sha256(raw) == files[name]['sha256']:
            physical[name] = [{**proof, 'evidence_kind': 'project_git_blob_bytes'}]
            add_occurrence(app_identity, name)
    remaining_by_hash = {}
    for path, value in members['physical_files'].items():
        if value['status'] == 'unmapped' and path not in physical:
            remaining_by_hash.setdefault(files[path]['sha256'], []).append(path)
    for purl, data in builds.items():
        record_name = data['proof']['record_path']
        target = '_internal/' + record_name
        if target in files and members['physical_files'][target]['status'] == 'unmapped':
            own_rows = [row for row in data['rows'] if row[0] == record_name]
            if len(own_rows) == 1 and own_rows[0][1:] == ['', ''] and files[target]['sha256'] == data['proof']['record_sha256']:
                physical[target] = [{'identity': purl, 'source_path': record_name,
                                     'source_sha256': data['proof']['record_sha256'],
                                     'metadata_sha256': data['proof']['metadata_sha256'],
                                     'evidence_kind': 'local_record_metadata_bytes', 'record_self_hash_declared': False}]
                add_occurrence(purl, target)
        for name, digest, size in data['rows']:
            if not digest.startswith('sha256=') or '..' in PurePosixPath(name).parts:
                continue
            selected = [sha for sha in remaining_by_hash
                        if digest == 'sha256=' + base64.urlsafe_b64encode(bytes.fromhex(sha)).decode().rstrip('=')]
            if not selected:
                continue
            _, proof = build_source(purl, name, digest, size)
            for target in remaining_by_hash[selected[0]]:
                physical.setdefault(target, []).append({**proof, 'evidence_kind': 'relocated_build_record_bytes'})
                add_occurrence(purl, target)

    with zipfile.ZipFile(io.BytesIO(python_raw)) as nuget:
        info = zip_members(nuget)
        cache, expanded = {}, 0

        def nuget_source(name, limit):
            nonlocal expanded
            safe_name(name)
            item = info[name.casefold()]
            if item.filename.casefold() != name.casefold() or item.is_dir() or item.file_size > limit:
                raise ValueError('NuGet source name or member budget differs: ' + name)
            name = item.filename
            if name not in cache:
                with nuget.open(item) as stream:
                    raw = stream.read(min(limit, MAX_ZIP_MEMBER_BYTES) + 1)
                if len(raw) != item.file_size or len(raw) > limit:
                    raise ValueError('NuGet actual expanded bytes differ or exceed budget')
                expanded += len(raw)
                if expanded > MAX_ZIP_BYTES:
                    raise ValueError('NuGet read byte budget exceeded')
                cache[name] = raw
            raw = cache[name]
            return raw, {'identity': 'pkg:nuget/python@' + PYTHON_VERSION, 'source_path': name,
                         'source_sha256': sha256(raw), 'archive_sha256': PYTHON_ARCHIVE_SHA256}

        raw_nuspec, _ = nuget_source('python.nuspec', MAX_RECORD_BYTES)
        try:
            spec = SafeET.fromstring(raw_nuspec, forbid_dtd=True)
        except DefusedXmlException as exc:
            raise ValueError('NuGet XML entities are not allowed') from exc
        metadata_nodes = spec.findall('{*}metadata')
        if spec.tag.rsplit('}', 1)[-1] != 'package' or len(metadata_nodes) != 1:
            raise ValueError('Missing or ambiguous NuGet metadata')
        fields = [(x.tag.rsplit('}', 1)[-1], x.text) for x in metadata_nodes[0]]
        if any(sum(name == field for name, _ in fields) != 1 for field in ('id', 'version')):
            raise ValueError('Missing or duplicate NuGet identity')
        package_meta = dict(fields)
        if package_meta.get('id') != 'python' or package_meta.get('version') != PYTHON_VERSION:
            raise ValueError('Pinned NuGet metadata identity differs')
        pyz_at = next(x['offset'] for x in archive['carchive'] if x['kind'] == 'z')
        for name, item in members['modules'].items():
            if item['status'] != 'unmapped':
                continue
            entry = archive['pyz'][name]
            if entry['kind'] == 3:
                children = {n: v for n, v in members['modules'].items()
                            if n.startswith(name + '.') and v['status'] == 'matched'}
                namespaces[name] = {'kind': 'namespace_container', 'stored_code_bytes': 0,
                                    'namespace_version': None, 'package_identity_authenticated': False,
                                    'verified_child_modules': len(children),
                                    'contributing_build_distributions': sorted({v['candidates'][0]['purl'] for v in children.values()})}
                continue
            relative = 'tools/Lib/' + name.replace('.', '/') + ('/__init__.py' if entry['kind'] == 1 else '.py')
            if relative.casefold() not in info:
                continue
            raw, proof = nuget_source(relative, MAX_MEMBER_BYTES)
            start = pyz_at + entry['offset']
            actual = marshal.loads(bounded_inflate(raw_exe[start:start + entry['compressed_bytes']]))
            optimization = levels(actual, raw)
            if optimization:
                pyz[name] = [{**proof, 'equivalent_optimization_levels': optimization}]
                add_occurrence(proof['identity'], 'study_backend.exe!PYZ.pyz/' + name)
        for name, item in members['physical_files'].items():
            if item['status'] != 'unmapped':
                continue
            for relative in ('tools/' + Path(name).name, 'tools/DLLs/' + Path(name).name):
                if relative.casefold() not in info:
                    continue
                raw, proof = nuget_source(relative, MAX_ZIP_MEMBER_BYTES)
                if sha256(raw) == files[name]['sha256']:
                    physical.setdefault(name, []).append({**proof, 'evidence_kind': 'pinned_nuget_bytes'})
                    add_occurrence(proof['identity'], name)
        with zipfile.ZipFile(payload / '_internal/base_library.zip') as base:
            for item in base.infolist():
                name = safe_name(item.orig_filename)
                relative = 'tools/Lib/' + name.removesuffix('.pyc') + '.py'
                if not name.endswith('.pyc') or relative.casefold() not in info:
                    continue
                with base.open(item) as stream:
                    raw = stream.read(MAX_MEMBER_BYTES + 1)
                if (len(raw) != item.file_size or len(raw) > MAX_MEMBER_BYTES or len(raw) < 16
                        or raw[:4] != importlib.util.MAGIC_NUMBER or struct.unpack('<I', raw[4:8])[0] not in (0, 1, 3)):
                    raise ValueError('Invalid or oversized base-library pyc')
                source_bytes, proof = nuget_source(relative, MAX_MEMBER_BYTES)
                optimization = levels(marshal.loads(raw[16:]), source_bytes)
                if optimization:
                    base_zip[name] = [{**proof, 'equivalent_optimization_levels': optimization}]
                    add_occurrence(proof['identity'], '_internal/base_library.zip!/' + name)
        for entry in archive['carchive']:
            name = entry['name']
            if entry['kind'] not in {'s', 'm'}:
                startup[name] = {'kind': entry['kind'], 'status': 'embedded_container', 'candidates': []}
                continue
            stored = raw_exe[entry['offset']:entry['offset'] + entry['stored_bytes']]
            raw = bounded_inflate(stored) if entry['compressed'] else stored
            if len(raw) > MAX_MEMBER_BYTES or len(raw) != entry['declared_unpacked_bytes']:
                raise ValueError('CArchive code length differs or exceeds budget')
            actual, candidates, sources = marshal.loads(raw), [], []
            if name == 'struct':
                sources.append(nuget_source('tools/Lib/struct.py', MAX_MEMBER_BYTES))
            elif name == 'frozen_entry':
                sources.append(project_source('tools/frozen_entry.py'))
            else:
                for purl, data in builds.items():
                    if not purl.startswith('pkg:pypi/pyinstaller@'):
                        continue
                    for relative, digest, size in data['rows']:
                        if relative.startswith('PyInstaller/') and Path(relative).name == name + '.py':
                            sources.append(build_source(purl, relative, digest, size))
            for source_bytes, proof in sources:
                optimization = levels(actual, source_bytes)
                if optimization:
                    candidates.append({**proof, 'equivalent_optimization_levels': optimization})
                    add_occurrence(proof['identity'], 'study_backend.exe!CArchive/' + name)
            startup[name] = {'kind': entry['kind'], 'status': 'source_matched' if len(candidates) == 1
                             else 'multiple_matching_sources' if candidates else 'unmapped', 'candidates': candidates}
        nuget_reads = {name: {'sha256': sha256(raw), 'bytes': len(raw)} for name, raw in cache.items()}

    if (files != inventory(payload) or archive != embedded(payload / 'study_backend.exe', source)
            or python_raw != bounded_file(python_package, MAX_ARCHIVE_BYTES)
            or tree_raw != bounded_file(source_tree, MAX_REPORT_BYTES)
            or coverage_raw != bounded_file(coverage_file, MAX_REPORT_BYTES)
            or member_raw != bounded_file(output / 'local-members/members.json', MAX_REPORT_BYTES)
            or bom_raw != bounded_file(output / 'local-members/python-members.cdx.json', MAX_REPORT_BYTES)
            or locks != {n: read_lock(source / n) for n in LOCKS}):
        raise ValueError('Payload, declared Git source, archive, coverage or locks changed')
    for path, proof in inputs.items():
        if sha256(bounded_file(path, proof['limit'])) != proof['sha256']:
            raise ValueError('Build or project source changed during matching')
    bom = copy.deepcopy(json.loads(bom_raw))
    components = {x['bom-ref']: x for x in bom['components']}
    for identity, locations in sorted(occurrences.items()):
        if identity not in components:
            if identity == app_identity:
                item = {'type': 'application', 'bom-ref': identity, 'name': 'StudyWorkbench-backend', 'version': tree['commit'],
                        'properties': [{'name': 'studyworkbench:version-kind', 'value': 'declared-source-commit'},
                                       {'name': 'studyworkbench:source-tree-authenticated', 'value': 'false'}]}
            elif identity.startswith('pkg:nuget/'):
                item = {'type': 'library', 'bom-ref': identity, 'purl': identity, 'name': 'python', 'version': PYTHON_VERSION,
                        'hashes': [{'alg': 'SHA-256', 'content': PYTHON_ARCHIVE_SHA256}],
                        'externalReferences': [{'type': 'distribution', 'url': 'https://api.nuget.org/v3-flatcontainer/python/'
                                                 + PYTHON_VERSION + '/python.' + PYTHON_VERSION + '.nupkg'}],
                        'properties': [{'name': 'studyworkbench:archive-pin-matched', 'value': 'true'},
                                       {'name': 'studyworkbench:publisher-signature-verified', 'value': 'false'}]}
            else:
                build = builds[identity]['proof']
                name, version = identity.removeprefix('pkg:pypi/').rsplit('@', 1)
                item = {'type': 'library', 'bom-ref': identity, 'purl': identity, 'name': name, 'version': version,
                        'properties': [{'name': 'studyworkbench:metadata-sha256', 'value': build['metadata_sha256']},
                                       {'name': 'studyworkbench:record-sha256', 'value': build['record_sha256']},
                                       {'name': 'studyworkbench:upstream-provenance-verified', 'value': 'false'}]}
            components[identity] = item
        component = components[identity]
        old = {x['location'] for x in component.get('evidence', {}).get('occurrences', [])}
        component['evidence'] = {'occurrences': [{'location': x} for x in sorted(old | locations)]}
    bom['components'] = [components[n] for n in sorted(components)]
    bom['metadata']['properties'].append({'name': 'studyworkbench:scope-extension', 'value': 'pinned-Python-and-declared-source-origins'})
    augmented_raw = (json.dumps(bom, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
    (output / 'python-origins.cdx.json').write_bytes(augmented_raw)
    report = {'schema_version': 1, 'scope': 'extended-frozen-Python-source-origins', 'product_sbom_complete': False,
              'upstream_provenance_verified': False, 'source_tree_authenticated': False,
              'collector_sha256': sha256(Path(__file__).read_bytes()), 'base_members_sha256': sha256(member_raw),
              'base_bom_sha256': sha256(bom_raw), 'coverage_sha256': sha256(coverage_raw),
              'source_head_assertion': tree['commit'], 'source_tree_assertion': tree['tree'], 'source_tree_input_sha256': sha256(tree_raw),
              'payload_fingerprint': members['payload_fingerprint'], 'exe_sha256': members['exe_sha256'],
              'source_lock_sha256': members['source_lock_sha256'], 'python_archive_sha256': PYTHON_ARCHIVE_SHA256,
              'python_nuspec_sha256': sha256(raw_nuspec), 'python_package_metadata': package_meta,
              'nuget_members_read': nuget_reads, 'additional_pyz_origins': pyz, 'base_library_origins': base_zip,
              'additional_physical_origins': physical, 'carchive_origins': startup, 'namespace_descriptions': namespaces,
              'remaining_unmapped_code_modules': sorted(n for n, x in members['modules'].items()
                                                       if x['status'] == 'unmapped' and n not in pyz and n not in namespaces),
              'remaining_unmapped_physical': sorted(n for n, x in members['physical_files'].items()
                                                    if x['status'] == 'unmapped' and n not in physical),
              'remaining_unmapped_base_library': sorted(set(coverage['base_library_zip']) - set(base_zip)),
              'build_records_indexed': rows_total, 'source_files_rechecked': len(inputs), 'source_logical_bytes': logical_bytes,
              'bom_sha256': sha256(augmented_raw), 'limitations': LIMITATIONS}
    (output / 'origins.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--payload', type=Path, required=True)
    parser.add_argument('--source', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--coverage', type=Path, required=True)
    parser.add_argument('--python-package', type=Path, required=True)
    parser.add_argument('--source-tree', type=Path, required=True, help='Caller-declared Git blob manifest; authenticate separately')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    try:
        report = generate(args.payload, args.source, args.coverage, args.python_package, args.source_tree, args.output)
    except (OSError, ValueError, TypeError, KeyError, EOFError, SyntaxError, struct.error, zlib.error,
            yaml.YAMLError, zipfile.BadZipFile, ET.ParseError) as exc:
        parser.exit(1, f'Frozen Python origins failed: {exc}\n')
    print(f"Compared {len(report['additional_pyz_origins'])} additional modules; product and native origins remain incomplete.")
    return 2


if __name__ == '__main__':
    raise SystemExit(main())
