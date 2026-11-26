import sqlite3
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from threading import Barrier

import pytest
from study_workbench import backup_store
from study_workbench.data_root import write_settings
from test_imports import SCOPE, client
from test_knowledge_points import body
from test_knowledge_subjects import SUBJECTS
from test_question_files import preview, publish

LINKS = SCOPE + '/knowledge/links'


def point(c, name):
    subject = c.post(SUBJECTS, json=body(name + '_subject', name=name)).json()['id']
    url = SUBJECTS + '/' + subject + '/points'
    identifier = c.post(url, json=body(name + '_point', name=name)).json()['id']
    return dict(subject_id=subject, id=identifier), url + '/' + identifier


def test_material_question_receipts_after_removal_and_restore(tmp_path):
    root = tmp_path / 'source'
    with client(root) as c:
        ref, path = point(c, 'alpha')
        qid = 'demo-integral'
        proposal = c.get(SCOPE + '/questions/' + qid + '/file-preview').json()
        result = c.post(
            SCOPE + '/questions/' + qid + '/file',
            json=dict(
                expected_source_sha256=proposal['source_sha256'],
                expected_preview_sha256=proposal['preview_sha256'],
                confirm=True,
            ),
        )
        assert result.status_code == 200
        node = result.json()['resource_item_id']
        version = publish(c, node, preview(c, node)).json()
        snapshot_url = SCOPE + '/question-versions/' + version['id']
        snapshot = c.get(snapshot_url).json()
        question = body('q_link', source=ref, target=dict(kind='question', id=qid))
        file_link = body('file_link', source=ref, target=dict(kind='resource', id=node))
        q = c.post(LINKS, json=question).json()
        f = c.post(LINKS, json=file_link).json()
        assert q['target'] == question['target'] and f['target'] == file_link['target']
        assert c.post(LINKS, json=dict(question, target=file_link['target'])).status_code == 409
        assert c.post(LINKS, json=dict(question, target=dict(kind='question', id=node))).status_code == 404
        assert (
            c.post(
                LINKS, json=body('wrong_type', source=ref, target=dict(kind='question', id=node))
            ).status_code
            == 404
        )
        assert (
            c.post(
                LINKS, json=body('wrong_type2', source=ref, target=dict(kind='resource', id=qid))
            ).status_code
            == 404
        )
        assert c.post(SUBJECTS, json=body('q_link', name='collision')).status_code == 409
        assert (
            c.post(path + '/rename', json=body('q_link', name='collision', expected_revision=1)).status_code
            == 409
        )
        assert (
            c.post(LINKS, json=body('alpha_subject', source=ref, target=question['target'])).status_code
            == 409
        )
        assert (
            c.post(path + '/rename', json=body('rename', name='新名', expected_revision=1)).status_code == 200
        )
        assert c.get(snapshot_url).json() == snapshot
        assert c.delete(SCOPE + '/nodes/' + node).status_code == 200
        by_id = {row['id']: row for row in c.get(LINKS).json()}
        assert not by_id[f['id']]['available'] and by_id[q['id']]['available']
        assert c.post(LINKS, json=file_link).json() == f
        assert (
            c.post(path + '/remove', json=body('remove_point', expected_revision=2, confirm=True)).status_code
            == 200
        )
        assert all(
            not row['available']
            for row in c.get(LINKS, params={'subject_id': ref['subject_id'], 'point_id': ref['id']}).json()
        )
        revoke = body('revoke', expected_revision=1, confirm=True)
        address = LINKS + '/' + f['id'] + '/remove'
        assert c.post(address, json=dict(revoke, confirm=False)).status_code == 422
        assert c.post(address, json=dict(revoke, expected_revision=2)).status_code == 409
        removed = c.post(address, json=revoke).json()
        assert removed == dict(f, removed=True, revision=2)
        assert c.post(address, json=revoke).json() == removed
    package = tmp_path / 'all.zip'
    restored = tmp_path / 'restored'
    backup_store.create_backup(root, package)
    assert (
        backup_store.restore_backup(package, restored, tmp_path / 'settings.json')['schema_revision']
        == '0021'
    )
    for library in (root, restored):
        with client(library) as c:
            assert c.get(snapshot_url).json() == snapshot
            assert c.post(LINKS, json=file_link).json() == f
            assert c.get(LINKS + '/' + f['id'] + '/revisions').json() == [removed, f]
            assert c.get(LINKS).json() == [dict(q, available=False)]


