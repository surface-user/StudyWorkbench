"""Generate a local CycloneDX inventory for a prepared Office/JRE component; never install it."""
import argparse
import hashlib
import json
import os
import re
import sys
import zipfile
from collections import defaultdict
from pathlib import Path

import pefile
from check_native_dependencies import component_payload
from lock_office_runtime import URL as OFFICE_URL
from native_dependencies import inspect_dependencies
from office_msi_members import file_sha, verify_msi
from prepare_java_runtime import LOCK_NAME, PACKAGE_SIZE, SOURCE_URL, no_links, package_entries
from source_vulnerabilities import unique_object

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from study_workbench.office_runtime import (  # noqa: E402
    APP_LOCAL_CRT,
    APP_LOCAL_PYTHON,
    JAVA,
    PACKAGE_SHA256,
    PYTHON_CORE,
    VERSION,
    OfficeRuntime,
)

MOUNT = 'converters/libreoffice/'
CRT = re.compile(r'(?:msvcp140(?:_\w+)?|vcruntime140(?:_\w+)?|vccorlib140|concrt140|ucrtbase|api-ms-win-crt-[\w-]+)\.dll')


def prop(name, value):
    return {'name': 'studyworkbench:' + name, 'value': str(value)}


def hashes(digest):
    return [{'alg': 'SHA-256', 'content': digest}]


def verify_java(package, expected):
    no_links(package.absolute())
    if package.stat().st_size != PACKAGE_SIZE or file_sha(package) != JAVA['package_sha256']:
        raise ValueError('Temurin package differs')
    found = {}
    with zipfile.ZipFile(package) as archive:
        for info, relative in package_entries(archive):
            if not info.is_dir():
                with archive.open(info) as data:
                    found[relative] = hashlib.file_digest(data, 'sha256').hexdigest()
    if found != expected:
        raise ValueError('Java files differ from pinned ZIP')


def pe_version(file, company, product=None):
    # Vendor/version fields are PE resource assertions. Origin is verified separately.
    with pefile.PE(str(file), fast_load=True) as image:
        image.parse_data_directories(directories=[pefile.DIRECTORY_ENTRY['IMAGE_DIRECTORY_ENTRY_RESOURCE']])
        versions = {t.entries.get(b'ProductVersion', b'').decode().strip()
                    for group in getattr(image, 'FileInfo', []) for section in group
                    for t in getattr(section, 'StringTable', []) if t.entries.get(b'CompanyName') == company
                    and (product is None or t.entries.get(b'ProductName') == product)}
        if len(versions) != 1 or not re.fullmatch(r'\d+(?:\.\d+){2,3}', next(iter(versions), '')):
            return None
        return versions.pop(), f'{image.FILE_HEADER.Machine:#x}'


def compare_base(bom, setup, expected_bom_sha):
    for path, limit in ((bom, 32 << 20), (setup, 1 << 30)):
        no_links(path.absolute())
        if not path.is_file() or not 0 < path.stat().st_size <= limit:
            raise ValueError('Unexpected base comparison input')
    raw = bom.read_bytes()
    bom_sha = hashlib.sha256(raw).hexdigest()
    if bom_sha != expected_bom_sha:
        raise ValueError('Base SBOM differs from previously verified receipt')
    data = json.loads(raw, object_pairs_hook=unique_object)
    root = data['metadata']['component']
    setup_sha = file_sha(setup)
    if (data['bomFormat'] != 'CycloneDX' or data['specVersion'] != '1.6' or
            root['bom-ref'] != 'setup:' + setup_sha or root['hashes'] != hashes(setup_sha)):
        raise ValueError('Base installer and SBOM differ')
    refs = [c['bom-ref'] for c in data['components']]
    if len(refs) != len(set(refs)) or 'file:app/build-inventory.json' not in refs:
        raise ValueError('Expected the verified base installer file inventory')
    if any(ref.casefold().startswith('file:app/' + MOUNT) for ref in refs):
        raise ValueError('Comparison installer already lists Office files')
    return [prop('compared-base-installer-sha256', setup_sha),
            prop('compared-base-sbom-sha256', bom_sha),
            prop('office-mount-in-compared-base-inventory', 'absent')]


def native_edges(graph, files):
    deps = defaultdict(set)
    unproven = {row['path'] for row in graph['unproven_runtime_candidates']}
    if not unproven.issubset(files):
        raise ValueError('Unknown native candidate outside component')
    for domain in graph['domains'].values():
        for edge in domain['edges']:
            if edge['resolution'] in ('package', 'private-crt'):
                source, target = edge['source'], edge['target']
                if source not in files or target not in files:
                    raise ValueError('Native dependency outside component')
                deps['file:app/' + source].add('file:app/' + target)
    return unproven, [{'ref': source, 'dependsOn': sorted(targets)} for source, targets in sorted(deps.items())]


