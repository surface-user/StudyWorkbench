"""Generate and compare a source-lock SBOM; this is not a product payload SBOM."""

import argparse
import hashlib
import json
import os
import re
import stat
import subprocess
from pathlib import Path
from urllib.parse import quote, urlsplit

import yaml
from packaging.utils import canonicalize_name
from packaging.version import Version

SYFT_VERSION = '1.57.1'
SYFT_SHA256 = '42deb23bff7852997bf0316a540d3dcb364953273152749205e47881dd270c53'
LOCKS = ('backend/requirements.lock.txt', 'apps/desktop/pubspec.lock')
CONFIG = 'check-for-app-update: false\nenrich: []\npython:\n  search-remote-licenses: false\n'
LIMITATIONS = [
    'Source locks include build/development and non-Windows packages; runtime membership is unknown.',
    'Flutter/Dart SDK components have no exact SDK version in these locks and are excluded explicitly.',
    'No installed/frozen/native/CRT/WebView2/NuGet/Office/Java/installer payload coverage.',
    'No dependency edges, complete license texts/obligations, vulnerability or signature verification.',
    'Lock hashes identify the inputs; package archives and Git source contents are not verified.',
]


class UniqueLoader(yaml.SafeLoader):
    pass


def unique_mapping(loader, node):
    pairs = loader.construct_pairs(node)
    result = dict(pairs)
    if len(result) != len(pairs):
        raise ValueError('Duplicate lock key')
    return result


UniqueLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, unique_mapping)


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def no_links(path):
    for part in (path, *path.parents):
        info = part.lstat()
        if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT:
            raise ValueError('Links/reparse points are not supported')


def read_lock(path):
    no_links(path)
    if not path.is_file() or path.stat().st_size > 1024 * 1024:
        raise ValueError('Lock must be a regular file of at most 1 MiB')
    return path.read_bytes()


def lock_inventory(raw):
    """Return exact supported identities, an explicit SDK exclusion, and scan inputs."""
    expected = {}
    for line in raw[LOCKS[0]].decode('utf-8').splitlines():
        if not line.strip() or line.startswith('#'):
            continue
        match = re.fullmatch(r'([A-Za-z0-9][A-Za-z0-9._-]*)==([A-Za-z0-9.+!_-]+)', line)
        if not match:
            raise ValueError('Python lock requires one exact name==version per line')
        name, version = match.groups()
        Version(version)
        key = 'pkg:pypi/' + canonicalize_name(name) + '@' + quote(version, safe='')
        if key in expected or any(x['name'] == canonicalize_name(name) for x in expected.values()):
            raise ValueError('Duplicate Python package')
        expected[key] = {'name': canonicalize_name(name), 'version': version, 'lock': LOCKS[0]}
    lock = yaml.load(raw[LOCKS[1]].decode('utf-8'), Loader=UniqueLoader)
    if not isinstance(lock, dict) or not isinstance(lock.get('packages'), dict) or not expected:
        raise ValueError('Missing lock packages')
    packages, excluded = {}, []
    for name, entry in lock['packages'].items():
        if not isinstance(name, str) or not re.fullmatch(r'[a-z][a-z0-9_]*', name) or not isinstance(entry, dict):
            raise ValueError('Invalid Dart package')
        version, source = entry.get('version'), entry.get('source')
        if not isinstance(version, str) or not re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+(?:[-+][A-Za-z0-9.+-]+)?', version):
            raise ValueError('Invalid Dart locked version')
        if source == 'sdk':
            excluded.append({'name': name, 'locked_version': version, 'sdk': entry.get('description'),
                             'reason': 'SDK constraint is not an installed SDK version'})
            continue
        description = entry.get('description')
        if not isinstance(description, dict):
            raise ValueError('Missing Dart source identity')
        key = f'pkg:pub/{name}@{quote(version, safe="")}'
        if source == 'hosted':
            if (description.get('name') != name or description.get('url') != 'https://pub.dev'
                    or not re.fullmatch(r'[0-9a-f]{64}', str(description.get('sha256', '')))):
                raise ValueError('Expected a hashed pub.dev package')
            key += '?hosted_url=pub.dev'
        elif source == 'git':
            url, commit = description.get('url'), description.get('resolved-ref')
            parsed = urlsplit(url) if isinstance(url, str) else None
            if (not parsed or parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password
                    or parsed.query or parsed.fragment or description.get('path') != '.'
                    or not re.fullmatch(r'[0-9a-f]{40}', str(commit))):
                raise ValueError('Git package requires HTTPS, a root package and a full commit')
            key += '?vcs_url=' + quote(url + '@' + commit, safe='')
        else:
            raise ValueError('Unsupported Dart source')
        packages[name] = entry
        expected[key] = {'name': name, 'version': version, 'lock': LOCKS[1]}
    if not packages:
        raise ValueError('Missing supported Dart packages')
    # SDK lock placeholders must not be turned into invented SDK versions by the cataloger.
    projected = {LOCKS[0]: raw[LOCKS[0]], LOCKS[1]: yaml.safe_dump({'packages': packages}, sort_keys=True).encode()}
    return expected, excluded, projected


