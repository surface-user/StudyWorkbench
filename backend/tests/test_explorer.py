import hashlib
import json
import os
import shutil
import sqlite3
import time
from pathlib import Path
from threading import Event

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from study_workbench.app import create_app
from study_workbench.content import DEMO, SUBJECTIVE
from study_workbench.db import ResourceAddJob, database, write_transaction
from study_workbench.explorer import normalized_name

TOKEN = 'explorer-test-' * 4
PREFIX = '/api/workspaces/default'


def client(path):
    return TestClient(create_app(path, TOKEN), base_url='http://127.0.0.1',
                      headers={'Authorization': 'Bearer ' + TOKEN})


def wait_job(c, identifier):
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        job = c.get(f'{PREFIX}/resource-add-jobs/{identifier}').json()
        if job['status'] not in {'queued', 'running'}:
            return job
        time.sleep(.01)
    raise AssertionError('Copy did not complete')


def start(c, source, parent=None):
    response = c.post(PREFIX + '/resource-add-jobs', json={'source_path': str(source), 'parent_id': parent})
    assert response.status_code == 200, response.text
    return wait_job(c, response.json()['id'])


@pytest.mark.parametrize('value', ['', '.', '..', 'CON', 'aux.txt', 'Lpt¹.doc', 'x.', 'x ', 'a/b', 'a\\b', 'a:b', 'a\nx'])
def test_windows_names(value):
    with pytest.raises(ValueError):
        normalized_name(value)


@pytest.mark.skipif(os.name != 'nt', reason='Windows mapped-drive API')
def test_mapped_network_drive_is_rejected_before_reading(tmp_path, monkeypatch):
    import ctypes

    from fastapi import HTTPException
    from study_workbench.explorer import source_path

    monkeypatch.setattr(ctypes.windll.kernel32, 'GetDriveTypeW', lambda _: 4)

    def refuse_stat(_):
        raise AssertionError('Mapped network source must be rejected before filesystem access')

    monkeypatch.setattr(Path, 'lstat', refuse_stat)
    with pytest.raises(HTTPException) as error:
        source_path(str(tmp_path / 'mapped-source'), tmp_path / 'data')
    assert error.value.status_code == 422


def test_tree_names_move_scope_and_urls(tmp_path):
    with client(tmp_path / 'data') as c:
        def create(name, parent=None):
            return c.post(PREFIX + '/nodes', json={'kind': 'folder', 'name': name, 'parent_id': parent})
        first = create('资料').json()
        assert create('资料').json()['name'] == '资料 (2)'
        assert create('ABC').json()['name'] == 'ABC'
        assert create('abc').json()['name'] == 'abc (2)'
        parent = first['resource_item_id']
        child = create('子目录', parent).json()['resource_item_id']
        assert c.patch(f'{PREFIX}/nodes/{parent}', json={'name': '资料', 'parent_id': child}).status_code == 409
        assert c.patch(f'{PREFIX}/nodes/{child}', json={'name': '移动', 'parent_id': None}).json()['resource_item_id'] == child
        other = c.post('/api/workspaces', json={'name': '其他'}).json()['id']
        assert c.get(f'/api/workspaces/{other}/nodes/{parent}').status_code == 404
        assert c.post(f'/api/workspaces/{other}/nodes', json={'name': 'x', 'kind': 'folder', 'parent_id': parent}).status_code == 404
        for url in [None, 'file:///C:/x', 'http://example.com', 'https://127.0.0.1', 'https://a:b@example.com']:
            assert c.post(PREFIX + '/nodes', json={'name': '链接', 'kind': 'link', 'url': url}).status_code == 422
        link = c.post(PREFIX + '/nodes', json={'name': '网页', 'kind': 'link', 'url': 'https://example.com/a'}).json()
        assert c.post(PREFIX + '/nodes', json={'name': 'x', 'kind': 'folder', 'parent_id': link['resource_item_id']}).status_code == 422
        assert c.get(PREFIX + '/nodes', headers={'Origin': 'https://example.com'}).status_code == 403
        assert c.get(PREFIX + '/nodes', headers={'Authorization': 'bad'}).status_code == 401
        for i in range(8):
            create(f'page{i}')
        a = c.get(PREFIX + '/nodes?limit=3').json()
        b = c.get(PREFIX + '/nodes?limit=3&offset=3').json()
        assert len(a) == len(b) == 3
        assert not {n['resource_item_id'] for n in a} & {n['resource_item_id'] for n in b}