def assemble(files, manifest, original, java, graph, cabinet_entries, base_properties):
    fp = manifest.fingerprint
    payload = {MOUNT + name: path for name, path in files.items()}
    unknown, dependencies = native_edges(graph, payload)
    def layer(name, version, digest, url, publisher):
        return {'type': 'application', 'bom-ref': 'archive:' + digest, 'name': name, 'version': version,
                'publisher': publisher,
                'externalReferences': [{'type': 'distribution', 'url': url, 'hashes': hashes(digest)}], 'components': []}
    office = layer('LibreOffice', VERSION, PACKAGE_SHA256, OFFICE_URL, 'The Document Foundation')
    jre = layer('Eclipse Temurin JRE', JAVA['version'], JAVA['package_sha256'], SOURCE_URL, 'Eclipse Adoptium')
    components = [office, jre]
    copies = {'program/' + name: 'System64/' + name for name in APP_LOCAL_CRT}
    if manifest.python_launchers:
        copies.update({PYTHON_CORE + 'bin/' + name: src for name, src in APP_LOCAL_PYTHON.items()})
    management = {'runtime-lock.json', 'office-runtime-lock.json', 'java/' + LOCK_NAME}
    identified = defaultdict(list)
    for name in sorted(files):
        location = 'app/' + MOUNT + name
        digest = fp if name == 'runtime-lock.json' else manifest.files[name]
        file = {'type': 'file', 'bom-ref': 'file:' + location, 'name': location, 'hashes': hashes(digest)}
        attributes = []
        if name in original:
            if digest != original[name]:
                raise ValueError('Office origin differs')
            office['components'].append(file)
        elif name.startswith('java/') and name[5:] in java:
            if digest != java[name[5:]]:
                raise ValueError('Java origin differs')
            jre['components'].append(file)
        elif name in copies:
            src = copies[name]
            if digest != original[src]:
                raise ValueError('Application-local copy differs from its source')
            attributes.append(prop('copied-from', 'app/' + MOUNT + src))
            components.append(file)
        elif name in management:
            attributes.append(prop('role', 'component inventory'))
            components.append(file)
        else:
            raise ValueError('Unaccounted component file')
        if MOUNT + name in unknown:
            attributes.append(prop('native-loading-domain', 'unproven'))
        if attributes:
            file['properties'] = attributes
        basename = name.rsplit('/', 1)[-1].lower()
        if CRT.fullmatch(basename):
            version = pe_version(files[name], b'Microsoft Corporation')
            if version:
                identified[(basename, *version, 'Microsoft Corporation')].append({'location': location})
        elif basename in ('python313.dll', 'python3.dll'):
            version = pe_version(files[name], b'Python Software Foundation', b'Python')
            if version:
                identified[('CPython', *version, 'Python Software Foundation')].append({'location': location})
    for (name, version, machine, publisher), places in sorted(identified.items()):
        components.append({'type': 'library', 'bom-ref': f'pe-library:{name}@{version}:{machine}', 'name': name,
                           'version': version, 'publisher': publisher, 'evidence': {'occurrences': places},
                           'properties': [prop('identity-source', 'PE product version and company'), prop('pe-machine', machine)]})
    root = {'type': 'application', 'name': 'StudyWorkbench prepared optional Office component', 'bom-ref': 'prepared:' + fp}
    props = [prop('role', 'prepared component, final installer membership unverified'), prop('runtime-lock-sha256', fp),
             prop('msi-cabinet-members-compared', cabinet_entries), prop('office-msi-output-paths', len(original)),
             prop('java-zip-files-compared', len(java)), prop('native-pe-files', graph['pe_images']),
             prop('unproven-native-load-candidates', len(unknown)), *base_properties]
    return {'bomFormat': 'CycloneDX', 'specVersion': '1.6', 'version': 1, 'metadata': {'component': root, 'properties': props},
            'components': components, 'dependencies': [{'ref': root['bom-ref'], 'dependsOn': [office['bom-ref'], jre['bom-ref']]},
                                                        *dependencies],
            'compositions': [{'aggregate': 'incomplete', 'assemblies': [root['bom-ref']]}]}


def generate(directory, msi, zip_path, output, base_bom=None, base_setup=None, base_bom_sha=None):
    for path in (directory, output.parent):
        no_links(path.absolute())
    if output.exists() or output.resolve().is_relative_to(directory.resolve()):
        raise ValueError('Use a new external output')
    if any((base_bom, base_setup, base_bom_sha)) and not all((base_bom, base_setup, base_bom_sha)):
        raise ValueError('Base comparison requires the installer, its verified SBOM and its expected digest')
    base_properties = compare_base(base_bom, base_setup, base_bom_sha) if base_bom else []
    directory = directory.resolve()
    manifest = OfficeRuntime(directory)
    if manifest.java_home is None:
        raise ValueError('Expected a composed Office/JRE component')
    files, fp = component_payload(directory)
    if fp != manifest.fingerprint:
        raise ValueError('Component inventory changed')
    original = json.loads(files['office-runtime-lock.json'].read_bytes(), object_pairs_hook=unique_object)['files']
    java = json.loads(files['java/' + LOCK_NAME].read_bytes(), object_pairs_hook=unique_object)['files']
    entries = verify_msi(msi, PACKAGE_SHA256, original, output.parent)
    verify_java(zip_path, java)
    graph = inspect_dependencies({MOUNT + name: path for name, path in files.items()}, Path(os.environ['SystemRoot']) / 'System32')
    bom = assemble(files, manifest, original, java, graph, entries, base_properties)
    if (component_payload(directory) != (files, fp) or file_sha(msi) != PACKAGE_SHA256 or
            file_sha(zip_path) != JAVA['package_sha256'] or
            (base_bom and compare_base(base_bom, base_setup, base_bom_sha) != base_properties)):
        raise ValueError('Input changed during inventory')
    with output.open('x', encoding='utf-8') as dest:
        json.dump(bom, dest, ensure_ascii=False, separators=(',', ':'))
        dest.write('\n')
    return len(files), len(graph['unproven_runtime_candidates'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for flag in ('directory', 'msi', 'jre-zip', 'output', 'base-bom', 'base-setup'):
        parser.add_argument('--' + flag, type=Path, required=not flag.startswith('base-'))
    parser.add_argument('--base-bom-sha256', help='Previously verified base installer SBOM digest')
    args = parser.parse_args()
    count, unresolved = generate(args.directory, args.msi, args.jre_zip, args.output, args.base_bom, args.base_setup, args.base_bom_sha256)
    print(f'Inventoried {count} prepared files; {unresolved} native loading candidates remain unproven.')
