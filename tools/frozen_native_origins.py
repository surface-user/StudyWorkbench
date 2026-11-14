"""Compare fixed bootloader bytes and declared local CRT sources without executing them."""

import argparse
import ast
import base64
import copy
import csv
import importlib.metadata
import io
import json
import os
import re
import struct
import xml.etree.ElementTree as ET
import zipfile
import zlib
from email.parser import BytesParser
from pathlib import Path

import pefile
import yaml
from frozen_python_members import MAX_RECORD_BYTES, MAX_RECORD_ROWS, MAX_REPORT_BYTES, bounded_file
from frozen_python_origins import generate as match_origins
from frozen_python_origins import zip_members
from frozen_sbom import MAX_FILE_BYTES, inventory, safe_name
from packaging.utils import canonicalize_name
from source_sbom import LOCKS, no_links, read_lock, sha256

VERSION = '6.22.3'
WHEEL_BYTES = 1454907
WHEEL_SHA256 = '500bd58c7bf7e584a8435adccbd763a0b918d5c12b08d74ff50fd79b2915458b'
WHEEL_URL = ('https://files.pythonhosted.org/packages/24/83/'
             'c5422204772a27aef643280fdc887b7ef55679989096b21dceb1b9625fc4/'
             'pyinstaller-6.22.3-py3-none-win_amd64.whl')
BOOT = 'PyInstaller/bootloader/Windows-64bit-intel/run.exe'
BUILD_SOURCES = (BOOT, 'PyInstaller/utils/win32/winutils.py', 'PyInstaller/building/api.py')
MAX_TOC_BYTES = 1024 * 1024
MAX_TOC_NODES = 100000
MAX_NEW_FILES = 128
MAX_NEW_BYTES = 128 * 1024 * 1024
LIMITATIONS = [
    'COLLECT is an untrusted caller build record, not a signed build attestation or official archive.',
    'Local CRT byte correspondence does not establish component identity, version, publisher archive, license or redistribution permission.',
    'The fixed PyInstaller wheel pin and matching executable sections do not authenticate the entire generated executable.',
    'Headers, generated resources, overlay and all reported differences remain separate; no executable reconstruction or reproducible build is claimed.',
    'The product SBOM, native identities, dependency edges, licenses, vulnerabilities and signatures remain incomplete.',
    'Before/after checks observe stability but do not provide an atomic filesystem snapshot.',
]


def collect_entries(raw):
    if len(raw) > MAX_TOC_BYTES:
        raise ValueError('COLLECT input byte budget exceeded')
    tree = ast.parse(raw.decode('utf-8'), mode='eval')
    pending, count = [(tree, 0)], 0
    while pending:
        node, depth = pending.pop()
        count += 1
        if count > MAX_TOC_NODES or depth > 8 or not isinstance(
                node, (ast.Expression, ast.Tuple, ast.List, ast.Constant, ast.Load)):
            raise ValueError('COLLECT syntax or node/depth budget rejected')
        if isinstance(node, ast.Constant) and not isinstance(node.value, str):
            raise ValueError('COLLECT constants must be strings')
        pending.extend((child, depth + 1) for child in ast.iter_child_nodes(node))
    value = ast.literal_eval(tree)
    if not isinstance(value, tuple) or len(value) != 1 or not isinstance(value[0], list) or len(value[0]) > 20000:
        raise ValueError('Unsupported COLLECT structure or entry budget')
    result = {}
    for index, item in enumerate(value[0]):
        if not isinstance(item, tuple) or len(item) != 3 or not all(isinstance(x, str) for x in item):
            raise ValueError('Malformed COLLECT entry')
        target, source, kind = item
        target = safe_name(target.replace('\\', '/'))
        if (kind not in ('EXECUTABLE', 'BINARY', 'EXTENSION', 'DATA') or not Path(source).is_absolute()
                or '..' in Path(source).parts):
            raise ValueError('Unsupported COLLECT kind or nonabsolute source')
        name = target if kind == 'EXECUTABLE' else '_internal/' + target
        if name.casefold() in result:
            raise ValueError('Duplicate COLLECT target')
        result[name.casefold()] = {'path': name, 'source': source, 'kind': kind, 'index': index}
    return result


def record_rows(raw, allow_script_paths=False):
    rows = list(csv.reader(io.StringIO(raw.decode('utf-8'))))
    if len(rows) > MAX_RECORD_ROWS or any(len(row) != 3 for row in rows):
        raise ValueError('RECORD row budget or structure rejected')
    result = {}
    for name, digest, size in rows:
        if name.casefold() in result:
            raise ValueError('Duplicate RECORD path')
        result[name.casefold()] = (digest, size)
        try:
            safe_name(name)
        except ValueError:
            if not allow_script_paths or not name.startswith('../../Scripts/'):
                raise
    return result


