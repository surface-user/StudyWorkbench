"""Inventory the default Windows installer and verify the compiler's solid LZMA2 file stream."""
import argparse
import hashlib
import io
import json
import lzma
import mmap
import ntpath
import re
import tempfile
import zipfile
from pathlib import Path

import yaml
from frozen_member_licenses import BUNDLE_PATH, bundle_bytes, verify_bundle
from frozen_sbom import inventory
from source_sbom import UniqueLoader, no_links, sha256
from source_vulnerabilities import unique_object

MAX_SETUP = 1024 * 1024**2
BLOCK = 65536
CALL = re.compile(rb'[\xe8\xe9]....', re.DOTALL)


def file_digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def encoded_calls(data, offset):
    # Inno's executable filter resets at each 64 KiB file block.
    def encode(match):
        instruction = match.group()
        if instruction[4] not in (0, 255):
            return instruction
        operand = int.from_bytes(instruction[1:4], 'little')
        absolute = (operand + offset + match.start() + 5) & 0xffffff
        high = instruction[4] ^ (255 if operand & 0x800000 else 0)
        return instruction[:1] + absolute.to_bytes(3, 'little') + bytes([high])

    return CALL.sub(encode, data)


def path_key(path):
    return ntpath.normcase(ntpath.normpath(str(path).removeprefix('\\\\?\\')))


def compiler_order(log_bytes, targets):
    keys = {path_key(path): ref for ref, path in targets.items()}
    if len(keys) != len(targets):
        raise ValueError('Compiler input path collision')
    ordered = []
    for line in log_bytes.decode('utf-8-sig').splitlines():
        match = re.fullmatch(r'\s*Compressing: (.+)', line)
        if match:
            name = path_key(match[1])
            if name not in keys:
                name = re.sub(r'   \([0-9.]+\)$', '', name)
            if name not in keys:
                raise ValueError('Unexpected compiler input')
            ordered.append(keys[name])
    if len(ordered) != len(keys) or set(ordered) != set(targets):
        raise ValueError('Missing or duplicate compiler input')
    return ordered


def unpack_solid(setup, output, size):
    if not 0 < setup.stat().st_size <= MAX_SETUP:
        raise ValueError('Installer exceeds supported size')
    with setup.open('rb') as src, mmap.mmap(src.fileno(), 0, access=mmap.ACCESS_READ) as packed:
        # The current setup.iss has a single unencrypted solid LZMA2 stream.
        mark = b'zlb\x1a'
        pos = 0
        for _ in range(32):
            pos = packed.find(mark, pos)
            if pos < 0:
                break
            pos += len(mark)
            if pos >= len(packed) or packed[pos] > 28:
                continue
            prop = packed[pos]
            decoder = lzma.LZMADecompressor(format=lzma.FORMAT_RAW, filters=[{
                'id': lzma.FILTER_LZMA2, 'dict_size': (2 | (prop & 1)) << ((prop >> 1) + 11)}])
            read = pos + 1
            output.seek(0)
            output.truncate()
            try:
                while not decoder.eof and output.tell() <= size:
                    chunk = packed[read:read + BLOCK] if decoder.needs_input else b''
                    if decoder.needs_input and not chunk:
                        break
                    read += len(chunk)
                    output.write(decoder.decompress(chunk, max_length=min(1 << 20, size - output.tell() + 1)))
                if decoder.eof and output.tell() == size:
                    output.seek(0)
                    return
            except lzma.LZMAError:
                continue
    raise ValueError('Missing or mismatched installer file stream')


def verify_stream(stream, ordered, targets, records):
    for name in ordered:
        raw_ok = filtered_ok = True
        record = records[name]
        digest = hashlib.sha256()
        with targets[name].open('rb') as source:
            for offset in range(0, record['bytes'], BLOCK):
                length = min(BLOCK, record['bytes'] - offset)
                raw = source.read(length)
                packed = stream.read(length)
                if len(raw) != length or len(packed) != length:
                    raise ValueError('Truncated installer input')
                digest.update(raw)
                raw_ok = raw_ok and packed == raw
                filtered_ok = filtered_ok and packed == encoded_calls(raw, offset)
                if not raw_ok and not filtered_ok:
                    raise ValueError('Installer bytes differ from staged input')
            if source.read(1) or digest.hexdigest() != record['sha256']:
                raise ValueError('Compiler input changed')
    if stream.read(1):
        raise ValueError('Unlisted installer stream bytes')


