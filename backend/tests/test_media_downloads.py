import hashlib
import json
import sqlite3
import subprocess
import sys
import time
from threading import Event

from sqlalchemy import select
from sqlalchemy.orm import Session
from study_workbench.db import MediaDownloadJob, MediaEntry, WorkspaceNode, write_transaction
from study_workbench.media_download_http import DownloadError
from study_workbench.media_downloads import MediaDownloads
from test_explorer import PREFIX, client

RAW = b'\x1aE\xdf\xa3' + b'self-authored test container bytes' * 8
URL = 'https://media.example.com/video.webm?signature=private-test'

def test_history_pages_keep_order_across_status_changes_new_jobs_and_restart(monkeypatch, tmp_path):
    with client(tmp_path) as c:
        with write_transaction(c.app.state.engine) as session:
            for i in range(125):
                identifier = f'{i:032x}'
                session.add(MediaDownloadJob(id=identifier, workspace_id='default', parent_id=None,
                    request_id=f'history-fixture-{i:04}', source_url=URL, name=f'历史{i}.webm',
                    status='paused', cancel_requested=False, attempt=1,
                    relative_path=f'workspaces/default/downloads/{identifier}/1.webm',
                    progress={'received': 0}, result={}, error=None,
                    created_at=f'2000-01-{10 + i // 50:02}T00:00:00+00:00'))
        endpoint = PREFIX + '/media-downloads'
        first = c.get(endpoint, params={'history': True, 'limit': 50}).json()
        assert [item['id'] for item in first[:25]] == [f'{i:032x}' for i in range(100, 125)]
        boundary = first[0]['id']
        with write_transaction(c.app.state.engine) as session:
            session.get(MediaDownloadJob, f'{30:032x}').status = 'queued'
            session.get(MediaDownloadJob, f'{100:032x}').status = 'ready'
        monkeypatch.setattr(c.app.state.downloads.pool, 'submit', lambda *args: None)
        new = c.post(endpoint, json=body('history-newly-created-job')).json()
        query = {'history': True, 'newest_id': boundary, 'limit': 50}
        second = c.get(endpoint, params={**query, 'offset': 50}).json()
        third = c.get(endpoint, params={**query, 'offset': 100}).json()
        seen = [item['id'] for item in first + second + third]
        assert len(seen) == len(set(seen)) == 125
        assert set(seen) == {f'{i:032x}' for i in range(125)}
        assert new['id'] not in seen
        assert c.get(endpoint, params={'history': True}).json()[0]['id'] == new['id']
        assert [item['id'] for item in c.get(endpoint, params=query).json()] == [item['id'] for item in first]
        assert c.get(endpoint).json()[0]['status'] == 'queued'
        assert all('signature' not in str(item) and 'source_url' not in item for item in first + second + third)
    with client(tmp_path) as c:
        after = c.get(endpoint, params={**query, 'offset': 100}).json()
        assert [item['id'] for item in after] == [item['id'] for item in third]
        assert next(item for item in after if item['id'] == f'{30:032x}')['status'] == 'interrupted'


def test_history_boundary_is_scoped_and_validated(monkeypatch, tmp_path):
    with client(tmp_path) as c:
        monkeypatch.setattr(c.app.state.downloads.pool, 'submit', lambda *args: None)
        identifier = c.post(PREFIX + '/media-downloads', json=body()).json()['id']
        other = c.post('/api/workspaces', json={'name': '另一空间'}).json()['id']
        endpoint = PREFIX + '/media-downloads'
        assert c.get(f'/api/workspaces/{other}/media-downloads',
            params={'history': True, 'newest_id': identifier}).status_code == 404
        for params, status in [
            ({'history': True, 'newest_id': 'f' * 32}, 404),
            ({'history': True, 'newest_id': 'invalid'}, 422),
            ({'newest_id': identifier}, 422),
            ({'history': True, 'offset': -1}, 422),
            ({'history': True, 'limit': 101}, 422),
        ]:
            assert c.get(endpoint, params=params).status_code == status
        assert c.get(endpoint, params={'history': True, 'newest_id': identifier},
            headers={'Origin': 'https://example.com'}).status_code == 403


def body(request='download-test-request-0001', name='自编.webm'):
    return dict(url=URL, name=name, request_id=request, rights_confirmed=True)


def wait(c, identifier, state):
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        value = c.get(f'{PREFIX}/media-downloads/{identifier}').json()
        if value['status'] in state:
            return value
        time.sleep(.01)
    raise AssertionError(value)


