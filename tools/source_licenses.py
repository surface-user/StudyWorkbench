"""Collect local license evidence for exact source locks, without approving distribution."""

import argparse
import base64
import csv
import hashlib
import importlib.metadata
import io
import json
from pathlib import Path, PurePosixPath
from urllib.parse import urljoin, urlsplit
from urllib.request import url2pathname

import yaml
from packaging.utils import canonicalize_name
from source_sbom import LOCKS, UniqueLoader, lock_inventory, no_links, read_lock, sha256

PREFIXES = ('license', 'licence', 'copying', 'notice', 'copyright', 'authors')
LIMITATIONS = [
    'Local installed/cache evidence plus pinned supplements; this command does not authenticate archives or Git.',
    'Declared licenses and source URLs are not reviewed distribution obligations or legal conclusions.',
    'Named-file discovery and pinned embedded scopes can still omit other source notices or headers.',
    'SDK, frozen/native/Office/Java/installer payload and runtime membership are not covered.',
]


def read_file(path):
    no_links(path)
    if not path.is_file() or path.stat().st_size > 4 * 1024 * 1024:
        raise ValueError('Evidence must be a regular file of at most 4 MiB')
    data = path.read_bytes()
    if not data or len(data) > 4 * 1024 * 1024:
        raise ValueError('Empty or oversized evidence')
    return data


def relative_file(root, name):
    relative = PurePosixPath(str(name).replace('\\', '/'))
    if relative.is_absolute() or '..' in relative.parts or ':' in str(relative):
        raise ValueError('Unsafe evidence path')
    path = root.joinpath(*relative.parts)
    if not path.resolve().is_relative_to(root.resolve()):
        raise ValueError('Evidence escapes package')
    return path


def is_license(name):
    path = PurePosixPath(str(name).replace('\\', '/'))
    return path.suffix.lower() not in {'.py', '.pyc'} and (
        path.name.lower().startswith(PREFIXES)
        or any(part.upper() in {'LICENSES', 'BUILD_LICENSES'} for part in path.parts))


def keep_text(output, name, data):
    digest = sha256(data)
    path = output / 'texts' / digest
    if not path.exists():
        with path.open('xb') as stream:
            stream.write(data)
    elif path.read_bytes() != data:
        raise ValueError('Conflicting evidence digest')
    return {'source_path': str(name).replace('\\', '/'), 'sha256': digest,
            'bytes': len(data), 'text_path': 'texts/' + digest}


def latex2mathml_supplement(source, package_root, output):
    folder = source / 'packaging/licenses/latex2mathml-3.81.1'
    raw = read_file(folder / 'provenance.json')
    profile = json.loads(raw)
    if profile['purl'] != 'pkg:pypi/latex2mathml@3.81.1' or len(profile['package_files']) != 9:
        raise ValueError('Unexpected supplemental package identity')
    for name, expected in profile['package_files'].items():
        if not name.startswith('latex2mathml/'):
            raise ValueError('Supplement references another package')
        if sha256(read_file(relative_file(package_root, name))) != expected:
            raise ValueError('Installed package differs from pinned supplemental source')
    texts = []
    for item in profile['license_texts']:
        data = read_file(relative_file(folder, item['path']))
        if sha256(data) != item['sha256'] or len(data) != item['bytes']:
            raise ValueError('Supplemental license text changed')
        texts.append({**keep_text(output, item['path'], data),
                      'evidence_kind': 'repository_supplement',
                      'license': item['license'], 'applies_to': item['applies_to'],
                      'source_url': item['source_url']})
    if raw != read_file(folder / 'provenance.json') or any(
            sha256(read_file(relative_file(package_root, name))) != expected
            for name, expected in profile['package_files'].items()):
        raise ValueError('Supplemental inputs changed during collection')
    return {'profile_sha256': sha256(raw), 'upstream_commit': profile['upstream_commit'],
            'upstream_tag': profile['upstream_tag'], 'upstream_tag_object': profile['upstream_tag_object'],
            'upstream_license_blob': profile['upstream_license_blob'],
            'archive_sha256': profile['archive_sha256'], 'package_files': profile['package_files'],
            'embedded_notices': profile['embedded_notices'],
            'pinned_package_files_matched': 9, 'files': texts, 'issues': profile['issues'],
            'distribution_obligations_reviewed': False, 'notes': profile['notes']}


