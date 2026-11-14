"""Inventory one Windows CI desktop artifact and compare selected copied sources."""

import argparse
import gzip
import hashlib
import io
import json
import os
import re
import stat
import struct
import tarfile
import zipfile
from pathlib import Path

import pefile
import yaml
from defusedxml import ElementTree as SafeET
from defusedxml.common import DefusedXmlException
from frozen_python_members import bounded_file
from frozen_sbom import safe_name
from source_sbom import LOCKS, UniqueLoader, lock_inventory, no_links, read_lock, sha256
from source_vulnerabilities import unique_object

DESKTOP_PREFIX = 'apps/desktop/build/windows/x64/runner/Release/'
ENGINE_REVISION = '5d531788691ec3404cac0cee66ead4007b177363'
ENGINE_BYTES = 70289419
ENGINE_SHA256 = 'a553d14c6087cf3f049ab1ddeedaf9e3216d341b39b036f7dc29cee52119fc4e'
ENGINE_URL = ('https://storage.googleapis.com/flutter_infra_release/flutter/' + ENGINE_REVISION
              + '/windows-x64-release/windows-x64-flutter.zip')
ICU_ARCHIVE_BYTES = 30535798
ICU_ARCHIVE_SHA256 = 'fd626db3afddcc37dcf052f1a26cc43834ac6dcc4c45d8e0a5c10e6a2272b3df'
ICU_ARCHIVE_URL = ('https://storage.googleapis.com/flutter_infra_release/flutter/' + ENGINE_REVISION
                   + '/windows-x64/artifacts.zip')
WEBVIEW_VERSION = '1.0.2792.45'
WEBVIEW_BYTES = 8474494
WEBVIEW_SHA256 = '02ffd77440c09b5ff60f5f06defdc3fb07fb5630077c7cf6115bf6be793f91e3'
WEBVIEW_URL = ('https://api.nuget.org/v3-flatcontainer/microsoft.web.webview2/' + WEBVIEW_VERSION
               + '/microsoft.web.webview2.' + WEBVIEW_VERSION + '.nupkg')
MAX_ARCHIVE_BYTES = 128 * 1024 * 1024
MAX_MEMBER_BYTES = 256 * 1024 * 1024
MAX_EXPANDED_BYTES = 1024**3
MAX_READ_BYTES = 512 * 1024 * 1024
MAX_INPUT_FILES = 20000
MAX_INPUT_BYTES = 512 * 1024 * 1024
MAX_TAR_BYTES = 128 * 1024 * 1024
PLUGIN_PRODUCERS = {'flutter_inappwebview_windows_plugin.dll': 'flutter_inappwebview_windows',
                    'url_launcher_windows_plugin.dll': 'url_launcher_windows'}
LIMITATIONS = [
    'Artifact/run/checkout/Git metadata are caller-provided snapshots; the offline tool does not authenticate GitHub or a build attestation.',
    'A matching checkout Git tree identifies tracked inputs, not every SDK/toolchain/header or actual compiler read.',
    'Only observed copied assets/binaries are associated with package archives; package_config, lock or cache membership is not AOT membership.',
    'Generated AOT, runner/plugins, fonts/shaders/manifests/notices and differing project bytes retain unknown source equivalence.',
    'Without the optional fixed host archive, ICU has only a local cache comparison; archive correspondence does not identify its independent ICU version, license obligations or SDK-wide provenance.',
    'Archive pins and partial byte correspondence do not certify signatures, dependency edges, native embedded libraries, licenses or vulnerabilities.',
    'The backend, build-only packages, CRT staging, Office/Java, WebView2 installer and final setup are outside this desktop subset.',
    'Before/after hashes detect observed changes, not an atomic snapshot or reproducible build.',
]


def zip_index(archive):
    entries, total = {}, 0
    for info in archive.infolist():
        name = safe_name(info.orig_filename[:-1] if info.is_dir() else info.orig_filename)
        mode = info.external_attr >> 16
        total += info.file_size
        if (info.orig_filename != info.filename or name.casefold() in entries or info.flag_bits & 1
                or stat.S_ISLNK(mode) or (stat.S_IFMT(mode) and not (stat.S_ISREG(mode) or stat.S_ISDIR(mode)))):
            raise ValueError('Unsafe, duplicate, encrypted or special ZIP member')
        if len(entries) >= MAX_INPUT_FILES or info.file_size > MAX_MEMBER_BYTES or total > MAX_EXPANDED_BYTES:
            raise ValueError('ZIP declared member/count/byte budget exceeded')
        entries[name.casefold()] = info
    return entries