def completed(self, job, path):
    self.check(job.id)
    if job.progress.get('received', 0):
        assert hashlib.sha256(path.read_bytes()).hexdigest() == job.progress['partial_sha256']
        with path.open('ab') as out:
            out.write(RAW[len(path.read_bytes()):])
    else:
        path.write_bytes(RAW)
    return dict(size=len(RAW), sha256=hashlib.sha256(RAW).hexdigest(), etag='"v1"')


def test_scoped_creation_idempotence_publication_and_verified_media_dedup(monkeypatch, tmp_path):
    monkeypatch.setattr(MediaDownloads, 'child', completed)
    with client(tmp_path) as c:
        response = c.post(PREFIX + '/media-downloads', json=body())
        assert response.status_code == 200, response.text
        job = wait(c, response.json()['id'], {'ready', 'failed'})
        assert job['status'] == 'ready', job
        assert 'private-test' not in str(job) and 'example.com' in job['source_host']
        assert c.post(PREFIX + '/media-downloads', json=body()).json()['id'] == job['id']
        assert c.post(PREFIX + '/media-downloads', json={**body(), 'name': '不同.webm'}).status_code == 409
        second = c.post(PREFIX + '/media-downloads', json=body('download-test-request-0002')).json()
        second = wait(c, second['id'], {'ready', 'failed'})
        assert second['status'] == 'ready' and second['result']['deduplicated']
        assert second['result']['media_id'] == job['result']['media_id']
        assert second['result']['resource_item_id'] != job['result']['resource_item_id']
        with Session(c.app.state.engine) as session:
            assert len(list(session.scalars(select(MediaEntry).where(MediaEntry.workspace_id == 'default')))) == 1
            assert session.get(WorkspaceNode, job['result']['resource_item_id']).kind == 'media'
        other = c.post('/api/workspaces', json={'name': '另一个空间'}).json()['id']
        assert c.get(f'/api/workspaces/{other}/media-downloads/{job["id"]}').status_code == 404
        assert c.post(f'/api/workspaces/{other}/media-downloads/{job["id"]}/pause').status_code == 404
        assert c.post(f'{PREFIX}/media-downloads/{job["id"]}/retry', json={'mode': 'restart'}).status_code == 409
        assert c.get(PREFIX + '/media-downloads', headers={'Origin': 'https://example.com'}).status_code == 403
        assert c.post(PREFIX + '/media-downloads', json={**body('download-test-request-0003'), 'rights_confirmed': 1}).status_code == 422
        assert c.post(PREFIX + '/media-downloads', json={**body('download-test-request-0003'), 'path': 'C:/other'}).status_code == 422


def test_pause_resume_and_restart_keep_old_bytes(monkeypatch, tmp_path):
    entered, release = Event(), Event()
    def partial(self, job, path):
        prefix = RAW[:32]
        path.write_bytes(prefix)
        self.progress(job.id, {'received': len(prefix), 'total': len(RAW), 'etag': '"v1"',
                              'partial_sha256': hashlib.sha256(prefix).hexdigest()})
        entered.set()
        assert release.wait(5)
        self.check(job.id)
        raise AssertionError('Expected cancellation')
    monkeypatch.setattr(MediaDownloads, 'child', partial)
    with client(tmp_path) as c:
        try:
            identifier = c.post(PREFIX + '/media-downloads', json=body()).json()['id']
            assert entered.wait(5)
            assert c.post(f'{PREFIX}/media-downloads/{identifier}/pause').status_code == 200
        finally:
            release.set()
        paused = wait(c, identifier, {'paused'})
        assert paused['can_resume'] and paused['progress']['received'] == 32
        with Session(c.app.state.engine) as session:
            first_path = tmp_path / session.get(MediaDownloadJob, identifier).relative_path
        assert first_path.read_bytes() == RAW[:32]
        monkeypatch.setattr(MediaDownloads, 'child', completed)
        assert c.post(f'{PREFIX}/media-downloads/{identifier}/retry', json={'mode': 'resume'}).status_code == 200
        assert wait(c, identifier, {'ready', 'failed'})['status'] == 'ready'
        assert first_path.read_bytes() == RAW


