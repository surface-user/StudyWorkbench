"""Inventory an administratively extracted, pinned optional LibreOffice package."""
import argparse
import hashlib
import json
import stat
from pathlib import Path

VERSION = '26.8.1'
PACKAGE_SHA256 = 'c6298b10cfa1748bcbedad94c62ce771e240e5021bfd6d7a967cd571b04b5312'
URL = 'https://download.documentfoundation.org/libreoffice/stable/26.8.1/win/x86_64/LibreOffice_26.8.1_Win_x86-64.msi'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--package', type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    with args.package.open('rb') as handle:
        assert hashlib.file_digest(handle, 'sha256').hexdigest() == PACKAGE_SHA256, 'Official package hash differs'
    files, size = {}, 0
    for path in sorted(root.rglob('*')):
        info = path.lstat()
        assert not path.is_symlink() and not getattr(info, 'st_file_attributes', 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT
        if not path.is_file() or path.suffix.lower() == '.msi' or path.name == 'runtime-lock.json':
            continue
        with path.open('rb') as handle:
            files[path.relative_to(root).as_posix()] = hashlib.file_digest(handle, 'sha256').hexdigest()
        size += info.st_size
    assert {'program/soffice.com', 'program/soffice.bin', 'license.txt', 'LICENSE.html', 'NOTICE'} <= files.keys()
    assert len(files) <= 20000
    value = dict(version=VERSION, package_sha256=PACKAGE_SHA256, source_url=URL,
                 bytes=size, files=files)
    (root / 'runtime-lock.json').write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(dict(version=VERSION, files=len(files), bytes=size, package_sha256=PACKAGE_SHA256)))


if __name__ == '__main__':
    main()