def test_related_reverse_race_directed_and_workspace_scope(tmp_path):
    with client(tmp_path / 'library') as c:
        a, _ = point(c, 'first')
        b, _ = point(c, 'second')
        first = body('one', source=a, target=dict(kind='related', **b))
        second = body('two', source=b, target=dict(kind='related', **a))
        barrier = Barrier(2)

        def send(payload):
            barrier.wait(timeout=10)
            return c.post(LINKS, json=payload)

        with ThreadPoolExecutor(2) as pool:
            results = list(pool.map(send, [first, second]))
        assert sorted(r.status_code for r in results) == [200, 409]
        success = next(i for i, r in enumerate(results) if r.status_code == 200)
        row = results[success].json()
        assert (
            c.post(
                LINKS, json=dict([second, first][success], request_id=[first, second][success]['request_id'])
            ).json()
            == row
        )
        for key, source, target in [('d1', a, b), ('d2', b, a)]:
            response = c.post(
                LINKS, json=body(key, source=source, target=dict(kind='directed', label='先修', **target))
            )
            assert response.status_code == 200
            assert response.json()['source'] == source
        assert c.post(LINKS, json=body('self', source=a, target=dict(kind='related', **a))).status_code == 422
        other = c.post('/api/workspaces', json={'name': '另一个'}).json()['id']
        foreign = LINKS.replace('/default/', '/' + other + '/')
        assert c.post(foreign, json=first).status_code == 404
        assert c.get(foreign + '/' + row['id'] + '/revisions').status_code == 404
        assert c.get(foreign).json() == []
        page = c.get(LINKS + '?limit=1').json()
        assert len(page) == 1 and len(c.get(LINKS, params={'after_id': page[0]['id']}).json()) == 2
        assert (
            c.post(
                LINKS + '/' + row['id'] + '/remove', json=body('revoke', expected_revision=1, confirm=True)
            ).status_code
            == 200
        )
        assert (
            c.post(LINKS, json=body('again', source=a, target=dict(kind='related', **b))).json()['id']
            != row['id']
        )


def test_corrupt_removal_with_valid_foreign_keys_refused_before_restore(tmp_path, monkeypatch):
    root = tmp_path / 'source'
    with client(root) as c:
        a, _ = point(c, 'one')
        b, _ = point(c, 'two')
        row = c.post(
            LINKS, json=body('directed', source=a, target=dict(kind='directed', label='先修', **b))
        ).json()
    with closing(sqlite3.connect(root / 'study.db')) as db:
        db.execute('PRAGMA foreign_keys=ON')
        db.execute(
            """INSERT INTO knowledge_link_revisions
            (workspace_id,link_id,revision,previous_revision,request_id,subject_id,point_id,kind,label,target_subject_id,target_point_id)
            SELECT workspace_id,link_id,2,1,'corrupt_remove',subject_id,point_id,kind,'改写旧关系',target_subject_id,target_point_id
            FROM knowledge_link_revisions WHERE link_id=?""",
            (row['id'],),
        )
        db.commit()
        assert not db.execute('PRAGMA foreign_key_check').fetchall()
    package = tmp_path / 'bad.zip'
    with pytest.raises(ValueError, match='知识关联'):
        backup_store.create_backup(root, package)
    assert not package.exists()

    def unchecked(path, checkpoint):
        with closing(backup_store.connect(path)) as db:
            return '0021', backup_store.table_summary(db, checkpoint)

    with monkeypatch.context() as patch:
        patch.setattr(backup_store, 'database_info', unchecked)
        backup_store.create_backup(root, package)
    settings = tmp_path / 'settings.json'
    write_settings(settings, root)
    previous = settings.read_bytes()
    with pytest.raises(ValueError, match='知识关联'):
        backup_store.restore_backup(package, tmp_path / 'target', settings)
    assert settings.read_bytes() == previous
