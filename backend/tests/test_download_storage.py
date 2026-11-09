import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

import pytest
from study_workbench import recovery_storage as scan
from study_workbench.data_root import DataLock
from study_workbench.media_downloads import MediaDownloads
from test_explorer import PREFIX, client, make_0006
from test_library_integrity import snapshot
from test_media_downloads import RAW, body, completed, wait


def download_library(root, statuses=None, *, missing=False, archived=False):
    jobs = []
    with client(root) as c:
        c.app.state.downloads.pool.submit = lambda *args: None
        other = c.post('/api/workspaces', json={'name': 'Archived downloads'}).json()['id'] if archived else None
        for i, status in enumerate(sorted(statuses or scan.DOWNLOAD_STATUSES)):
            workspace = other if archived and i == 0 else 'default'
            result = c.post(f'/api/workspaces/{workspace}/media-downloads', json=body('storage-fixture-request-' + status, status + '.webm'))
            assert result.status_code == 200, result.text
            jobs.append(dict(id=result.json()['id'], status=status, workspace=workspace))
        if archived:
            assert c.request('DELETE', f'/api/workspaces/{other}', json={'confirm_name': 'Archived downloads'}).status_code == 200
    with sqlite3.connect(root / 'study.db') as db:
        for job in jobs:
            db.execute('UPDATE media_download_jobs SET status=? WHERE id=?', (job['status'], job['id']))
            relative = db.execute('SELECT relative_path FROM media_download_jobs WHERE id=?', (job['id'],)).fetchone()[0]
            job['path'] = root / relative
            if not missing:
                job['path'].parent.mkdir(parents=True, exist_ok=True)
                job['path'].write_bytes(b'retained ' + job['status'].encode())
    return jobs


def media_reference(root, relative, *, status='ready', workspace='default'):
    with sqlite3.connect(root / 'study.db') as db:
        db.execute('INSERT INTO media_entries (id,workspace_id,title,relative_path,mime,size,sha256,status,playback) '
                   'VALUES (?,?,?,?,?,?,?,?,?)', (uuid4().hex, workspace, 'private media title', relative,
                   'video/webm', 1, uuid4().hex * 2, status, '{}'))


def test_real_publication_dedup_restart_and_media_aliases_preserve_every_file(tmp_path, monkeypatch):
    monkeypatch.setattr(MediaDownloads, 'child', completed)
    with client(tmp_path) as c:
        first = c.post(PREFIX + '/media-downloads', json=body('storage-real-request-first', 'first.webm')).json()
        first = wait(c, first['id'], {'ready', 'failed'})
        assert first['status'] == 'ready', first
        second = c.post(PREFIX + '/media-downloads', json=body('storage-real-request-second', 'second.webm')).json()
        second = wait(c, second['id'], {'ready', 'failed'})
        assert second['status'] == 'ready' and second['result']['deduplicated'], second
        assert first['result']['media_id'] == second['result']['media_id']
        assert c.delete(f"{PREFIX}/nodes/{first['result']['resource_item_id']}").status_code == 200
        c.app.state.downloads.pool.submit = lambda *args: None
        third = c.post(PREFIX + '/media-downloads', json=body('storage-real-request-third', 'retained.webm')).json()['id']
        for _ in range(2):
            assert c.post(f'{PREFIX}/media-downloads/{third}/pause').status_code == 200
            assert c.post(f'{PREFIX}/media-downloads/{third}/retry', json={'mode': 'restart'}).status_code == 200
    with sqlite3.connect(tmp_path / 'study.db') as db:
        paths = dict(db.execute('SELECT id,relative_path FROM media_download_jobs'))
    directory = (tmp_path / paths[third]).parent
    directory.mkdir(parents=True)
    for name, data in {'1.webm': b'old authority', '2.webm': b'old attempt', '3.webm': b'current attempt',
                       '01.webm': b'noncanonical', '4.webm': b'future number', '2.mp4': b'other suffix',
                       'nested/1.webm': b'unknown nested evidence'}.items():
        path = directory / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    first_path = paths[first['id']]
    media_reference(tmp_path, first_path, status='failed')  # Multiple row references do not double byte totals.
    media_reference(tmp_path, (directory / '1.webm').relative_to(tmp_path).as_posix(), status='failed')
    before = snapshot(tmp_path)
    result = scan.report_download_storage(tmp_path)
    assert result['complete'], result
    assert result['media_reference_rows'] == 3 and result['media_referenced_paths'] == 2
    assert result['categories']['media_referenced_file'] == dict(file_count=2, logical_bytes=len(RAW) + len(b'old authority'))
    assert result['categories']['current_attempt_file'] == dict(file_count=2, logical_bytes=len(RAW) + len(b'current attempt'))
    assert result['categories']['lower_numbered_attempt_file'] == dict(file_count=1, logical_bytes=len(b'old attempt'))
    assert result['categories']['other_download_file']['file_count'] == 4
    largest = {i['relative_path']: i for i in result['largest_files']}
    assert largest[first_path]['media_reference_count'] == 2 and largest[first_path]['attempt_relation'] == 'current'
    old = largest[(directory / '1.webm').relative_to(tmp_path).as_posix()]
    assert old['role'] == 'media_referenced_file' and old['attempt_relation'] == 'lower_numbered'
    assert old['current_job_status'] == 'queued'  # Never invent an old-attempt status.
    assert result['attempt_history_checked'] is False and not result['deletion_authorized']
    assert snapshot(tmp_path) == before


