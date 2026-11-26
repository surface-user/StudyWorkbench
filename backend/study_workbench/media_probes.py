"""Synchronous, cancellable local probe. No durable queue, SQL, network or arbitrary CLI."""
import ctypes
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
from decimal import Decimal
from pathlib import Path
from typing import Literal
from uuid import uuid4

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field

from . import media_probe_runtime as runtime
from .imports import resource_path
from .media_inputs import INPUT_LIMIT, POLICY_VERSION, inspect_media_input
from .office_runtime import WindowsProcessJob

TIME_LIMIT = 60


class VideoStream(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    index: int = Field(ge=0, le=1)
    role: Literal['video']
    codec: Literal['h264']
    duration_ms: int = Field(ge=1, le=604800000)
    width: int = Field(ge=1, le=32768)
    height: int = Field(ge=1, le=32768)


class AudioStream(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    index: int = Field(ge=0, le=1)
    role: Literal['audio']
    codec: Literal['aac']
    duration_ms: int = Field(ge=1, le=604800000)
    sample_rate: int = Field(ge=8000, le=192000)
    channels: int = Field(ge=1, le=8)


class ProbeMetadata(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    container: Literal['mp4']
    duration_ms: int = Field(ge=1, le=604800000)
    streams: list[VideoStream | AudioStream] = Field(min_length=1, max_length=2)


class ProbeStopped(Exception):
    pass


class ProbeBudget(Exception):
    pass


def integer(value, lower, upper):
    if type(value) is not int or not lower <= value <= upper:
        raise ValueError('Probe integer')
    return value


def decimal_integer(value, lower, upper):
    if not isinstance(value, str) or not re.fullmatch('[0-9]{1,12}', value):
        raise ValueError('Probe decimal integer')
    return integer(int(value), lower, upper)


def milliseconds(value):
    if not isinstance(value, str) or not re.fullmatch(r'[0-9]{1,6}(\.[0-9]{1,9})?', value):
        raise ValueError('Probe duration')
    duration = Decimal(value)
    if not 0 < duration <= 604800:
        raise ValueError('Probe duration range')
    return integer(int(duration * 1000), 1, 604800000)


def validated_result(raw, size, declarations):
    value = runtime.strict_json(raw, runtime.OUTPUT_LIMIT)
    if (not isinstance(value, dict) or set(value) != {'programs', 'stream_groups', 'streams', 'format'} or
            value['programs'] != [] or value['stream_groups'] != [] or
            not isinstance(value['streams'], list) or not 1 <= len(value['streams']) <= 2):
        raise ValueError('Probe sections')
    summary = value['format']
    if (not isinstance(summary, dict) or set(summary) != {'format_name', 'duration', 'size'} or
            summary['format_name'] != 'mov,mp4,m4a,3gp,3g2,mj2' or
            decimal_integer(summary['size'], 1, INPUT_LIMIT) != size):
        raise ValueError('Probe container')
    streams = []
    for index, item in enumerate(value['streams']):
        if not isinstance(item, dict):
            raise ValueError('Probe stream')
        role = item.get('codec_type')
        common = {'index', 'codec_name', 'codec_type', 'duration'}
        fields = {'width', 'height'} if role == 'video' else {'sample_rate', 'channels'}
        if (set(item) != common | fields or role not in ('video', 'audio') or
                item['codec_name'] != ('h264' if role == 'video' else 'aac') or
                integer(item['index'], 0, 1) != index):
            raise ValueError('Unsupported probe stream')
        stream = {'index': index, 'role': role, 'codec': item['codec_name'], 'duration_ms': milliseconds(item['duration'])}
        if role == 'video':
            stream.update(width=integer(item['width'], 1, 32768), height=integer(item['height'], 1, 32768))
        else:
            stream.update(sample_rate=decimal_integer(item['sample_rate'], 8000, 192000),
                          channels=integer(item['channels'], 1, 8))
        streams.append(stream)
    if ([(item['role'], item['codec']) for item in streams] !=
            [(item['role'], item['declared_codec']) for item in declarations]):
        raise ValueError('Stream declaration changed')
    return {'container': 'mp4', 'duration_ms': milliseconds(summary['duration']), 'streams': streams}


def checked_worker_result(result, size, checksum, declarations, policy_version=POLICY_VERSION):
    metadata_fields = {'container', 'duration_ms', 'streams'}
    identity = {'native_probe_performed': True, 'probe_version': runtime.VERSION,
                'component_snapshot_sha256': runtime.SNAPSHOT, 'policy_version': policy_version,
                'size': size, 'sha256': checksum}
    if (not isinstance(result, dict) or set(result) != metadata_fields | set(identity) or
            any(result[key] != expected or type(result[key]) is not type(expected) for key, expected in identity.items())):
        raise ValueError('Private result identity')
    metadata = ProbeMetadata.model_validate({key: result[key] for key in metadata_fields}).model_dump()
    if ([(s['index'], s['role'], s['codec']) for s in metadata['streams']] !=
            [(i, s['role'], s['declared_codec']) for i, s in enumerate(declarations)]):
        raise ValueError('Private result streams')
    return {**identity, **metadata}


def clear_native_dll_directory():
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.SetDllDirectoryW.argtypes = [ctypes.c_wchar_p]
    kernel.SetDllDirectoryW.restype = ctypes.c_int
    if not kernel.SetDllDirectoryW(None):
        raise ctypes.WinError(ctypes.get_last_error())


def native_process(job, command, operation, checkpoint, output, limit):
    """Fixed recipes share one existing Job; only their own process handle is released here."""
    process = None
    try:
        checkpoint()
        process = job.start(command, operation, runtime.environment(operation))
        while process.poll() is None:
            checkpoint()
            if output.exists() and output.stat().st_size > limit:
                raise ProbeBudget()
            time.sleep(.025)
        checkpoint()
        if process.returncode != 0:
            raise ValueError('Native media command rejected input')
    except BaseException:
        job.close()
        raise
    finally:
        if process is not None:
            try:
                process.wait(timeout=2)
            finally:
                process.close()


def worker():
    """Only private stdin supplies a previously frozen server-owned operation and pinned component."""
    operation = None
    parent_thread = None
    cancelled = threading.Event()
    deadline = time.monotonic() + TIME_LIMIT
    def check():
        if cancelled.is_set():
            raise ProbeStopped()
        if time.monotonic() > deadline:
            raise ProbeBudget()
    try:
        options = runtime.strict_json(sys.stdin.buffer.readline(8193), 8192)
        if not isinstance(options, dict) or set(options) != {'directory', 'runtime', 'suffix', 'size', 'sha256'}:
            raise ValueError('Private input fields')
        operation = runtime.local_path(Path(options['directory']))
        if operation.parent.name != 'media-probes' or not re.fullmatch('[0-9a-f]{32}', operation.name):
            operation = None
            raise ValueError('Private operation identity')
        suffix, size, checksum = options['suffix'], options['size'], options['sha256']
        integer(size, 1, INPUT_LIMIT)
        if suffix not in ('.mp4', '.m4a') or not isinstance(checksum, str) or not re.fullmatch('[0-9a-f]{64}', checksum):
            raise ValueError('Private source')
        def parent():
            # A raw pipe read holds no BufferedReader lock during interpreter shutdown.
            os.read(sys.stdin.fileno(), 1)
            cancelled.set()
        parent_thread = threading.Thread(target=parent, daemon=True)
        parent_thread.start()
        component = runtime.verify_component(Path(options['runtime']), check)
        preview = inspect_media_input(operation, 'source' + suffix, size, checksum,
                                      'audio/mp4' if suffix == '.m4a' else 'video/mp4', check)
        runtime.local_path(operation / 'tmp')
        for name in ('probe.json', 'result.json'):
            if (operation / name).exists() or (operation / name).is_symlink():
                raise ValueError('Private output already exists')
        clear_native_dll_directory()
        job = WindowsProcessJob()
        try:
            native_process(job, runtime.command(component, operation, suffix), operation, check,
                           operation / 'probe.json', runtime.OUTPUT_LIMIT)
            with runtime.local_path(operation / 'probe.json').open('rb') as output:
                result = validated_result(output.read(runtime.OUTPUT_LIMIT + 1), size, preview['streams'])
        finally:
            job.close()
        result.update(native_probe_performed=True, probe_version=runtime.VERSION,
                      component_snapshot_sha256=runtime.SNAPSHOT, policy_version=preview['policy_version'],
                      size=size, sha256=checksum)
    except ProbeStopped:
        result = {'error_code': 'cancelled'}
    except ProbeBudget:
        result = {'error_code': 'budget'}
    except Exception:
        result = {'error_code': 'unsupported'}
    if operation is not None:
        try:
            with (operation / 'result.json').open('x', encoding='utf-8', newline='\n') as output:
                json.dump(result, output, allow_nan=False)
        except OSError:
            return 1
    if parent_thread is not None:
        parent_thread.join(timeout=2)
    return 1 if 'error_code' in result else 0


def probe_media_input(root, workspace, identifier, relative, size, checksum, mime, cancelled, stopping):
    deadline = time.monotonic() + TIME_LIMIT
    process = None
    def check():
        if cancelled.is_set() or stopping.is_set():
            raise ProbeStopped()
        if time.monotonic() > deadline:
            raise ProbeBudget()
    try:
        check()
        try:
            component = runtime.verify_component(runtime.component_directory(), check)
        except (OSError, ValueError, KeyError, TypeError) as error:
            raise HTTPException(503, '未找到已核验的本地探测组件；原文件保留') from error
        preview = inspect_media_input(root, relative, size, checksum, mime, check)
        operation = resource_path(root, f'workspaces/{workspace}/media-probes/{uuid4().hex}')
        operation.mkdir(parents=True, exist_ok=False)
        runtime.local_path(operation)
        (operation / 'tmp').mkdir()
        if shutil.disk_usage(operation).free < size + 16 * 1024 * 1024:
            raise HTTPException(507, '本地探测空间不足；原文件及已生成字节保留')
        suffix = '.m4a' if mime == 'audio/mp4' else '.mp4'
        digest, received = hashlib.sha256(), 0
        with resource_path(root, relative).open('rb') as original, (operation / ('source' + suffix)).open('xb') as frozen:
            while chunk := original.read(1024 * 1024):
                check()
                received += len(chunk)
                if received > size:
                    raise HTTPException(409, '媒体在探测前改变；原文件及已生成字节保留')
                frozen.write(chunk)
                digest.update(chunk)
            frozen.flush()
            os.fsync(frozen.fileno())
        if received != size or digest.hexdigest() != checksum:
            raise HTTPException(409, '媒体在探测前改变；原文件及已生成字节保留')
        command = [sys.executable]
        if not getattr(sys, 'frozen', False):
            command.extend(['-m', 'study_workbench'])
        command.append('--probe-media')
        environment = {key: os.environ[key] for key in ('SystemRoot', 'WINDIR') if key in os.environ}
        environment.update(PATH=str(Path(os.environ['SystemRoot']) / 'System32'),
                           TEMP=str(operation / 'tmp'), TMP=str(operation / 'tmp'), PYTHONUTF8='1', PYTHONIOENCODING='utf-8')
        if not getattr(sys, 'frozen', False):
            environment['PYTHONPATH'] = str(Path(__file__).resolve().parents[1])
        process = subprocess.Popen(command, cwd=operation, env=environment, stdin=subprocess.PIPE,
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                   creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        options = {'directory': str(operation), 'runtime': str(component), 'suffix': suffix, 'size': size, 'sha256': checksum}
        process.stdin.write(json.dumps(options).encode() + b'\n')
        process.stdin.flush()
        while process.poll() is None:
            check()
            # The fixed result receipt is also the parent's EOF acknowledgement boundary.
            if (operation / 'result.json').exists() and not process.stdin.closed:
                process.stdin.close()
            time.sleep(.025)
        check()
        with runtime.local_path(operation / 'result.json').open('rb') as output:
            result = runtime.strict_json(output.read(runtime.OUTPUT_LIMIT + 1), runtime.OUTPUT_LIMIT)
        if not isinstance(result, dict):
            raise ValueError('Private result')
        if 'error_code' in result:
            if set(result) != {'error_code'}:
                raise ValueError('Private error fields')
            if result['error_code'] == 'cancelled':
                raise ProbeStopped()
            if result['error_code'] == 'budget':
                raise ProbeBudget()
            raise HTTPException(422, '此媒体无法完成受控探测；可能损坏或超出支持子集，原文件保留')
        if process.returncode != 0:
            raise ValueError('Private exit')
        result = checked_worker_result(result, size, checksum, preview['streams'], preview['policy_version'])
        # Check the original again, so a result for an old selection is never adopted silently.
        inspect_media_input(root, relative, size, checksum, mime, check)
        check()
        return {'media_id': identifier, **result}
    except ProbeStopped as error:
        raise HTTPException(409, '媒体探测已取消；原文件及已生成字节保留') from error
    except ProbeBudget as error:
        raise HTTPException(413, '媒体探测超过资源或时间预算；原文件及已生成字节保留') from error
    except (OSError, ValueError, TypeError, KeyError, subprocess.SubprocessError) as error:
        raise HTTPException(409, '媒体探测未完成；原文件及已生成字节保留') from error
    finally:
        if process is not None:
            if process.stdin and not process.stdin.closed:
                try:
                    process.stdin.close()
                except OSError:
                    pass  # A failed child may already have closed its private input.
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=2)