def compare_desktop(report, files):
    no_links(report.absolute())
    if report.stat().st_size > 16 << 20:
        raise ValueError('Desktop evidence exceeds budget')
    data = json.loads(report.read_bytes(), object_pairs_hook=unique_object)
    if data['scope'] != 'Windows-desktop-artifact-and-selected-copy-origins':
        raise ValueError('Unexpected desktop evidence scope')
    packages = {}
    for path, row in data['physical_files'].items():
        if row.get('copied_source_bytes_verified') is not True or path not in files:
            continue
        if (row['bytes'], row['sha256']) != (files[path]['bytes'], files[path]['sha256']):
            continue
        identity = row['source_identity']
        if (not re.fullmatch(r'pkg:(?:generic|pub|nuget)/[\w.-]+@[\w.\-]+(?:\?hosted_url=pub\.dev)?', identity)
                or not row['sources'] or not all(s['sha256'] == row['sha256'] for s in row['sources'])):
            raise ValueError('Invalid desktop source assertion')
        packages.setdefault(identity, []).append({'location': 'app/' + path})
    return packages


def webview_version(manifest, digest):
    no_links(manifest.absolute())
    if manifest.stat().st_size > 1 << 20:
        raise ValueError('WinGet manifest exceeds budget')
    data = yaml.load(manifest.read_bytes(), Loader=UniqueLoader)
    version = data['PackageVersion']
    if (data['PackageIdentifier'] != 'Microsoft.EdgeWebView2Runtime' or
            not re.fullmatch(r'\d+(?:\.\d+){3}', version) or
            not any(row.get('Architecture') == 'x64' and row.get('InstallerSha256', '').lower() == digest
                    for row in data['Installers'])):
        raise ValueError('Runtime installer differs from supplied version manifest')
    return version


def backend_dependencies(report, files, mapped_packages):
    no_links(report.absolute())
    if report.stat().st_size > 32 << 20:
        raise ValueError('Backend SBOM exceeds budget')
    data = json.loads(report.read_bytes(), object_pairs_hook=unique_object)
    if (data['bomFormat'], data['specVersion']) != ('CycloneDX', '1.6'):
        raise ValueError('Expected backend CycloneDX 1.6')
    remaining = {key.removeprefix('backend/'): v['sha256'] for key, v in files.items() if key.startswith('backend/')}
    libraries = {}
    for component in data['components']:
        if component['type'] == 'file':
            name = component['name']
            digest = remaining.pop(name, None)
            if digest is None or {'alg': 'SHA-256', 'content': digest} not in component['hashes']:
                raise ValueError('Backend SBOM file differs from this stage')
        elif component['type'] == 'library':
            purl = component['purl']
            if (component['bom-ref'] != purl or purl in libraries
                    or not re.fullmatch(r'pkg:(?:pypi|nuget|generic)/[A-Za-z0-9_.-]+@[A-Za-z0-9.+-]+', purl)):
                raise ValueError('Invalid backend library identity')
            libraries[purl] = None
        else:
            raise ValueError('Unexpected backend component')
    if remaining or not set(mapped_packages).issubset(libraries):
        raise ValueError('Incomplete backend file or library set')
    graph = data['dependencies']
    if len({row['ref'] for row in graph}) != len(graph):
        raise ValueError('Duplicate backend dependency row')
    for row in graph:
        if (row['ref'] not in mapped_packages or not set(row['dependsOn']).issubset(mapped_packages)
                or len(set(row['dependsOn'])) != len(row['dependsOn'])):
            raise ValueError('Dependency refers to a library outside the mapped backend set')
    return libraries, [{'ref': row['ref'], 'dependsOn': row['dependsOn']} for row in graph]