def test_interrupted_queue_never_auto_connects_and_restart_retains_partial(monkeypatch, tmp_path):
    with client(tmp_path) as c:
        monkeypatch.setattr(c.app.state.downloads.pool, 'submit', lambda *args: None)
        identifier = c.post(PREFIX + '/media-downloads', json=body()).json()['id']
        with write_transaction(c.app.state.engine) as session:
            item = session.get(MediaDownloadJob, identifier)
            partial = tmp_path / item.relative_path
            partial.parent.mkdir(parents=True)
            partial.write_bytes(b'old failed bytes')
    with client(tmp_path) as c:
        assert c.get(f'{PREFIX}/media-downloads/{identifier}').json()['status'] == 'interrupted'
        assert c.post(f'{PREFIX}/media-downloads/{identifier}/retry', json={'mode': 'resume'}).status_code == 409
        monkeypatch.setattr(MediaDownloads, 'child', completed)
        restarted = c.post(f'{PREFIX}/media-downloads/{identifier}/retry', json={'mode': 'restart'})
        assert restarted.status_code == 200 and restarted.json()['attempt'] == 2
        assert wait(c, identifier, {'ready', 'failed'})['status'] == 'ready'
        assert partial.read_bytes() == b'old failed bytes'


def test_queue_bound_rights_confirmation_and_network_errors_keep_private_url_out_of_api(monkeypatch, tmp_path):
    with client(tmp_path) as c:
        monkeypatch.setattr(c.app.state.downloads.pool, 'submit', lambda *args: None)
        assert c.post(PREFIX + '/media-downloads', json={**body(), 'rights_confirmed': False}).status_code == 422
        assert c.post(PREFIX + '/media-downloads', json={**body(), 'url': 'http://127.0.0.1/'}).status_code == 422
        for i in range(32):
            assert c.post(PREFIX + '/media-downloads', json=body(f'bounded-request-number-{i:04}')).status_code == 200
        assert c.post(PREFIX + '/media-downloads', json=body('bounded-request-overflow')).status_code == 429
        assert len(c.get(PREFIX + '/media-downloads?offset=20&limit=10').json()) == 10
        assert 'private-test' not in c.get(PREFIX + '/media-downloads').text
    def fail(self, job, path):
        path.write_bytes(b'bad retained bytes')
        raise DownloadError('下载网络或写入失败，已存部分保留')
    monkeypatch.setattr(MediaDownloads, 'child', fail)
    with client(tmp_path) as c:
        item = c.post(PREFIX + '/media-downloads', json=body('failed-network-request-0001')).json()
        item = wait(c, item['id'], {'failed'})
        assert 'private-test' not in str(item)
        with Session(c.app.state.engine) as session:
            assert (tmp_path / session.get(MediaDownloadJob, item['id']).relative_path).read_bytes() == b'bad retained bytes'


def test_offline_backup_restores_ready_task_partial_task_signed_url_and_all_bytes(monkeypatch, tmp_path):
    from study_workbench.backup_archive import inspect_archive
    from study_workbench.backup_store import create_backup, restore_backup
    source = tmp_path / 'source'
    monkeypatch.setattr(MediaDownloads, 'child', completed)
    with client(source) as c:
        identifier = c.post(PREFIX + '/media-downloads', json=body()).json()['id']
        assert wait(c, identifier, {'ready', 'failed'})['status'] == 'ready'
        monkeypatch.setattr(c.app.state.downloads.pool, 'submit', lambda *args: None)
        paused = c.post(PREFIX + '/media-downloads', json=body('paused-backup-request-0001')).json()['id']
        with write_transaction(c.app.state.engine) as session:
            job = session.get(MediaDownloadJob, paused)
            part = source / job.relative_path
            part.parent.mkdir(parents=True)
            part.write_bytes(RAW[:32])
            job.status = 'paused'
            job.progress = {'received': 32, 'total': len(RAW), 'etag': '"v1"',
                            'partial_sha256': hashlib.sha256(RAW[:32]).hexdigest()}
    def rows(root):
        with sqlite3.connect(root / 'study.db') as connection:
            return connection.execute('SELECT * FROM media_download_jobs ORDER BY id').fetchall()
    before = rows(source)
    package, target = tmp_path / 'library.zip', tmp_path / 'restored'
    create_backup(source, package)
    manifest = inspect_archive(package)
    assert manifest['schema_revision'] == '0016'
    assert manifest['tables']['media_download_jobs']['rows'] == 2
    assert restore_backup(package, target, tmp_path / 'settings.json')['data_activated']
    assert rows(target) == before == rows(source)
    assert (target / part.relative_to(source)).read_bytes() == RAW[:32]
    assert any(URL in row for row in before)


