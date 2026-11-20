import copy
import ctypes
import hashlib
import io
import json
import os
import struct
import subprocess
import sys
import threading
import time

import pytest
from fastapi import HTTPException
from study_workbench import media_library, media_probe_runtime, media_probes
from study_workbench.office_runtime import WindowsProcessJob
from test_imports import SCOPE, client
from test_media_inputs import mp4


def native_json():
    return {'programs': [], 'stream_groups': [],
            'streams': [{'index': 0, 'codec_name': 'h264', 'codec_type': 'video',
                         'width': 16, 'height': 16, 'duration': '0.200000'}],
            'format': {'format_name': 'mov,mp4,m4a,3gp,3g2,mj2', 'duration': '0.200000', 'size': '100'}}


def test_strict_native_output_is_metadata_only():
    result = media_probes.validated_result(json.dumps(native_json()).encode(), 100,
                                           [{'role': 'video', 'declared_codec': 'h264'}])
    assert result == {'container': 'mp4', 'duration_ms': 200, 'streams': [
        {'index': 0, 'role': 'video', 'codec': 'h264', 'width': 16, 'height': 16, 'duration_ms': 200}]}


@pytest.mark.parametrize('case', ['extra', 'tags', 'program', 'codec', 'role', 'width_bool', 'width_zero',
                                  'index_bool', 'index_gap', 'duration_nan', 'duration_large', 'duration_zero',
                                  'format', 'size', 'extra_stream', 'missing'])
def test_native_json_unknown_fields_unsafe_values_and_declared_mismatch_fail(case):
    value = native_json()
    stream = value['streams'][0]
    if case == 'extra':
        value['url'] = 'https://example.invalid/private'
    elif case == 'tags':
        stream['tags'] = {'filename': 'C:/private'}
    elif case == 'program':
        value['programs'] = [{'streams': []}]
    elif case == 'codec':
        stream['codec_name'] = 'hevc'
    elif case == 'role':
        stream['codec_type'] = 'subtitle'
    elif case == 'width_bool':
        stream['width'] = True
    elif case == 'width_zero':
        stream['width'] = 0
    elif case == 'index_bool':
        stream['index'] = False
    elif case == 'index_gap':
        stream['index'] = 1
    elif case == 'duration_nan':
        stream['duration'] = 'NaN'
    elif case == 'duration_large':
        stream['duration'] = '604801.0'
    elif case == 'duration_zero':
        stream['duration'] = '0.000000'
    elif case == 'format':
        value['format']['format_name'] = 'matroska,webm'
    elif case == 'size':
        value['format']['size'] = '101'
    elif case == 'extra_stream':
        value['streams'].append(copy.deepcopy(stream))
    else:
        del stream['duration']
    with pytest.raises(ValueError):
        media_probes.validated_result(json.dumps(value).encode(), 100, [{'role': 'video', 'declared_codec': 'h264'}])


@pytest.mark.parametrize('raw,limit', [(b'{"a":1,"a":2}', 32), (b'{"a":NaN}', 32),
    (b'[' * 20 + b'0' + b']' * 20, 128), (b'[' + b'0,' * 1024 + b'0]', 4096), (b'\xff', 32), (b'0' * 40, 32)])
def test_private_json_structure_and_bytes_are_bounded(raw, limit):
    with pytest.raises(ValueError):
        media_probe_runtime.strict_json(raw, limit)


@pytest.mark.parametrize('case', ['valid', 'extra', 'native_bool', 'source_hash', 'source_size', 'component',
                                  'index_bool', 'width_bool', 'stream_role', 'duplicate_role'])
def test_parent_accepts_only_bounded_worker_whitelist(case):
    declarations = [{'role': 'video', 'declared_codec': 'h264'}]
    value = media_probes.validated_result(json.dumps(native_json()).encode(), 100, declarations)
    value.update(native_probe_performed=True, probe_version=media_probe_runtime.VERSION,
                 component_snapshot_sha256=media_probe_runtime.SNAPSHOT, policy_version=media_probes.POLICY_VERSION,
                 size=100, sha256='0' * 64)
    if case == 'extra':
        value['path'] = 'C:/private'
    elif case == 'native_bool':
        value['native_probe_performed'] = 1
    elif case == 'source_hash':
        value['sha256'] = '1' * 64
    elif case == 'source_size':
        value['size'] = 100.0
    elif case == 'component':
        value['component_snapshot_sha256'] = '1' * 64
    elif case == 'index_bool':
        value['streams'][0]['index'] = False
    elif case == 'width_bool':
        value['streams'][0]['width'] = True
    elif case == 'stream_role':
        value['streams'][0]['role'] = 'audio'
    elif case == 'duplicate_role':
        value['streams'].append(copy.deepcopy(value['streams'][0]))
    if case == 'valid':
        assert media_probes.checked_worker_result(value, 100, '0' * 64, declarations) == value
    else:
        with pytest.raises(ValueError):
            media_probes.checked_worker_result(value, 100, '0' * 64, declarations)


