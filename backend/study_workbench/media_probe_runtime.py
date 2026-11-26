"""Fixed optional developer FFmpeg component; no PATH lookup, downloading or user CLI options."""
import hashlib
import json
import os
import stat
import sys
from pathlib import Path

from .backup_archive import archive_path, invalid_constant, unique_object

SNAPSHOT = '2cd1cbbdc939fc6ab27818a71092e24d122519cdb7fb9dca78c9bf29037e9390'
PROFILE = 'ee0f21d31ae183a6579bbf0b3414ae84f46d7ce6c6cd5660e07906b0e8e7af9f'
VERSION = 'ffprobe-mp4-local-v1'
OUTPUT_LIMIT = 256 * 1024
ENTRIES = ('stream=index,codec_name,codec_type,width,height,sample_rate,channels,duration:'
           'format=format_name,duration,size')


def strict_json(raw, limit):
    if len(raw) > limit:
        raise ValueError('JSON byte budget')
    try:
        value = json.loads(raw.decode('utf-8'), object_pairs_hook=unique_object, parse_constant=invalid_constant)
    except (UnicodeError, RecursionError, json.JSONDecodeError) as error:
        raise ValueError('Invalid JSON') from error
    pending, count = [(value, 0)], 0
    while pending:
        item, depth = pending.pop()
        count += 1
        if depth > 12 or count > 1024:
            raise ValueError('JSON structure budget')
        if isinstance(item, dict):
            pending.extend((v, depth + 1) for v in item.values())
        elif isinstance(item, list):
            pending.extend((v, depth + 1) for v in item)
    return value


def local_path(path):
    if not path.is_absolute() or str(path).startswith(('\\\\', '//')) or ':' in str(path)[3:]:
        raise ValueError('Not a local absolute path')
    if os.name == 'nt':
        import ctypes
        if ctypes.windll.kernel32.GetDriveTypeW(ctypes.c_wchar_p(path.anchor)) == 4:
            raise ValueError('Network drive')
    for component in [*reversed(path.parents), path]:
        info = component.lstat()
        if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT:
            raise ValueError('Link/reparse path')
    return path


def component_directory():
    configured = os.environ.get('STUDY_FFMPEG_RUNTIME')
    if configured is not None:
        return Path(configured)
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).resolve().parent.parent / 'converters/ffmpeg'
    return Path(__file__).resolve().parents[2] / '.local/ffmpeg-runtime'


def verify_component(directory, checkpoint):
    if os.name != 'nt':
        raise ValueError('Only Windows x64 component verified')
    directory = local_path(directory)
    lock = directory / 'ffmpeg-component-lock.json'
    local_path(lock)
    with lock.open('rb') as stream:
        envelope = strict_json(stream.read(32769), 32768)
    if not isinstance(envelope, dict) or set(envelope) != {'payload', 'snapshot_sha256'}:
        raise ValueError('Component envelope')
    payload = envelope['payload']
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
    if envelope['snapshot_sha256'] != SNAPSHOT or hashlib.sha256(canonical).hexdigest() != SNAPSHOT:
        raise ValueError('Unpinned component snapshot')
    if payload['profile_sha256'] != PROFILE or len(payload['files']) != 17:
        raise ValueError('Unpinned component profile')
    found, pending, count = set(), [directory], 0
    while pending:
        for path in pending.pop().iterdir():
            checkpoint()
            count += 1
            if count > 64:
                raise ValueError('Component inventory budget')
            local_path(path)
            if path.is_dir():
                pending.append(path)
            elif path.is_file():
                found.add(path.relative_to(directory).as_posix())
            else:
                raise ValueError('Component special file')
    if found != set(payload['files']) | {'ffmpeg-component-lock.json'}:
        raise ValueError('Component file set changed')
    for name, expected in payload['files'].items():
        archive_path(name)
        path = local_path(directory / name)
        with path.open('rb') as stream:
            before = os.fstat(stream.fileno())
            if not stat.S_ISREG(before.st_mode) or before.st_size != expected['bytes']:
                raise ValueError('Component size changed')
            digest = hashlib.sha256()
            received = 0
            while chunk := stream.read(1024 * 1024):
                checkpoint()
                received += len(chunk)
                if received > expected['bytes']:
                    raise ValueError('Component grew')
                digest.update(chunk)
            after = os.fstat(stream.fileno())
        if (received != expected['bytes'] or digest.hexdigest() != expected['sha256'] or
                (before.st_ino, before.st_size, before.st_mtime_ns) !=
                (after.st_ino, after.st_size, after.st_mtime_ns)):
            raise ValueError('Component hash/identity changed')
    checkpoint()
    return directory


def command(directory, operation, suffix):
    if suffix not in ('.mp4', '.m4a'):
        raise ValueError('Unsupported probe input')
    return probe_command(directory, operation, 'source' + suffix, 'probe.json')


def probe_command(directory, operation, source, output):
    if source not in {'source.mp4', 'source.m4a', 'input0.mp4', 'input0.m4a', 'input1.mp4', 'input1.m4a', 'output.pending.mp4'}:
        raise ValueError('Unsupported fixed probe source')
    if output not in {'probe.json', 'probe0.json', 'probe1.json', 'output-probe.json'}:
        raise ValueError('Unsupported fixed probe output')
    return [str(directory / 'bin/ffprobe.exe'), '-hide_banner', '-v', 'error', '-max_alloc', '33554432',
            '-protocol_whitelist', 'file', '-f', 'mov', '-enable_drefs', '0', '-use_absolute_path', '0',
            '-probesize', '2097152', '-analyzeduration', '1000000', '-show_entries', ENTRIES,
            '-of', 'json', '-o', str(operation / output), str(operation / source)]


def mux_command(directory, operation, inputs, indices):
    if (len(inputs) != 2 or any(name not in {'input0.mp4', 'input0.m4a'} for name in inputs[:1]) or
            any(name not in {'input1.mp4', 'input1.m4a'} for name in inputs[1:]) or
            len(indices) != 2 or any(type(index) is not int or not 0 <= index <= 1 for index in indices)):
        raise ValueError('Unsupported fixed mux selection')
    result = [str(directory / 'bin/ffmpeg.exe'), '-hide_banner', '-loglevel', 'error', '-nostdin', '-n',
              '-max_alloc', '33554432']
    for name in inputs:
        result += ['-protocol_whitelist', 'file', '-f', 'mov', '-enable_drefs', '0', '-use_absolute_path', '0',
                   '-probesize', '2097152', '-analyzeduration', '1000000', '-i', str(operation / name)]
    return result + ['-map', f'0:{indices[0]}', '-map', f'1:{indices[1]}', '-c', 'copy',
                     '-map_metadata', '-1', '-map_chapters', '-1', '-threads', '1', '-f', 'mp4',
                     str(operation / 'output.pending.mp4')]


def environment(operation):
    return {'SystemRoot': os.environ['SystemRoot'], 'WINDIR': os.environ['SystemRoot'],
            'PATH': str(Path(os.environ['SystemRoot']) / 'System32'),
            'TEMP': str(operation / 'tmp'), 'TMP': str(operation / 'tmp')}
