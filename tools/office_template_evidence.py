"""Read fixed Office Python source/template evidence; never approve runtime exclusion."""
import argparse
import hashlib
import io
import json
import os
import stat
import tarfile
from email.parser import BytesParser
from pathlib import Path, PurePosixPath
from zipfile import BadZipFile, ZipFile, is_zipfile

import pefile
from check_native_dependencies import component_payload
from prepare_java_runtime import no_links
from release_inventory import stage_files

COMPONENT_SHA256 = '156b4421aeb8eaadb565d6d33234bf69c58d22b5e46b78c9de81548dfe7b9bc9'
PYTHON_SIZE = 23160540
PYTHON_SHA256 = '1e66a7945a48390ee4c2a4268a0e4185884059a13c4aab6d148aa208deea4a76'
TAR_ROOT = 'Python-3.13.15/'
LIB = 'program/python-core-3.13.15/lib/'
MAX_MEMBER = 4 * 1024 * 1024
MAX_WHEEL = 8 * 1024 * 1024
WHEELS = {
    'pip': dict(version='26.2.1', path='Lib/ensurepip/_bundled/pip-26.2.1-py3-none-any.whl',
                sha256='71138adf1f4ca900cdb7d289c21b7494329f2332b6d85f0e1c42108c0384ed3e'),
    'setuptools': dict(version='79.0.1', path='Lib/test/wheeldata/setuptools-79.0.1-py3-none-any.whl',
                       sha256='e147c0549f27767ba362f9da434eab9c5dc0045d5304feb602a0af001089fc51'),
}
PATCH_PATH = 'setuptools/_vendor/jaraco/text/__init__.py'
PATCH_HASHES = ('636614a9747fa2b5280da6384a43d17ba65985be4750707f021f5108db15ca1a',
                'c9e90f78f9ca8155e9fbc24fa46c33ffc0c50553f4f8a96f855233da5eba5991')
RENAMED = 'setuptools/_vendor/jaraco/text/Lorem_ipsum.txt'
ORIGINAL_NAME = 'setuptools/_vendor/jaraco/text/Lorem ipsum.txt'
RENAMED_SHA256 = '37fedcffbf73c4eb9f058f47677cb33203a436ff9390e4d38a8e01c9dad28e0b'
TEMPLATES = {'pip/_vendor/distlib/' + name for name in
             ('t32.exe', 't64.exe', 't64-arm.exe', 'w32.exe', 'w64.exe', 'w64-arm.exe')} | {
    'setuptools/' + name for name in ('cli.exe', 'cli-32.exe', 'cli-64.exe', 'cli-arm64.exe',
                                     'gui.exe', 'gui-32.exe', 'gui-64.exe', 'gui-arm64.exe')}
PRODUCERS = {'pip/_vendor/distlib/scripts.py': dict(kind='append-shebang-and-zip',
              source='pypa/distlib', commit='8183ea60e83bf021bf7d6903f4a6b3c8df0905a6',
              launcher='PC/launcher.c', launcher_blob='727f79165c8d328843598cace030e630045be066'),
             'setuptools/command/easy_install.py': dict(kind='copy-exe-and-companion-script',
              source='pypa/setuptools', commit='607f6be776db97d83c9cc54e0eaa578567dcc44c',
              launcher='launcher.c', launcher_blob='b87cb32ad65b70ddf53c59317eed2433d9b3bd42')}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def read_file(path, limit, *, allow_empty=False):
    no_links(path)
    with path.open('rb') as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
            raise ValueError('Evidence input is not a regular file')
        data = stream.read(limit + 1)
    if (not data and not allow_empty) or len(data) > limit:
        raise ValueError('Evidence input is empty or exceeds budget')
    return data


def safe_name(name):
    path = PurePosixPath(name.rstrip('/'))
    if (not name or '\\' in name or '\x00' in name or '//' in name or path.is_absolute()
            or any(part in {'.', '..'} or ':' in part for part in name.rstrip('/').split('/'))):
        raise ValueError('Unsafe archive member path')