def check_record(rows, name, raw):
    digest, size = rows[name.casefold()]
    encoded = base64.urlsafe_b64encode(bytes.fromhex(sha256(raw))).decode().rstrip('=')
    if digest != 'sha256=' + encoded or not size.isdecimal() or int(size) != len(raw):
        raise ValueError('Source bytes differ from exact RECORD hash/size')


def pe_sections(raw):
    pe = pefile.PE(data=raw, fast_load=True)
    try:
        if pe.FILE_HEADER.Machine != 0x8664 or pe.OPTIONAL_HEADER.Magic != 0x20b:
            raise ValueError('Expected AMD64 PE32+ bootloader')
        if not 1 <= len(pe.sections) <= 16:
            raise ValueError('PE section count rejected')
        sections, spans = {}, []
        for section in pe.sections:
            name = section.Name.rstrip(b'\0').decode('ascii')
            start, size = section.PointerToRawData, section.SizeOfRawData
            if (not re.fullmatch(r'[.A-Za-z0-9_$]{1,8}', name) or name in sections
                    or start < pe.OPTIONAL_HEADER.SizeOfHeaders or start + size > len(raw)):
                raise ValueError('Invalid or duplicate PE section range')
            if size:
                spans.append((start, start + size))
            sections[name] = {'raw_offset': start, 'raw_bytes': size, 'virtual_address': section.VirtualAddress,
                              'virtual_bytes': section.Misc_VirtualSize, 'characteristics': section.Characteristics,
                              'sha256': sha256(raw[start:start + size])}
        spans.sort()
        if any(a[1] > b[0] for a, b in zip(spans, spans[1:])):
            raise ValueError('Overlapping PE sections')
        if not spans or not 0 < pe.OPTIONAL_HEADER.SizeOfHeaders <= spans[0][0]:
            raise ValueError('Invalid PE header range')
        pe.parse_data_directories(directories=[pefile.DIRECTORY_ENTRY['IMAGE_DIRECTORY_ENTRY_DEBUG']])
        debug = []
        for entry in getattr(pe, 'DIRECTORY_ENTRY_DEBUG', []):
            if len(debug) >= 16:
                raise ValueError('PE debug entry budget exceeded')
            offset = entry.struct.get_file_offset()
            if offset < 0 or offset + 28 > len(raw):
                raise ValueError('Invalid PE debug range')
            debug.append({'offset': offset, 'timestamp_offset': offset + 4,
                          'timestamp': entry.struct.TimeDateStamp, 'raw': raw[offset:offset + 28]})
        headers = pe.OPTIONAL_HEADER.SizeOfHeaders
        overlay = spans[-1][1]
        return {'sections': sections, 'debug': debug, 'coff_timestamp': pe.FILE_HEADER.TimeDateStamp,
                'entry_point': pe.OPTIONAL_HEADER.AddressOfEntryPoint, 'image_base': pe.OPTIONAL_HEADER.ImageBase,
                'headers': {'bytes': headers, 'sha256': sha256(raw[:headers])},
                'overlay': {'offset': overlay, 'bytes': len(raw) - overlay, 'sha256': sha256(raw[overlay:])}}
    finally:
        pe.close()