def test_managed_copy_hierarchy_duplicates_media_and_restart(tmp_path):
    source = tmp_path / '中文资料'
    (source / '子目录').mkdir(parents=True)
    (source / 'a.md').write_text('# 无答案资料', encoding='utf-8')
    (source / '子目录' / 'copy.md').write_bytes((source / 'a.md').read_bytes())
    (source / '讲义.pptx').write_bytes(b'opaque-no-parser-required')
    (source / '片段.webm').write_bytes(b'\x1aE\xdf\xa3' + b'fixture')
    originals = {p.relative_to(source).as_posix(): p.read_bytes() for p in source.rglob('*') if p.is_file()}
    root = tmp_path / 'data'
    with client(root) as c:
        job = start(c, source)
        assert job['status'] == 'completed', job
        assert len(job['results']) == 6
        assert sum(r['status'] == 'duplicate' for r in job['results']) == 1
        top = c.get(PREFIX + '/nodes').json()[0]
        children = c.get(PREFIX + '/nodes?parent_id=' + top['resource_item_id']).json()
        media = next(n for n in children if n['kind'] == 'media')
        assert c.get(f"{PREFIX}/media/{media['media_id']}/player").status_code == 200
        assert len(c.get(PREFIX + '/imports').json()) == 0
        assert len(c.get(PREFIX + '/questions').json()) == 2  # no auto-created questions
        blob = next(n for n in children if n['name'] == 'a.md')
        assert c.get(PREFIX + '/nodes/' + blob['resource_item_id']).json()['status'] == 'ready'
        with sqlite3.connect(root / 'study.db') as db:
            relative = db.execute('SELECT relative_path FROM resources WHERE id=?', (blob['resource_id'],)).fetchone()[0]
        path = root / relative
        path.write_bytes(b'x' * path.stat().st_size)
        assert c.get(PREFIX + '/nodes/' + blob['resource_item_id']).json()['status'] == 'conflict'
        path.unlink()  # test fixture only: prove missing original keeps identity
        assert c.get(PREFIX + '/nodes/' + blob['resource_item_id']).json()['status'] == 'missing'
        ids = {r['resource_item_id'] for r in job['results']}
    with client(root) as c:
        assert wait_job(c, job['id'])['results'] == job['results']
        assert len(ids) == 6
    assert {p.relative_to(source).as_posix(): p.read_bytes() for p in source.rglob('*') if p.is_file()} == originals


def test_cancel_mid_chunk_and_interrupted_restart(tmp_path, monkeypatch):
    source = tmp_path / 'source.bin'
    source.write_bytes(b'a' * (3 * 1024 * 1024))
    root = tmp_path / 'data'
    entered, release = Event(), Event()
    with client(root) as c:
        explorer = c.app.state.explorer
        original = explorer.check
        calls = 0

        def pause(identifier):
            nonlocal calls
            calls += 1
            if calls == 3:
                entered.set()
                assert release.wait(10)
            original(identifier)

        monkeypatch.setattr(explorer, 'check', pause)
        job = c.post(PREFIX + '/resource-add-jobs', json={'source_path': str(source)}).json()
        assert entered.wait(10)
        assert c.post(f"{PREFIX}/resource-add-jobs/{job['id']}/cancel").json()['cancel_requested']
        release.set()
        assert wait_job(c, job['id'])['status'] == 'cancelled'
        assert c.get(PREFIX + '/nodes').json() == []
        copied = list((root / 'workspaces/default/originals').glob('*'))
        assert len(copied) == 1 and copied[0].stat().st_size == 1024 * 1024
        with write_transaction(c.app.state.engine) as session:
            session.add(ResourceAddJob(id='interrupted', workspace_id='default', parent_id=None,
                                      source_path=str(source), status='running', cancel_requested=False, results=[]))
    with client(root) as c:
        assert c.get(PREFIX + '/resource-add-jobs/interrupted').json()['status'] == 'interrupted'
    assert source.stat().st_size == 3 * 1024 * 1024


