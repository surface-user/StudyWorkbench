"""Private local-only stream-copy worker. No SQL, business token or network requests."""
import hashlib
import json
import os
import shutil
import sys
import threading
import time
from pathlib import Path

from . import media_probe_runtime as runtime
from .imports import resource_path
from .media_inputs import inspect_media_input, managed_media_path
from .media_probes import (
    ProbeBudget,
    ProbeMetadata,
    ProbeStopped,
    clear_native_dll_directory,
    native_process,
    validated_result,
)
from .media_sources import (
    INPUT_LIMIT,
    OutputReceipt,
    attempt_context,
    attempt_record,
    source_digest,
    source_snapshot,
)
from .office_runtime import WindowsProcessJob

METADATA_TOTAL = 3 * runtime.OUTPUT_LIMIT
RESERVE = 16 * 1024 * 1024


def worker():
    parent_thread, job = None, None
    cancelled = threading.Event()
    result = None
    try:
        options = runtime.strict_json(sys.stdin.buffer.readline(32769), 32768)
        fields = {'root', 'workspace', 'job', 'attempt', 'generation', 'snapshot', 'inputs', 'runtime', 'remaining_ms'}
        if not isinstance(options, dict) or set(options) not in (fields, fields | {'record'}):
            raise ValueError('Private mux fields')
        if type(options['remaining_ms']) is not int or not 1 <= options['remaining_ms'] <= 900000:
            raise ValueError('Private shared deadline')
        deadline = time.monotonic() + options['remaining_ms'] / 1000
        def check():
            if cancelled.is_set():
                raise ProbeStopped()
            if time.monotonic() >= deadline:
                raise ProbeBudget()
        def parent():
            os.read(sys.stdin.fileno(), 1)
            cancelled.set()
        parent_thread = threading.Thread(target=parent, daemon=True)
        parent_thread.start()
        source = source_snapshot(options['snapshot'])
        root = runtime.local_path(Path(options['root']))
        site = source.kind == 'site_pair'
        if site != ('record' in options):
            raise ValueError('Unexpected acquired inputs')
        record = attempt_record(options['record'] if site else dict(schema_version=1, source_snapshot_sha256=source_digest(source), tracks=[
            dict(ordinal=i, state='pending',
                 relative_path=f"workspaces/{options['workspace']}/downloads/{options['job']}/{options['attempt']}/{options['generation']}/input{i}" +
                               ('.m4a' if track.mime == 'audio/mp4' else '.mp4'), metadata=None)
            for i, track in enumerate(source.tracks)], output=None))
        relative = attempt_context(options['workspace'], options['job'], options['attempt'],
                                   options['generation'], source, record)
        operation = runtime.local_path(resource_path(root, relative))
        expected = {operation / 'tmp'}
        if site:
            if record.output or any(track.state != 'copied' for track in record.tracks):
                raise ValueError('Acquired single-track files required')
            expected.update(resource_path(root, t.relative_path) for t in record.tracks)
        if not operation.is_dir() or set(operation.iterdir()) != expected:
            raise ValueError('Private operation is not new')
        runtime.local_path(operation / 'tmp')
        if not isinstance(options['inputs'], list) or len(options['inputs']) != (0 if site else 2):
            raise ValueError('Private source count')
        local_tracks = () if site else source.tracks
        for selection, original in zip(local_tracks, options['inputs'], strict=True):
            if not isinstance(original, str) or len(original) > 2048:
                raise ValueError('Private source path')
            managed_media_path(options['workspace'], selection.media_id, original)
        component = runtime.verify_component(Path(options['runtime']), check)
        total = sum(t.received.size for t in record.tracks) if site else source.input_size
        received, metadata_bytes = total if site else 0, 0
        def disk(output_size=0):
            check()
            if shutil.disk_usage(operation).free < total - received + INPUT_LIMIT - output_size + RESERVE:
                raise ProbeBudget()
        def emit(phase):
            check()
            value = dict(phase=phase, received=received, total=total, record=record.model_dump(mode='json'))
            print(json.dumps({'progress': value}, allow_nan=False), flush=True)
        names, previews = [], []
        if site:
            for selection, track in zip(source.tracks, record.tracks, strict=True):
                names.append(Path(track.relative_path).name)
                previews.append(inspect_media_input(root, track.relative_path, track.received.size,
                                                    track.received.sha256, selection.mime, check))
        else:
            emit('copying')
        for selection, original, frozen in zip(local_tracks, options['inputs'], () if site else record.tracks, strict=True):
            disk()
            inspect_media_input(root, original, selection.size, selection.sha256, selection.mime, check)
            target = resource_path(root, frozen.relative_path)
            runtime.local_path(target.parent)
            names.append(target.name)
            count, checksum = 0, hashlib.sha256()
            last = time.monotonic()
            with resource_path(root, original).open('rb') as stream, target.open('xb') as output:
                while chunk := stream.read(1024 * 1024):
                    disk()
                    count += len(chunk)
                    received += len(chunk)
                    if count > selection.size or received > total:
                        raise ValueError('Source grew')
                    output.write(chunk)
                    checksum.update(chunk)
                    if time.monotonic() - last >= .2:
                        emit('copying')
                        last = time.monotonic()
                output.flush()
                os.fsync(output.fileno())
            if count != selection.size or checksum.hexdigest() != selection.sha256:
                raise ValueError('Source changed during copy')
            frozen.state = 'copied'
            previews.append(inspect_media_input(root, frozen.relative_path, selection.size,
                                                selection.sha256, selection.mime, check))
            emit('copying')
        clear_native_dll_directory()
        job = WindowsProcessJob()
        for i, (selection, frozen, preview, name) in enumerate(zip(source.tracks, record.tracks, previews, names, strict=True)):
            disk()
            emit('probing')
            output_name = f'probe{i}.json'
            native_process(job, runtime.probe_command(component, operation, name, output_name),
                           operation, check, operation / output_name, runtime.OUTPUT_LIMIT)
            with runtime.local_path(operation / output_name).open('rb') as output:
                raw = output.read(runtime.OUTPUT_LIMIT + 1)
            metadata_bytes += len(raw)
            if metadata_bytes > METADATA_TOTAL:
                raise ProbeBudget()
            metadata = validated_result(raw, (frozen.received or selection).size, preview['streams'])
            frozen.metadata = ProbeMetadata.model_validate(metadata)
            frozen.state = 'probed'
            attempt_context(options['workspace'], options['job'], options['attempt'],
                            options['generation'], source, record)
            emit('probing')
        disk()
        emit('muxing')
        pending = operation / 'output.pending.mp4'
        if pending.exists() or pending.is_symlink():
            raise ValueError('Output already exists')
        native_process(job, runtime.mux_command(component, operation, names, [t.stream_index for t in source.tracks]),
                       operation, lambda: disk(pending.stat().st_size if pending.exists() else 0), pending, INPUT_LIMIT)
        emit('validating')
        runtime.local_path(pending)
        size = pending.stat().st_size
        if not 1 <= size <= INPUT_LIMIT:
            raise ProbeBudget()
        checksum = hashlib.sha256()
        with pending.open('rb') as stream:
            count = 0
            while chunk := stream.read(1024 * 1024):
                check()
                count += len(chunk)
                if count > size:
                    raise ValueError('Output grew')
                checksum.update(chunk)
        if count != size:
            raise ValueError('Output changed')
        sha = checksum.hexdigest()
        preview = inspect_media_input(root, pending.relative_to(root).as_posix(), size, sha, 'video/mp4', check)
        if preview['streams'] != [{'role': 'video', 'declared_codec': 'h264'}, {'role': 'audio', 'declared_codec': 'aac'}]:
            raise ValueError('Output pair differs')
        native_process(job, runtime.probe_command(component, operation, pending.name, 'output-probe.json'),
                       operation, check, operation / 'output-probe.json', runtime.OUTPUT_LIMIT)
        with runtime.local_path(operation / 'output-probe.json').open('rb') as output:
            raw = output.read(runtime.OUTPUT_LIMIT + 1)
        metadata_bytes += len(raw)
        if metadata_bytes > METADATA_TOTAL:
            raise ProbeBudget()
        metadata = validated_result(raw, size, preview['streams'])
        for selected, original in zip(local_tracks, options['inputs'], strict=True):
            inspect_media_input(root, original, selected.size, selected.sha256, selected.mime, check)
        record.output = OutputReceipt.model_validate(dict(state='prepared', pending_path=pending.relative_to(root).as_posix(),
                             final_path=f"workspaces/{options['workspace']}/downloads/{options['job']}/{options['attempt']}.mp4",
                             size=size, sha256=sha, metadata=metadata))
        record = attempt_record(record.model_dump(mode='json'))
        attempt_context(options['workspace'], options['job'], options['attempt'], options['generation'], source, record)
        check()
        result = {'result': record.model_dump(mode='json')}
    except ProbeStopped:
        result = {'error_code': 'cancelled'}
    except ProbeBudget:
        result = {'error_code': 'budget'}
    except Exception:
        result = {'error_code': 'unsupported'}
    finally:
        if job is not None:
            job.close()
    try:
        print(json.dumps(result, allow_nan=False), flush=True)
    except OSError:
        return 1
    if parent_thread is not None:
        parent_thread.join(timeout=2)
    return 0 if 'result' in result else 1
