"""Pinned offline FFmpeg source preparation; never installs, builds or auto-downloads."""
import argparse
import hashlib
import json
import os
import re
import stat
import tarfile
from pathlib import Path, PurePosixPath

from release_inventory import stage_files

VERSION = '9.0.2'
PACKAGE_SIZE = 12040788
PACKAGE_SHA256 = '8c3850283eb25fa026482078a04051e0be17347b09ef81a0849bec15a96e002e'
SOURCE_URL = 'https://ffmpeg.org/releases/ffmpeg-9.0.2.tar.xz'
SOURCE_COMMIT = '946fcce07b6dcd0331c8cc609192aeff5e1924f8'
RELEASE_FINGERPRINT = 'FCF986EA15E6E293A5644F10B4322F04D67658D8'
GIT_FILES = {"configure":"374bd5c1512943439480825f32e448e7871eb61c","fftools/ffmpeg.c":"b394243f59964b74d59311f2166f67c3078c5618","fftools/ffprobe.c":"31f74106f9f8b489bb4dd6c9419def766a63958b","LICENSE.md":"371b0913ce7c199c4092d9344680c80f78ebeb2a"}
ARCHIVE_ROOT = 'ffmpeg-9.0.2'
SOURCE_LOCK = 'source-lock.json'
MAX_ENTRIES = 20000
MAX_BYTES = 256 * 1024 * 1024
MAX_MEMBER = 8 * 1024 * 1024
REQUIRED = {'configure', 'Makefile', 'RELEASE', 'LICENSE.md', 'COPYING.LGPLv2.1',
            'COPYING.LGPLv3', 'COPYING.GPLv2', 'COPYING.GPLv3', 'fftools/ffmpeg.c', 'fftools/ffprobe.c'}


def canonical(payload):
    """The preimage is the payload alone, never the envelope's derived digest."""
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')


def envelope(payload):
    if 'snapshot_sha256' in payload:
        raise ValueError('Derived snapshot digest cannot enter its own preimage')
    return {'payload': payload, 'snapshot_sha256': hashlib.sha256(canonical(payload)).hexdigest()}


def checked_envelope(value):
    if (not isinstance(value, dict) or set(value) != {'payload', 'snapshot_sha256'}
            or not isinstance(value['payload'], dict) or envelope(value['payload']) != value):
        raise ValueError('Snapshot envelope or canonical digest differs')
    return value['payload']


def read_snapshot(path):
    no_links(path)
    with path.open('rb') as stream:
        raw = stream.read(8 * 1024 * 1024 + 1)
    if len(raw) > 8 * 1024 * 1024:
        raise ValueError('Snapshot exceeds read budget')

    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('Duplicate snapshot field')
            result[key] = value
        return result

    def constant(_):
        raise ValueError('Non-finite snapshot number')

    try:
        value = json.loads(raw.decode('utf-8'), object_pairs_hook=pairs, parse_constant=constant)
    except RecursionError:
        raise ValueError('Snapshot nesting exceeds budget') from None
    pending, count = [(value, 0)], 0
    while pending:
        item, depth = pending.pop()
        count += 1
        if depth > 16 or count > 100000:
            raise ValueError('Snapshot structure exceeds budget')
        if isinstance(item, dict):
            pending.extend((child, depth + 1) for child in item.values())
        elif isinstance(item, list):
            pending.extend((child, depth + 1) for child in item)
    return checked_envelope(value)


def no_links(path):
    for part in (path, *path.parents):
        info = part.lstat()
        if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT:
            raise ValueError('Component paths cannot contain links/reparse points')


def safe_relative(name):
    parts = name.split('/')
    if (not name or '\\' in name or len(parts) > 16
            or any(part in {'', '.', '..'} or not re.fullmatch(r'[A-Za-z0-9_.+-]+', part)
                   or part.endswith('.') or re.fullmatch(r'(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?', part, re.I)
                   for part in parts)):
        raise ValueError('Unsafe source member path')
    return name


def members(archive):
    result, names, files, directories, total = [], set(), set(), set(), 0
    for index, info in enumerate(archive, 1):
        if index > MAX_ENTRIES or info.sparse is not None or not (info.isfile() or info.isdir()):
            raise ValueError('Source contains special entries or exceeds count budget')
        name = info.name.rstrip('/')
        if name == ARCHIVE_ROOT and info.isdir():
            continue
        if not name.startswith(ARCHIVE_ROOT + '/'):
            raise ValueError('Source archive root differs')
        relative = safe_relative(name[len(ARCHIVE_ROOT) + 1:])
        key = relative.casefold()
        parents = {p.as_posix().casefold() for p in PurePosixPath(relative).parents if p.as_posix() != '.'}
        if key in names or parents & files or info.isfile() and key in directories:
            raise ValueError('Source paths collide or conflict')
        names.add(key)
        directories.update(parents)
        if info.isdir():
            directories.add(key)
        else:
            if not 0 <= info.size <= MAX_MEMBER:
                raise ValueError('Source member exceeds size budget')
            total += info.size
            if total > MAX_BYTES:
                raise ValueError('Source expansion exceeds shared byte budget')
            files.add(key)
        result.append((info, relative))
    if not {name.casefold() for name in REQUIRED} <= files or {SOURCE_LOCK, 'build-inventory.json'} & files:
        raise ValueError('Source lacks required original files or uses reserved output names')
    return result


