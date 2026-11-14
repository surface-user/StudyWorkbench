import copy
import json
import subprocess
import sys
import time
from threading import Event

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from study_workbench import media_site_previews as previews
from study_workbench.db import MediaDownloadJob, MediaEntry
from study_workbench.media_download_http import DownloadError
from test_explorer import PREFIX, client

ENDPOINT = PREFIX + '/media-site-previews'
PAGE = 'https://www.bilibili.com/video/BV1234567890'


def body(request='self-authored-preview-001'):
    return {'url': PAGE, 'request_id': request, 'rights_confirmed': True}


@pytest.fixture
def result():
    return dict(title='自编格式预览', video_id='BV1234567890', source_host='www.bilibili.com', source_url=PAGE,
                extractor_version=previews.VERSION, duration_seconds=120, returned_formats_only=True,
                formats=[dict(format_id='video-0', delivery='dash_video', source_format_id=64,
                              container='mp4', codecs='avc1.fixture', width=1280, height=720, fps=30,
                              size_bytes=None, requires_merge=True, download_supported=False,
                              url='https://media.example.org/item.m4s?private=do-not-echo', fragments=None,
                              limitation='暂不支持分轨下载')])


def finished(c, identifier):
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        response = c.get(ENDPOINT + '/' + identifier)
        assert response.status_code == 200
        if response.json()['status'] != 'running':
            return response.json()
        time.sleep(.01)
    pytest.fail('Preview did not finish')


def test_preview_is_scoped_idempotent_private_and_does_not_create_media(monkeypatch, tmp_path, result):
    calls = []

    def child(self, entry):
        calls.append(entry['url'])
        return copy.deepcopy(result)

    monkeypatch.setattr(previews.MediaSitePreviews, 'child', child)
    with client(tmp_path) as c:
        created = c.post(ENDPOINT, json=body())
        assert created.status_code == 200
        identifier = created.json()['id']
        value = finished(c, identifier)
        assert value['status'] == 'ready' and value['result']['formats'][0]['height'] == 720
        assert c.post(ENDPOINT, json=body()).json()['id'] == identifier and calls == [PAGE]
        assert c.post(ENDPOINT, json={**body(), 'url': PAGE.replace('1234567890', '0000000000')}).status_code == 409
        other = c.post('/api/workspaces', json={'name': '隔离空间'}).json()['id']
        different = f'/api/workspaces/{other}/media-site-previews/{identifier}'
        assert c.get(different).status_code == c.post(different + '/cancel', json={}).status_code == 404
        encoded = json.dumps(value)
        assert all(name not in encoded for name in ('source_url', 'fragments', 'private=', 'do-not-echo'))
        assert 'url' in c.app.state.site_previews.entries[identifier]['result']['formats'][0]
        with Session(c.app.state.engine) as session:
            assert session.scalar(select(func.count()).select_from(MediaDownloadJob)) == 0
            assert session.scalar(select(func.count()).select_from(MediaEntry)) == 0
    with client(tmp_path) as c:
        assert c.get(ENDPOINT + '/' + identifier).status_code == 404


@pytest.mark.parametrize('change', [{'rights_confirmed': False}, {'rights_confirmed': 1},
                                   {'headers': {'Authorization': 'never-forward'}},
                                   {'url': 'https://evil.example.org/video/BV1234567890'},
                                   {'request_id': 'short'}])
def test_invalid_creation_never_starts_worker(monkeypatch, tmp_path, change):
    monkeypatch.setattr(previews.MediaSitePreviews, 'child', lambda *_: pytest.fail('Must not start worker'))
    with client(tmp_path) as c:
        assert c.post(ENDPOINT, json={**body(), **change}).status_code == 422
        assert not c.app.state.site_previews.entries
        assert c.post(ENDPOINT, json=body(), headers={'authorization': ''}).status_code == 401
        assert c.post(ENDPOINT, json=body(), headers={'origin': 'https://example.org'}).status_code == 403


def test_cancel_discards_late_result_and_expired_entries_are_unusable(monkeypatch, tmp_path, result):
    started, completed = Event(), Event()

    def child(self, entry):
        started.set()
        entry['cancel'].wait(3)
        completed.set()
        return copy.deepcopy(result)

    monkeypatch.setattr(previews.MediaSitePreviews, 'child', child)
    with client(tmp_path) as c:
        identifier = c.post(ENDPOINT, json=body()).json()['id']
        assert started.wait(1)
        assert c.post(ENDPOINT + '/' + identifier + '/cancel', json={}).json()['status'] == 'cancelled'
        assert completed.wait(1)
        value = c.get(ENDPOINT + '/' + identifier).json()
        assert value['status'] == 'cancelled' and value['result'] is None
        assert c.post(ENDPOINT + '/' + identifier + '/cancel', json={}).json()['status'] == 'cancelled'
        entry = c.app.state.site_previews.entries[identifier]
        entry['expires'] = time.monotonic() - 1
        assert c.get(ENDPOINT + '/' + identifier).status_code == 404
        assert identifier not in c.app.state.site_previews.entries


