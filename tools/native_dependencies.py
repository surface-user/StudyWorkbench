"""Bounded static PE closures for the application's documented Windows loading domains."""
import hashlib
import json
import re
import xml.etree.ElementTree as ET
from pathlib import PurePosixPath

import pefile
from check_frozen_sources import code_fingerprint

PE_SUFFIXES = {'.exe', '.dll', '.pyd', '.com', '.bin'}
PRIVATE_CRT = re.compile(r'^(?:msvcp|msvcr|vcruntime|concrt|vccorlib|mfc|mfcm|atl)\d', re.I)
API_SET = re.compile(r'^(?:api|ext)-[a-z0-9-]+-l\d+-\d+-\d+\.dll$')
# Full frozen initializer fingerprints: an upgrade must re-establish its directory registration.
DLL_REGISTRATIONS = {
    'numpy': dict(version='2.5.4', code_sha256='e4f5a942c031e942cb3d44e0f38adedba8c24dd51ae9cbc0c5788c998647e31a'),
    'pandas': dict(version='3.1.0', code_sha256='0786ce19ddf69547b54b04728688dad0c8d36b2d54c275ed9bedc608a4d14572'),
}
# Fixed Office startup/registration bytes, not a general UNO bootstrap interpreter.
OFFICE_UNO_FILES = {
    'program/uno.ini': 'e4b23a72009455cef8b105312e6893a1523f1a00005de502f821317708f2b6d6',
    'program/fundamental.ini': 'b4d54f865c2ae335dad400114f4638051360e04491fae41359f62511eb8160c2',
    'program/services.rdb': 'ea90dacd3cae92582dd02c03b93f73e3307d8017fa3403e38c6a07f6cc1522cb',
    'program/services/postgresql-sdbc.rdb': '5e2fdbdfd2f01f37e23df3ddbfe8a082da75fb7b3579a5009d6d0d12a5813362',
    'program/services/pyuno.rdb': 'b4495431256f030c6e2da038d64f6ccaa09e60709ba7206ced73ebe17c869ff6',
    'program/services/scriptproviderforbeanshell.rdb': '4b290aaf66192075ab16404ceadd28b3e38c1890fe53e17572da400af5dac3be',
    'program/services/scriptproviderforjavascript.rdb': 'fe5092c30ac96be4e45ca5df7b60ad0118273f26c07e9d7c1a78d177dc046e83',
    'program/services/scriptproviderforpython.rdb': 'ed096e982ec7996361fcd1159b270f8169aa9547a09463a6a006bff5057a3c2d',
    'program/services/services.rdb': 'bc996be9362ebf3a9c6be11d4c3c9fef26941182743c70d1649a6e5fe317f094',
}
OFFICE_JAVA_LOCK_SHA256 = '159433e3a2fc9f2a9c4f633a613d3db5aaca29d1b52caa64e3a63755ac8e1907'
OFFICE_PYTHON_LOCK_SHA256 = '156b4421aeb8eaadb565d6d33234bf69c58d22b5e46b78c9de81548dfe7b9bc9'
OFFICE_PYTHON_PYDS = ('_asyncio _bz2 _ctypes _decimal _elementtree _hashlib _lzma _multiprocessing '
                      '_overlapped _queue _socket _sqlite3 _ssl _uuid _zoneinfo pyexpat select unicodedata winsound').split()
OFFICE_PYTHON_DLLS = ['libcrypto-3.dll', 'libssl-3.dll', 'libffi-8.dll', 'sqlite3.dll']