def test_budgets_failures_and_source_changes(tmp_path, monkeypatch):
    from study_workbench import explorer as module
    source = tmp_path / 'source'
    source.mkdir()
    (source / 'bad.webm').write_bytes(b'bad')
    (source / 'ok.txt').write_bytes(b'hello')
    with client(tmp_path / 'data') as c:
        job = start(c, source)
        assert job['status'] == 'partial'
        assert any(r['status'] == 'failed' for r in job['results'])
        monkeypatch.setattr(module, 'NODE_LIMIT', 1)
        assert start(c, source)['status'] == 'failed'
        monkeypatch.setattr(module, 'NODE_LIMIT', 1000)
        monkeypatch.setattr(module, 'FILE_LIMIT', 2)
        assert start(c, source / 'ok.txt')['status'] == 'failed'
        monkeypatch.setattr(module, 'FILE_LIMIT', 128 * 1024 * 1024)
        original = c.app.state.explorer.check
        calls = 0

        def changed(identifier):
            nonlocal calls
            calls += 1
            if calls == 3:
                (source / 'ok.txt').write_bytes(b'changed-source')
            original(identifier)

        monkeypatch.setattr(c.app.state.explorer, 'check', changed)
        job = start(c, source / 'ok.txt')
        assert job['status'] == 'partial'
        assert '变化' in job['results'][0]['error']
        assert c.post(PREFIX + '/resource-add-jobs', json={'source_path': str(tmp_path / 'data')}).status_code == 422
        assert c.post(PREFIX + '/resource-add-jobs', json={'source_path': 'relative'}).status_code == 422


def test_reparse_points_rejected(tmp_path):
    import os
    import subprocess
    target, source = tmp_path / 'target', tmp_path / 'source'
    target.mkdir()
    source.mkdir()
    (target / 'secret.txt').write_text('fixture', encoding='utf-8')
    junction = source / 'junction'
    if os.name == 'nt':
        result = subprocess.run(['cmd', '/c', 'mklink', '/J', str(junction), str(target)], capture_output=True)
        assert result.returncode == 0
    else:
        junction.symlink_to(target, target_is_directory=True)
    with client(tmp_path / 'data') as c:
        assert c.post(PREFIX + '/resource-add-jobs', json={'source_path': str(junction)}).status_code == 422
        job = start(c, source)
        assert job['status'] == 'partial'
        assert any(r['status'] == 'failed' for r in job['results'])
        assert not list((tmp_path / 'data').rglob('secret.txt'))


def make_0006(root):
    root.mkdir()
    engine = database(root / 'study.db')
    config = Config()
    config.set_main_option('script_location', str(Path(__file__).parents[1] / 'migrations'))
    with engine.begin() as connection:
        config.attributes['connection'] = connection
        command.upgrade(config, '0006')
        for content in (DEMO, SUBJECTIVE):
            connection.execute(text('INSERT INTO questions (id,workspace_id,content) VALUES (:id,\'default\',:content)'),
                               {'id': content['id'], 'content': json.dumps(content)})
        connection.execute(text("UPDATE workspaces SET layout=:layout"), {'layout': '{"unknown":"草稿原文","tabs":[]}'})
        connection.exec_driver_sql("INSERT INTO resources VALUES ('r','default','CON','original.bin','hash',3,'application/octet-stream')")
        connection.exec_driver_sql("INSERT INTO media_entries VALUES ('m','default','con','media.bin','video/webm',4,'hash','ready','{}')")
        connection.exec_driver_sql("INSERT INTO attempts VALUES (12,'default','demo-proof','{\"text\":\"原作答\"}','pending_review',NULL,'2026-10-24',NULL,NULL)")
        connection.exec_driver_sql("INSERT INTO attempt_reviews VALUES (4,12,0.5,'旧评语','2026-10-24')")
        connection.exec_driver_sql("INSERT INTO import_jobs VALUES ('j','default','r','old','preview',NULL,'{\"draft\":\"候选草稿\"}','2026-10-24')")
        connection.exec_driver_sql("INSERT INTO notes VALUES ('n','default','r','笔记','[]')")
        connection.exec_driver_sql("INSERT INTO markdown_questions VALUES ('md','default','j',0,'r','r','旧MD','{}')")
        connection.exec_driver_sql("INSERT INTO study_tasks VALUES ('t','default','计划','[\"demo-proof\"]','2026-10-24')")
        connection.exec_driver_sql("INSERT INTO workspaces SELECT 'archived','归档',1,created_at,layout FROM workspaces WHERE id='default'")
    engine.dispose()
    (root / 'original.bin').write_bytes(b'old')
    return root / 'study.db'