def test_all_persisted_states_archived_exclusions_top_and_no_content_or_url_reads(tmp_path, monkeypatch):
    jobs = download_library(tmp_path, archived=True)
    folder = jobs[0]['path'].parent
    for n in range(25):
        (folder / f'other-{n}.bin').write_bytes(b'x' * n)
    os.link(folder / 'other-24.bin', folder / 'linked.bin')
    for kind in ['previews', 'working', 'media', 'originals', 'question-files', 'question-versions']:
        path = tmp_path / f'workspaces/default/{kind}/excluded.bin'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b'excluded authority')
    expected = {p.relative_to(tmp_path).as_posix(): p.stat().st_size for p in tmp_path.rglob('*')
                if p.is_file() and len(p.relative_to(tmp_path).parts) >= 4
                and p.relative_to(tmp_path).parts[0] == 'workspaces' and p.relative_to(tmp_path).parts[2] == 'downloads'}
    before = snapshot(tmp_path)
    real_open = Path.open
    real_connect = scan.connect

    def guarded(path, *args, **kwargs):
        assert path.name == '.study.lock', 'Download report opened business contents'
        return real_open(path, *args, **kwargs)

    def metadata_only_database(path):
        db = real_connect(path)
        private = {'media_download_jobs': {'source_url', 'name', 'progress', 'result', 'error', 'created_at'},
                   'media_entries': {'title', 'playback', 'sha256', 'size', 'mime'}}
        db.set_authorizer(lambda action, table, column, *_:
                          sqlite3.SQLITE_DENY if action == sqlite3.SQLITE_READ and column in private.get(table, set())
                          else sqlite3.SQLITE_OK)
        return db

    with monkeypatch.context() as patch:
        patch.setattr(Path, 'open', guarded)
        patch.setattr(scan, 'connect', metadata_only_database)
        result = scan.report_download_storage(tmp_path)
    assert result['complete'], result
    assert result['records_by_status'] == {s: 1 for s in scan.DOWNLOAD_STATUSES}
    assert result['categories']['current_attempt_file']['file_count'] == 6
    assert result['logical_bytes'] == sum(expected.values()) and result['file_count'] == len(expected)
    assert sum(g['logical_bytes'] for g in result['categories'].values()) == result['logical_bytes']
    assert len(result['largest_files']) == 20 and result['largest_files_truncated']
    assert result['largest_files'] == sorted(result['largest_files'], key=lambda i: (-i['logical_bytes'], i['relative_path']))
    assert result['scope'] == 'download_attempt_files' and result['bytes_kind'] == 'observed_logical_lengths'
    for flag in ['data_modified', 'deletion_authorized', 'content_integrity_checked', 'library_health_checked', 'snapshot_atomic', 'attempt_history_checked']:
        assert result[flag] is False
    serialized = json.dumps(result)
    assert all(secret not in serialized for secret in ['private-test', 'example.com', 'private media title', str(tmp_path)])
    assert 'save_status' not in serialized and 'preview_status' not in serialized and 'reclaimable_bytes' not in result
    assert snapshot(tmp_path) == before


@pytest.mark.parametrize('status', sorted(scan.DOWNLOAD_STATUSES))
def test_missing_current_attempt_only_ready_requires_presence(tmp_path, status):
    download_library(tmp_path, [status], missing=True)
    before = snapshot(tmp_path)
    result = scan.report_download_storage(tmp_path)
    assert result['complete'] is (status != 'ready'), result
    assert result['missing_optional_download_files'] == int(status != 'ready')
    assert snapshot(tmp_path) == before