def python_evidence(identity, output, source=None):
    matches = [d for d in importlib.metadata.distributions()
               if canonicalize_name(d.metadata.get('Name', '')) == identity['name']
               and d.version == identity['version']]
    if len(matches) != 1:
        return {'files': [], 'issues': ['missing_or_ambiguous_exact_installed_version']}
    dist = matches[0]
    root = Path(dist.locate_file('')).absolute()
    metadata = [f for f in dist.files or [] if len(f.parts) == 2 and str(f).endswith('.dist-info/METADATA')]
    if len(metadata) != 1:
        raise ValueError('Missing or ambiguous distribution metadata: ' + identity['name'])
    meta_data = read_file(relative_file(root, metadata[0]))
    found, issues = [], []
    declared = dist.metadata.get_all('License-File', [])
    metadata_dir = PurePosixPath(str(metadata[0])).parent
    record = read_file(relative_file(root, metadata_dir / 'RECORD'))
    # importlib.files() hides absent entries, which would hide missing or unsafe license paths.
    files = list(csv.reader(io.StringIO(record.decode('utf-8'))))
    if any(len(row) != 3 for row in files) or len({row[0].casefold() for row in files}) != len(files):
        raise ValueError('Malformed or duplicate installed RECORD entry')
    named = set()
    for name in declared:
        relative_file(root, name)
        candidates = {str(metadata_dir / 'licenses' / name), str(metadata_dir / name)}
        matching = candidates & {file for file, _, _ in files}
        if not matching:
            issues.append('declared_license_text_missing:' + name)
        named.update(matching)
    for file, file_hash, size in files:
        if not is_license(file) and file not in named:
            continue
        data = read_file(relative_file(root, file))
        digest = base64.urlsafe_b64encode(hashlib.sha256(data).digest()).decode().rstrip('=')
        verified = file_hash == 'sha256=' + digest
        if file_hash.startswith('sha256=') and not verified:
            raise ValueError('License bytes differ from installed RECORD')
        if size and (not size.isdecimal() or int(size) != len(data)):
            raise ValueError('License length differs from installed RECORD')
        if not verified:
            issues.append('license_record_hash_unverified:' + str(file))
        found.append({**keep_text(output, file, data), 'installed_record_sha256_matches': verified})
    result = {'metadata_sha256': sha256(meta_data), 'record_sha256': sha256(record),
            'declared_license': dist.metadata.get('License-Expression') or dist.metadata.get('License'),
            'declared_license_files': declared,
            'package_source': f"https://pypi.org/project/{identity['name']}/{identity['version']}/",
            'files': found, 'issues': issues or ([] if found else ['license_text_missing'])}
    if source is not None and (identity['name'], identity['version']) == ('latex2mathml', '3.81.1'):
        supplement = latex2mathml_supplement(source, root, output)
        result['files'].extend(supplement.pop('files'))
        result['issues'] = [x for x in result['issues'] if x != 'license_text_missing'] + supplement['issues']
        result['supplement'] = supplement
    return result


def dart_evidence(identity, entry, package, config, output):
    if package is None:
        return {'files': [], 'issues': ['package_config_entry_missing']}
    uri = urlsplit(urljoin(config.as_uri(), package['rootUri']))
    if uri.scheme != 'file' or uri.netloc or uri.query or uri.fragment:
        raise ValueError('Package root must be a local file URI')
    root = Path(url2pathname(uri.path)).absolute()
    raw = read_lock(root / 'pubspec.yaml')
    meta = yaml.load(raw.decode('utf-8'), Loader=UniqueLoader)
    if not isinstance(meta, dict):
        raise ValueError('Missing cached pubspec identity')
    if meta.get('name') != identity['name'] or str(meta.get('version')) != identity['version']:
        return {'files': [], 'issues': ['cached_pubspec_identity_mismatch']}
    found = []
    # Nested named license directories may contain third-party notices as well as the main license.
    pending = [root]
    visited = 0
    while pending:
        parent = pending.pop()
        for path in sorted(parent.iterdir()):
            visited += 1
            if visited > 10000:
                raise ValueError('Package license discovery exceeds entry budget')
            if parent == root and not is_license(path.relative_to(root)):
                continue
            no_links(path)
            if path.is_dir():
                pending.append(path)
            elif path.is_file():
                found.append(keep_text(output, path.relative_to(root), read_file(path)))
            else:
                raise ValueError('License is not a regular file or directory')
    return {'pubspec_sha256': sha256(raw), 'declared_source': entry['description'],
            'source_kind': entry['source'], 'files': found,
            'issues': [] if found else ['license_text_missing']}


def collect(source, config, output):
    source, config, output = source.absolute(), config.absolute(), output.absolute()
    raw = {name: read_lock(source / name) for name in LOCKS}
    expected, excluded, _ = lock_inventory(raw)
    config_raw = read_file(config)
    packages = json.loads(config_raw)['packages']
    by_name = {p['name']: p for p in packages}
    if len(by_name) != len(packages):
        raise ValueError('Duplicate package config identity')
    pub = yaml.load(raw[LOCKS[1]].decode('utf-8'), Loader=UniqueLoader)['packages']
    no_links(output.parent)
    output.mkdir(exist_ok=False)
    (output / 'texts').mkdir()
    result = {}
    for purl, identity in expected.items():
        evidence = (python_evidence(identity, output, source) if purl.startswith('pkg:pypi/') else
                    dart_evidence(identity, pub[identity['name']], by_name.get(identity['name']), config, output))
        result[purl] = {**identity, **evidence}
    if raw != {name: read_lock(source / name) for name in LOCKS} or read_file(config) != config_raw:
        raise ValueError('Inputs changed during collection')
    report = {'schema_version': 1, 'scope': 'source-lock-local-license-evidence',
              'collector_sha256': sha256(read_file(Path(__file__).absolute())),
              'distribution_obligations_reviewed': False,
              'product_licenses_complete': False, 'archive_provenance_verified': False,
              'source_lock_sha256': {name: sha256(data) for name, data in raw.items()},
              'package_config_sha256': sha256(config_raw), 'components': result,
              'excluded_sdk_components': excluded, 'limitations': LIMITATIONS,
              'packages_with_issues': sum(bool(x['issues']) for x in result.values())}
    (output / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--package-config', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True, help='New directory; parent must exist')
    args = parser.parse_args()
    try:
        report = collect(args.source, args.package_config, args.output)
    except (OSError, ValueError, TypeError, KeyError, yaml.YAMLError) as exc:
        parser.exit(1, f'License evidence failed: {exc}\n')
    print(f"Collected {len(report['components'])} locked packages; {report['packages_with_issues']} with missing evidence.")
    print('Archive provenance, full payload and distribution obligations remain unverified.')
    return 2 if report['packages_with_issues'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
