"""Read-only backup envelope verification. Never extracts or activates a learning library."""
import hashlib
import json
import re
import stat
import struct
import unicodedata
import zipfile
import zlib
from bisect import bisect_left
from contextlib import contextmanager
from datetime import datetime, timedelta

MANIFEST_LIMIT = 32 * 1024 * 1024
DIRECTORY_LIMIT = 64 * 1024 * 1024
FILE_LIMIT = 8 * 1024 ** 3
TOTAL_LIMIT = 100 * 1024 ** 3
COUNT_LIMIT = 100000
SUPPORTED_SCHEMA = '0016'
HASH = re.compile(r'[a-f0-9]{64}')
RESERVED = re.compile(r'(CON|PRN|AUX|NUL|COM[1-9¹²³]|LPT[1-9¹²³]|CONIN\$|CONOUT\$)(\.|$)', re.I)


@contextmanager
def bounded_zip(path):
    # ZipFile loads the whole central directory; bound it before constructing ZipFile.
    with open(path, 'rb') as handle:
        handle.seek(0, 2)
        length = handle.tell()
        tail_size = min(length, 65535 + 22)
        handle.seek(length - tail_size)
        tail = handle.read(tail_size)
        index = tail.rfind(b'PK\x05\x06')
        if index < 0 or len(tail) - index < 22:
            raise ValueError('ZIP缺少有效结束记录')
        _, disk, start_disk, disk_count, count, size, offset, comment = struct.unpack('<4s4H2LH', tail[index:index + 22])
        end = length - tail_size + index
        if index + 22 + comment != len(tail) or disk or start_disk or disk_count != count:
            raise ValueError('ZIP分卷或结束记录无效')
        directory_end = end
        classic = count, size, offset
        locator = b''
        if end >= 20:
            handle.seek(end - 20)
            locator = handle.read(20)
        has_zip64 = locator.startswith(b'PK\x06\x07')
        if (count == 0xffff or size == 0xffffffff or offset == 0xffffffff) and not has_zip64:
            raise ValueError('ZIP64定位记录缺失')
        if has_zip64:
            signature, disk, record, disks = struct.unpack('<4sLQL', locator)
            if signature != b'PK\x06\x07' or disk or disks != 1 or record > end - 76:
                raise ValueError('ZIP64定位记录无效')
            handle.seek(record)
            raw = handle.read(56)
            if len(raw) != 56:
                raise ValueError('ZIP64结束记录不足')
            signature, record_size, _, _, disk, start_disk, disk_count, count, size, offset = struct.unpack('<4sQ2H2L4Q', raw)
            if signature != b'PK\x06\x06' or record_size < 44 or record + record_size + 12 != end - 20:
                raise ValueError('ZIP64结束记录无效')
            if disk or start_disk or disk_count != count:
                raise ValueError('ZIP64分卷不支持')
            if any(old != sentinel and old != new for old, new, sentinel in
                   zip(classic, (count, size, offset), (0xffff, 0xffffffff, 0xffffffff), strict=True)):
                raise ValueError('ZIP64与普通结束记录不符')
            directory_end = record
        if count > COUNT_LIMIT + 1 or size > DIRECTORY_LIMIT:
            raise ValueError('ZIP条目或64MiB目录预算超限')
        if offset + size != directory_end:
            raise ValueError('ZIP目录边界无效')
        position, found = offset, 0
        while position < directory_end:
            handle.seek(position)
            raw = handle.read(46)
            if len(raw) != 46 or raw[:4] != b'PK\x01\x02':
                raise ValueError('ZIP目录条目无效')
            fields = struct.unpack('<4s6H3L5H2L', raw)
            found += 1
            if found > COUNT_LIMIT + 1 or fields[13]:
                raise ValueError('ZIP实际目录条目超限或分卷不支持')
            position += 46 + sum(fields[10:13])
        if position != directory_end or found != count:
            raise ValueError('ZIP实际目录数量或边界不符')
        handle.seek(0)
        with zipfile.ZipFile(handle) as archive:
            yield archive


