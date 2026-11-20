"""Local build inventory and license texts; not a vulnerability certification."""
import argparse
import hashlib
import importlib.metadata
import json
import platform
import re
import shutil
import stat
from pathlib import Path
from urllib.parse import urljoin, urlsplit
from urllib.request import url2pathname


def stage_files(stage):
    files = {}
    pending = [stage]
    while pending:
        for path in pending.pop().iterdir():
            info = path.lstat()
            if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT:
                raise ValueError('Release staging contains a link or reparse point')
            if stat.S_ISDIR(info.st_mode):
                pending.append(path)
            elif stat.S_ISREG(info.st_mode):
                if path != stage / 'build-inventory.json':
                    files[path.relative_to(stage).as_posix()] = path
            else:
                raise ValueError('Release staging contains a non-regular payload')
    return dict(sorted(files.items()))


def check_backend_install_metadata(files, prefix):
    for relative, path in files.items():
        if (not relative.casefold().startswith(prefix) or path.name.casefold() != 'direct_url.json'
                or not path.parent.name.casefold().endswith('.dist-info')):
            continue
        with path.open('rb') as stream:
            raw = stream.read(65537)
        if len(raw) > 65536:
            raise ValueError('Oversized Python installation metadata')
        try:
            url = json.loads(raw)['url']
            scheme = urlsplit(url).scheme if isinstance(url, str) else ''
        except (ValueError, TypeError, KeyError):
            raise ValueError('Invalid Python installation metadata') from None
        if len(scheme) < 2 or scheme.rsplit('+', 1)[-1] == 'file':
            raise ValueError('Frozen backend contains a local installation path; install the wheel by package name')


def license_destination(root, name, file):
    if not isinstance(name, str) or not re.fullmatch(r'[A-Za-z0-9](?:[A-Za-z0-9._-]*[A-Za-z0-9])?', name):
        raise ValueError('Invalid license package directory')
    relative = Path(file)
    directory = root / name
    destination = directory / relative
    if (relative.drive or relative.root or ':' in str(relative)
            or any(part.rstrip(' .') != part for part in relative.parts)
            or not destination.resolve().is_relative_to(directory.resolve())):
        raise ValueError('Invalid license file destination')
    return destination


NATIVE_LICENSE_PROFILE = 'cpython-native-3.13.17'
NATIVE_DLL_TARGETS = {'backend/_internal/libcrypto-3.dll', 'backend/_internal/libssl-3.dll',
                     'backend/_internal/libffi-8.dll'}
NATIVE_DLL_PRODUCERS = {'backend/_internal/libcrypto-3.dll': 'openssl', 'backend/_internal/libssl-3.dll': 'openssl',
                        'backend/_internal/libffi-8.dll': 'libffi'}
NATIVE_LICENSE_FILES = {'openssl': ('OpenSSL-LICENSE.txt', 'Apache-2.0'), 'libffi': ('libffi-LICENSE', 'MIT')}


def _native_input(path, limit):
    for part in (path, *path.parents):
        info = part.lstat()
        if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT:
            raise ValueError('Native license input contains a link or reparse point')
    info = path.stat()
    if not stat.S_ISREG(info.st_mode) or info.st_size > limit:
        raise ValueError('Native license input is not a bounded regular file')
    with path.open('rb') as stream:
        raw = stream.read(limit + 1)
    if len(raw) > limit:
        raise ValueError('Native license input grew beyond its byte budget')
    return raw


def _native_json(pairs):
    result = dict(pairs)
    if len(result) != len(pairs):
        raise ValueError('Native license profile contains duplicate keys')
    return result


def _native_digest(raw):
    return hashlib.sha256(raw).hexdigest()