def office_python_libraries(payload, nodes, office):
    """Fixed potential extension roots, not evidence that pyuno initialized or imported them."""
    lock = payload.get(office + 'runtime-lock.json')
    if lock is None:
        raise ValueError('Missing fixed Office Python component inventory')
    with lock.open('rb') as stream:
        raw = stream.read(4 * 1024 * 1024 + 1)
    if len(raw) > 4 * 1024 * 1024 or hashlib.sha256(raw).hexdigest() != OFFICE_PYTHON_LOCK_SHA256:
        raise ValueError('Office Python component inventory changed; renew loading evidence')
    files = json.loads(raw)['files']
    directory = 'program/python-core-3.13.15/lib/'
    extensions = {directory + name + '.pyd' for name in OFFICE_PYTHON_PYDS}
    libraries = {directory + name for name in OFFICE_PYTHON_DLLS}
    expected = extensions | libraries
    inventory_images = {name for name in files if name.startswith(directory)
                        and PurePosixPath(name).suffix in PE_SUFFIXES}
    actual = {name for name in nodes if name.startswith(office + directory)}
    immediate = {name for name in inventory_images if str(PurePosixPath(name).parent) == directory.rstrip('/')}
    if actual != {office + name for name in inventory_images} or immediate != expected:
        raise ValueError('Office Python extension/library PE set changed; renew loading evidence')
    # Nested pip/setuptools templates retain their authenticated identity and unclassified role.
    for name in inventory_images - expected:
        if nodes[office + name]['sha256'] != files[name]:
            raise ValueError('Office Python nested PE bytes changed: ' + name)
    required = expected | {'program/python313.dll', 'program/vcruntime140.dll'}
    for name in sorted(required):
        image = nodes.get(office + name)
        if image is None or image['sha256'] != files.get(name):
            raise ValueError('Office Python PE path or bytes changed: ' + name)
        if image['machine'] != 0x8664 or image['magic'] != 0x20B:
            raise ValueError('Expected x64 PE32+ Office Python image: ' + name)
    configuration = 'program/pythonloader.uno.ini'
    path = payload.get(office + configuration)
    if path is None:
        raise ValueError('Missing fixed Office Python loader configuration')
    with path.open('rb') as stream:
        data = stream.read(65536 + 1)
    if len(data) > 65536 or hashlib.sha256(data).hexdigest() != files.get(configuration):
        raise ValueError('Office Python loader configuration changed')
    return dict(component_inventory_sha256=OFFICE_PYTHON_LOCK_SHA256,
                extensions={office + name: files[name] for name in sorted(extensions)},
                libraries={office + name: files[name] for name in sorted(libraries)},
                unclassified_images={office + name: files[name] for name in sorted(inventory_images - expected)},
                program_libraries={office + name: files[name] for name in sorted(required - expected)},
                configuration_sha256={office + configuration: files[configuration]})


def office_java_libraries(payload, nodes, office):
    path = payload.get(office + 'java/java-runtime-lock.json')
    if path is None:
        raise ValueError('Missing fixed Java component inventory')
    with path.open('rb') as stream:
        raw = stream.read(1024 * 1024 + 1)
    if len(raw) > 1024 * 1024 or hashlib.sha256(raw).hexdigest() != OFFICE_JAVA_LOCK_SHA256:
        raise ValueError('Java component inventory changed; renew loading evidence')
    manifest = json.loads(raw)
    directories = {office + 'java/bin', office + 'java/bin/server'}
    images = {}
    for suffix in ('.dll', '.exe'):
        expected = {office + 'java/' + name.casefold(): digest for name, digest in manifest['files'].items()
                    if name.casefold().endswith(suffix)}
        actual = {name for name in nodes if name.startswith(office + 'java/') and name.endswith(suffix)}
        label = suffix[1:].upper()
        if actual != expected.keys():
            raise ValueError(f'Java {label} set changed; renew loading evidence')
        allowed = directories if suffix == '.dll' else {office + 'java/bin'}
        for name, digest in expected.items():
            node = nodes[name]
            if str(PurePosixPath(name).parent) not in allowed or node['sha256'] != digest:
                raise ValueError(f'Java {label} path or bytes changed: ' + node['path'])
            if node['machine'] != 0x8664 or node['magic'] != 0x20B:
                raise ValueError(f'Expected x64 PE32+ Java {label}: ' + node['path'])
        images[suffix] = dict(sorted(expected.items()))
    if office + 'java/bin/java.exe' not in images['.exe']:
        raise ValueError('Missing fixed primary Java launcher')
    release = payload.get(office + 'java/release')
    if release is None:
        raise ValueError('Missing fixed Java release identity')
    with release.open('rb') as stream:
        data = stream.read(65536 + 1)
    if len(data) > 65536 or hashlib.sha256(data).hexdigest() != manifest['files']['release']:
        raise ValueError('Java release identity changed')
    return dict(component_inventory_sha256=OFFICE_JAVA_LOCK_SHA256,
                release_sha256=manifest['files']['release'], dlls=images['.dll'], executables=images['.exe'])