@pytest.mark.parametrize('status', ['ready', 'failed', 'importing', 'unknown'])
def test_media_reference_presence_overrides_nonready_job_and_merges_missing_paths(tmp_path, status):
    job = download_library(tmp_path, ['failed'], missing=True)[0]
    relative = job['path'].relative_to(tmp_path).as_posix()
    media_reference(tmp_path, relative, status=status)
    media_reference(tmp_path, relative, status='failed')
    before = snapshot(tmp_path)
    result = scan.report_download_storage(tmp_path)
    required = status in {'ready', 'unknown'}
    assert result['complete'] is (not required), result
    assert result['missing_optional_download_files'] == int(not required)
    assert result['media_reference_rows'] == 2 and result['media_referenced_paths'] == 1
    if required:
        assert any(i['code'] == 'missing_required_reference' for i in result['issues'])
    assert snapshot(tmp_path) == before


def test_media_path_without_download_job_still_has_priority_and_missing_ready_is_incomplete(tmp_path):
    with client(tmp_path):
        pass
    path = tmp_path / 'workspaces/default/downloads/legacy/authority.bin'
    path.parent.mkdir(parents=True)
    path.write_bytes(b'authority outside known attempt naming')
    media_reference(tmp_path, path.relative_to(tmp_path).as_posix())
    before = snapshot(tmp_path)
    result = scan.report_download_storage(tmp_path)
    assert result['complete'] and result['categories']['media_referenced_file']['file_count'] == 1
    assert result['largest_files'][0]['attempt_relation'] == 'other'
    assert snapshot(tmp_path) == before
    path.rename(tmp_path / 'retained-authority.bin')
    before = snapshot(tmp_path)
    assert not scan.report_download_storage(tmp_path)['complete'] and snapshot(tmp_path) == before


@pytest.mark.parametrize('fault', ['path', 'id', 'attempt_zero', 'attempt_text', 'workspace', 'status', 'suffix', 'leading_zero'])
def test_bad_job_metadata_never_demotes_independent_media_path_reference(tmp_path, fault):
    job = download_library(tmp_path, ['failed'])[0]
    relative = job['path'].relative_to(tmp_path).as_posix()
    media_reference(tmp_path, relative)
    with sqlite3.connect(tmp_path / 'study.db') as db:
        # Inject otherwise CHECK-protected corruption only into this disposable fixture.
        db.execute('PRAGMA ignore_check_constraints=ON')
        sql = {'path': "UPDATE media_download_jobs SET relative_path='../../outside/private.webm'",
               'id': "UPDATE media_download_jobs SET id='bad'", 'attempt_zero': 'UPDATE media_download_jobs SET attempt=0',
               'attempt_text': "UPDATE media_download_jobs SET attempt='bad'",
               'workspace': "UPDATE media_download_jobs SET workspace_id='foreign'",
               'status': "UPDATE media_download_jobs SET status='unknown'",
               'suffix': "UPDATE media_download_jobs SET relative_path=replace(relative_path,'.webm','.txt')",
               'leading_zero': "UPDATE media_download_jobs SET relative_path=replace(relative_path,'/1.webm','/01.webm')"}[fault]
        db.execute(sql)
    before = snapshot(tmp_path)
    result = scan.report_download_storage(tmp_path)
    assert not result['complete'] and result['issues'], result
    assert result['categories']['media_referenced_file']['file_count'] == 1
    assert result['largest_files'][0]['media_reference_count'] == 1
    assert all('outside' not in i['relative_path'] for i in result['largest_files'])
    assert snapshot(tmp_path) == before


@pytest.mark.parametrize('fault', ['path', 'workspace'])
def test_bad_media_reference_is_incomplete_and_not_followed(tmp_path, fault):
    job = download_library(tmp_path, ['failed'])[0]
    media_reference(tmp_path, '../../outside/private.webm' if fault == 'path' else job['path'].relative_to(tmp_path).as_posix(),
                    workspace='foreign' if fault == 'workspace' else 'default')
    before = snapshot(tmp_path)
    result = scan.report_download_storage(tmp_path)
    assert not result['complete'] and result['categories']['current_attempt_file']['file_count'] == 1
    assert snapshot(tmp_path) == before