def native_license_plan(stage, payload, repository=None):
    """Validate all fixed inputs before any stage write; absence preserves generic stages."""
    matched = {}
    for relative, path in payload.items():
        key = relative.lower()
        if key in NATIVE_DLL_TARGETS:
            if key in matched:
                raise ValueError('Ambiguous native license DLL path')
            matched[key] = (relative, path)
    record = {'scope': 'fixed-cpython-native-license-texts', 'applied': False,
              'product_licenses_complete': False, 'distribution_obligations_reviewed': False,
              'vulnerabilities_verified': False, 'release_ready': False}
    if not matched:
        return {'record': record, 'inputs': [], 'writes': []}
    if set(matched) != NATIVE_DLL_TARGETS:
        raise ValueError('Partial fixed native license component set')
    repository = repository or Path(__file__).resolve().parent.parent
    directory = repository / 'packaging/licenses' / NATIVE_LICENSE_PROFILE
    profile_path = directory / 'provenance.json'
    profile_raw = _native_input(profile_path, 1024 * 1024)
    profile = json.loads(profile_raw, object_pairs_hook=_native_json)
    if type(profile.get('schema_version')) is not int or profile['schema_version'] != 1:
        raise ValueError('Unsupported native license profile')
    inputs, dlls, texts, writes, providers = [(profile_path, profile_raw, 1024 * 1024)], [], [], [], []
    groups, seen = set(), set()
    for archive in profile['binary_archives']:
        group, version = archive['name'], archive['recipe_declared_version']
        if group not in NATIVE_LICENSE_FILES or group in groups or not isinstance(version, str) or not re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+', version):
            raise ValueError('Invalid fixed native license producer')
        commit, archive_hash = archive.get('commit'), archive.get('sha256')
        if (not isinstance(commit, str) or not re.fullmatch(r'[0-9a-f]{40}', commit)
                or not isinstance(archive_hash, str) or not re.fullmatch(r'[0-9a-f]{64}', archive_hash)
                or archive.get('producer_repository') != 'https://github.com/python/cpython-bin-deps'
                or archive.get('url') != 'https://codeload.github.com/python/cpython-bin-deps/zip/' + commit):
            raise ValueError('Invalid fixed native license producer source')
        providers.append({'name': group, 'recipe_declared_version': version, 'repository': archive['producer_repository'],
                          'commit': commit, 'archive_url': archive['url'], 'archive_sha256': archive_hash})
        groups.add(group)
        license_items = []
        for item in archive['members']:
            if (not isinstance(item.get('sha256'), str) or not re.fullmatch(r'[0-9a-f]{64}', item['sha256'])
                    or type(item.get('bytes')) is not int or not 0 < item['bytes'] <= 8 * 1024 * 1024):
                raise ValueError('Invalid fixed native license member digest or size')
            if 'payload_path' not in item:
                license_items.append(item)
                continue
            if 'license_file' in item or not isinstance(item['payload_path'], str):
                raise ValueError('Ambiguous native license profile member')
            key = 'backend/' + item['payload_path']
            if key not in matched or key in seen or NATIVE_DLL_PRODUCERS.get(key) != group:
                raise ValueError('Unexpected or duplicate native license DLL')
            seen.add(key)
            relative, path = matched[key]
            raw = _native_input(path, 8 * 1024 * 1024)
            if len(raw) != item['bytes'] or _native_digest(raw) != item['sha256']:
                raise ValueError('Staged native DLL differs from fixed license source')
            inputs.append((path, raw, 8 * 1024 * 1024))
            dlls.append({'path': relative, 'bytes': len(raw), 'sha256': item['sha256'],
                         'producer': group, 'recipe_declared_version': version})
        if len(license_items) != 1:
            raise ValueError('Missing or duplicate fixed native license text')
        item = license_items[0]
        filename, spdx_id = NATIVE_LICENSE_FILES[group]
        if item.get('license_file') != filename or item.get('declared_spdx_id') != spdx_id:
            raise ValueError('Unexpected fixed native license file or declaration')
        source = directory / filename
        raw = _native_input(source, 1024 * 1024)
        if len(raw) != item['bytes'] or _native_digest(raw) != item['sha256']:
            raise ValueError('Fixed native license original differs from source record')
        inputs.append((source, raw, 1024 * 1024))
        # This subtree cannot collide with validated Python package names or the dart/native collectors.
        destination = license_destination(stage / 'licenses/_native', NATIVE_LICENSE_PROFILE, filename)
        for parent in destination.parents:
            if not parent.is_relative_to(stage):
                break
            if parent.exists() and not parent.is_dir():
                raise ValueError('Native license destination parent is not a directory')
        if destination.exists() and _native_input(destination, 1024 * 1024) != raw:
            raise ValueError('Native license destination conflicts with existing bytes')
        writes.append((source, destination, raw))
        texts.append({'path': destination.relative_to(stage).as_posix(), 'source': source.relative_to(repository).as_posix(),
                      'bytes': len(raw), 'sha256': item['sha256'], 'producer': group, 'license_id': spdx_id})
    if seen != NATIVE_DLL_TARGETS or groups != set(NATIVE_LICENSE_FILES):
        raise ValueError('Fixed native license profile does not cover the component set')
    record.update(applied=True, profile=NATIVE_LICENSE_PROFILE, profile_sha256=_native_digest(profile_raw),
                  dlls=sorted(dlls, key=lambda x: x['path']), license_files=sorted(texts, key=lambda x: x['path']),
                  providers=sorted(providers, key=lambda x: x['name']))
    return {'record': record, 'inputs': inputs, 'writes': writes}