def office_uno_entries(payload, office):
    expected = {office + name: digest for name, digest in OFFICE_UNO_FILES.items()}
    actual = {name for name in payload if name.startswith(office + 'program/services/')}
    if actual != {name for name in expected if name.startswith(office + 'program/services/')}:
        raise ValueError('Office UNO registration file set changed; renew loading evidence')
    entries = {}
    for name, digest in expected.items():
        path = payload.get(name)
        if path is None:
            raise ValueError('Missing Office UNO configuration: ' + name)
        with path.open('rb') as stream:
            raw = stream.read(1024 * 1024 + 1)
        if len(raw) > 1024 * 1024 or hashlib.sha256(raw).hexdigest() != digest:
            raise ValueError('Office UNO configuration changed or exceeds budget: ' + name)
        if not name.endswith('.rdb'):
            continue
        # Parse only the exact, bounded bytes above; untrusted XML never reaches this parser.
        document = ET.fromstring(raw)
        if document.tag != '{http://openoffice.org/2010/uno-components}components':
            raise ValueError('Unknown Office UNO registry format: ' + name)
        for component in document:
            if component.get('loader') != 'com.sun.star.loader.SharedLibrary':
                continue
            match = re.fullmatch(r'vnd\.sun\.star\.expand:\$(?:URE_INTERNAL_LIB_DIR|LO_LIB_DIR)/'
                                 r'([a-zA-Z0-9_+-]+\.(?:dll|pyd))', component.get('uri', ''))
            if match is None:
                raise ValueError('Unsupported Office UNO library URI in ' + name)
            target = office + 'program/' + match[1].casefold()
            entries.setdefault(target, []).append(name)
    return {name: sorted(set(sources)) for name, sources in sorted(entries.items())}


def registered_directories(payload):
    prefixes = sorted({name.split('/')[2][:-5] for name in payload
                       if name.startswith('backend/_internal/') and len(name.split('/')) > 3
                       and name.split('/')[2].endswith('.libs')})
    if not prefixes:
        return []
    executable = payload.get('backend/study_backend.exe')
    if executable is None:
        raise ValueError('Frozen DLL registration evidence requires backend/study_backend.exe')
    from PyInstaller.archive.readers import CArchiveReader
    archive = CArchiveReader(str(executable))
    pyz = archive.open_embedded_archive(next(name for name, entry in archive.toc.items() if entry[-1] == 'z'))
    directories = []
    for package in prefixes:
        expected = DLL_REGISTRATIONS.get(package)
        if expected is None:
            raise ValueError(f'Unknown frozen DLL registration: {package}.libs')
        if code_fingerprint(pyz.extract(package)) != expected['code_sha256']:
            raise ValueError(f'Frozen DLL registration changed: {package}; renew loading evidence')
        directories.append(f'backend/_internal/{package}.libs')
    return directories


def pe_nodes(payload):
    nodes = {}
    for relative, path in payload.items():
        suffix = path.suffix.lower()
        if suffix not in PE_SUFFIXES:
            continue
        if suffix in {'.com', '.bin'}:
            with path.open('rb') as stream:
                if stream.read(2) != b'MZ':
                    continue
        key = relative.casefold()
        if key in nodes:
            raise ValueError('Case-ambiguous PE path: ' + relative)
        pe = pefile.PE(str(path), fast_load=True)
        try:
            parts = PurePosixPath(key).parts
            main_image = (len(parts) == 1 or key == 'backend/study_backend.exe'
                          or parts[0] == 'backend' and suffix in {'.dll', '.pyd'})
            if main_image and (pe.FILE_HEADER.Machine != 0x8664 or pe.OPTIONAL_HEADER.Magic != 0x20B):
                raise ValueError('Expected x64 PE32+ image: ' + relative)
            pe.parse_data_directories(directories=[pefile.DIRECTORY_ENTRY['IMAGE_DIRECTORY_ENTRY_IMPORT'],
                                                  pefile.DIRECTORY_ENTRY['IMAGE_DIRECTORY_ENTRY_DELAY_IMPORT']])
            edges = []
            for attribute, kind in [('DIRECTORY_ENTRY_IMPORT', 'import'), ('DIRECTORY_ENTRY_DELAY_IMPORT', 'delay')]:
                for entry in getattr(pe, attribute, []):
                    name = entry.dll.decode('ascii').casefold()
                    if not re.fullmatch(r'[a-z0-9_.+-]+\.(?:dll|drv|ocx|pyd|exe|com|bin)', name):
                        raise ValueError('Invalid PE import name: ' + relative)
                    edges.append((name, kind))
            with path.open('rb') as stream:
                checksum = hashlib.file_digest(stream, 'sha256').hexdigest()
            nodes[key] = dict(path=relative, machine=pe.FILE_HEADER.Machine, magic=pe.OPTIONAL_HEADER.Magic,
                              edges=edges, sha256=checksum)
        finally:
            pe.close()
    return nodes