def read_zip(archive, info, budget):
    if info.is_dir() or budget[0] + info.file_size > MAX_READ_BYTES:
        raise ValueError('ZIP actual read budget exceeded or directory selected')
    with archive.open(info) as stream:
        raw = stream.read(min(MAX_MEMBER_BYTES, MAX_READ_BYTES - budget[0]) + 1)
    budget[0] += len(raw)
    if len(raw) != info.file_size or budget[0] > MAX_READ_BYTES or len(raw) > MAX_MEMBER_BYTES:
        raise ValueError('ZIP actual decompressed length/budget rejected')
    return raw


def pub_contents(raw, budget):
    allowed = min(MAX_TAR_BYTES, MAX_READ_BYTES - budget[0])
    with gzip.GzipFile(fileobj=io.BytesIO(raw)) as stream:
        plain = stream.read(allowed + 1)
    budget[0] += len(plain)
    if len(plain) > allowed:
        raise ValueError('Pub archive actual expansion budget exceeded')
    archive = tarfile.open(fileobj=io.BytesIO(plain), mode='r:')
    try:
        entries, total = {}, 0
        for info in archive:
            name = safe_name(info.name.rstrip('/') if info.isdir() else info.name)
            total += info.size
            if name.casefold() in entries or not (info.isfile() or info.isdir()):
                raise ValueError('Duplicate or special pub archive member')
            if len(entries) >= MAX_INPUT_FILES or info.size > 16 * 1024 * 1024 or total > MAX_TAR_BYTES:
                raise ValueError('Pub archive declared budget exceeded')
            entries[name.casefold()] = info
        return archive, entries
    except BaseException:
        archive.close()
        raise


def pe_header(raw):
    pe = pefile.PE(data=raw, fast_load=True)
    try:
        if pe.FILE_HEADER.Machine != 0x8664 or pe.OPTIONAL_HEADER.Magic != 0x20b:
            raise ValueError('Desktop native image must be AMD64 PE32+')
        return {'machine': pe.FILE_HEADER.Machine, 'optional_magic': pe.OPTIONAL_HEADER.Magic,
                'timestamp_claim': pe.FILE_HEADER.TimeDateStamp, 'signature_verified': False}
    finally:
        pe.close()