def generate(stage, setup, runtime, log, output, desktop_report=None, webview_manifest=None, backend_report=None):
    for path in (stage, setup, runtime, log, output.parent):
        no_links(path.absolute())
    if output.exists() or output.resolve().is_relative_to(stage.resolve()):
        raise ValueError('Use a new output outside the staging tree')
    if (not 0 < setup.stat().st_size <= MAX_SETUP or not 0 < log.stat().st_size <= 16 << 20
            or not 0 < runtime.stat().st_size <= 512 << 20):
        raise ValueError('Installer, compiler log or runtime input exceeds budget')
    stage = stage.resolve()
    files = inventory(stage)
    inventory_name = 'build-inventory.json'
    if inventory_name not in files or files[inventory_name]['bytes'] > 16 << 20:
        raise ValueError('Missing or oversized build inventory')
    index = json.loads((stage / inventory_name).read_bytes(), object_pairs_hook=unique_object)
    if {name: rec['sha256'] for name, rec in files.items() if name != inventory_name} != index['files']:
        raise ValueError('Build inventory does not match stage')
    license_record = index['python_license_bundle']
    verified = verify_bundle(stage / 'backend', stage / BUNDLE_PATH, license_record['sha256'])
    if verified != license_record:
        raise ValueError('Frozen license receipt differs')
    raw_zip = bundle_bytes(stage / BUNDLE_PATH)
    if verified['sha256'] != sha256(raw_zip):
        raise ValueError('Frozen license archive changed')
    with zipfile.ZipFile(io.BytesIO(raw_zip)) as archive:
        packages = json.loads(archive.read('index.json'))['packages']

    records = {'app/' + name: data for name, data in files.items()}
    targets = {'app/' + name: stage / name for name in files}
    if runtime.name != 'MicrosoftEdgeWebView2RuntimeInstallerX64.exe':
        raise ValueError('Unexpected WebView runtime installer name')
    bundled = 'installer/' + runtime.name
    targets[bundled] = runtime.resolve()
    records[bundled] = {'bytes': runtime.stat().st_size, 'sha256': file_digest(runtime)}
    log_bytes = log.read_bytes()
    ordered = compiler_order(log_bytes, targets)
    setup_hash = file_digest(setup)
    with tempfile.TemporaryFile(dir=output.parent) as stream:
        unpack_solid(setup, stream, sum(record['bytes'] for record in records.values()))
        verify_stream(stream, ordered, targets, records)
    components = [{'type': 'file', 'bom-ref': 'file:' + name, 'name': name,
                   'hashes': [{'alg': 'SHA-256', 'content': record['sha256']}]} for name, record in sorted(records.items())]
    evidence = {}
    for label, path, limit in (('backend-sbom', backend_report, 32 << 20), ('desktop-report', desktop_report, 16 << 20),
                               ('webview-manifest', webview_manifest, 1 << 20)):
        if path is not None:
            no_links(path.absolute())
            if path.stat().st_size > limit:
                raise ValueError('Component comparison input exceeds budget')
            evidence[label] = path, file_digest(path)
    providers, dependencies = dict.fromkeys(packages), []
    if backend_report:
        providers, dependencies = backend_dependencies(backend_report, files, packages)
    if desktop_report:
        providers.update(compare_desktop(desktop_report, files))
    for purl, occurrences in sorted(providers.items()):
        name, version = purl.split('/', 1)[1].split('@', 1)
        component = {'type': 'library', 'bom-ref': purl, 'purl': purl, 'name': name, 'version': version.split('?')[0]}
        if occurrences:
            component['evidence'] = {'occurrences': occurrences}
        components.append(component)
    if webview_manifest:
        version = webview_version(webview_manifest, records[bundled]['sha256'])
        components.append({'type': 'application', 'bom-ref': 'webview-runtime:' + version,
                           'name': 'Microsoft Edge WebView2 Runtime', 'version': version,
                           'evidence': {'occurrences': [{'location': bundled}]}})
    root = {'type': 'application', 'name': 'StudyWorkbench Windows setup', 'bom-ref': 'setup:' + setup_hash,
            'hashes': [{'alg': 'SHA-256', 'content': setup_hash}]}
    bom = {'bomFormat': 'CycloneDX', 'specVersion': '1.6', 'version': 1,
           'metadata': {'component': root, 'properties': [
               {'name': 'studyworkbench:scope', 'value': 'verified compiler input bytes, mapped frozen PyPI and supplied source comparisons'},
               {'name': 'studyworkbench:product-sbom-complete', 'value': 'false'}]},
           'components': components, 'compositions': [{'aggregate': 'incomplete', 'assemblies': [root['bom-ref']]}]}
    if dependencies:
        bom['dependencies'] = dependencies
    for label, (path, digest) in evidence.items():
        if file_digest(path) != digest:
            raise ValueError('Component comparison input changed during verification')
        bom['metadata']['properties'].append({'name': 'studyworkbench:' + label + '-sha256', 'value': digest})
    if (file_digest(setup) != setup_hash or file_digest(runtime) != records[bundled]['sha256']
            or file_digest(log) != sha256(log_bytes) or inventory(stage) != files):
        raise ValueError('Installer validation input changed')
    with output.open('x', encoding='utf-8') as dest:
        json.dump(bom, dest, ensure_ascii=False, indent=2)
        dest.write('\n')
    return len(files), len(packages)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('stage', 'setup', 'runtime', 'compiler-log', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--desktop-report', type=Path, help='Existing desktop_sbom.py copy-source comparison')
    parser.add_argument('--webview-manifest', type=Path, help='Upstream WinGet x64 installer manifest')
    parser.add_argument('--backend-sbom', type=Path, help='Backend file and Requires-Dist SBOM from this payload')
    args = parser.parse_args()
    files, packages = generate(args.stage, args.setup, args.runtime, args.compiler_log, args.output,
                               args.desktop_report, args.webview_manifest, args.backend_sbom)
    print(f'Verified {files} staged files, the offline runtime installer and {packages} mapped PyPI packages.')


if __name__ == '__main__':
    main()