def closure(nodes, roots, directories, crt_directories, system, *, registrations=()):
    """Resolve one process domain; no ambient PATH or package-wide basename fallback."""
    pending, visited, edges = list(roots), set(), []
    while pending:
        source = pending.pop().casefold()
        if source in visited:
            continue
        node = nodes.get(source)
        if node is None:
            raise ValueError('Missing declared PE entry: ' + source)
        if node['machine'] != 0x8664 or node['magic'] != 0x20B:
            raise ValueError('Expected x64 PE32+ image in loading domain: ' + node['path'])
        visited.add(source)
        for name, kind in node['edges']:
            record = dict(source=node['path'], name=name, kind=kind)
            if API_SET.fullmatch(name):
                edges.append(dict(record, resolution='api-set-contract', target=None))
                continue
            private = PRIVATE_CRT.match(name) is not None
            ordered = crt_directories if private else directories
            targets = [str(PurePosixPath(directory) / name).casefold() for directory in ordered]
            target = next((candidate for candidate in targets if candidate in nodes), None)
            registered = [str(PurePosixPath(directory) / name).casefold() for directory in registrations]
            registered = [candidate for candidate in registered if candidate in nodes]
            if private and not re.search(r'-[0-9a-f]{32}\.dll$', name):
                registered = []  # Bootstrap CRT cannot depend on later Python package initialization.
            if len({nodes[candidate]['sha256'] for candidate in registered}) > 1:
                raise ValueError(f'Ambiguous registered DLL search order: {node["path"]} -> {name}')
            if target is None and registered:
                target = registered[0]
            if target is not None:
                edges.append(dict(record, resolution='private-crt' if private else 'package', target=nodes[target]['path']))
                pending.append(target)
            elif not private and (system / name).is_file():
                edges.append(dict(record, resolution='host-system-file', target=name))
            else:
                elsewhere = [entry['path'] for candidate, entry in nodes.items() if PurePosixPath(candidate).name == name]
                raise ValueError(f'Unresolved {kind}: {node["path"]} -> {name}; '
                                 f'loading directories={list(ordered) + list(registrations)}; '
                                 f'elsewhere={elsewhere}; system CRT cannot satisfy private dependencies')
    return dict(roots=list(roots), directories=list(directories), crt_directories=list(crt_directories),
                registered_directories=list(registrations), nodes=sorted(visited), edges=edges)


