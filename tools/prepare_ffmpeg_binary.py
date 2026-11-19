"""Prepare/verify one audited FFmpeg developer component offline; never execute or install it."""
import argparse
import hashlib
import json
import os
import re
import stat
import tarfile
from pathlib import Path

import pefile
from prepare_ffmpeg_component import (
    PACKAGE_SHA256,
    PACKAGE_SIZE,
    SOURCE_COMMIT,
    VERSION,
    canonical,
    envelope,
    no_links,
    read_snapshot,
    source_payload,
    source_records,
    stage_files,
)

ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / 'packaging/windows/ffmpeg-component-profile.json'
RECIPE = ROOT / 'packaging/windows/ffmpeg-BUILDING.txt'
LOCK = 'ffmpeg-component-lock.json'
SOURCE_SNAPSHOT = '7a65ea9dcb64a778fe393c2582628c4ab339092971e0916422c63dd44833d81c'
PROFILE_ID = 'swb-remux-probe-msvc-v1'
RUNTIME = {
    'ffmpeg.exe': 'ffmpeg.exe',
    'ffprobe.exe': 'ffprobe.exe',
    'avcodec-63.dll': 'libavcodec/avcodec-63.dll',
    'avformat-63.dll': 'libavformat/avformat-63.dll',
    'avfilter-12.dll': 'libavfilter/avfilter-12.dll',
    'avutil-61.dll': 'libavutil/avutil-61.dll',
}
CONFIG = {'config.h', 'config_components.h', 'ffbuild/config.mak'}
LEGAL = {'LICENSE.md', 'COPYING.LGPLv2.1'}
DERIVED = {
    'configure': {'bytes': 311324, 'sha256': 'a512e0f6872453482bcf95ea2a4cc5d7a2ba246c74925f9fc47d35eae2527bed'},
    'compat/windows/mswindres': {'bytes': 644, 'sha256': '6e0241d34ca37c549a8a7f59cb36c07bdef941cf5f0036e3b40b9ca6b8f230ad'},
}
PATCHES = {
    'ffmpeg-9.0.2-msvc-banner.patch': '7550115a9c3f80f8960e7654cc08b64a7137953b96bd3c35f3f7b95f99c13aea',
    'ffmpeg-9.0.2-mswindres-utf8.patch': 'b2cc2e4a9fc26e94cd4014b703e2f0a5a4701c981c41d520192c754719ed7dfc',
}
SYSTEM_DLLS = {'kernel32.dll', 'shell32.dll', 'psapi.dll', 'bcrypt.dll'}
CAPABILITIES = {
    'protocols': ['file'],
    'demuxers': ['matroska', 'mov'],
    'muxers': ['ipod', 'mov', 'mp4', 'webm'],
    'parsers': ['aac', 'ac3', 'av1', 'h264', 'opus', 'vp8', 'vp9'],
    'bsfs': ['aac_adtstoasc', 'vp9_superframe'],
    'encoders': [], 'decoders': [], 'hwaccels': [],
}
READINESS = {
    'developer_prepared': True, 'release_ready': False,
    'product_integration': False, 'complete_untrusted_input_policy': False,
}
MAX_ASSETS = 24 * 1024 * 1024