def source_payload(records):
    for name, expected in GIT_FILES.items():
        if records.get(name, {}).get('git_blob') != expected:
            raise ValueError('Pinned Git/source association differs')
    return {'schema_version': 1, 'kind': 'ffmpeg-source', 'version': VERSION, 'source_url': SOURCE_URL,
            'package_bytes': PACKAGE_SIZE, 'package_sha256': PACKAGE_SHA256, 'git_commit': SOURCE_COMMIT,
            'tar_release_signer': RELEASE_FINGERPRINT, 'files': dict(sorted(records.items()))}


def source_records(package, destination=None):
    no_links(package)
    with package.open('rb') as stream:
        if (not stat.S_ISREG(os.fstat(stream.fileno()).st_mode) or os.fstat(stream.fileno()).st_size != PACKAGE_SIZE
                or hashlib.file_digest(stream, 'sha256').hexdigest() != PACKAGE_SHA256):
            raise ValueError('Authenticated source archive size/hash differs')
        stream.seek(0)
        with tarfile.open(fileobj=stream, mode='r:xz') as archive:
            entries = members(archive)
            if destination is not None:
                destination.mkdir()
            records, total = {}, 0
            for info, relative in entries:
                if info.isdir():
                    if destination is not None:
                        (destination / relative).mkdir(parents=True, exist_ok=True)
                    continue
                digest, count = hashlib.sha256(), 0
                git = hashlib.sha1(b'blob ' + str(info.size).encode('ascii') + b'\0')
                output = None
                try:
                    if destination is not None:
                        target = destination / relative
                        target.parent.mkdir(parents=True, exist_ok=True)
                        output = target.open('xb')
                    with archive.extractfile(info) as source:
                        while chunk := source.read(1024 * 1024):
                            count += len(chunk)
                            total += len(chunk)
                            if count > info.size or total > MAX_BYTES:
                                raise ValueError('Actual source expansion exceeds budget')
                            digest.update(chunk)
                            git.update(chunk)
                            if output is not None:
                                output.write(chunk)
                    if count != info.size:
                        raise ValueError('Source member length differs')
                    records[relative] = {'size': count, 'sha256': digest.hexdigest(), 'git_blob': git.hexdigest()}
                finally:
                    if output is not None:
                        output.close()
        stream.seek(0)
        if hashlib.file_digest(stream, 'sha256').hexdigest() != PACKAGE_SHA256:
            raise ValueError('Source archive changed during preparation')
    return records


def verify_source(package, root):
    no_links(root)
    if (root / 'build-inventory.json').exists():
        raise ValueError('Unexpected reserved inventory file')
    lock = read_snapshot(root / SOURCE_LOCK)
    # Authenticate every source member against the pinned original, not a mutable self-rehashed lock.
    expected = source_payload(source_records(package))
    if lock != expected:
        raise ValueError('Source snapshot differs from authenticated archive')
    paths = stage_files(root)
    paths.pop(SOURCE_LOCK, None)
    if paths.keys() != expected['files'].keys():
        raise ValueError('Source file set changed')
    for name, path in paths.items():
        with path.open('rb') as stream:
            if os.fstat(stream.fileno()).st_size != expected['files'][name]['size'] or hashlib.file_digest(stream, 'sha256').hexdigest() != expected['files'][name]['sha256']:
                raise ValueError('Source bytes changed')
    return envelope(expected)


def prepare_source(package, destination):
    package, destination = package.absolute(), destination.absolute()
    no_links(destination.parent)
    if destination.exists() or destination.is_symlink():
        raise ValueError('Destination exists; no replacement permitted')
    result = envelope(source_payload(source_records(package, destination)))
    with (destination / SOURCE_LOCK).open('x', encoding='utf-8', newline='\n') as output:
        output.write(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    verify_source(package, destination)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['prepare-source', 'verify-source'])
    parser.add_argument('--package', type=Path, required=True)
    parser.add_argument('--directory', type=Path, required=True)
    args = parser.parse_args()
    try:
        result = prepare_source(args.package, args.directory) if args.mode == 'prepare-source' else verify_source(args.package, args.directory)
    except (OSError, ValueError, tarfile.TarError) as error:
        parser.exit(1, f'Source preparation rejected; partial files retained: {error}\n')
    print(json.dumps({'version': VERSION, 'source_files': len(result['payload']['files']),
                      'source_snapshot_sha256': result['snapshot_sha256'], 'configure_executed': False,
                      'product_component_ready': False}))


if __name__ == '__main__':
    main()