def test_concurrency_and_memory_entry_limits_reject_without_a_second_queue(monkeypatch, tmp_path):
    with client(tmp_path) as c:
        service = c.app.state.site_previews
        monkeypatch.setattr(service.pool, 'submit', lambda *_: None)
        first = c.post(ENDPOINT, json=body('self-authored-parallel-1')).json()['id']
        assert c.post(ENDPOINT, json=body('self-authored-parallel-2')).status_code == 200
        assert c.post(ENDPOINT, json=body('self-authored-parallel-3')).status_code == 429
        c.post(ENDPOINT + '/' + first + '/cancel', json={})
        assert c.post(ENDPOINT, json=body('self-authored-parallel-3')).status_code == 200
        for entry in service.entries.values():
            entry['status'] = 'cancelled'
        for i in range(29):
            assert c.post(ENDPOINT, json=body(f'self-authored-memory-{i:03}')).status_code == 200
            for entry in service.entries.values():
                entry['status'] = 'cancelled'
        assert len(service.entries) == 32
        assert c.post(ENDPOINT, json=body('self-authored-memory-overflow')).status_code == 429


def test_real_fixed_worker_is_job_owned_and_does_not_inherit_proxy_or_token(monkeypatch, tmp_path):
    actual = subprocess.Popen
    seen = []
    monkeypatch.setenv('HTTP_PROXY', 'http://invalid.example.org:8080')
    monkeypatch.setenv('STUDY_TOKEN', 'private-fixture-token')

    def launch(command, **options):
        seen.append(options['env'])
        return actual(command, **options)

    monkeypatch.setattr(previews.subprocess, 'Popen', launch)
    with client(tmp_path) as c:
        with pytest.raises(DownloadError):
            c.app.state.site_previews.child({'url': 'https://evil.example.org/', 'cancel': Event()})
    assert len(seen) == 1
    assert all(key not in seen[0] for key in ('HTTP_PROXY', 'STUDY_TOKEN', 'PYTHONHOME'))
    assert seen[0]['PYTHONNOUSERSITE'] == '1'


@pytest.mark.parametrize('diagnostic', [{'stage': 'view', 'http_status': 412},
                                      {'stage': 'view', 'http_status': '412'},
                                      {'stage': 'view', 'http_status': 412, 'url': 'must-not-reflect'}])
def test_real_ipc_diagnostics_are_typed_filtered_and_do_not_change_ui_error(monkeypatch, tmp_path, diagnostic):
    actual = subprocess.Popen
    packet = json.dumps({'error': 'untrusted https://private.invalid/?secret=fixture', 'error_diagnostic': diagnostic})

    def launch(_command, **options):
        return actual([sys.executable, '-c', 'import sys;sys.stdin.buffer.readline();print(' + repr(packet) + ')'], **options)

    monkeypatch.setattr(previews.subprocess, 'Popen', launch)
    with client(tmp_path) as c:
        identifier = c.post(ENDPOINT, json=body()).json()['id']
        value = finished(c, identifier)
        assert value['status'] == 'failed' and value['result'] is None
        assert 'private.invalid' not in json.dumps(value) and 'must-not-reflect' not in json.dumps(value)
        if diagnostic == {'stage': 'view', 'http_status': 412}:
            assert value['error_diagnostic'] == diagnostic
            assert value['error'] == '该视频暂不可预览，可能需要权限或访问限制'
        else:
            assert value['error_diagnostic'] is None and value['error'] == '预览工作进程诊断格式无效'
        assert c.post(ENDPOINT + '/' + identifier + '/cancel', json={}).json()['error_diagnostic'] is None


def test_real_unresponsive_owned_child_is_killed_after_cancel(monkeypatch, tmp_path):
    actual = subprocess.Popen
    children = []
    cancelled = Event()

    def launch(_command, **options):
        process = actual([sys.executable, '-c',
                          'import sys,time;sys.stdin.buffer.readline();time.sleep(30)'], **options)
        children.append(process)
        cancelled.set()
        return process

    monkeypatch.setattr(previews.subprocess, 'Popen', launch)
    with client(tmp_path) as c:
        start = time.monotonic()
        with pytest.raises(DownloadError, match='取消'):
            c.app.state.site_previews.child({'url': PAGE, 'cancel': cancelled})
        assert time.monotonic() - start < 7
    assert len(children) == 1 and children[0].poll() is not None


def test_already_cancelled_entry_never_launches_process(monkeypatch, tmp_path):
    monkeypatch.setattr(previews.subprocess, 'Popen', lambda *_args, **_kwargs: pytest.fail('Cancelled before launch'))
    with client(tmp_path) as c:
        cancelled = Event()
        cancelled.set()
        with pytest.raises(DownloadError, match='取消'):
            c.app.state.site_previews.child({'url': PAGE, 'cancel': cancelled})


def test_expiry_removes_private_candidates_without_another_request(monkeypatch, tmp_path, result):
    monkeypatch.setattr(previews.MediaSitePreviews, 'child', lambda *_: copy.deepcopy(result))
    with client(tmp_path) as c:
        service = c.app.state.site_previews
        identifier = c.post(ENDPOINT, json=body()).json()['id']
        assert finished(c, identifier)['status'] == 'ready'
        service.entries[identifier]['expires'] = time.monotonic() - 1
        deadline = time.monotonic() + 3
        while identifier in service.entries and time.monotonic() < deadline:
            time.sleep(.02)
        assert identifier not in service.entries
