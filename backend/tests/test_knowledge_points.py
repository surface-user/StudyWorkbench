import sqlite3
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from threading import Barrier

import pytest
from alembic import command
from study_workbench import backup_store
from study_workbench.data_root import write_settings
from study_workbench.migrate import migrate
from test_imports import client
from test_knowledge_subjects import SUBJECTS
from test_media_sources import config, legacy_library


def body(key, **fields):
    return dict(request_id='knowledge_test_request_' + key, **fields)


def test_tree_receipts_scope_moves_removal_and_restore(tmp_path):
    root = tmp_path / 'original'
    with client(root) as c:
        subject = c.post(SUBJECTS, json=body('subject', name='数学')).json()['id']
        catalog = SUBJECTS + '/' + subject
        url = catalog + '/points'
        first = c.post(url, json=body('root', name='  分析  ')).json()
        assert first['name'] == '分析' and first['parent_id'] is None
        parent = first['id']
        assert c.post(url, json=body('dup', name='分析')).status_code == 409
        make_leaf = body('leaf', name='函数', parent_id=parent)
        leaf = c.post(url, json=make_leaf).json()
        path = url + '/' + leaf['id']
        assert c.get(url).json() == [first]
        assert c.get(url, params={'parent_id': parent}).json() == [leaf]
        assert c.get(url, params={'after_id': parent}).json() == []
        remove = body('remove', confirm=True, expected_revision=1)
        assert c.post(catalog + '/remove', json=remove).status_code == 409
        assert c.post(url + '/' + parent + '/remove', json=remove).status_code == 409
        assert c.post(url + '/' + parent + '/move', json=body('cycle', expected_revision=1, parent_id=leaf['id'])).status_code == 409
        second = c.post(SUBJECTS, json=body('subject2', name='其他')).json()['id']
        other = SUBJECTS + '/' + second + '/points'
        assert c.post(other, json=dict(make_leaf, request_id=body('foreign')['request_id'])).status_code == 404
        assert c.post(other, json=body('root', name='其他')).status_code == 409
        assert c.post(url, json=body('subject', name='x')).status_code == 409
        assert c.post(SUBJECTS, json=body('root', name='x')).status_code == 409
        workspace = c.post('/api/workspaces', json={'name': '第二空间'}).json()['id']
        assert c.get(path.replace('/default/', '/' + workspace + '/') + '/revisions').status_code == 404
        assert c.post(path + '/move', json=body('move', expected_revision=1)).status_code == 422
        moved = c.post(path + '/move', json=body('move', expected_revision=1, parent_id=None)).json()
        assert moved == dict(leaf, parent_id=None, revision=2)
        assert c.post(path + '/rename', json=body('stale', name='极限', expected_revision=1)).status_code == 409
        assert c.post(path + '/rename', json=body('collision', name='分析', expected_revision=2)).status_code == 409
        renamed = c.post(path + '/rename', json=body('rename', name='极限', expected_revision=2)).json()
        assert renamed == dict(moved, name='极限', revision=3)
        assert c.post(path + '/remove', json=dict(remove, confirm=False, expected_revision=3)).status_code == 422
        removed = c.post(path + '/remove', json=dict(remove, expected_revision=3)).json()
        assert removed == dict(renamed, revision=4, removed=True)
        assert c.post(url + '/' + parent + '/remove', json=body('remove1', confirm=True, expected_revision=1)).status_code == 200
        assert c.post(catalog + '/remove', json=body('remove_catalog', confirm=True, expected_revision=1)).status_code == 200
    package = tmp_path / 'backup.zip'
    restored = tmp_path / 'restored'
    backup_store.create_backup(root, package)
    assert backup_store.restore_backup(package, restored, tmp_path / 'settings.json')['schema_revision'] == '0023'
    for library in (root, restored):
        with client(library) as c:
            assert c.post(url, json=make_leaf).json() == leaf
            assert c.get(url).status_code == 404
            history = c.get(path + '/revisions').json()
            assert [r['action'] for r in history] == ['remove', 'rename', 'move', 'create']
            assert c.get(path + '/revisions?before=4&limit=2').json() == history[1:3]
        with closing(sqlite3.connect(library / 'study.db')) as db:
            with pytest.raises(sqlite3.IntegrityError, match='append only'):
                db.execute('DELETE FROM knowledge_point_revisions')