def compare_bootloader(original, target):
    left, right = pe_sections(original), pe_sections(target)
    executable = {n for n, s in left['sections'].items() if s['characteristics'] & 0x20000000}
    if (not executable or executable != {n for n, s in right['sections'].items() if s['characteristics'] & 0x20000000}
            or (left['entry_point'], left['image_base']) != (right['entry_point'], right['image_base'])):
        raise ValueError('Executable bootloader layout differs')
    sections = {}
    for name in sorted(left['sections'].keys() | right['sections'].keys()):
        a, b = left['sections'].get(name), right['sections'].get(name)
        equal = a is not None and b is not None and a['sha256'] == b['sha256'] and a['raw_bytes'] == b['raw_bytes']
        sections[name] = {'source': a, 'target': b, 'bytes_identical': equal}
        if name in executable and (not equal or any(a[k] != b[k] for k in (
                'virtual_address', 'virtual_bytes', 'characteristics', 'raw_bytes'))):
            raise ValueError('Executable bootloader section differs')
    differences = []
    a, b = left['sections'].get('.rdata'), right['sections'].get('.rdata')
    timestamp_only = False
    if a and b and a['raw_bytes'] == b['raw_bytes'] and len(left['debug']) == len(right['debug']):
        before = original[a['raw_offset']:a['raw_offset'] + a['raw_bytes']]
        after = target[b['raw_offset']:b['raw_offset'] + b['raw_bytes']]
        normalized = bytearray(before)
        for x, y in zip(left['debug'], right['debug']):
            i, j = x['timestamp_offset'] - a['raw_offset'], y['timestamp_offset'] - b['raw_offset']
            if (i != j or not 4 <= i <= len(before) - 24 or x['raw'][:4] + x['raw'][8:] != y['raw'][:4] + y['raw'][8:]
                    or not x['timestamp'] or x['timestamp'] != left['coff_timestamp']
                    or y['timestamp'] != right['coff_timestamp']):
                break
            normalized[i:i + 4] = after[j:j + 4]
            if x['timestamp'] != y['timestamp']:
                differences.append({'source_offset': x['timestamp_offset'], 'target_offset': y['timestamp_offset'],
                                    'field': 'IMAGE_DEBUG_DIRECTORY.TimeDateStamp', 'source_value': x['timestamp'],
                                    'target_value': y['timestamp'], 'source_hex': before[i:i + 4].hex(),
                                    'target_hex': after[j:j + 4].hex(),
                                    'changed_byte_offsets': [a['raw_offset'] + k for k in range(i, i + 4) if before[k] != after[k]]})
        else:
            timestamp_only = bool(differences) and bytes(normalized) == after
    for data in (left, right):
        data.pop('debug')
    return {'whole_bootloader_verified': False, 'reproducible_build_verified': False,
            'source_sha256': sha256(original), 'target_sha256': sha256(target),
            'source_pe': left, 'target_pe': right, 'sections': sections, 'executable_sections_identical': sorted(executable),
            'rdata_equal_except_confirmed_debug_timestamps': timestamp_only, 'debug_timestamp_fields': differences,
            'headers_authenticated': False, 'generated_resources_authenticated': False, 'overlay_authenticated': False}


