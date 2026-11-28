"""Stage and verify the optional Temurin source files alongside the Windows application."""
import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

from prepare_java_runtime import LOCK_NAME, PACKAGE_SHA256, VERSION, no_links, verify_runtime
from temurin_sources import BUILD_COMMIT, JDK_COMMIT, PINS

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from study_workbench.office_runtime import JAVA_LOCK_SHA256  # noqa: E402

DEST = Path('sources/temurin')
OPENJDK = 'OpenJDK21U-jdk-sources_21.0.13_9.tar.gz'
BUILD = f'temurin-build-{BUILD_COMMIT}.zip'
ARCHIVES = {OPENJDK: ('sources', 'https://github.com/adoptium/temurin21-binaries/releases/download/'
                      'jdk-21.0.13%2B9/' + OPENJDK),
            BUILD: ('build_sources', 'https://codeload.github.com/adoptium/temurin-build/zip/' + BUILD_COMMIT)}


def manifest():
    value = {'component': 'Eclipse Temurin Windows x64 JRE', 'version': VERSION, 'jreZipSha256': PACKAGE_SHA256,
             'openjdkCommit': JDK_COMMIT, 'buildCommit': BUILD_COMMIT,
             'archives': {name: {'sha256': PINS[kind], 'url': url} for name, (kind, url) in ARCHIVES.items()}}
    return (json.dumps(value, indent=2, sort_keys=True) + '\n').encode()


def check_java(root):
    java = root / 'converters/libreoffice/java'
    lock = java / LOCK_NAME
    no_links(lock.absolute())
    with lock.open('rb') as stream:
        raw = stream.read(262145)
    if hashlib.sha256(raw).hexdigest() != JAVA_LOCK_SHA256:
        raise ValueError('Optional matching Office JRE required')
    verify_runtime(java, json.loads(raw)['files'])


def check_files(directory):
    no_links(directory.absolute())
    if {p.name for p in directory.iterdir()} != {*ARCHIVES, 'manifest.json'}:
        raise ValueError('Incomplete or unexpected source delivery files')
    for path in directory.iterdir():
        no_links(path.absolute())
        if not path.is_file():
            raise ValueError('Expected a regular source delivery file')
    expected = manifest()
    with (directory / 'manifest.json').open('rb') as stream:
        if stream.read(len(expected) + 1) != expected:
            raise ValueError('Source delivery manifest differs')
    for name, (kind, _) in ARCHIVES.items():
        with (directory / name).open('rb') as stream:
            if hashlib.file_digest(stream, 'sha256').hexdigest() != PINS[kind]:
                raise ValueError('Source delivery archive differs')


def stage(root, source, build):
    check_java(root)
    destination = root / DEST
    if destination.parent.exists() or destination.parent.is_symlink():
        no_links(destination.parent.absolute())
    if destination.exists() or destination.is_symlink():
        raise ValueError('Source delivery destination already exists')
    with TemporaryDirectory(dir=root.parent) as scratch:
        bundle = Path(scratch) / 'temurin'
        bundle.mkdir()
        for path, name in ((source, OPENJDK), (build, BUILD)):
            no_links(path.absolute())
            if not path.is_file():
                raise ValueError('Expected a regular source archive')
            with path.open('rb') as stream:
                if hashlib.file_digest(stream, 'sha256').hexdigest() != PINS[ARCHIVES[name][0]]:
                    raise ValueError('Source input archive differs')
                stream.seek(0)
                with (bundle / name).open('xb') as out:
                    shutil.copyfileobj(stream, out)
        (bundle / 'manifest.json').write_bytes(manifest())
        check_files(bundle)
        destination.parent.mkdir(exist_ok=True)
        no_links(destination.parent.absolute())
        bundle.rename(destination)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--installed', type=Path, required=True, help='application directory or unpacked installer root')
    root = parser.parse_args().installed
    check_java(root)
    check_files(root / DEST)
    print(f'Verified optional Temurin {VERSION} JRE and both delivered source archives')