def test_concurrent_opposite_moves_and_backup_cycle(tmp_path, monkeypatch):
    root = tmp_path / 'source'
    with client(root) as c:
        subject = c.post(SUBJECTS, json=body('subject', name='课程')).json()['id']
        url = SUBJECTS + '/' + subject + '/points'
        ids = [c.post(url, json=body(name, name=name)).json()['id'] for name in ('A', 'B')]
        barrier = Barrier(2)

        def move(i):
            barrier.wait(timeout=10)
            return c.post(url + '/' + ids[i] + '/move', json=body(f'move{i}', parent_id=ids[1-i], expected_revision=1)).status_code

        with ThreadPoolExecutor(2) as pool:
            outcomes = list(pool.map(move, [0, 1]))
        assert sorted(outcomes) == [200, 409]
    rejected = outcomes.index(409)
    with closing(sqlite3.connect(root / 'study.db')) as db:
        db.execute('PRAGMA foreign_keys=ON')
        db.execute("""INSERT INTO knowledge_point_revisions
                      (workspace_id, subject_id, point_id, revision, previous_revision, parent_id, action, name, request_id)
                      VALUES ('default', ?, ?, 2, 1, ?, 'move', ?, 'fixture_corrupt_cycle')""",
                   (subject, ids[rejected], ids[1-rejected], ['A', 'B'][rejected]))
        db.commit()
        assert not db.execute('PRAGMA foreign_key_check').fetchall()
    package = tmp_path / 'broken.zip'
    with pytest.raises(ValueError, match='知识点'):
        backup_store.create_backup(root, package)
    assert not package.exists()

    def unchecked(path, checkpoint):
        with closing(backup_store.connect(path)) as db:
            return '0023', backup_store.table_summary(db, checkpoint)

    with monkeypatch.context() as patch:
        patch.setattr(backup_store, 'database_info', unchecked)
        backup_store.create_backup(root, package)
    settings = tmp_path / 'settings.json'
    write_settings(settings, root)
    previous = settings.read_bytes()
    with pytest.raises(ValueError, match='知识点'):
        backup_store.restore_backup(package, tmp_path / 'target', settings)
    assert settings.read_bytes() == previous


def test_0019_subjects_upgrade_without_inferred_points(tmp_path):
    library = tmp_path / 'old'
    engine, path = legacy_library(library)
    with engine.begin() as conn:
        conn.exec_driver_sql('BEGIN')
        cfg = config()
        cfg.attributes['connection'] = conn
        command.upgrade(cfg, '0019')
        conn.exec_driver_sql("""INSERT INTO knowledge_subject_revisions
            (workspace_id,subject_id,revision,request_id,action,name) VALUES ('default','s',1,'earlier','create','既有')""")
    with closing(backup_store.connect(path)) as db:
        before = backup_store.table_summary(db)
        old_columns = [row['name'] for row in db.execute('PRAGMA table_info(media_download_jobs)')]
    migrate(engine, path)
    with closing(backup_store.connect(path)) as db:
        after = backup_store.table_summary(db)
        # Migration 0022 appends one empty receipt column; compare every previously stored field.
        assert [r['name'] for r in db.execute('PRAGMA table_info(media_download_jobs)')] == [*old_columns, 'site_receipt']
        assert db.execute('SELECT count(*) FROM media_download_jobs WHERE site_receipt IS NOT NULL').fetchone()[0] == 0
        after.update(backup_store.table_summary(db, columns={'media_download_jobs': old_columns}))
    assert after.pop('knowledge_point_revisions')['rows'] == 0
    assert after.pop('knowledge_link_revisions')['rows'] == 0
    assert after.pop('alembic_version')['rows'] == before.pop('alembic_version')['rows'] == 1
    assert after == before
    assert (library / 'retained.partial').read_bytes() == b'original failed attempt'
    engine.dispose()