def inspect_dependencies(payload, system):
    nodes = pe_nodes(payload)
    registrations = registered_directories(payload)
    domains = {}
    java_libraries = None
    main = [name for name in nodes if '/' not in name]
    if main:
        domains['main'] = closure(nodes, main, ['.'], ['.'], system)
    backend = [name for name in nodes if name.startswith('backend/') and (
        str(PurePosixPath(name).parent) == 'backend'
        or PurePosixPath(name).suffix in {'.dll', '.pyd'})]
    backend_parts = []
    for name in backend:
        # CPython extension loading supplies the extension directory; PyInstaller supplies _internal.
        directories = list(dict.fromkeys([str(PurePosixPath(name).parent), 'backend/_internal', 'backend']))
        backend_parts.append(closure(nodes, [name], directories, ['backend/_internal', 'backend'], system,
                                     registrations=registrations))
    if backend_parts:
        identities = {}
        for part in backend_parts:
            for edge in part['edges']:
                if edge['resolution'] in {'package', 'private-crt'}:
                    identities.setdefault(edge['name'], set()).add(nodes[edge['target'].casefold()]['sha256'])
        if any(len(values) > 1 for values in identities.values()):
            raise ValueError('Ambiguous process-local backend DLL identity across plugin loading domains')
        unique_edges = {json.dumps(edge, sort_keys=True): edge for part in backend_parts for edge in part['edges']}
        domains['backend'] = dict(roots=backend, directories=['backend/_internal', 'backend'],
                                  plugin_directories={part['roots'][0]: part['directories'] for part in backend_parts},
                                  crt_directories=['backend/_internal', 'backend'], registered_directories=registrations,
                                  nodes=sorted({name for part in backend_parts for name in part['nodes']}),
                                  edges=[unique_edges[key] for key in sorted(unique_edges)])
    office = 'converters/libreoffice/'
    program, java, server = (office + suffix for suffix in ('program', 'java/bin', 'java/bin/server'))
    has_office = office + 'runtime-lock.json' in payload or any(
        program + '/' + entry in nodes for entry in ('soffice.com', 'soffice.bin', 'officebean.dll'))
    if has_office:
        lock = payload.get(office + 'runtime-lock.json')
        if lock is None:
            raise ValueError('Office loading domain requires its component inventory')
        with lock.open('rb') as stream:
            raw = stream.read(4 * 1024 * 1024 + 1)
        if len(raw) > 4 * 1024 * 1024:
            raise ValueError('Office inventory exceeds budget')
        manifest = json.loads(raw)
        if (manifest.get('version') != '26.8.1'
                or manifest.get('package_sha256') != 'c6298b10cfa1748bcbedad94c62ce771e240e5021bfd6d7a967cd571b04b5312'
                or manifest.get('java') != dict(version='21.0.13+9', directory='java',
                                               package_sha256='2332c0b4cff6bed722da3567c91d5e47568bcba863fa4945d0a8d6fc76158628')):
            raise ValueError('Office/Java loading policy version changed; renew loading evidence')
        entry_names = ['soffice.com', 'soffice.bin', 'officebean.dll', 'javavmlo.dll', 'jvmfwklo.dll',
                       'jvmaccesslo.dll', 'javaloaderlo.dll', 'juh.dll', 'juhx.dll', 'java_uno.dll']
        roots = [program + '/' + name for name in entry_names]
        if any(name.startswith(java + '/') for name in nodes):
            java_libraries = office_java_libraries(payload, nodes, office)
            roots.extend(java_libraries['dlls'])
            # Conservatively include every fixed launcher; this does not assert the product executes it.
            domains['java'] = closure(nodes, sorted(java_libraries['executables']) + list(java_libraries['dlls']),
                                      [java, server], [java], system)
        uno_entries = office_uno_entries(payload, office)
        domains['office'] = closure(nodes, sorted(set(roots) | uno_entries.keys()),
                                    [program, java, server], [program], system)
        domains['office']['uno_entries'] = uno_entries
        domains['office']['uno_configuration_sha256'] = {
            office + name: digest for name, digest in OFFICE_UNO_FILES.items()}
        python_libraries = office_python_libraries(payload, nodes, office)
        # CPython's DEFAULT_DIRS | DLL_LOAD_DIR: fixed extension parent plus application directory.
        # USER_DIRS/loaded-module/SxS and export forwarding are not certified by this static graph.
        domains['office_python'] = closure(nodes, list(python_libraries['extensions']),
                                           [program + '/python-core-3.13.15/lib', program], [program], system)
        domains['office_python']['pinned_inputs'] = python_libraries
    covered = {name for domain in domains.values() for name in domain['nodes']}
    return dict(scope='documented-entry-and-plugin-domains-v1', pe_images=len(nodes),
                pe_coverage='partial' if len(covered) < len(nodes) else 'all-images-in-declared-static-domains',
                delay_edges=sum(kind == 'delay' for node in nodes.values() for _, kind in node['edges']),
                domains=domains,
                pinned_java_libraries=java_libraries,
                unproven_runtime_candidates=[dict(path=node['path'], machine=hex(node['machine']))
                                             for name, node in nodes.items() if name not in covered],
                limitations=['Images outside declared domains remain unclassified; reachability does not prove they never execute.',
                             'API-set and host system leaves do not certify minimum Windows compatibility.',
                             'Dynamic loading, loaded-module state, SxS and export forwarding require runtime evidence.'])