def test_child_watchdog_terminates_only_its_own_blocked_process(monkeypatch, tmp_path):
    from study_workbench import media_downloads
    real_popen = subprocess.Popen
    owned = []
    def blocked(command, **kwargs):
        child = real_popen([sys.executable, '-c', 'import time; time.sleep(60)'], **kwargs)
        owned.append(child)
        return child
    with client(tmp_path) as c:
        monkeypatch.setattr(c.app.state.downloads.pool, 'submit', lambda *args: None)
        identifier = c.post(PREFIX + '/media-downloads', json=body()).json()['id']
        with Session(c.app.state.engine) as session:
            job = session.get(MediaDownloadJob, identifier)
            session.expunge(job)
        monkeypatch.setattr(media_downloads.subprocess, 'Popen', blocked)
        monkeypatch.setattr(media_downloads, 'JOB_SECONDS', .01)
        monkeypatch.setattr(media_downloads, 'STOP_SECONDS', .01)
        started = time.monotonic()
        try:
            c.app.state.downloads.child(job, tmp_path / 'owned.webm')
            raise AssertionError('Expected watchdog timeout')
        except DownloadError as error:
            assert '15分钟' in str(error)
        assert time.monotonic() - started < 3
        assert len(owned) == 1 and owned[0].poll() is not None


def test_actual_worker_rejects_invalid_url_without_echoing_query_or_opening_target(tmp_path):
    from pathlib import Path
    root = Path(__file__).resolve().parents[2]
    target = tmp_path / 'never-created.webm'
    options = dict(url='http://example.com/?secret=fixture', path=str(target), suffix='.webm', offset=0)
    result = subprocess.run([sys.executable, '-m', 'study_workbench', '--download-media'],
                            input=json.dumps(options).encode() + b'\n', cwd=root / 'backend',
                            capture_output=True, timeout=10, creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0)
    assert result.returncode == 0
    value = json.loads(result.stdout)
    assert 'error' in value and 'secret' not in value['error']
    assert not target.exists()


def test_complete_verified_partial_can_finish_publication_after_interruption_without_network(monkeypatch, tmp_path):
    with client(tmp_path) as c:
        monkeypatch.setattr(c.app.state.downloads.pool, 'submit', lambda *args: None)
        identifier = c.post(PREFIX + '/media-downloads', json=body()).json()['id']
        with write_transaction(c.app.state.engine) as session:
            job = session.get(MediaDownloadJob, identifier)
            path = tmp_path / job.relative_path
            path.parent.mkdir(parents=True)
            path.write_bytes(RAW)
            job.status = 'interrupted'
            job.progress = dict(received=len(RAW), total=len(RAW), etag='"v1"', partial_sha256=hashlib.sha256(RAW).hexdigest())
        monkeypatch.undo()
        def no_network(*args):
            raise AssertionError('Already complete data must not request Range beyond EOF')
        monkeypatch.setattr(MediaDownloads, 'child', no_network)
        assert c.post(f'{PREFIX}/media-downloads/{identifier}/retry', json={'mode': 'resume'}).status_code == 200
        result = wait(c, identifier, {'ready', 'failed'})
        assert result['status'] == 'ready', result
        assert result['progress']['received'] == len(RAW) and path.read_bytes() == RAW


def test_removed_target_stops_running_download_without_losing_partial(monkeypatch, tmp_path):
    entered, release = Event(), Event()
    def pending(self, job, path):
        path.write_bytes(RAW[:32])
        entered.set()
        assert release.wait(5)
        self.check(job.id)
        raise AssertionError('Removed folder must stop the task')
    monkeypatch.setattr(MediaDownloads, 'child', pending)
    with client(tmp_path) as c:
        folder = c.post(PREFIX + '/nodes', json={'kind': 'folder', 'name': '下载目录'}).json()['resource_item_id']
        try:
            identifier = c.post(PREFIX + '/media-downloads', json={**body(), 'parent_id': folder}).json()['id']
            assert entered.wait(5)
            with write_transaction(c.app.state.engine) as session:
                session.get(WorkspaceNode, folder).removed_at = '2026-11-05T00:00:00+00:00'
        finally:
            release.set()
        assert wait(c, identifier, {'failed'})['result'] == {}
        with Session(c.app.state.engine) as session:
            assert (tmp_path / session.get(MediaDownloadJob, identifier).relative_path).read_bytes() == RAW[:32]