def archive_path(value):
    if not isinstance(value, str) or not value or len(value) > 2048:
        raise ValueError('备份相对路径无效')
    if value != unicodedata.normalize('NFC', value):
        raise ValueError('备份路径必须为NFC规范形式')
    for part in value.split('/'):
        if part in {'', '.', '..'} or part.endswith((' ', '.')) or RESERVED.match(part):
            raise ValueError('备份路径含空段、点段或Windows保留名')
        if any(c in '\\:<>"|?*' or unicodedata.category(c) in {'Cc', 'Cf', 'Cs'} for c in part):
            raise ValueError('备份路径含控制字符或Windows非法字符')
        if len(part.encode('utf-16-le')) // 2 > 255:
            raise ValueError('备份文件名超长')
    return value


def exact_fields(value, fields):
    if not isinstance(value, dict) or set(value) != set(fields):
        raise ValueError('备份清单字段不完整或包含未知字段')


def unique_object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError('备份清单JSON键重复')
        value[key] = item
    return value


def invalid_constant(value):
    raise ValueError('备份清单不允许非有限JSON数值')


def manifest_bytes(data):
    if len(data) > MANIFEST_LIMIT:
        raise ValueError('备份清单超过32MiB')
    try:
        value = json.loads(data.decode('utf-8'), object_pairs_hook=unique_object, parse_constant=invalid_constant)
    except (UnicodeError, json.JSONDecodeError, RecursionError) as error:
        raise ValueError('备份清单不是有效UTF-8 JSON') from error
    exact_fields(value, {'format', 'version', 'schema_revision', 'app_version', 'created_at', 'files', 'tables', 'excluded'})
    if value['format'] != 'studyworkbench-backup' or type(value['version']) is not int or value['version'] != 1:
        raise ValueError('不支持的备份包版本')
    schema = value['schema_revision']
    if not isinstance(schema, str) or not re.fullmatch(r'00[0-9]{2}', schema) or not '0001' <= schema <= SUPPORTED_SCHEMA:
        raise ValueError('备份schema过新或不支持，不会激活')
    if not isinstance(value['app_version'], str) or not 1 <= len(value['app_version']) <= 100:
        raise ValueError('备份应用版本无效')
    try:
        created = value['created_at']
        if not isinstance(created, str) or len(created) > 64 or 'T' not in created:
            raise ValueError('备份时间无效')
        if datetime.fromisoformat(created).utcoffset() != timedelta(0):
            raise ValueError('备份时间必须为UTC')
    except (ValueError, TypeError) as error:
        raise ValueError('备份时间必须为UTC ISO8601') from error
    files = value['files']
    if not isinstance(files, list) or not 1 <= len(files) <= COUNT_LIMIT:
        raise ValueError('备份文件数量超限或为空')
    paths, total = {}, 0
    for item in files:
        exact_fields(item, {'path', 'size', 'sha256'})
        name = archive_path(item['path'])
        key = name.casefold()
        if key in paths:
            raise ValueError('备份路径重复或Windows大小写碰撞')
        paths[key] = name
        if type(item['size']) is not int or not 0 <= item['size'] <= FILE_LIMIT:
            raise ValueError('备份单文件大小无效或超过8GiB')
        total += item['size']
        if total > TOTAL_LIMIT:
            raise ValueError('备份总大小超过100GiB')
        if not isinstance(item['sha256'], str) or not HASH.fullmatch(item['sha256']):
            raise ValueError('备份SHA256无效')
    if paths.get('study.db') != 'study.db':
        raise ValueError('备份缺少study.db')
    # A file cannot also be a parent directory; reject before any future extraction.
    keys = sorted(paths)
    for key in keys:
        index = bisect_left(keys, key + '/')
        if index < len(keys) and keys[index].startswith(key + '/'):
            raise ValueError('备份文件与目录路径冲突')
    tables = value['tables']
    if not isinstance(tables, dict) or not 1 <= len(tables) <= 10000 or 'alembic_version' not in tables:
        raise ValueError('备份表摘要无效')
    for name, item in tables.items():
        if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]{0,127}', name):
            raise ValueError('备份表名无效')
        exact_fields(item, {'rows', 'sha256'})
        if type(item['rows']) is not int or not 0 <= item['rows'] <= 2 ** 63 - 1:
            raise ValueError('备份表行数无效')
        if not isinstance(item['sha256'], str) or not HASH.fullmatch(item['sha256']):
            raise ValueError('备份表摘要SHA256无效')
    excluded = value['excluded']
    if not isinstance(excluded, list) or len(excluded) > COUNT_LIMIT:
        raise ValueError('备份排除清单无效')
    exclusions = set()
    for name in excluded:
        key = archive_path(name).casefold()
        index = bisect_left(keys, key + '/')
        if key in exclusions or key in paths or index < len(keys) and keys[index].startswith(key + '/'):
            raise ValueError('备份排除清单重复或与文件冲突')
        exclusions.add(key)
    return value


