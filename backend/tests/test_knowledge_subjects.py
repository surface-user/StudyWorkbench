import sqlite3
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from threading import Barrier

import pytest
from alembic import command, op
from study_workbench import backup_store
from study_workbench.migrate import migrate
from test_imports import SCOPE, client
from test_media_sources import config, legacy_library

SUBJECTS = SCOPE + '/knowledge/subjects'


def test_subject_history_retries_scope_and_backup(tmp_path):
    root = tmp_path / 'source'
    create = {'name': '  分析  ', 'request_id': 'create_subject_0001'}
    rename = {'name': '分析基础', 'expected_revision': 1, 'request_id': 'rename_subject_0001'}
    remove = {'confirm': True, 'expected_revision': 2, 'request_id': 'remove_subject_0001'}
    with client(root) as c:
        assert c.get(SUBJECTS).json() == []
        for invalid in ('  ', '\x00x', '题' * 501):
            assert c.post(SUBJECTS, json=dict(create, name=invalid)).status_code == 422
        stats_before = c.get(SCOPE + '/statistics').json()
        first = c.post(SUBJECTS, json=create).json()
        path = SUBJECTS + '/' + first['id']
        assert first['name'] == '分析' and first['revision'] == 1
        assert c.post(SUBJECTS, json=dict(create, request_id='create_subject_0002')).status_code == 409
        assert c.post(SUBJECTS, json=dict(create, name='代数')).status_code == 409
        other = c.post('/api/workspaces', json={'name': '另一个'}).json()['id']
        other_subjects = f'/api/workspaces/{other}/knowledge/subjects'
        assert c.post(other_subjects, json=create).status_code == 200
        foreign = other_subjects + '/' + first['id']
        assert c.post(foreign + '/rename', json=dict(rename, request_id=create['request_id'])).status_code == 404
        assert c.get(foreign + '/revisions').status_code == 404
        second = c.post(path + '/rename', json=rename).json()
        assert second == dict(first, name='分析基础', revision=2)
        assert c.post(path + '/rename', json=dict(rename, request_id='rename_subject_0002')).status_code == 409
        assert c.post(path + '/remove', json=dict(remove, confirm=False)).status_code == 422
        assert c.post(path + '/remove', json=dict(remove, confirm=1)).status_code == 422
        final = c.post(path + '/remove', json=remove).json()
        assert final == dict(second, revision=3, removed=True)
        assert c.post(path + '/remove', json=remove).json() == final
        assert c.post(SUBJECTS, json=create).json() == first
        assert c.post(path + '/rename', json=rename).json() == second
        assert c.get(SUBJECTS).json() == []
        new = c.post(SUBJECTS, json=dict(create, name=final['name'], request_id='create_subject_0003')).json()
        assert new['id'] != first['id']
        assert c.get(SUBJECTS).json() == [new]
        assert c.get(SCOPE + '/statistics').json() == stats_before

    package = tmp_path / 'library.zip'
    backup_store.create_backup(root, package)
    copy = tmp_path / 'restored'
    assert backup_store.restore_backup(package, copy, tmp_path / 'settings.json')['schema_revision'] == '0023'
    for library in (root, copy):
        with client(library) as c:
            assert c.get(SUBJECTS).json() == [new]
            history = c.get(path + '/revisions').json()
            assert [r['action'] for r in history] == ['remove', 'rename', 'create']
            assert c.get(path + '/revisions?before=3&limit=1').json() == [history[1]]
            assert c.post(SUBJECTS, json=create).json() == first
        with closing(sqlite3.connect(library / 'study.db')) as db:
            with pytest.raises(sqlite3.IntegrityError, match='append only'):
                db.execute('DELETE FROM knowledge_subject_revisions')


def test_concurrent_same_name_and_stale_revision(tmp_path):
    with client(tmp_path / 'library') as c:
        def race(endpoint, bodies):
            barrier = Barrier(2)

            def send(body):
                barrier.wait(timeout=10)
                return c.post(endpoint, json=body)

            with ThreadPoolExecutor(2) as pool:
                return list(pool.map(send, bodies))

        results = race(SUBJECTS, [dict(name='新科目', request_id=f'concurrent_create_{i}') for i in range(2)])
        assert sorted(r.status_code for r in results) == [200, 409]
        subject, = c.get(SUBJECTS).json()
        path = SUBJECTS + '/' + subject['id']
        results = race(path + '/rename', [dict(name=f'新名称{i}', expected_revision=1,
                                               request_id=f'concurrent_rename_{i}') for i in range(2)])
        assert sorted(r.status_code for r in results) == [200, 409]
        assert len(c.get(path + '/revisions').json()) == 2