def generate(artifact, provenance_file, source_tree_file, source, engine_archive, webview_package, pub_archives, sdk, output, icu_archive=None):
    artifact, provenance_file, source_tree_file, source, engine_archive, webview_package, pub_archives, sdk, output = [
        Path(os.path.abspath(p)) for p in (artifact, provenance_file, source_tree_file, source, engine_archive,
                                         webview_package, pub_archives, sdk, output)]
    no_links(output.parent)
    if ((output.is_relative_to(source) and not output.is_relative_to(source / 'artifacts'))
            or output.is_relative_to(sdk) or output.is_relative_to(pub_archives)):
        raise ValueError('Output must be an artifact directory outside tracked source')
    inputs, input_bytes = {}, 0

    def remember(path, limit):
        nonlocal input_bytes
        no_links(path)
        if path not in inputs and (len(inputs) >= MAX_INPUT_FILES or input_bytes + path.stat().st_size > MAX_INPUT_BYTES):
            raise ValueError('Source input count/byte budget exceeded')
        if path not in inputs:
            limit = min(limit, MAX_INPUT_BYTES - input_bytes)
        raw = bounded_file(path, limit)
        if path in inputs and inputs[path]['sha256'] != sha256(raw):
            raise ValueError('Source input changed during matching')
        if path not in inputs:
            input_bytes += len(raw)
        inputs[path] = {'sha256': sha256(raw), 'limit': min(limit, inputs.get(path, {}).get('limit', limit))}
        return raw

    provenance_raw = remember(provenance_file, 4 * 1024 * 1024)
    tree_raw = remember(source_tree_file, 16 * 1024 * 1024)
    provenance = json.loads(provenance_raw, object_pairs_hook=unique_object)
    tree = json.loads(tree_raw, object_pairs_hook=unique_object)
    head, tree_sha = tree['commit'], tree['tree']
    run, item, checkout = [provenance[n] for n in ('run', 'artifact', 'checkout')]
    if (not all(re.fullmatch('[0-9a-f]{40}', n) for n in (head, tree_sha, checkout['commit']))
            or checkout['tree'] != tree_sha or run['head_sha'] != head or item['workflow_run']['head_sha'] != head
            or run['id'] != item['workflow_run']['id'] or run['status'] != 'completed' or run['conclusion'] != 'success'
            or item['name'] != 'windows-release-inputs-' + head or not re.fullmatch('sha256:[0-9a-f]{64}', item['digest'])):
        raise ValueError('Artifact/run/checkout source declarations disagree')
    artifact_raw = remember(artifact, MAX_ARCHIVE_BYTES)
    if sha256(artifact_raw) != item['digest'].split(':')[1] or len(artifact_raw) != item['size_in_bytes']:
        raise ValueError('Artifact bytes differ from declared service digest/size')
    locks = {n: read_lock(source / n) for n in LOCKS}
    expected, sdk_unknown, _ = lock_inventory(locks)
    dart_lock = yaml.load(locks[LOCKS[1]], Loader=UniqueLoader)['packages']
    blobs = {}
    if len(tree['entries']) > MAX_INPUT_FILES:
        raise ValueError('Git tree entry budget exceeded')
    for entry in tree['entries']:
        name = safe_name(entry['path'])
        if (name.casefold() in blobs or entry['type'] != 'blob' or entry['mode'] != '100644'
                or not re.fullmatch('[0-9a-f]{40}', entry['sha'])):
            raise ValueError('Malformed or duplicate Git blob declaration')
        blobs[name.casefold()] = {'path': name, 'sha': entry['sha']}
    project = {}
    for entry in sorted(blobs.values(), key=lambda x: x['path']):
        name = entry['path']
        if (not name.startswith(('apps/desktop/lib/', 'apps/desktop/windows/', 'apps/desktop/assets/'))
                and name not in ('apps/desktop/pubspec.yaml', 'apps/desktop/pubspec.lock', '.gitattributes', '.github/workflows/check.yml')):
            continue
        raw = remember(source / name, 8 * 1024 * 1024)
        blob = hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()
        if blob != entry['sha']:
            raise ValueError('Tracked desktop input differs from declared Git blob')
        project[name] = {'sha256': sha256(raw), 'git_blob_sha1': blob}
    engine_raw = remember(engine_archive, MAX_ARCHIVE_BYTES)
    webview_raw = remember(webview_package, 32 * 1024 * 1024)
    if ((len(engine_raw), sha256(engine_raw)) != (ENGINE_BYTES, ENGINE_SHA256)
            or (len(webview_raw), sha256(webview_raw)) != (WEBVIEW_BYTES, WEBVIEW_SHA256)):
        raise ValueError('Wrong fixed engine or WebView2 archive')
    sdk_metadata = json.loads(remember(sdk / 'bin/cache/flutter.version.json', 1024 * 1024), object_pairs_hook=unique_object)
    if sdk_metadata['frameworkVersion'] != '3.47.1' or sdk_metadata['engineRevision'] != ENGINE_REVISION:
        raise ValueError('Local SDK context differs from fixed engine declaration')
    if icu_archive is None:
        icu = remember(sdk / 'bin/cache/artifacts/engine/windows-x64/icudtl.dat', 16 * 1024 * 1024)
        icu_archive_raw = None
    else:
        icu_archive_raw = remember(Path(os.path.abspath(icu_archive)), MAX_ARCHIVE_BYTES)
        if (len(icu_archive_raw), sha256(icu_archive_raw)) != (ICU_ARCHIVE_BYTES, ICU_ARCHIVE_SHA256):
            raise ValueError('Wrong fixed ICU host archive')
    budget, physical, packages, pub_cache, producer_sources = [0], {}, {}, {}, {}
    if icu_archive_raw is not None:
        with zipfile.ZipFile(io.BytesIO(icu_archive_raw)) as shared:
            icu_info = zip_index(shared)['icudtl.dat']
            icu = read_zip(shared, icu_info, budget)

    def pub_source(package):
        if package in pub_cache:
            return pub_cache[package]
        spec = dart_lock[package]
        if spec['source'] != 'hosted' or spec['description']['url'] != 'https://pub.dev':
            raise ValueError('Observed pub asset requires fixed hosted archive')
        raw = remember(pub_archives / (package + '-' + spec['version'] + '.tar.gz'), 32 * 1024 * 1024)
        if sha256(raw) != spec['description']['sha256']:
            raise ValueError('Pub archive differs from locked hash')
        archive, index = pub_contents(raw, budget)
        try:
            stream = archive.extractfile(index['pubspec.yaml'])
            metadata_raw = stream.read(1024 * 1024 + 1)
            if len(metadata_raw) > 1024 * 1024:
                raise ValueError('Pub metadata budget exceeded')
            metadata = yaml.load(metadata_raw, Loader=UniqueLoader)
            if metadata['name'] != package or str(metadata['version']) != spec['version']:
                raise ValueError('Pub metadata identity differs from lock')
            selected = {}
            for name, info in index.items():
                if info.isfile() and (name.startswith(('assets/', 'lib/')) or name == 'windows/cmakelists.txt'):
                    with archive.extractfile(info) as handle:
                        data = handle.read(info.size + 1)
                    if len(data) != info.size:
                        raise ValueError('Pub member actual length differs')
                    selected[name] = (info.name, data)
        finally:
            archive.close()
        purl = next(n for n, v in expected.items() if n.startswith('pkg:pub/') and v['name'] == package)
        value = {'purl': purl, 'version': spec['version'], 'archive_sha256': sha256(raw), 'members': selected}
        pub_cache[package] = value
        return value

    with zipfile.ZipFile(io.BytesIO(artifact_raw)) as archive, zipfile.ZipFile(io.BytesIO(engine_raw)) as engine, zipfile.ZipFile(io.BytesIO(webview_raw)) as webview:
        entries, engines, webviews = [zip_index(z) for z in (archive, engine, webview)]
        engine_bytes = read_zip(engine, engines['flutter_windows.dll'], budget)
        nuspec_name = next(n for n in webviews if n.endswith('.nuspec'))
        nuspec = read_zip(webview, webviews[nuspec_name], budget)
        metadata = SafeET.fromstring(nuspec, forbid_dtd=True, forbid_entities=True, forbid_external=True)
        declared = {}
        for node in metadata.iter():
            key = node.tag.rsplit('}', 1)[-1]
            if key in ('id', 'version'):
                if key in declared:
                    raise ValueError('Duplicate WebView2 package metadata')
                declared[key] = node.text
        if declared != {'id': 'Microsoft.Web.WebView2', 'version': WEBVIEW_VERSION}:
            raise ValueError('Wrong WebView2 package identity')
        loader_sources = {}
        for name, info in webviews.items():
            if name.endswith('/webview2loader.dll'):
                loader_sources[info.filename] = read_zip(webview, info, budget)
        for name, info in entries.items():
            if not info.filename.startswith(DESKTOP_PREFIX) or info.is_dir():
                continue
            relative = safe_name(info.filename.removeprefix(DESKTOP_PREFIX))
            raw = read_zip(archive, info, budget)
            proof = {'bytes': len(raw), 'sha256': sha256(raw), 'artifact_member': info.filename,
                     'source_identity': None, 'copied_source_bytes_verified': False, 'sources': [], 'role': 'generated_or_unknown'}
            if relative.endswith(('.dll', '.exe')):
                proof['pe'] = pe_header(raw)
                proof['role'] = 'generated_native_image'
            if relative == 'data/app.so':
                proof['role'] = 'generated_AOT'
                proof['observed_magic_hex'] = raw[:16].hex()
            if relative.startswith('data/flutter_assets/packages/'):
                package, member = relative.removeprefix('data/flutter_assets/packages/').split('/', 1)
                data = pub_source(package)
                matches = [data['members'][n] for n in (member.casefold(), ('lib/' + member).casefold())
                           if n in data['members'] and data['members'][n][1] == raw]
                if matches:
                    proof.update(source_identity=data['purl'], copied_source_bytes_verified=True, role='copied_pub_asset',
                                 sources=[{'member': n, 'sha256': sha256(b), 'archive_sha256': data['archive_sha256']} for n, b in matches])
                    packages.setdefault(data['purl'], {'name': package, 'version': data['version'], 'hashes': data['archive_sha256'], 'locations': []})['locations'].append(relative)
            elif relative == 'flutter_windows.dll' and raw == engine_bytes:
                identity = 'pkg:generic/flutter-engine@' + ENGINE_REVISION
                proof.update(source_identity=identity, copied_source_bytes_verified=True, role='copied_engine_binary',
                             sources=[{'member': 'flutter_windows.dll', 'sha256': sha256(raw), 'archive_sha256': ENGINE_SHA256}])
                packages[identity] = {'name': 'flutter-engine', 'version': ENGINE_REVISION, 'hashes': ENGINE_SHA256, 'locations': [relative], 'url': ENGINE_URL}
            elif relative == 'WebView2Loader.dll':
                matches = [n for n, b in loader_sources.items() if b == raw]
                if matches:
                    identity = 'pkg:nuget/Microsoft.Web.WebView2@' + WEBVIEW_VERSION
                    proof.update(source_identity=identity, copied_source_bytes_verified=True, role='copied_nuget_loader',
                                 sources=[{'member': n, 'sha256': sha256(raw), 'archive_sha256': WEBVIEW_SHA256} for n in matches])
                    packages[identity] = {'name': 'Microsoft.Web.WebView2', 'version': WEBVIEW_VERSION, 'hashes': WEBVIEW_SHA256, 'locations': [relative], 'url': WEBVIEW_URL}
            elif relative == 'data/icudtl.dat':
                proof.update(independent_icu_identity_verified=False, icu_version=None,
                             license_obligations_verified=False, publisher_signature_verified=False)
                if icu_archive_raw is not None:
                    if raw != icu:
                        raise ValueError('Actual ICU bytes differ from fixed host archive member')
                    identity = 'pkg:generic/flutter-host-artifacts@' + ENGINE_REVISION
                    proof.update(source_identity=identity, copied_source_bytes_verified=True, role='copied_host_archive_icu_data',
                                 sources=[{'member': icu_info.filename, 'sha256': sha256(icu), 'archive_sha256': ICU_ARCHIVE_SHA256,
                                           'archive_bytes': ICU_ARCHIVE_BYTES, 'archive_url': ICU_ARCHIVE_URL,
                                           'official_archive_verified': True}])
                    packages[identity] = {'name': 'flutter-host-artifacts', 'version': ENGINE_REVISION,
                                          'hashes': ICU_ARCHIVE_SHA256, 'locations': [relative], 'url': ICU_ARCHIVE_URL,
                                          'identity_scope': 'archive-provider-not-independent-ICU-package'}
                elif raw == icu:
                    proof.update(role='local_sdk_cache_byte_match', sources=[{'member': 'bin/cache/artifacts/engine/windows-x64/icudtl.dat', 'sha256': sha256(icu), 'official_archive_verified': False}])
            elif relative.startswith('data/flutter_assets/assets/'):
                source_name = 'apps/desktop/assets/' + relative.removeprefix('data/flutter_assets/assets/')
                if source_name in project:
                    proof['declared_project_source'] = project[source_name]
                    proof['source_bytes_identical'] = proof['sha256'] == project[source_name]['sha256']
            physical[relative] = proof
        for target, package in PLUGIN_PRODUCERS.items():
            if target in physical:
                data = pub_source(package)
                name, raw = data['members']['windows/cmakelists.txt']
                producer_sources[target] = {'declared_package': package, 'declared_version': data['version'],
                                            'archive_sha256': data['archive_sha256'], 'cmake_member': name,
                                            'cmake_sha256': sha256(raw), 'binary_source_equivalence_verified': False}
        excluded = sorted(i.filename for i in entries.values() if not i.is_dir() and not i.filename.startswith(DESKTOP_PREFIX))
    if not physical or 'data/app.so' not in physical or 'study_workbench.exe' not in physical:
        raise ValueError('Missing actual Windows desktop payload')
    for path, proof in inputs.items():
        if sha256(bounded_file(path, proof['limit'])) != proof['sha256']:
            raise ValueError('Desktop source or artifact input changed at completion')
    if locks != {n: read_lock(source / n) for n in LOCKS}:
        raise ValueError('Source locks changed at completion')
    components = [{'type': 'file', 'bom-ref': 'desktop-file:' + n, 'name': n,
                   'hashes': [{'alg': 'SHA-256', 'content': p['sha256']}],
                   'properties': [{'name': 'studyworkbench:role', 'value': p['role']},
                                  {'name': 'studyworkbench:copied-source-bytes-verified', 'value': str(p['copied_source_bytes_verified']).lower()}]}
                  for n, p in sorted(physical.items())]
    for identity, data in sorted(packages.items()):
        component = {'type': 'library', 'bom-ref': identity, 'purl': identity, 'name': data['name'], 'version': data['version'],
                     'hashes': [{'alg': 'SHA-256', 'content': data['hashes']}],
                     'evidence': {'occurrences': [{'location': n} for n in sorted(data['locations'])]},
                     'properties': [{'name': 'studyworkbench:scope', 'value': 'observed-copied-members-only'},
                                    {'name': 'studyworkbench:publisher-signature-verified', 'value': 'false'}]}
        if 'url' in data:
            component['externalReferences'] = [{'type': 'distribution', 'url': data['url']}]
        if 'identity_scope' in data:
            component['properties'].append({'name': 'studyworkbench:identity-scope', 'value': data['identity_scope']})
        components.append(component)
    bom = {'bomFormat': 'CycloneDX', 'specVersion': '1.6', 'version': 1,
           'metadata': {'properties': [{'name': 'studyworkbench:product-sbom-complete', 'value': 'false'},
                                       {'name': 'studyworkbench:scope', 'value': 'one-Windows-desktop-CI-artifact-subset'},
                                       {'name': 'studyworkbench:source-tree-authenticated', 'value': 'false'}]}, 'components': components}
    bom_raw = (json.dumps(bom, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
    report = {'schema_version': 1, 'scope': 'Windows-desktop-artifact-and-selected-copy-origins', 'product_sbom_complete': False,
              'upstream_provenance_verified': False, 'source_tree_authenticated': False, 'build_attestation_verified': False,
              'AOT_source_equivalence_verified': False, 'reproducible_build_verified': False, 'signatures_verified': False,
              'collector_sha256': sha256(Path(__file__).read_bytes()), 'artifact_sha256': sha256(artifact_raw),
              'provenance_input_sha256': sha256(provenance_raw), 'source_tree_input_sha256': sha256(tree_raw),
              'source_head_assertion': head, 'source_tree_assertion': tree_sha, 'checkout_assertion': checkout,
              'run_assertion': run, 'artifact_id_assertion': item['id'], 'physical_files': physical,
              'copied_member_packages': sorted(packages), 'project_build_inputs': project, 'project_build_inputs_complete': False,
              'plugin_producer_associations': producer_sources, 'local_sdk_context': sdk_metadata,
              'sdk_lock_placeholders_not_runtime_members': sdk_unknown, 'excluded_artifact_files': excluded,
              'source_lock_sha256': {n: sha256(raw) for n, raw in locks.items()}, 'input_files_rechecked': len(inputs),
              'input_logical_bytes': input_bytes, 'actual_archive_bytes_read': budget[0], 'bom_sha256': sha256(bom_raw), 'limitations': LIMITATIONS}
    output.mkdir(exist_ok=False)
    (output / 'desktop.cdx.json').write_bytes(bom_raw)
    (output / 'desktop.json').write_bytes((json.dumps(report, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('artifact', 'provenance', 'source-tree', 'engine-archive', 'webview-package', 'pub-archives', 'sdk-root', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--source', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--icu-archive', type=Path, help='Optional fixed Windows shared host archive; no cache fallback on failure')
    args = parser.parse_args()
    try:
        report = generate(args.artifact, args.provenance, args.source_tree, args.source, args.engine_archive,
                          args.webview_package, args.pub_archives, args.sdk_root, args.output, args.icu_archive)
    except (OSError, ValueError, TypeError, KeyError, EOFError, SyntaxError, struct.error, yaml.YAMLError,
            zipfile.BadZipFile, tarfile.TarError, pefile.PEFormatError, DefusedXmlException) as exc:
        parser.exit(1, f'Desktop SBOM failed: {exc}\n')
    print(f"Inventoried {len(report['physical_files'])} desktop files; generated code and complete product SBOM remain unverified.")
    return 2


if __name__ == '__main__':
    raise SystemExit(main())