def snapshot(path):
    with sqlite3.connect(path) as db:
        return {name: db.execute(f'SELECT * FROM "{name}" ORDER BY rowid').fetchall() for name, in db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name != 'alembic_version'")}


def assert_preserved(before, after):
    for name, rows in before.items():
        actual = after[name]
        if name == 'attempts' and rows and actual and len(actual[0]) == len(rows[0]) + 1:
            assert all(row[-1] is None for row in actual), 'Old attempts must not acquire invented version bindings'
            actual = [row[:-1] for row in actual]
        assert actual == rows, name


def test_0006_compatibility_backup_restore_and_sql_constraints(tmp_path):
    root = tmp_path / 'old'
    path = make_0006(root)
    before = snapshot(path)
    checksum = hashlib.sha256((root / 'original.bin').read_bytes()).hexdigest()
    with client(root) as c:
        nodes = c.get(PREFIX + '/nodes').json()
        assert {n['kind'] for n in nodes} == {'resource', 'media'}
        assert len({n['name'].casefold() for n in nodes}) == 2
        with sqlite3.connect(path) as db:
            assert db.execute('PRAGMA integrity_check').fetchone() == ('ok',)
            assert db.execute('PRAGMA foreign_key_check').fetchall() == []
            assert db.execute('SELECT version_num FROM alembic_version').fetchone() == ('0011',)
        with c.app.state.engine.begin() as conn:
            with pytest.raises(IntegrityError):
                conn.exec_driver_sql("INSERT INTO workspace_nodes(id,workspace_id,kind,name,name_key,resource_id) VALUES ('bad','default','folder','x','x','r')")
            with pytest.raises(IntegrityError):
                conn.exec_driver_sql("INSERT INTO workspace_nodes(id,workspace_id,kind,name,name_key,resource_id) VALUES ('bad2','archived','resource','x','x','r')")
    after = snapshot(path)
    assert_preserved(before, after)
    assert hashlib.sha256((root / 'original.bin').read_bytes()).hexdigest() == checksum
    with client(root) as c:
        assert c.get(PREFIX + '/nodes').json() == nodes
    backup = list((root / 'backups').glob('study-before-0011-*.db'))
    assert len(backup) == 1 and snapshot(backup[0]) == before
    restore = tmp_path / 'restore'
    restore.mkdir()
    shutil.copy2(backup[0], restore / 'study.db')
    with client(restore):
        restored = snapshot(restore / 'study.db')
        assert_preserved(before, restored)


def test_copy_failure_receipt_and_legacy_service_adaptation(tmp_path, monkeypatch):
    source = tmp_path / 'fixture.txt'
    source.write_text('fixture', encoding='utf-8')
    root = tmp_path / 'data'
    with client(root) as c:
        legacy = c.post(PREFIX + '/imports?filename=legacy.txt', content=b'old-import').json()
        rows = c.get(PREFIX + '/nodes').json()
        assert len(rows) == 1 and rows[0]['resource_id'] == legacy['resource_id']
        assert c.get(PREFIX + '/nodes').json() == rows
        from sqlalchemy import event

        def fail(_, cursor, statement, parameters, context, many):
            if statement.startswith('INSERT INTO resources'):
                raise RuntimeError('injected registration failure')

        event.listen(c.app.state.engine, 'before_cursor_execute', fail)
        try:
            job = start(c, source)
            assert job['status'] == 'failed'
            assert len(job['results']) == 1 and job['results'][0]['status'] == 'failed'
            receipt = job['results'][0]['copied_path']
            assert (root / receipt).read_bytes() == source.read_bytes()
            assert c.get(PREFIX + '/nodes').json() == rows
        finally:
            event.remove(c.app.state.engine, 'before_cursor_execute', fail)
        successful = start(c, source)
        assert successful['status'] == 'completed'
        copied = root / successful['results'][0]['copied_path']
        copied.write_bytes(b'xxxxxxx')
        duplicate = start(c, source)
        assert duplicate['status'] == 'partial'
        assert '旧文件缺失或冲突' in duplicate['results'][0]['error']


def test_depth_total_budget_and_queued_cancellation(tmp_path, monkeypatch):
    from study_workbench import explorer as module
    source = tmp_path / 'fixture.txt'
    source.write_bytes(b'content')
    directory = tmp_path / 'deep'
    directory.mkdir()
    cursor = directory
    for _ in range(33):
        cursor = cursor / 'd'
        cursor.mkdir()
    entered, release = Event(), Event()
    with client(tmp_path / 'data') as c:
        monkeypatch.setattr(module, 'TOTAL_LIMIT', 2)
        assert start(c, source)['status'] == 'failed'
        monkeypatch.setattr(module, 'TOTAL_LIMIT', 1024 * 1024 * 1024)
        assert start(c, directory)['status'] == 'failed'
        original = c.app.state.explorer.check

        def pause(identifier):
            entered.set()
            assert release.wait(10)
            original(identifier)

        monkeypatch.setattr(c.app.state.explorer, 'check', pause)
        first = c.post(PREFIX + '/resource-add-jobs', json={'source_path': str(source)}).json()['id']
        assert entered.wait(10)
        queued = c.post(PREFIX + '/resource-add-jobs', json={'source_path': str(source)}).json()['id']
        assert c.post(PREFIX + '/resource-add-jobs/' + queued + '/cancel').status_code == 200
        release.set()
        assert wait_job(c, first)['status'] == 'completed'
        assert wait_job(c, queued)['status'] == 'cancelled'


def test_head_failure_preserves_old_database_and_backup(tmp_path, monkeypatch):
    root = tmp_path / 'old'
    path = make_0006(root)
    before = snapshot(path)
    upgrade = command.upgrade

    def interrupted(config, revision):
        upgrade(config, revision)
        raise RuntimeError('injected failure after directory/workfile DDL/backfill')

    monkeypatch.setattr(command, 'upgrade', interrupted)
    with pytest.raises(RuntimeError, match='injected'):
        create_app(root, TOKEN)
    assert snapshot(path) == before
    with sqlite3.connect(path) as db:
        assert db.execute('SELECT version_num FROM alembic_version').fetchone() == ('0006',)
    backup = list((root / 'backups').glob('*.db'))
    assert len(backup) == 1 and snapshot(backup[0]) == before


@pytest.mark.parametrize('revision', ['0002', '0003', '0004', '0005'])
def test_intermediate_revision_preserves_every_old_column(tmp_path, revision):
    root = tmp_path / revision
    root.mkdir()
    engine = database(root / 'study.db')
    config = Config()
    config.set_main_option('script_location', str(Path(__file__).parents[1] / 'migrations'))
    with engine.begin() as connection:
        config.attributes['connection'] = connection
        command.upgrade(config, revision)
        for content in (DEMO, SUBJECTIVE):
            connection.execute(text('INSERT INTO questions VALUES (:id,\'default\',:content)'),
                               dict(id=content['id'], content=json.dumps(content)))
        connection.exec_driver_sql("INSERT INTO attempts(id,workspace_id,question_id,response,status,score,created_at) "
                                   "VALUES (91,'default','demo-proof','{\"text\":\"保留原作答\"}','pending_review',NULL,'2026-10-24')")
    engine.dispose()
    before = snapshot(root / 'study.db')
    with sqlite3.connect(root / 'study.db') as db:
        columns = {table: ','.join('"' + row[1] + '"' for row in db.execute(f'PRAGMA table_info("{table}")')) for table in before}
    with client(root):
        with sqlite3.connect(root / 'study.db') as db:
            for table, rows in before.items():
                assert db.execute(f'SELECT {columns[table]} FROM "{table}" ORDER BY rowid').fetchall() == rows
            assert db.execute('PRAGMA foreign_key_check').fetchall() == []
    backup = list((root / 'backups').glob('study-before-0011-*.db'))
    assert len(backup) == 1 and snapshot(backup[0]) == before


def test_fresh_workspace_is_resource_first_and_restart_keeps_renamed_layout(tmp_path):
    with client(tmp_path) as c:
        state = c.get('/api/workbench').json()
        assert state['workspaces'][0]['name'] == '我的学习空间'
        assert c.get(PREFIX + '/layout').json() == {'version': 1, 'tabs': [], 'closed_tabs': [], 'active_tab_id': None}
        assert c.patch('/api/workspaces/default', json={'name': '自定义'}).status_code == 200
        layout = {'version': 1, 'tabs': [{'id': 'legacy', 'kind': 'question', 'draft': '保留草稿'}],
                  'closed_tabs': [], 'active_tab_id': 'legacy'}
        assert c.put(PREFIX + '/layout', json=layout).status_code == 200
    with client(tmp_path) as c:
        assert c.get('/api/workbench').json()['workspaces'][0]['name'] == '自定义'
        assert c.get(PREFIX + '/layout').json()['tabs'][0]['draft'] == '保留草稿'
