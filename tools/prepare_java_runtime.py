"""Prepare the pinned optional Temurin JRE without installing or executing it."""

import argparse
import hashlib
import json
import os
import re
import stat
from pathlib import Path, PurePosixPath
from zipfile import BadZipFile, ZipFile

import pefile
from release_inventory import stage_files

VERSION = '21.0.13+9'
PACKAGE_SIZE = 49106397
PACKAGE_SHA256 = '2332c0b4cff6bed722da3567c91d5e47568bcba863fa4945d0a8d6fc76158628'
SOURCE_URL = ('https://github.com/adoptium/temurin21-binaries/releases/download/jdk-21.0.13%2B9/'
              'OpenJDK21U-jre_x64_windows_hotspot_21.0.13_9.zip')
ARCHIVE_ROOT = 'jdk-21.0.13+9-jre'
LOCK_NAME = 'java-runtime-lock.json'
MAX_BYTES = 200 * 1024 * 1024
MAX_ENTRIES = 1024
ENTRIES = ('bin/java.exe', 'bin/jawt.dll', 'bin/server/jvm.dll')
REQUIRED = {*ENTRIES, 'release', 'NOTICE', 'legal/java.base/LICENSE',
            'legal/java.base/ASSEMBLY_EXCEPTION', 'legal/java.desktop/LICENSE'}


def no_links(path):
    for part in (path, *path.parents):
        info = part.lstat()
        if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT:
            raise ValueError('Runtime paths cannot contain links/reparse points')


def package_entries(archive):
    infos = archive.infolist()
    if not 1 <= len(infos) <= MAX_ENTRIES or sum(info.file_size for info in infos) > MAX_BYTES:
        raise ValueError('Java package exceeds extraction budget')
    names, files, directories, result = set(), set(), set(), []
    for info in infos:
        name = info.filename
        parts = name.rstrip('/').split('/')
        if (info.orig_filename != name or not name.startswith(ARCHIVE_ROOT + '/')
                or '\\' in name or '\x00' in name or '//' in name
                or any(not re.fullmatch(r'[A-Za-z0-9_][A-Za-z0-9_.+-]*', part)
                       or part.endswith('.') or re.fullmatch(r'(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?', part, re.I)
                       for part in parts)):
            raise ValueError('Unsafe Java archive path')
        mode = info.external_attr >> 16
        if info.flag_bits & 1 or stat.S_IFMT(mode) not in (0, stat.S_IFREG, stat.S_IFDIR):
            raise ValueError('Java package contains encrypted or special entries')
        if bool(stat.S_ISDIR(mode)) != info.is_dir() and stat.S_IFMT(mode):
            raise ValueError('Java entry type disagrees with its path')
        relative = '/'.join(parts[1:])
        key = relative.casefold()
        parents = {parent.as_posix().casefold() for parent in PurePosixPath(relative).parents
                   if parent.as_posix() != '.'}
        if key in names or parents & files or (not info.is_dir() and key in directories):
            raise ValueError('Duplicate or conflicting Java archive paths')
        names.add(key)
        directories.update(parents)
        if info.is_dir():
            directories.add(key)
        else:
            files.add(key)
        if relative:
            result.append((info, relative))
    if not {name.casefold() for name in REQUIRED} <= files or LOCK_NAME in files or 'build-inventory.json' in files:
        raise ValueError('Java package lacks runtime/legal files or contains reserved output names')
    return result


def verify_runtime(root, expected):
    no_links(root)
    if (root / 'build-inventory.json').exists():
        raise ValueError('Unexpected release inventory inside Java runtime')
    paths = stage_files(root)
    paths.pop(LOCK_NAME, None)
    if paths.keys() != expected.keys():
        raise ValueError('Java runtime file set differs')
    for name, path in paths.items():
        with path.open('rb') as stream:
            if hashlib.file_digest(stream, 'sha256').hexdigest() != expected[name]:
                raise ValueError('Java runtime file hash differs')
    release = (root / 'release').read_text(encoding='utf-8')
    for line in ['IMPLEMENTOR="Eclipse Adoptium"', 'SEMANTIC_VERSION="21.0.13+9"',
                 'OS_NAME="Windows"', 'OS_ARCH="x86_64"', 'IMAGE_TYPE="JRE"']:
        if line not in release.splitlines():
            raise ValueError('Java release metadata differs from the pinned runtime')
    for name in ENTRIES:
        image = pefile.PE(str(root / name), fast_load=True)
        try:
            if image.FILE_HEADER.Machine != 0x8664 or image.OPTIONAL_HEADER.Magic != 0x20B:
                raise ValueError('Java entry must be Windows x64 PE32+')
        finally:
            image.close()


def prepare(package, destination):
    package, destination = package.absolute(), destination.absolute()
    no_links(package)
    no_links(destination.parent)
    if destination.exists() or destination.is_symlink():
        raise ValueError('Destination already exists; no replacement allowed')
    with package.open('rb') as stream:
        if (not stat.S_ISREG(os.fstat(stream.fileno()).st_mode)
                or os.fstat(stream.fileno()).st_size != PACKAGE_SIZE
                or hashlib.file_digest(stream, 'sha256').hexdigest() != PACKAGE_SHA256):
            raise ValueError('Official Java package size/hash differs')
        stream.seek(0)
        with ZipFile(stream) as archive:
            entries = package_entries(archive)
            destination.mkdir()
            files, total = {}, 0
            for info, relative in entries:
                target = destination / relative
                if info.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                digest, count = hashlib.sha256(), 0
                with archive.open(info) as source, target.open('xb') as output:
                    while chunk := source.read(1024 * 1024):
                        count += len(chunk)
                        total += len(chunk)
                        if count > info.file_size or total > MAX_BYTES:
                            raise ValueError('Expanded Java entry exceeds budget')
                        digest.update(chunk)
                        output.write(chunk)
                if count != info.file_size:
                    raise ValueError('Expanded Java entry size differs')
                files[relative] = digest.hexdigest()
        stream.seek(0)
        if hashlib.file_digest(stream, 'sha256').hexdigest() != PACKAGE_SHA256:
            raise ValueError('Java package changed during extraction')
    verify_runtime(destination, files)
    value = {'version': VERSION, 'package_sha256': PACKAGE_SHA256, 'source_url': SOURCE_URL,
             'bytes': total, 'files': dict(sorted(files.items()))}
    with (destination / LOCK_NAME).open('x', encoding='utf-8', newline='\n') as output:
        output.write(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package', type=Path, required=True)
    parser.add_argument('--destination', type=Path, required=True, help='New directory; parent must exist')
    args = parser.parse_args()
    try:
        result = prepare(args.package, args.destination)
    except (OSError, ValueError, BadZipFile, pefile.PEFormatError) as exc:
        parser.exit(1, f'Java preparation failed; partial output retained: {exc}\n')
    print(f"Prepared Temurin {VERSION}: {len(result['files'])} files, {result['bytes']} bytes; no installation.")


if __name__ == '__main__':
    main()