@pytest.fixture
def policy_component(tmp_path, monkeypatch):
    """Owned policy fixture, never executed and never represented as a real FFmpeg build."""
    directory = tmp_path / 'component'
    directory.mkdir()
    files = {}
    for index in range(17):
        name, raw = f'bin/owned{index}.dat', bytes([index]) * (index + 1)
        path = directory / name
        path.parent.mkdir(exist_ok=True)
        path.write_bytes(raw)
        files[name] = {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}
    payload = {'profile_sha256': media_probe_runtime.PROFILE, 'files': files}
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    envelope = {'payload': payload, 'snapshot_sha256': digest}
    (directory / 'ffmpeg-component-lock.json').write_text(json.dumps(envelope), 'utf-8')
    monkeypatch.setattr(media_probe_runtime, 'SNAPSHOT', digest)
    return directory, envelope


@pytest.mark.parametrize('case', ['valid', 'missing', 'changed', 'extra', 'self_rehash', 'duplicate_lock'])
@pytest.mark.skipif(os.name != 'nt', reason='Pinned Windows component boundary')
def test_component_fixed_snapshot_file_set_and_bytes(policy_component, case):
    directory, envelope = policy_component
    path = directory / 'bin/owned0.dat'
    if case == 'missing':
        path.unlink()
    elif case == 'changed':
        path.write_bytes(b'x')
    elif case == 'extra':
        (directory / 'unexpected.dll').write_bytes(b'foreign')
    elif case == 'self_rehash':
        envelope['payload']['files']['bin/owned0.dat']['sha256'] = '0' * 64
        envelope['snapshot_sha256'] = hashlib.sha256(json.dumps(envelope['payload'], sort_keys=True, separators=(',', ':')).encode()).hexdigest()
        (directory / 'ffmpeg-component-lock.json').write_text(json.dumps(envelope), 'utf-8')
    elif case == 'duplicate_lock':
        (directory / 'ffmpeg-component-lock.json').write_text('{"payload":{},"payload":{}}', 'utf-8')
    if case == 'valid':
        assert media_probe_runtime.verify_component(directory, lambda: None) == directory
    else:
        with pytest.raises((ValueError, OSError)):
            media_probe_runtime.verify_component(directory, lambda: None)


@pytest.mark.parametrize('case', ['cancelled', 'stopping', 'deadline'])
def test_cancel_parent_shutdown_and_deadline_prevent_component_or_input_access(tmp_path, monkeypatch, case):
    cancelled, stopping = threading.Event(), threading.Event()
    if case == 'cancelled':
        cancelled.set()
    elif case == 'stopping':
        stopping.set()
    else:
        monkeypatch.setattr(media_probes, 'TIME_LIMIT', -1)
    monkeypatch.setattr(media_probe_runtime, 'verify_component', lambda *args: pytest.fail('Must stop before component access'))
    with pytest.raises(HTTPException) as caught:
        media_probes.probe_media_input(tmp_path, 'default', 'id', 'unread', 1, '0' * 64, 'video/mp4', cancelled, stopping)
    assert caught.value.status_code == (413 if case == 'deadline' else 409)
    assert list(tmp_path.iterdir()) == []


def test_native_api_auth_body_missing_runtime_and_shutdown(tmp_path, monkeypatch):
    monkeypatch.setenv('STUDY_FFMPEG_RUNTIME', str(tmp_path / 'missing-component'))
    with client(tmp_path) as c:
        item = c.post(f'{SCOPE}/media/import?filename=local.mp4', content=mp4()).json()
        route, body = f"{SCOPE}/media/{item['id']}/native-probe", {'expected_sha256': item['sha256']}
        assert c.post(route, json=body).status_code == 503
        assert c.post(route, json={**body, 'command': 'not allowed'}).status_code == 422
        assert c.post(route, json=body, headers={'Authorization': ''}).status_code == 401
        assert c.post(route, json=body, headers={'Origin': 'https://example.invalid'}).status_code == 403
        assert c.post('/api/workspaces/missing/media/' + item['id'] + '/native-probe', json=body).status_code == 404
        assert c.post(route, json={'expected_sha256': '0' * 64}).status_code == 409
        from study_workbench.document_files import VIEW_SLOTS
        assert VIEW_SLOTS.acquire(blocking=False) and VIEW_SLOTS.acquire(blocking=False)
        try:
            assert c.post(route, json=body).status_code == 429
        finally:
            VIEW_SLOTS.release()
            VIEW_SLOTS.release()
        c.app.state.media_probe_stopping.set()
        assert c.post(route, json=body).status_code == 409
        assert c.get(f'{SCOPE}/media').json() == [item]


def test_http_disconnect_sets_only_this_probe_cancel_event(tmp_path, monkeypatch):
    seen = []
    def controlled_probe(*args):
        cancelled, stopping = args[-2:]
        until = time.monotonic() + 2
        while not cancelled.is_set() and time.monotonic() < until:
            time.sleep(.005)
        seen.append((cancelled.is_set(), stopping.is_set()))
        raise HTTPException(409, 'cancelled')
    async def disconnected(_, cancelled):
        cancelled.set()
    monkeypatch.setattr(media_library, 'probe_media_input', controlled_probe)
    monkeypatch.setattr(media_library, 'cancel_probe_on_disconnect', disconnected)
    with client(tmp_path) as c:
        item = c.post(f'{SCOPE}/media/import?filename=local.mp4', content=mp4()).json()
        response = c.post(f"{SCOPE}/media/{item['id']}/native-probe", json={'expected_sha256': item['sha256']})
        assert response.status_code == 409 and seen == [(True, False)]