def compare_bom(bom, expected, projected):
    if not isinstance(bom, dict) or bom.get('bomFormat') != 'CycloneDX' or bom.get('specVersion') != '1.6':
        raise ValueError('Expected CycloneDX 1.6')
    components = bom.get('components')
    if not isinstance(components, list):
        raise ValueError('Missing SBOM components')
    found, files, refs = set(), set(), set()
    for component in components:
        if not isinstance(component, dict):
            raise ValueError('Invalid SBOM component')
        reference = component.get('bom-ref')
        if not isinstance(reference, str) or reference in refs:
            raise ValueError('Missing or duplicate SBOM reference')
        refs.add(reference)
        if component.get('type') == 'file':
            name = component.get('name', '').removeprefix('/')
            hashes = component.get('hashes', [])
            if (name not in projected or name in files
                    or {'alg': 'SHA-256', 'content': sha256(projected[name])} not in hashes):
                raise ValueError('Unexpected or changed cataloged lock file')
            files.add(name)
            continue
        purl = component.get('purl')
        if purl not in expected or purl in found or component.get('type') != 'library':
            raise ValueError('Extra or duplicate SBOM package identity')
        identity = expected[purl]
        name = component.get('name')
        if purl.startswith('pkg:pypi/') and isinstance(name, str):
            name = canonicalize_name(name)
        if name != identity['name'] or component.get('version') != identity['version']:
            raise ValueError('SBOM name/version does not match the lock')
        if {'name': 'syft:location:0:path', 'value': '/' + identity['lock']} not in component.get('properties', []):
            raise ValueError('SBOM package has no matching lock evidence')
        found.add(purl)
    if found != set(expected) or files != set(projected):
        raise ValueError('SBOM is missing locked packages or source files')
    return len(found)


def generate(source, syft, output):
    source, syft, output = source.absolute(), syft.absolute(), output.absolute()
    no_links(syft)
    with syft.open('rb') as stream:
        if hashlib.file_digest(stream, 'sha256').hexdigest() != SYFT_SHA256:
            raise ValueError('Syft executable does not match the pinned Windows x64 build')
    raw = {name: read_lock(source / name) for name in LOCKS}
    expected, excluded, projected = lock_inventory(raw)
    no_links(output.parent)
    output.mkdir(exist_ok=False)
    inputs = output / 'inputs'
    for name, data in projected.items():
        path = inputs / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    config = output / 'syft.yaml'
    config.write_text(CONFIG, encoding='utf-8')
    fingerprint = sha256(json.dumps({name: sha256(data) for name, data in raw.items()}, sort_keys=True).encode())
    bom_path = output / 'source.cdx.json'
    env = {key: value for key, value in os.environ.items() if not key.upper().startswith('SYFT_')}
    env['SYFT_CHECK_FOR_APP_UPDATE'] = 'false'
    command = [str(syft), 'scan', 'dir:inputs', '--config', 'syft.yaml',
               '--override-default-catalogers', 'python-package-cataloger,dart-pubspec-lock-cataloger',
               '--source-name', 'StudyWorkbench-source-locks', '--source-version', fingerprint,
               '-o', 'cyclonedx-json@1.6=source.cdx.json']
    with (output / 'syft.log').open('wb') as log:
        subprocess.run(command, cwd=output, env=env, stdout=log, stderr=subprocess.STDOUT, check=True, timeout=120)
    bom_bytes = bom_path.read_bytes()
    count = compare_bom(json.loads(bom_bytes), expected, projected)
    if raw != {name: read_lock(source / name) for name in LOCKS}:
        raise ValueError('Source locks changed during generation')
    result = {'scope': 'source-locks-only', 'product_sbom_complete': False,
              'syft_version': SYFT_VERSION, 'syft_executable_sha256': SYFT_SHA256,
              'source_lock_sha256': {name: sha256(data) for name, data in raw.items()},
              'scan_input_sha256': {name: sha256(data) for name, data in projected.items()},
              'bom_sha256': sha256(bom_bytes), 'matched_components': count,
              'components': expected, 'excluded_sdk_components': excluded, 'limitations': LIMITATIONS}
    (output / 'comparison.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--syft', type=Path, required=True, help='Pinned Syft 1.57.1 Windows x64 executable')
    parser.add_argument('--output', type=Path, required=True, help='New directory; parent must exist')
    args = parser.parse_args()
    try:
        result = generate(args.source, args.syft, args.output)
    except (OSError, ValueError, TypeError, yaml.YAMLError, subprocess.SubprocessError) as exc:
        parser.exit(1, f'Source SBOM failed: {exc}\n')
    print(f"Matched {result['matched_components']} source-lock packages; SDK and product payload remain incomplete.")


if __name__ == '__main__':
    main()