def inspect_archive(path, checkpoint=lambda _: None):
    """Check declared structure and every payload byte. SQLite/relationship semantics are a separate gate."""
    try:
        with bounded_zip(path) as archive:
            entries = archive.infolist()
            if len(entries) > COUNT_LIMIT + 1:
                raise ValueError('ZIP条目数量超限')
            names, folded = {}, set()
            for info in entries:
                checkpoint('zip-directory')
                name = archive_path(info.filename)
                if name != info.orig_filename or name.casefold() in folded:
                    raise ValueError('ZIP条目重复、截断或大小写碰撞')
                folded.add(name.casefold())
                names[name] = info
                mode = stat.S_IFMT(info.external_attr >> 16)
                if mode not in {0, stat.S_IFREG} or info.external_attr & 0x410 or info.is_dir():
                    raise ValueError('ZIP不允许符号链接、重解析点或特殊文件/目录条目')
                if info.flag_bits & 1 or info.compress_type not in {zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED}:
                    raise ValueError('ZIP不允许加密或未知压缩方法')
                position = 0
                while position < len(info.extra):
                    if position + 4 > len(info.extra):
                        raise ValueError('ZIP扩展字段损坏')
                    kind, size = struct.unpack_from('<HH', info.extra, position)
                    position += 4 + size
                    if kind != 1 or position > len(info.extra):
                        raise ValueError('ZIP仅允许ZIP64大小/偏移扩展字段')
            header = names.get('backup-manifest.json')
            if header is None or header.file_size > MANIFEST_LIMIT:
                raise ValueError('ZIP缺少备份清单或清单超限')
            with archive.open(header) as handle:
                manifest = manifest_bytes(handle.read(MANIFEST_LIMIT + 1))
            expected = {'payload/' + item['path']: item for item in manifest['files']}
            if set(names) != {'backup-manifest.json', *expected}:
                raise ValueError('ZIP包含未列出文件或缺少payload')
            total = 0
            for name, item in expected.items():
                info = names[name]
                if info.file_size != item['size']:
                    raise ValueError('ZIP头大小与清单不符')
                actual, checksum = 0, hashlib.sha256()
                with archive.open(info) as handle:
                    while chunk := handle.read(1024 * 1024):
                        checkpoint('payload-hashing')
                        actual += len(chunk)
                        total += len(chunk)
                        if actual > item['size'] or total > TOTAL_LIMIT:
                            raise ValueError('ZIP实际字节超过清单或总预算')
                        checksum.update(chunk)
                if actual != item['size'] or checksum.hexdigest() != item['sha256']:
                    raise ValueError('备份payload大小或SHA256不符')
            return manifest
    except (zipfile.BadZipFile, NotImplementedError, RuntimeError, EOFError, struct.error, zlib.error) as error:
        raise ValueError('ZIP损坏、读取中断或不支持') from error