def wheel_files(data):
    files = {}
    with ZipFile(io.BytesIO(data)) as archive:
        infos = archive.infolist()
        if len(infos) > 4000 or sum(item.file_size for item in infos) > 64 * 1024 * 1024:
            raise ValueError('Wheel entry/expanded budget exceeded')
        seen = set()
        for item in infos:
            safe_name(item.filename)
            key = item.filename.rstrip('/').casefold()
            mode = stat.S_IFMT(item.external_attr >> 16)
            if (item.orig_filename != item.filename or key in seen or item.flag_bits & 1
                    or mode not in {0, stat.S_IFREG, stat.S_IFDIR}
                    or bool(mode == stat.S_IFDIR) != item.is_dir() and mode):
                raise ValueError('Duplicate, normalized, encrypted or special wheel member')
            seen.add(key)
            if item.is_dir():
                continue
            if item.file_size > MAX_MEMBER:
                raise ValueError('Wheel member exceeds budget')
            with archive.open(item) as stream:
                content = stream.read(MAX_MEMBER + 1)
                if len(content) != item.file_size or len(content) > MAX_MEMBER or stream.read(1):
                    raise ValueError('Actual wheel expansion differs or exceeds budget')
            files[item.filename] = content
    return files


def template_structure(name, data, component_names):
    image = pefile.PE(data=data, fast_load=True)
    try:
        result = dict(machine=hex(image.FILE_HEADER.Machine), magic=hex(image.OPTIONAL_HEADER.Magic),
                      subsystem=image.OPTIONAL_HEADER.Subsystem,
                      overlay_offset=image.get_overlay_data_start_offset(),
                      zip_archive=is_zipfile(io.BytesIO(data)))
    finally:
        image.close()
    if result['zip_archive'] or result['overlay_offset'] is not None:
        raise ValueError('Original template unexpectedly contains appended payload')
    if name.startswith('pip/'):
        if b'PK\x05\x06' in data:
            raise ValueError('Original distlib template contains an archive trailer signature')
        result.update(required_data='appended-shebang-and-zip', archive_trailer_absent=True)
    else:
        suffix = '-script.pyw' if PurePosixPath(name).name.startswith('gui') else '-script.py'
        companion = str(PurePosixPath(LIB + name).with_suffix('')) + suffix
        result.update(required_data='same-directory-companion-script', companion_path=companion,
                      companion_absent=companion not in component_names)
        if not result['companion_absent']:
            raise ValueError('Original setuptools template has a companion script')
    return result