@pytest.mark.parametrize('limit', ['ENTRY_LIMIT', 'ROW_LIMIT', 'SECONDS', 'ISSUE_LIMIT'])
def test_download_budget_is_explicit_and_leaves_all_bytes(tmp_path, monkeypatch, limit):
    download_library(tmp_path, ['failed'])
    if limit == 'ISSUE_LIMIT':
        with sqlite3.connect(tmp_path / 'study.db') as db:
            db.execute('PRAGMA ignore_check_constraints=ON')
            db.execute("UPDATE media_download_jobs SET status='unknown'")
    before = snapshot(tmp_path)
    monkeypatch.setattr(scan, limit, 0)
    result = scan.report_download_storage(tmp_path)
    assert not result['complete'] and 'limit_reason' in result
    assert snapshot(tmp_path) == before


def test_row_budget_includes_media_rows_and_outside_namespace_is_not_scanned(tmp_path, monkeypatch):
    job = download_library(tmp_path, ['failed'])[0]
    media_reference(tmp_path, 'workspaces/default/media/missing-but-excluded.webm')
    assert scan.report_download_storage(tmp_path)['complete']
    before = snapshot(tmp_path)
    monkeypatch.setattr(scan, 'ROW_LIMIT', 1)
    result = scan.report_download_storage(tmp_path)
    assert not result['complete'] and result['limit_reason'] == 'row_limit'
    assert result['rows_checked'] == 1 and snapshot(tmp_path) == before and job['path'].is_file()


def test_missing_locked_old_and_corrupt_library_never_create_or_migrate(tmp_path):
    absent = tmp_path / 'absent'
    with pytest.raises(ValueError):
        scan.report_download_storage(absent)
    assert not absent.exists()
    active = tmp_path / 'active'
    download_library(active, ['failed'])
    with DataLock(active), pytest.raises(RuntimeError):
        scan.report_download_storage(active)
    old = tmp_path / 'old'
    make_0006(old)
    before = snapshot(old)
    result = scan.report_download_storage(old)
    assert not result['complete'] and result['issues'] == [dict(code='unsupported_schema')]
    assert snapshot(old) == before
    (active / 'study.db').write_bytes(b'corrupt fixture')
    before = snapshot(active)
    assert not scan.report_download_storage(active)['complete'] and snapshot(active) == before


def test_windows_download_junction_is_not_expanded(tmp_path):
    if os.name != 'nt':
        pytest.skip('Windows junction boundary')
    download_library(tmp_path, ['failed'])
    downloads = tmp_path / 'workspaces/default/downloads'
    retained = downloads.with_name('retained-downloads')
    expected = {p.relative_to(downloads).as_posix(): p.read_bytes() for p in downloads.rglob('*') if p.is_file()}
    downloads.rename(retained)
    run = subprocess.run(['cmd', '/c', 'mklink', '/J', str(downloads), str(retained)], capture_output=True, timeout=15)
    assert run.returncode == 0, run.stderr.decode(errors='replace')
    result = scan.report_download_storage(tmp_path)
    assert not result['complete'] and result['file_count'] == 0
    assert any(i['code'] == 'reparse_point' for i in result['issues'])
    assert {p.relative_to(retained).as_posix(): p.read_bytes() for p in retained.rglob('*') if p.is_file()} == expected


def test_download_cli_requires_scope_rejects_other_operations_and_preserves_private_fields(tmp_path):
    download_library(tmp_path, ['failed'])
    command = [sys.executable, '-m', 'study_workbench', '--data-dir', str(tmp_path), '--report-download-storage']
    env = {**os.environ, 'PYTHONPATH': str(Path(__file__).parents[1]), 'PYTHONUTF8': '1'}
    before = snapshot(tmp_path)
    for flags in [[], ['--confirm-all-workspaces', '--config', str(tmp_path / 'config.json')],
                  ['--confirm-all-workspaces', '--media', str(tmp_path / 'movie.webm')],
                  ['--confirm-all-workspaces', '--parent-pipe'], ['--check-library'], ['--report-recovery-storage'],
                  ['--report-office-storage'], ['--backup-to', str(tmp_path / 'new.zip')],
                  ['--restore-backup', str(tmp_path / 'missing.zip')], ['--move-data', str(tmp_path / 'moved')]]:
        run = subprocess.run(command + flags, env=env, capture_output=True, timeout=40)
        assert run.returncode != 0 and snapshot(tmp_path) == before
    run = subprocess.run(command + ['--confirm-all-workspaces'], env=env, capture_output=True, timeout=40)
    assert run.returncode == 0, run.stderr.decode(errors='replace')
    assert all(secret not in run.stdout.decode('utf-8') for secret in ['private-test', 'example.com'])
    assert json.loads(run.stdout)['result']['scope'] == 'download_attempt_files'
    assert snapshot(tmp_path) == before and not (tmp_path / 'new.zip').exists()