def generate(payload, source, coverage_file, python_package, source_tree, collect_toc, wheel_file, crt_root, output):
    payload, source, coverage_file, python_package, source_tree, collect_toc, wheel_file, crt_root, output = [
        Path(os.path.abspath(p)) for p in (payload, source, coverage_file, python_package, source_tree, collect_toc, wheel_file, crt_root, output)]
    no_links(output.parent)
    no_links(crt_root)
    if (not crt_root.is_dir() or output.is_relative_to(payload) or payload.is_relative_to(output)
            or crt_root.is_relative_to(payload) or payload.is_relative_to(crt_root)):
        raise ValueError('Separate source root and new output required')
    files, locks = inventory(payload), {n: read_lock(source / n) for n in LOCKS}
    inputs, total = {}, 0

    def read_input(path, limit):
        nonlocal total
        no_links(path)
        if path not in inputs and (len(inputs) >= MAX_NEW_FILES or total + path.stat().st_size > MAX_NEW_BYTES):
            raise ValueError('Native source input file/byte budget exceeded')
        raw = bounded_file(path, limit)
        if path not in inputs:
            total += len(raw)
        if (len(inputs) + (path not in inputs) > MAX_NEW_FILES or total > MAX_NEW_BYTES
                or (path in inputs and sha256(raw) != inputs[path]['sha256'])):
            raise ValueError('Native source input changed or file/byte budget exceeded')
        inputs[path] = {'sha256': sha256(raw), 'limit': min(limit, inputs.get(path, {}).get('limit', limit))}
        return raw

    coverage_raw = read_input(coverage_file, MAX_REPORT_BYTES)
    tree_raw = read_input(source_tree, MAX_REPORT_BYTES)
    python_raw = read_input(python_package, 64 * 1024 * 1024)
    toc_raw = read_input(collect_toc, MAX_TOC_BYTES)
    entries = collect_entries(toc_raw)
    if {x['path'] for x in entries.values()} != set(files):
        raise ValueError('COLLECT target set differs from payload')
    wheel_raw = read_input(wheel_file, 8 * 1024 * 1024)
    if len(wheel_raw) != WHEEL_BYTES or sha256(wheel_raw) != WHEEL_SHA256:
        raise ValueError('Wrong fixed PyInstaller wheel')
    found = [d for d in importlib.metadata.distributions() if canonicalize_name(d.metadata.get('Name', '')) == 'pyinstaller'
             and d.version == VERSION]
    if len(found) != 1:
        raise ValueError('Expected unique exact PyInstaller build distribution')
    site = Path(found[0].locate_file('')).absolute()
    metadata_name, record_name = [f'pyinstaller-{VERSION}.dist-info/' + n for n in ('METADATA', 'RECORD')]
    metadata_raw = read_input(site / metadata_name, MAX_RECORD_BYTES)
    record_raw = read_input(site / record_name, MAX_RECORD_BYTES)
    installed_rows = record_rows(record_raw, allow_script_paths=True)
    check_record(installed_rows, metadata_name, metadata_raw)
    meta = BytesParser().parsebytes(metadata_raw)
    names = meta.get_all('Name', [])
    if len(names) != 1 or canonicalize_name(names[0]) != 'pyinstaller' or meta.get_all('Version') != [VERSION]:
        raise ValueError('Unexpected PyInstaller METADATA identity')
    wheel_reads, sources = {}, {}
    with zipfile.ZipFile(io.BytesIO(wheel_raw)) as archive:
        members = zip_members(archive)
        if len(members) > 10000 or sum(x.file_size for x in members.values()) > 32 * 1024 * 1024:
            raise ValueError('Wheel declared member/byte budget exceeded')
        expanded = 0

        def wheel_source(name, limit):
            nonlocal expanded
            item = members[name.casefold()]
            with archive.open(item) as stream:
                raw = stream.read(limit + 1)
            expanded += len(raw)
            if len(raw) != item.file_size or len(raw) > limit or expanded > 32 * 1024 * 1024:
                raise ValueError('Wheel actual decompression budget exceeded')
            wheel_reads[name] = {'bytes': len(raw), 'sha256': sha256(raw)}
            return raw

        wheel_meta = wheel_source(metadata_name, MAX_RECORD_BYTES)
        wheel_record = wheel_source(record_name, MAX_RECORD_BYTES)
        wheel_rows = record_rows(wheel_record)
        if wheel_meta != metadata_raw:
            raise ValueError('Installed metadata differs from pinned wheel')
        check_record(wheel_rows, metadata_name, wheel_meta)
        for name in BUILD_SOURCES:
            raw = read_input(site / name, 8 * 1024 * 1024)
            check_record(installed_rows, name, raw)
            wheel_bytes = wheel_source(name, 8 * 1024 * 1024)
            check_record(wheel_rows, name, wheel_bytes)
            if raw != wheel_bytes:
                raise ValueError('Build bootloader/source differs from fixed wheel')
            sources[name] = {'source_path': name, 'source_sha256': sha256(raw), 'source_bytes': len(raw),
                             'metadata_sha256': sha256(metadata_raw), 'installed_record_sha256': sha256(record_raw),
                             'wheel_record_sha256': sha256(wheel_record), 'wheel_sha256': WHEEL_SHA256}
        original = read_input(site / BOOT, MAX_FILE_BYTES)
    target = read_input(payload / 'study_backend.exe', MAX_FILE_BYTES)
    bootloader = compare_bootloader(original, target)
    local = {}
    for item in entries.values():
        name = item['path']
        if (item['kind'] != 'BINARY' or not name.endswith('.dll')
                or not (name.startswith('_internal/api-ms-win-') or name == '_internal/ucrtbase.dll')):
            continue
        path = Path(item['source']).absolute()
        if not path.is_relative_to(crt_root):
            raise ValueError('Selected CRT source escapes caller source root')
        raw = read_input(path, 16 * 1024 * 1024)
        if sha256(raw) != files[name]['sha256'] or len(raw) != files[name]['bytes']:
            raise ValueError('Selected CRT source differs from payload')
        local[name] = {'collect_entry_index': item['index'], 'collect_source_path': str(path),
                       'source_relative_path': path.relative_to(crt_root).as_posix(), 'source_sha256': sha256(raw),
                       'source_bytes': len(raw), 'payload_sha256': files[name]['sha256'],
                       'component_identity': None, 'component_version': None, 'official_archive': None,
                       'upstream_provenance_verified': False, 'license_verified': False, 'redistribution_permission_verified': False}
    output.mkdir(exist_ok=False)
    base = match_origins(payload, source, coverage_file, python_package, source_tree, output / 'python-origins')
    base_raw = read_input(output / 'python-origins/origins.json', MAX_REPORT_BYTES)
    bom_raw = read_input(output / 'python-origins/python-origins.cdx.json', MAX_REPORT_BYTES)
    member_raw = read_input(output / 'python-origins/local-members/members.json', MAX_REPORT_BYTES)
    member = json.loads(member_raw)
    build = member['build_packages']['pkg:pypi/pyinstaller@' + VERSION]
    if build['metadata_sha256'] != sha256(metadata_raw) or build['record_sha256'] != sha256(record_raw):
        raise ValueError('PyInstaller build source changed between phases')
    if not set(local).issubset(base['remaining_unmapped_physical']):
        raise ValueError('Local CRT trace overlaps earlier identity evidence')
    for path, proof in inputs.items():
        if sha256(bounded_file(path, proof['limit'])) != proof['sha256']:
            raise ValueError('Native source input changed at completion')
    if (files != inventory(payload) or locks != {n: read_lock(source / n) for n in LOCKS}
            or coverage_raw != bounded_file(coverage_file, MAX_REPORT_BYTES)
            or tree_raw != bounded_file(source_tree, MAX_REPORT_BYTES)
            or python_raw != bounded_file(python_package, 64 * 1024 * 1024)):
        raise ValueError('Payload, coverage, declared tree, Python archive or locks changed')
    bom = copy.deepcopy(json.loads(bom_raw))
    component = next(x for x in bom['components'] if x['bom-ref'] == 'pkg:pypi/pyinstaller@' + VERSION)
    component['hashes'] = [{'alg': 'SHA-256', 'content': WHEEL_SHA256}]
    component['externalReferences'] = [{'type': 'distribution', 'url': WHEEL_URL}]
    component['properties'].extend([
        {'name': 'studyworkbench:pyinstaller-wheel-pin-matched', 'value': 'true'},
        {'name': 'studyworkbench:whole-generated-bootloader-verified', 'value': 'false'}])
    occurrences = component['evidence']['occurrences']
    old = {x['location'] for x in occurrences}
    component['evidence']['occurrences'] = [{'location': x} for x in sorted(
        old | {'study_backend.exe#PE/' + n for n, s in bootloader['sections'].items() if s['bytes_identical']})]
    bom['metadata']['properties'].append({'name': 'studyworkbench:native-scope', 'value': 'fixed-wheel-sections-and-unidentified-local-CRT'})
    enhanced = (json.dumps(bom, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
    report = {'schema_version': 1, 'scope': 'bounded-bootloader-and-local-CRT-source-trace',
              'product_sbom_complete': False, 'upstream_provenance_verified': False, 'source_tree_authenticated': False,
              'collector_sha256': sha256(Path(__file__).read_bytes()), 'base_origins_sha256': sha256(base_raw),
              'base_bom_sha256': sha256(bom_raw), 'payload_fingerprint': base['payload_fingerprint'],
              'exe_sha256': base['exe_sha256'], 'coverage_sha256': sha256(coverage_raw),
              'collect_toc_sha256': sha256(toc_raw), 'collect_entries': len(entries), 'collect_authenticated': False,
              'caller_crt_source_root': str(crt_root), 'local_crt_sources': local,
              'pyinstaller_wheel_sha256': WHEEL_SHA256, 'pyinstaller_wheel_bytes': len(wheel_raw),
              'pyinstaller_wheel_members_read': wheel_reads, 'pyinstaller_build_sources': sources, 'bootloader': bootloader,
              'remaining_unmapped_physical': base['remaining_unmapped_physical'],
              'remaining_unmapped_code_modules': base['remaining_unmapped_code_modules'],
              'remaining_unmapped_base_library': base['remaining_unmapped_base_library'],
              'native_source_files_rechecked': len(inputs), 'native_source_logical_bytes': total,
              'bom_sha256': sha256(enhanced), 'limitations': LIMITATIONS}
    (output / 'native-origins.cdx.json').write_bytes(enhanced)
    (output / 'native-origins.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('payload', 'coverage', 'python-package', 'source-tree', 'collect-toc', 'pyinstaller-wheel', 'crt-source-root', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--source', type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    try:
        report = generate(args.payload, args.source, args.coverage, args.python_package, args.source_tree,
                          args.collect_toc, args.pyinstaller_wheel, args.crt_source_root, args.output)
    except (OSError, ValueError, TypeError, KeyError, EOFError, SyntaxError, struct.error, zipfile.BadZipFile,
            pefile.PEFormatError, zlib.error, yaml.YAMLError, ET.ParseError) as exc:
        parser.exit(1, f'Frozen native origins failed: {exc}\n')
    print(f"Traced {len(report['local_crt_sources'])} unidentified local CRT files; complete product and native provenance remain false.")
    return 2


if __name__ == '__main__':
    raise SystemExit(main())