def generate(office, python_source, output):
    office, python_source, output = (path.absolute() for path in (office, python_source, output))
    no_links(office)
    no_links(python_source)
    no_links(output.parent)
    if output.exists() or output.is_symlink() or output.is_relative_to(office):
        raise ValueError('Output must be a new directory outside the component')
    lock_raw = read_file(office / 'runtime-lock.json', MAX_MEMBER)
    if digest(lock_raw) != COMPONENT_SHA256:
        raise ValueError('Fixed Office component inventory differs')
    with python_source.open('rb') as stream:
        info = os.fstat(stream.fileno())
        if (not stat.S_ISREG(info.st_mode) or info.st_size != PYTHON_SIZE
                or hashlib.file_digest(stream, 'sha256').hexdigest() != PYTHON_SHA256):
            raise ValueError('Fixed Python source size/hash differs')
        stream.seek(0)
        paths, component_hash = component_payload(office)
        if len(paths) > 20000 or component_hash != COMPONENT_SHA256:
            raise ValueError('Component budget or inventory changed')
        expected = json.loads(lock_raw)['files']
        wanted = {TAR_ROOT + item['path']: name for name, item in WHEELS.items()}
        wheels, seen, expanded = {}, set(), 0
        with tarfile.open(fileobj=stream, mode='r:xz') as archive:
            for count, member in enumerate(archive, 1):
                if count > 50000:
                    raise ValueError('Source tar entry budget exceeded')
                safe_name(member.name)
                key = member.name.rstrip('/').casefold()
                if key in seen or not (member.isfile() or member.isdir()):
                    raise ValueError('Duplicate or special source tar member')
                seen.add(key)
                expanded += member.size
                if member.size > 64 * 1024 * 1024 or expanded > 512 * 1024 * 1024:
                    raise ValueError('Source tar expanded budget exceeded')
                if member.name not in wanted:
                    continue
                if not member.isfile() or member.size > MAX_WHEEL:
                    raise ValueError('Source wheel is not a bounded regular file')
                data = archive.extractfile(member).read(MAX_WHEEL + 1)
                name = wanted[member.name]
                if len(data) != member.size or digest(data) != WHEELS[name]['sha256']:
                    raise ValueError('Source wheel size/hash differs')
                wheels[name] = wheel_files(data)
        if wheels.keys() != WHEELS.keys():
            raise ValueError('Missing source wheel')
        output.mkdir()
        packages, assets, producers, observed = {}, {}, {}, {}
        for name, specification in WHEELS.items():
            files = wheels[name]
            metadata = BytesParser().parsebytes(files[f"{name}-{specification['version']}.dist-info/METADATA"])
            if metadata['Name'] != name or metadata['Version'] != specification['version']:
                raise ValueError('Source distribution metadata differs')
            records = []
            selected = {key: path for key, path in paths.items() if key.startswith(LIB + name + '/')}
            if len(observed) + len(selected) > 1500:
                raise ValueError('Selected package file budget exceeded')
            for key, path in selected.items():
                relative = key.removeprefix(LIB)
                original_name = ORIGINAL_NAME if relative == RENAMED else relative
                data = read_file(path, MAX_MEMBER, allow_empty=True)
                original = files[original_name]
                current_hash, source_hash = digest(data), digest(original)
                if current_hash != expected[key]:
                    raise ValueError('Selected component file changed')
                relation = 'identical'
                if relative == PATCH_PATH:
                    if (source_hash, current_hash) != PATCH_HASHES:
                        raise ValueError('Fixed LibreOffice patch input/output differs')
                    relation = 'fixed-libreoffice-patch'
                elif original_name != relative:
                    if current_hash != RENAMED_SHA256 or source_hash != RENAMED_SHA256:
                        raise ValueError('Fixed LibreOffice rename bytes differ')
                    relation = 'fixed-libreoffice-rename'
                elif data != original:
                    raise ValueError('Unexplained source/installed content difference')
                observed[key] = current_hash
                records.append(dict(path=key, source_wheel_path=original_name, source_sha256=source_hash,
                                    installed_sha256=current_hash, relation=relation))
                if relative in TEMPLATES:
                    assets[key] = dict(sha256=current_hash,
                        git_blob=hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest(),
                        role='producer-input-pe-template', **template_structure(relative, data, paths))
                if relative in PRODUCERS:
                    producers[key] = dict(sha256=current_hash, **PRODUCERS[relative])
            packages[name] = dict(source_distribution_version=specification['version'],
                source_wheel=specification['path'], source_wheel_sha256=specification['sha256'],
                installed_content_scope='matched LibreOffice package-directory subset; not full installed distribution',
                files=records)
        if set(assets) != {LIB + name for name in TEMPLATES} or set(producers) != {LIB + name for name in PRODUCERS}:
            raise ValueError('Missing fixed template or producer')
        stream.seek(0)
        if hashlib.file_digest(stream, 'sha256').hexdigest() != PYTHON_SHA256:
            raise ValueError('Source archive changed during collection')
    if (digest(read_file(python_source, PYTHON_SIZE)) != PYTHON_SHA256
            or lock_raw != read_file(office / 'runtime-lock.json', MAX_MEMBER) or paths.keys() != stage_files(office).keys()
            or any(digest(read_file(paths[key], MAX_MEMBER, allow_empty=True)) != value
                   for key, value in observed.items())):
        raise ValueError('Component evidence changed during collection')
    report = dict(scope='fixed Office Python source and template-role evidence',
        collector_sha256=digest(read_file(Path(__file__).absolute(), MAX_MEMBER)),
        component_inventory_sha256=component_hash, component_files_verified=len(paths),
        source_archive_sha256=PYTHON_SHA256, source_archive_bytes=PYTHON_SIZE,
        packages=packages, templates=assets, producers=producers,
        runtime_classification='unclassified', runtime_exclusion_verified=False, product_release_ready=False,
        limitations=['Source distribution versions do not imply complete installed distributions.',
                    'Launcher source links are curated publisher associations, not a reproducible compilation proof.',
                    'Producer resource use and missing launch data do not prove runtime unreachability.',
                    'No source, PE template or generated launcher was executed or installed; native release gates are unchanged.',
                    'Stable build inputs are required; this is not an atomic snapshot or an operating-system sandbox.'])
    rendered = (json.dumps(report, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
    if len(rendered) > 2 * 1024 * 1024:
        raise ValueError('Report budget exceeded')
    with (output / 'report.json').open('xb') as result:
        result.write(rendered)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--office', type=Path, required=True)
    parser.add_argument('--python-source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True, help='New directory; parent must exist')
    args = parser.parse_args()
    try:
        report = generate(args.office, args.python_source, args.output)
    except (OSError, ValueError, KeyError, BadZipFile, tarfile.TarError, pefile.PEFormatError) as error:
        parser.exit(1, f'Office template evidence failed: {error}\n')
    print(f"Matched {sum(len(p['files']) for p in report['packages'].values())} source files and "
          f"{len(report['templates'])} templates; runtime exclusion remains unverified.")


if __name__ == '__main__':
    main()