@pytest.mark.skipif(os.name != 'nt', reason='Actual Windows owned-helper termination')
def test_unresponsive_owned_helper_is_terminated_after_eof_grace(tmp_path, monkeypatch):
    data = mp4()
    (tmp_path / 'input.mp4').write_bytes(data)
    cancelled, stopping, processes = threading.Event(), threading.Event(), []
    real_popen = subprocess.Popen
    def unresponsive_helper(*args, **kwargs):
        process = real_popen([sys.executable, '-c', 'import time; time.sleep(60)'],
            stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW)
        processes.append(process)
        cancelled.set()
        return process
    # Only this owned failure fixture substitutes a helper; it supplies no native success evidence.
    monkeypatch.setattr(media_probe_runtime, 'verify_component', lambda *args: tmp_path)
    monkeypatch.setattr(subprocess, 'Popen', unresponsive_helper)
    start = time.monotonic()
    try:
        with pytest.raises(HTTPException) as caught:
            media_probes.probe_media_input(tmp_path, 'default', 'id', 'input.mp4', len(data),
                hashlib.sha256(data).hexdigest(), 'video/mp4', cancelled, stopping)
        assert caught.value.status_code == 409 and 2 <= time.monotonic() - start < 8
        assert len(processes) == 1 and processes[0].poll() is not None
        assert (tmp_path / 'input.mp4').read_bytes() == data
    finally:
        for process in processes:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=2)


@pytest.mark.parametrize('raw', [b'null\n', b'{"command":"unknown"}\n', b'{"directory":1}\n', b'NaN\n'])
def test_private_worker_malformed_input_never_verifies_or_executes(raw, monkeypatch):
    monkeypatch.setattr(sys, 'stdin', io.TextIOWrapper(io.BytesIO(raw)))
    monkeypatch.setattr(media_probe_runtime, 'verify_component', lambda *args: pytest.fail('No component access'))
    assert media_probes.worker() == 1


@pytest.mark.skipif(os.name != 'nt', reason='Actual Windows Job lifecycle')
def test_windows_job_limits_and_kills_only_its_owned_tree(tmp_path):
    helper = tmp_path / 'owned_helper.py'
    marker = tmp_path / 'child.json'
    helper.write_text('import json,os,pathlib,subprocess,sys,time\n'
        'if len(sys.argv)>1:\n'
        ' child=subprocess.Popen([sys.executable,__file__])\n'
        ' pathlib.Path(sys.argv[1]).write_text(json.dumps({"child":child.pid}))\n'
        'time.sleep(60)\n', 'utf-8')
    outside = subprocess.Popen([sys.executable, str(helper)], creationflags=subprocess.CREATE_NO_WINDOW)
    job, process, child_handle = WindowsProcessJob(), None, None
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.QueryInformationJobObject.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p, ctypes.c_uint32, ctypes.c_void_p]
    kernel.QueryInformationJobObject.restype = ctypes.c_int
    kernel.OpenProcess.argtypes = [ctypes.c_uint32, ctypes.c_int, ctypes.c_uint32]
    kernel.OpenProcess.restype = ctypes.c_void_p
    kernel.IsProcessInJob.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(ctypes.c_int)]
    kernel.IsProcessInJob.restype = ctypes.c_int
    kernel.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
    kernel.WaitForSingleObject.restype = ctypes.c_uint32
    kernel.CloseHandle.argtypes = [ctypes.c_void_p]
    try:
        limits = ctypes.create_string_buffer(144)
        assert kernel.QueryInformationJobObject(job.handle, 9, limits, len(limits), None)
        assert struct.unpack_from('<I', limits, 16)[0] & 0x2208 == 0x2208
        assert struct.unpack_from('<I', limits, 40)[0] == 4
        assert struct.unpack_from('<Q', limits, 120)[0] == 1024 * 1024 * 1024
        process = job.start([sys.executable, str(helper), str(marker)], tmp_path, dict(os.environ))
        until = time.monotonic() + 5
        while not marker.exists() and time.monotonic() < until:
            time.sleep(.01)
        child_handle = kernel.OpenProcess(0x100000 | 0x1000, False, json.loads(marker.read_text())['child'])
        assert child_handle
        belongs = ctypes.c_int()
        assert kernel.IsProcessInJob(child_handle, job.handle, ctypes.byref(belongs)) and belongs.value
        job.close()
        assert kernel.WaitForSingleObject(child_handle, 2000) == 0
        assert process.wait(timeout=2) != 259 and outside.poll() is None
    finally:
        job.close()
        if process is not None:
            process.close()
        if child_handle:
            kernel.CloseHandle(child_handle)
        outside.terminate()
        outside.wait(timeout=2)