def test_backup_and_restore_refuse_conflicting_active_subjects_before_activation(tmp_path, monkeypatch):
    root = tmp_path / 'source'
    with client(root) as c:
        assert c.post(SUBJECTS, json=dict(name='重复', request_id='create_subject_0001')).status_code == 200
    with closing(sqlite3.connect(root / 'study.db')) as db:
        db.execute("""INSERT INTO knowledge_subject_revisions
            (workspace_id, subject_id, revision, previous_revision, request_id, action, name)
            VALUES ('default', 'another', 1, NULL, 'create_subject_0002', 'create', '重复')""")
        db.commit()
    with pytest.raises(ValueError, match='科目'):
        backup_store.create_backup(root, tmp_path / 'invalid.zip')
    assert not (tmp_path / 'invalid.zip').exists()
    # Produce a fixture with accurate bytes and table digests to reach the restore-side check.
    def database_summary(path, checkpoint):
        with closing(backup_store.connect(path)) as db:
            return '0023', backup_store.table_summary(db, checkpoint)

    package = tmp_path / 'inconsistent.zip'
    with monkeypatch.context() as patch:
        patch.setattr(backup_store, 'database_info', database_summary)
        backup_store.create_backup(root, package)
    config = tmp_path / 'settings.json'
    with pytest.raises(ValueError, match='科目'):
        backup_store.restore_backup(package, tmp_path / 'target', config)
    assert not config.exists()


@pytest.mark.parametrize('inject_failure', [False, True])
def test_0018_upgrade_retains_rows_and_pre_upgrade_backup(tmp_path, monkeypatch, inject_failure):
    root = tmp_path / 'legacy'
    engine, path = legacy_library(root)
    with engine.begin() as connection:
        connection.exec_driver_sql('BEGIN')
        cfg = config()
        cfg.attributes['connection'] = connection
        command.upgrade(cfg, '0018')
    with closing(backup_store.connect(path)) as db:
        before = backup_store.table_summary(db)
        old_columns = [row['name'] for row in db.execute('PRAGMA table_info(media_download_jobs)')]
    if inject_failure:
        execute = op.execute

        def fail_on_new_trigger(sql):
            if 'CREATE TRIGGER knowledge_subjects' in sql:
                raise RuntimeError('subject migration fault')
            return execute(sql)

        monkeypatch.setattr(op, 'execute', fail_on_new_trigger)
        with pytest.raises(RuntimeError, match='subject migration fault'):
            migrate(engine, path)
    else:
        migrate(engine, path)
    backup, = (root / 'backups').glob('study-before-0023-*.db')
    with closing(backup_store.connect(backup)) as db:
        assert backup_store.table_summary(db) == before
    with closing(backup_store.connect(path)) as db:
        after = backup_store.table_summary(db)
        if not inject_failure:
            # Migration 0022 appends one empty receipt column; compare every previously stored field.
            assert [r['name'] for r in db.execute('PRAGMA table_info(media_download_jobs)')] == [*old_columns, 'site_receipt']
            assert db.execute('SELECT count(*) FROM media_download_jobs WHERE site_receipt IS NOT NULL').fetchone()[0] == 0
            after.update(backup_store.table_summary(db, columns={'media_download_jobs': old_columns}))
        if inject_failure:
            assert after == before
        else:
            assert after.pop('knowledge_subject_revisions')['rows'] == 0
            assert after.pop('knowledge_point_revisions')['rows'] == 0
            assert after.pop('knowledge_link_revisions')['rows'] == 0
            assert after.pop('alembic_version')['rows'] == before.pop('alembic_version')['rows'] == 1
            assert after == before
            assert db.execute('SELECT version_num FROM alembic_version').fetchone()[0] == '0023'
    assert (root / 'retained.partial').read_bytes() == b'original failed attempt'
    engine.dispose()