def _verify_native_plan(plan, complete):
    for source, raw, limit in plan['inputs']:
        if _native_input(source, limit) != raw:
            raise ValueError('Native license input changed during staging')
    for source, destination, raw in plan['writes']:
        if destination.exists():
            if _native_input(destination, 1024 * 1024) != raw:
                raise ValueError('Native license destination differs from original')
        elif complete:
            raise ValueError('Staged native license original is missing')


def stage_native_license_texts(stage, plan):
    """Copy only missing originals; leave conflicting or partial output for diagnosis."""
    stage_files(stage)
    _verify_native_plan(plan, complete=False)
    for source, destination, raw in plan['writes']:
        if destination.exists():
            if _native_input(destination, 1024 * 1024) != raw:
                raise ValueError('Native license destination changed before copy')
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open('xb') as stream:
            if stream.write(raw) != len(raw):
                raise OSError('Incomplete native license copy; output preserved')
    _verify_native_plan(plan, complete=True)
    return plan['record']


def verify_native_license_texts(stage, payload, record):
    """Independently check the declared subset without writing or approving all licenses."""
    plan = native_license_plan(stage, payload)
    expected = plan['record']
    if record != expected and not (not expected['applied'] and record is None):
        raise ValueError('Native license inventory evidence is missing or differs')
    _verify_native_plan(plan, complete=True)
    return expected


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", type=Path, required=True)
    args = parser.parse_args()
    stage = args.stage.resolve()
    payload = stage_files(stage)
    repository = Path(__file__).resolve().parent.parent
    native_plan = native_license_plan(stage, payload, repository)
    licenses = stage / "licenses"
    licenses.mkdir(exist_ok=True)
    packages = []
    for dist in importlib.metadata.distributions():
        name = dist.metadata["Name"]
        packages.append({"name": name, "version": dist.version,
                         "license": dist.metadata.get("License-Expression") or dist.metadata.get("License", "See license files")})
        for file in dist.files or []:
            if (not file.name.lower().startswith(("license", "licence", "copying", "notice", "copyright", "authors"))
                    and not any(part.upper() in {"LICENSES", "BUILD_LICENSES"} for part in file.parts)):
                continue
            if file.suffix.lower() in {".py", ".pyc"}:
                continue
            if ".." in file.parts:
                continue
            destination = license_destination(licenses, name, file)
            source = Path(dist.locate_file(file))
            if source.is_file():
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, destination)
    python_license = Path(__import__("sys").base_prefix) / "LICENSE.txt"
    if python_license.is_file():
        shutil.copy2(python_license, licenses / "Python-LICENSE.txt")
    package_file = repository / "apps/desktop/.dart_tool/package_config.json"
    flutter = json.loads(package_file.read_text(encoding="utf-8"))
    for package in flutter["packages"]:
        uri = urljoin(package_file.as_uri(), package["rootUri"])
        package_root = Path(url2pathname(urlsplit(uri).path))
        for path in package_root.iterdir():
            if path.is_file() and path.name.lower().startswith(("license", "notice", "copying")):
                destination = license_destination(licenses / "dart", package["name"], path.name)
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, destination)
    sdk = Path(url2pathname(urlsplit(flutter["flutterRoot"]).path))
    shutil.copy2(sdk / "LICENSE", licenses / "Flutter-LICENSE")
    native = repository / "apps/desktop/build/windows/x64/packages"
    for package in native.iterdir():
        if not package.is_dir():
            continue
        for path in package.iterdir():
            if path.is_file() and path.name.lower().startswith(("license", "notice")):
                destination = license_destination(licenses / "native", package.name, path.name)
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, destination)
    json_license = repository / ".local/release-tools/nlohmann-json-3.11.2-LICENSE.MIT"
    destination = licenses / "native/nlohmann.json/LICENSE.MIT"
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(json_license, destination)
    native_licenses = stage_native_license_texts(stage, native_plan)
    files = {}
    for relative, path in stage_files(stage).items():
        with path.open("rb") as handle:
            files[relative] = hashlib.file_digest(handle, "sha256").hexdigest()
    (stage / "build-inventory.json").write_text(json.dumps({
        "python": platform.python_version(), "flutter": flutter["flutterVersion"], "build_environment_packages": packages,
        "native_license_texts": native_licenses,
        "files": files, "note": "Build environment list is not the frozen module set. Native/Flutter license review and clean-machine acceptance remain separate.",
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Inventory: {len(files)} files, {len(packages)} build packages; staged hashes and build metadata only")


if __name__ == "__main__":
    main()
