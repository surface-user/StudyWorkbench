"""Verify offline source and build archives for the pinned Windows Temurin JRE."""
import argparse
import hashlib
import json
import re
import tarfile
from contextlib import ExitStack, contextmanager
from pathlib import Path
from zipfile import ZipFile

from prepare_java_runtime import ARCHIVE_ROOT, PACKAGE_SHA256, VERSION, no_links

JDK_COMMIT = '2ab10ca20c191701c3a9f3153bfc6e93d63714c1'
BUILD_COMMIT = '1cf43d7a3e77886bfea7d550a902e151a87d724d'
PINS = {
    'jre': PACKAGE_SHA256,
    'jre_metadata': '6b980e8b05bbc1fd3a0d244e40e793208b95d2743f97d3ba220a8e3405e8f348',
    'sources': 'b5232c9980d8a0f0459676c084c41c6e2c771ed9e785890b03c6a438406ad1ca',
    'sources_metadata': '861168ce2bc2d2e1aff09823d749d6cd961380a5db524220ec963b2efd25739d',
    'build_sources': '00a1cbe9d103742c5ab7383dfd770f2c313900eead8f5c0b894a7aad4f7a53d1',
}
WINDOWS_SOURCES = {'configure', 'Makefile', 'src/hotspot/os/windows/os_windows.cpp',
                   'src/java.base/windows/native/libjava/java_props_md.c',
                   'src/java.base/share/classes/java/lang/Object.java'}
COMMON = {'ASSEMBLY_EXCEPTION', 'LICENSE', 'ADDITIONAL_LICENSE_INFO'}


@contextmanager
def checked(path, key):
    no_links(path.absolute())
    with path.open('rb') as stream:
        if hashlib.file_digest(stream, 'sha256').hexdigest() != PINS[key]:
            raise ValueError(f'Wrong pinned input: {key}')
        stream.seek(0)
        yield stream
        stream.seek(0)
        if hashlib.file_digest(stream, 'sha256').hexdigest() != PINS[key]:
            raise ValueError(f'Input changed during verification: {key}')


def check_metadata(metadata, kind):
    expected = {'binary_type': kind, 'variant': 'temurin', 'sha256': PINS[kind],
                'scmRef': 'jdk-' + VERSION + '_adopt',
                'openjdk_source': 'https://github.com/adoptium/jdk21u/commit/' + JDK_COMMIT,
                'buildRef': 'https://github.com/adoptium/temurin-build/commit/' + BUILD_COMMIT}
    if kind == 'jre':
        expected.update(os='windows', arch='x64')
    if any(metadata.get(k) != v for k, v in expected.items()):
        raise ValueError(f'Build identity differs: {kind}')


def source_contents(stream):
    root = f'jdk-{VERSION}-src/'
    anchors, modules, bodies = set(), set(), set()
    with tarfile.open(fileobj=stream, mode='r|gz') as archive:
        for member in archive:
            if not member.isfile():
                continue
            if not member.name.startswith(root):
                raise ValueError('Unexpected source archive root')
            name = member.name[len(root):]
            if name in WINDOWS_SOURCES and member.size:
                anchors.add(name)
            match = re.fullmatch(r'src/([^/]+)/(?:share|windows)/classes/module-info\.java', name)
            if match and member.size:
                modules.add(match[1])
            if name in COMMON or re.fullmatch(r'src/[^/]+/[^/]+/legal/[^/]+', name):
                with archive.extractfile(member) as raw:
                    bodies.add((name.rsplit('/', 1)[-1], hashlib.file_digest(raw, 'sha256').hexdigest()))
    if anchors != WINDOWS_SOURCES:
        raise ValueError('Missing Windows or build source')
    return modules, bodies


def verify(paths):
    with ExitStack() as stack:
        files = {key: stack.enter_context(checked(paths[key], key)) for key in PINS}
        for kind in ('jre', 'sources'):
            check_metadata(json.load(files[kind + '_metadata']), kind)
        modules, bodies = source_contents(files['sources'])
        with ZipFile(files['jre']) as jre, ZipFile(files['build_sources']) as build:
            rel = jre.read(ARCHIVE_ROOT + '/release').decode().splitlines()
            if not {f'SOURCE=".:git:{JDK_COMMIT[:12]}"', f'BUILD_SOURCE="git:{BUILD_COMMIT}"'} <= set(rel):
                raise ValueError('JRE release file disagrees with publisher metadata')
            legal_modules, direct = set(), set()
            for entry in jre.infolist():
                match = re.fullmatch(re.escape(ARCHIVE_ROOT) + r'/legal/([^/]+)/([^/]+)', entry.filename)
                if match:
                    legal_modules.add(match[1])
                    raw = jre.read(entry)
                    if not raw.strip().startswith(b'Please see'):
                        direct.add((match[2], hashlib.sha256(raw).hexdigest()))
            if not legal_modules or not direct or not legal_modules <= modules or not direct <= bodies:
                raise ValueError('Missing module source descriptor or matching license text')
            prefix = f'temurin-build-{BUILD_COMMIT}/'
            if (build.read(prefix + 'sbin/NOTICE.template') != jre.read(ARCHIVE_ROOT + '/NOTICE')
                    or not build.read(prefix + 'makejdk-any-platform.sh')):
                raise ValueError('Build scripts or root notice differ')
    return {'version': VERSION, 'openjdkCommit': JDK_COMMIT, 'buildCommit': BUILD_COMMIT,
            'archiveModuleDescriptors': len(modules), 'jreLegalModulesWithDescriptor': len(legal_modules),
            'matchedDirectModuleTexts': len(direct), 'matchedRootNotice': True, 'sha256': PINS,
            'distributionInspected': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for key in PINS:
        parser.add_argument('--' + key.replace('_', '-'), type=Path, required=True)
    print(json.dumps(verify(vars(parser.parse_args())), sort_keys=True))