def record(raw):
    return {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def valid_record(value, cap):
    return (isinstance(value, dict) and set(value) == {'bytes', 'sha256'}
            and type(value['bytes']) is int and 0 < value['bytes'] <= cap
            and isinstance(value['sha256'], str)
            and re.fullmatch('[0-9a-f]{64}', value['sha256']))


def profile():
    value = read_snapshot(PROFILE)
    fields = {'schema_version', 'kind', 'build_profile', 'upstream_version',
              'source_snapshot_sha256', 'source_commit', 'runtime', 'source_legal',
              'source_config', 'compiler_license', 'recipe', 'producer', 'capabilities', 'readiness'}
    if (set(value) != fields or type(value['schema_version']) is not int or value['schema_version'] != 1
            or value['kind'] != 'ffmpeg-developer-component-profile'
            or value['build_profile'] != PROFILE_ID or value['upstream_version'] != VERSION
            or value['source_snapshot_sha256'] != SOURCE_SNAPSHOT or value['source_commit'] != SOURCE_COMMIT
            or value['capabilities'] != CAPABILITIES or value['readiness'] != READINESS):
        raise ValueError('Unsupported component profile or scope')
    if any(type(value['readiness'][key]) is not bool for key in READINESS):
        raise ValueError('Readiness fields must be booleans')
    producer = value['producer']
    producer_fields = {'msvc', 'windows_sdk', 'msys_make', 'crt_linkage', 'crt_libraries'}
    if (not isinstance(producer, dict) or set(producer) != producer_fields
            or any(not isinstance(producer[k], str) or len(producer[k]) > 256 for k in producer_fields - {'crt_libraries'})
            or not isinstance(producer['crt_libraries'], list) or len(producer['crt_libraries']) != 4):
        raise ValueError('Producer provenance differs')
    library_names = set()
    for item in producer['crt_libraries']:
        if (not isinstance(item, dict) or set(item) != {'name', 'bytes', 'sha256'}
                or not valid_record({k: item[k] for k in ['bytes', 'sha256']}, 64 * 1024 * 1024)):
            raise ValueError('CRT provenance differs')
        library_names.add(item['name'])
    if library_names != {'LIBCMT.lib', 'OLDNAMES.lib', 'libvcruntime.lib', 'libucrt.lib'}:
        raise ValueError('CRT library set differs')
    for field, names, cap in [('runtime', set(RUNTIME), 4 * 1024 * 1024),
                               ('source_legal', LEGAL, 128 * 1024),
                               ('source_config', CONFIG, 1024 * 1024)]:
        items = value[field]
        if not isinstance(items, dict) or set(items) != names or not all(valid_record(v, cap) for v in items.values()):
            raise ValueError('Component file profile differs')
    license_record = value['compiler_license']
    if (not isinstance(license_record, dict)
            or set(license_record) != {'name', 'source_url', 'bytes', 'sha256'}
            or license_record['name'] != 'Visual-Studio-2022-Community-License-EN.docx'
            or license_record['source_url'] != 'https://visualstudio.microsoft.com/wp-content/uploads/2021/11/Visual-Studio-2022-Community-License-EN.docx'
            or not valid_record({k: license_record[k] for k in ['bytes', 'sha256']}, 256 * 1024)
            or not valid_record(value['recipe'], 64 * 1024)):
        raise ValueError('Compiler legal input or build recipe differs')
    return value


def checked_file(path, expected):
    no_links(path)
    with path.open('rb') as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_size != expected['bytes']:
            raise ValueError('Component input size or kind differs')
        raw = stream.read(expected['bytes'] + 1)
    if record(raw) != expected:
        raise ValueError('Component input hash differs')
    return raw


def pe_closure(paths, expected):
    if set(paths) != set(RUNTIME) or set(expected) != set(RUNTIME):
        raise ValueError('Runtime entry set differs')
    images = {}
    try:
        for name, path in paths.items():
            image = pefile.PE(data=checked_file(path, expected[name]))
            images[name.lower()] = image
            if image.FILE_HEADER.Machine != 0x8664 or image.OPTIONAL_HEADER.Magic != 0x20B:
                raise ValueError('Component must be Windows AMD64 PE32+')
        for image in images.values():
            for entry in [*getattr(image, 'DIRECTORY_ENTRY_IMPORT', []), *getattr(image, 'DIRECTORY_ENTRY_DELAY_IMPORT', [])]:
                dependency = entry.dll.decode('ascii').lower()
                if dependency in SYSTEM_DLLS:
                    continue
                if dependency not in images:
                    raise ValueError('Unexpected component runtime dependency')
                exports = getattr(images[dependency], 'DIRECTORY_ENTRY_EXPORT', None)
                symbols = {}
                for symbol in exports.symbols if exports else []:
                    if symbol.forwarder:
                        raise ValueError('Forwarded component export requires separate validation')
                    symbols[symbol.name if symbol.name else symbol.ordinal] = True
                if any((symbol.name if symbol.name else symbol.ordinal) not in symbols for symbol in entry.imports):
                    raise ValueError('Unresolved component import symbol')
    finally:
        for image in images.values():
            image.close()


def configuration(raw_headers):
    values = {}
    for raw in raw_headers:
        for name, value in re.findall(rb'^#define CONFIG_([A-Z0-9_]+) ([01])$', raw, re.M):
            if name in values and values[name] != int(value):
                raise ValueError('Conflicting component configuration macro')
            values[name] = int(value)
    for name in ['NETWORK', 'GPL', 'NONFREE', 'VERSION3', 'AUTODETECT', 'STATIC',
                 'SWSCALE', 'SWRESAMPLE', 'AVDEVICE', 'ZLIB', 'BZLIB', 'LZMA']:
        if values.get(name.encode()) != 0:
            raise ValueError('Component feature policy differs')
    for name in ['SHARED', 'FFMPEG', 'FFPROBE', 'AVCODEC', 'AVFORMAT', 'AVFILTER', 'AVUTIL']:
        if values.get(name.encode()) != 1:
            raise ValueError('Required component library/program missing')
    groups = {'PROTOCOL': 'protocols', 'DEMUXER': 'demuxers', 'MUXER': 'muxers',
              'PARSER': 'parsers', 'BSF': 'bsfs', 'ENCODER': 'encoders',
              'DECODER': 'decoders', 'HWACCEL': 'hwaccels'}
    for suffix, field in groups.items():
        tail = ('_' + suffix).encode()
        actual = sorted(name[:-len(tail)].decode('ascii').lower() for name, enabled in values.items()
                        if name.endswith(tail) and enabled)
        if actual != CAPABILITIES[field]:
            raise ValueError('Compiled component set differs')
    filters = sorted(name[:-7].decode('ascii').lower() for name, enabled in values.items()
                     if name.endswith(b'_FILTER') and enabled)
    if filters != ['aformat', 'anull', 'atrim', 'crop', 'format', 'hflip',
                   'null', 'rotate', 'transpose', 'trim', 'vflip']:
        raise ValueError('Unexpected compiled filter')


def verify_build(package, build, value):
    original = source_payload(source_records(package))
    if len(original['files']) != 10399 or envelope(original)['snapshot_sha256'] != SOURCE_SNAPSHOT:
        raise ValueError('Authenticated original source snapshot differs')
    no_links(build)
    files = stage_files(build)
    for name, source_record in original['files'].items():
        expected = DERIVED.get(name, {'bytes': source_record['size'], 'sha256': source_record['sha256']})
        if name not in files:
            raise ValueError('Original source path missing')
        checked_file(files[name], expected)
    for name in LEGAL:
        if value['source_legal'][name] != {'bytes': original['files'][name]['size'], 'sha256': original['files'][name]['sha256']}:
            raise ValueError('Original legal record differs')
    headers = [checked_file(build / name, value['source_config'][name])
               for name in ['config.h', 'config_components.h']]
    checked_file(build / 'ffbuild/config.mak', value['source_config']['ffbuild/config.mak'])
    configuration(headers)
    pe_closure({name: build / relative for name, relative in RUNTIME.items()}, value['runtime'])


def assets(value):
    result = {f'bin/{name}': data for name, data in value['runtime'].items()}
    result[f'corresponding-source/ffmpeg-{VERSION}.tar.xz'] = {'bytes': PACKAGE_SIZE, 'sha256': PACKAGE_SHA256}
    for name, digest in PATCHES.items():
        path = ROOT / 'tools/patches' / name
        no_links(path)
        with path.open('rb') as stream:
            raw = stream.read(65537)
        if len(raw) > 65536 or hashlib.sha256(raw).hexdigest() != digest:
            raise ValueError('Fixed source patch changed')
        result[f'corresponding-source/patches/{name}'] = record(raw)
    for name, data in value['source_config'].items():
        result['corresponding-source/config/' + name] = data
    for name, data in value['source_legal'].items():
        result['licenses/ffmpeg/' + name] = data
    result['licenses/compiler/' + value['compiler_license']['name']] = {
        key: value['compiler_license'][key] for key in ['bytes', 'sha256']}
    checked_file(RECIPE, value['recipe'])
    result['corresponding-source/BUILDING.txt'] = value['recipe']
    result['corresponding-source/build-profile.json'] = record(canonical(envelope(value)) + b'\n')
    if sum(item['bytes'] for item in result.values()) > MAX_ASSETS:
        raise ValueError('Component output exceeds shared byte budget')
    return dict(sorted(result.items()))


def payload(value):
    return {'schema_version': 1, 'kind': 'ffmpeg-prepared-developer-component',
            'build_profile': PROFILE_ID, 'upstream_version': VERSION,
            'profile_sha256': envelope(value)['snapshot_sha256'],
            'readiness': READINESS, 'files': assets(value)}


def verify(directory, value=None):
    directory = directory.absolute()
    value = value if value is not None else profile()
    expected = payload(value)
    no_links(directory)
    if (directory / 'build-inventory.json').exists():
        raise ValueError('Unexpected reserved inventory')
    actual = read_snapshot(directory / LOCK)
    if canonical(actual) != canonical(expected):
        raise ValueError('Component snapshot differs from fixed profile')
    files = stage_files(directory)
    files.pop(LOCK, None)
    if files.keys() != expected['files'].keys():
        raise ValueError('Component file set differs')
    for name, path in files.items():
        checked_file(path, expected['files'][name])
    pe_closure({name: directory / 'bin' / name for name in RUNTIME}, value['runtime'])
    return envelope(expected)


def prepare(package, build, compiler_license, directory):
    package, build, compiler_license, directory = [path.absolute() for path in [package, build, compiler_license, directory]]
    value = profile()
    no_links(directory.parent)
    if directory.exists() or directory.is_symlink():
        raise ValueError('Destination exists; no replacement permitted')
    verify_build(package, build, value)
    expected = payload(value)
    inputs = {f'bin/{name}': build / relative for name, relative in RUNTIME.items()}
    inputs[f'corresponding-source/ffmpeg-{VERSION}.tar.xz'] = package
    inputs.update({f'corresponding-source/patches/{name}': ROOT / 'tools/patches' / name for name in PATCHES})
    inputs.update({'corresponding-source/config/' + name: build / name for name in CONFIG})
    inputs.update({'licenses/ffmpeg/' + name: build / name for name in LEGAL})
    inputs['licenses/compiler/' + value['compiler_license']['name']] = compiler_license
    inputs['corresponding-source/BUILDING.txt'] = RECIPE
    contents = {name: checked_file(path, expected['files'][name]) for name, path in inputs.items()}
    contents['corresponding-source/build-profile.json'] = canonical(envelope(value)) + b'\n'
    directory.mkdir()
    for name, raw in contents.items():
        target = directory / name
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open('xb') as output:
            output.write(raw)
    with (directory / LOCK).open('x', encoding='utf-8', newline='\n') as output:
        output.write(json.dumps(envelope(expected), ensure_ascii=False, indent=2) + '\n')
    return verify(directory, value)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['prepare', 'verify'])
    parser.add_argument('--directory', type=Path, required=True)
    parser.add_argument('--package', type=Path)
    parser.add_argument('--build-directory', type=Path)
    parser.add_argument('--compiler-license', type=Path)
    args = parser.parse_args()
    if args.mode == 'prepare' and any(item is None for item in [args.package, args.build_directory, args.compiler_license]):
        parser.error('prepare requires --package, --build-directory and --compiler-license')
    try:
        result = (prepare(args.package, args.build_directory, args.compiler_license, args.directory)
                  if args.mode == 'prepare' else verify(args.directory))
    except (OSError, ValueError, tarfile.TarError, pefile.PEFormatError) as error:
        parser.exit(1, f'Component rejected; all original/partial files retained: {error}\n')
    print(json.dumps({'build_profile': PROFILE_ID, 'files': len(result['payload']['files']),
                      'component_snapshot_sha256': result['snapshot_sha256'],
                      'developer_prepared': True, 'release_ready': False,
                      'product_integration': False, 'execution_performed': False}))


if __name__ == '__main__':
    main()
