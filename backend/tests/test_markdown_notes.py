import hashlib
import io
import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from zipfile import ZipFile

from alembic import command
from alembic.config import Config
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from study_workbench import markdown_notes
from study_workbench.content import DEMO, SUBJECTIVE
from study_workbench.db import MarkdownNoteCreation, Resource, WorkspaceNode, database
from test_explorer import PREFIX, assert_preserved, client, snapshot

URL = PREFIX + '/markdown-notes'


def create(c, request='note-create-request-1', name='课程笔记.md', parent=None):
    return c.post(URL, json={'request_id': request, 'name': name, 'parent_id': parent})


def test_create_edit_retry_restart_and_original_history(tmp_path):
    with client(tmp_path) as c:
        result = create(c)
        assert result.status_code == 200, result.text
        note = result.json()
        node = note['resource_item_id']
        doc_url = f'{PREFIX}/nodes/{node}/document'
        initial = c.get(doc_url).json()
        assert initial['type'] == 'markdown' and initial['working_copy']
        assert '# 课程笔记\n' in initial['text']
        assert c.get(PREFIX + '/notes').json() == []
        assert create(c).json()['resource_item_id'] == node
        saved = c.put(doc_url, json={'expected_sha256': initial['sha256'], 'text': '我的自由笔记'})
        assert saved.status_code == 200
        assert c.put(doc_url, json={'expected_sha256': initial['sha256'], 'text': '过时覆盖'}).status_code == 409
        assert create(c).json()['resource_item_id'] == node
        assert c.get(doc_url).json()['text'] == '我的自由笔记'
        # Legacy resource export retains the original; free-note workfiles need LW-05 full backup.
        exported = c.get(PREFIX + '/export')
        assert exported.status_code == 200
        with ZipFile(io.BytesIO(exported.content)) as archive:
            assert archive.read(f"resources/{note['source_resource_id']}.bin").decode() == initial['text']
        assert c.get(PREFIX + f"/resources/{note['source_resource_id']}").content.decode() == initial['text']
    with client(tmp_path) as c:
        assert c.get(doc_url).json()['text'] == '我的自由笔记'
        assert create(c).json()['resource_item_id'] == node
        assert c.get(URL + '/requests/note-create-request-1').json()['status'] == 'ready'
        assert len(c.get(URL + '/requests').json()) == 1
        assert c.delete(f'{PREFIX}/nodes/{node}').status_code == 200
        assert create(c).json()['status'] == 'removed'
        assert c.get(PREFIX + '/nodes').json() == []


def test_creation_scope_validation_and_same_name_independence(tmp_path):
    with client(tmp_path) as c:
        folder = c.post(PREFIX + '/nodes', json={'kind': 'folder', 'name': '笔记'}).json()['resource_item_id']
        a = create(c, parent=folder).json()
        b = create(c, request='note-create-request-2', parent=folder).json()
        assert a['resource_item_id'] != b['resource_item_id']
        assert a['source_resource_id'] != b['source_resource_id']
        assert b['name'] == '课程笔记.md (2)'
        assert create(c, parent=None).status_code == 409
        assert create(c, request='note-create-request-3', parent=a['resource_item_id']).status_code == 422
        other = c.post('/api/workspaces', json={'name': '隔离'}).json()['id']
        assert c.get(f'/api/workspaces/{other}/markdown-notes/requests/note-create-request-1').status_code == 404
        assert c.get(f'/api/workspaces/{other}/markdown-notes/requests').json() == []
        assert c.post(f'/api/workspaces/{other}/markdown-notes', json={
            'request_id': 'note-create-request-1', 'name': '笔记.md', 'parent_id': folder}).status_code == 404
        assert c.post(URL, headers={'Origin': 'https://example.com'}, json={}).status_code == 403
        assert c.get(URL + '/requests', headers={'Authorization': 'bad'}).status_code == 401
        for name in ['../x.md', 'CON.md', 'x.txt', '', 'x.md ', '<script>.md']:
            assert create(c, name=name).status_code == 422
        assert c.post(URL, json={'request_id': 'short', 'name': 'x.md'}).status_code == 422
        assert c.post(URL, json={'request_id': 'note-create-request-3', 'name': 'x.md', 'text': 'extra'}).status_code == 422
        assert c.get(URL + '/requests?limit=101').status_code == 422
        assert c.get(URL + '/requests?offset=-1').status_code == 422
        assert c.delete(f'{PREFIX}/nodes/{folder}').status_code == 200
        assert create(c, request='note-create-request-4', parent=folder).status_code == 409
        assert c.request('DELETE', f'/api/workspaces/{other}', json={'confirm_name': '隔离'}).status_code == 200
        assert c.get(f'/api/workspaces/{other}/markdown-notes/requests').status_code == 404


def test_partial_creation_bytes_survive_restart_and_resume(tmp_path, monkeypatch):
    actual = markdown_notes.write_new
    failed = False

    def fail_work(path, data):
        nonlocal failed
        if 'working' in path.parts and not failed:
            failed = True
            raise HTTPException(409, '模拟磁盘拒写')
        return actual(path, data)

    with client(tmp_path) as c:
        monkeypatch.setattr(markdown_notes, 'write_new', fail_work)
        assert create(c).status_code == 409
        receipt = c.get(URL + '/requests/note-create-request-1').json()
        assert receipt['status'] == 'interrupted'
        assert c.get(PREFIX + '/nodes').json() == []
        files = list((tmp_path / 'workspaces/default/originals').glob('*.md'))
        assert len(files) == 1
        original = files[0].read_bytes()
    monkeypatch.setattr(markdown_notes, 'write_new', actual)
    with client(tmp_path) as c:
        note = create(c).json()
        assert note['status'] == 'ready'
        assert files[0].read_bytes() == original
        assert c.get(f"{PREFIX}/nodes/{note['resource_item_id']}/document").json()['text'].encode() == original


def test_tampered_partial_file_is_never_overwritten(tmp_path, monkeypatch):
    actual = markdown_notes.write_new

    def corrupt(path, data):
        actual(path, data)
        path.write_bytes(b'foreign data')

    with client(tmp_path) as c:
        monkeypatch.setattr(markdown_notes, 'write_new', corrupt)
        assert create(c).status_code == 409
        assert c.get(URL + '/requests/note-create-request-1').json()['status'] == 'conflict'
        files = list((tmp_path / 'workspaces/default/originals').glob('*.md'))
        assert len(files) == 1 and files[0].read_bytes() == b'foreign data'
        monkeypatch.setattr(markdown_notes, 'write_new', actual)
        assert create(c).status_code == 409
        assert files[0].read_bytes() == b'foreign data'
        assert c.get(PREFIX + '/nodes').json() == []


def test_concurrent_same_request_returns_one_node(tmp_path):
    with client(tmp_path) as c:
        with ThreadPoolExecutor(max_workers=3) as pool:
            results = list(pool.map(lambda _: create(c), range(3)))
        assert all(r.status_code == 200 for r in results)
        assert len({r.json()['resource_item_id'] for r in results}) == 1
        with Session(c.app.state.engine) as session:
            assert len(list(session.scalars(select(MarkdownNoteCreation)))) == 1
            assert len(list(session.scalars(select(WorkspaceNode)))) == 1
            assert len(list(session.scalars(select(Resource)))) == 1


def test_failed_final_registration_rolls_back_and_reuses_preserved_bytes(tmp_path, monkeypatch):
    actual = markdown_notes.insert_node

    def fail_after_insert(*args, **kwargs):
        actual(*args, **kwargs)
        raise HTTPException(409, '模拟登记后事务失败')

    with client(tmp_path) as c:
        monkeypatch.setattr(markdown_notes, 'insert_node', fail_after_insert)
        assert create(c).status_code == 409
        assert c.get(URL + '/requests/note-create-request-1').json()['status'] == 'interrupted'
        with Session(c.app.state.engine) as session:
            assert list(session.scalars(select(WorkspaceNode))) == []
            assert list(session.scalars(select(Resource))) == []
        files = {path: path.read_bytes() for path in (tmp_path / 'workspaces').glob('**/*.md')}
        assert len(files) == 2
        monkeypatch.setattr(markdown_notes, 'insert_node', actual)
        assert create(c).json()['status'] == 'ready'
        assert all(path.read_bytes() == data for path, data in files.items())


def test_upgrade_0012_preserves_rows_files_and_backup(tmp_path):
    root = tmp_path / 'old'
    root.mkdir()
    db_path = root / 'study.db'
    config = Config()
    config.set_main_option('script_location', str(Path(__file__).parents[1] / 'migrations'))
    engine = database(db_path)
    with engine.begin() as connection:
        connection.exec_driver_sql('BEGIN')
        config.attributes['connection'] = connection
        command.upgrade(config, '0012')
    engine.dispose()
    with sqlite3.connect(db_path) as db:
        for content in (DEMO, SUBJECTIVE):
            db.execute('INSERT INTO questions VALUES (?,?,?)', (content['id'], 'default', json.dumps(content)))
        db.execute("INSERT INTO resources VALUES ('old','default','old.txt','old.txt','hash',3,'text/plain')")
        db.execute("INSERT INTO notes VALUES ('old-note','default','old','旧笔记','[{\"type\":\"text\",\"text\":\"旧正文\"}]')")
    (root / 'old.txt').write_bytes(b'old')
    before = snapshot(db_path)
    with client(root) as c:
        after = snapshot(db_path)
        assert_preserved(before, after)
        assert c.get(PREFIX + '/notes').json()[0]['id'] == 'old-note'
        assert create(c).status_code == 200
    assert (root / 'old.txt').read_bytes() == b'old'
    backups = list((root / 'backups').glob('study-before-0016-*.db'))
    assert len(backups) == 1 and snapshot(backups[0]) == before
    with sqlite3.connect(db_path) as db:
        assert db.execute('PRAGMA integrity_check').fetchone() == ('ok',)
        assert db.execute('PRAGMA foreign_key_check').fetchall() == []
        assert db.execute('SELECT version_num FROM alembic_version').fetchone() == ('0016',)


def test_prepared_receipt_startup_does_not_blindly_replay(tmp_path):
    with client(tmp_path) as c:
        with c.app.state.engine.begin() as connection:
            connection.exec_driver_sql("INSERT INTO markdown_note_creations VALUES (?,?,?,?,?,?,?)", (
                'a' * 32, 'default', 'note-create-request-1', '{"name":"课程笔记.md","parent_id":null}',
                'b' * 32, 'prepared', None))
    with client(tmp_path) as c:
        assert c.get(URL + '/requests/note-create-request-1').json()['status'] == 'interrupted'
        assert not list((tmp_path / 'workspaces').glob('**/*.md'))
        assert create(c).status_code == 200


def test_ordinary_text_same_title_cannot_capture_new_note(tmp_path):
    from test_document_files import add

    with client(tmp_path) as c:
        _, _, source = add(c, tmp_path, '课程笔记.txt', '# 课程笔记\n'.encode())
        checksum = hashlib.sha256(source.read_bytes()).hexdigest()
        note = create(c).json()
        document = c.get(f"{PREFIX}/nodes/{note['resource_item_id']}/document").json()
        assert document['type'] == 'markdown' and document['working_copy']
        assert hashlib.sha256(source.read_bytes()).hexdigest() == checksum


def test_ready_receipt_does_not_hide_missing_original_or_recreate_node(tmp_path):
    with client(tmp_path) as c:
        note = create(c).json()
        with Session(c.app.state.engine) as session:
            resource = session.get(Resource, note['source_resource_id'])
            original = tmp_path / resource.relative_path
        # Simulate a missing source by moving the self-authored fixture; preserve its bytes.
        original.rename(original.with_suffix('.retained'))
        receipt = c.get(URL + '/requests/note-create-request-1').json()
        assert receipt['creation_status'] == 'ready' and receipt['status'] == 'missing'
        retry = create(c).json()
        assert retry['resource_item_id'] == note['resource_item_id'] and retry['status'] == 'missing'
        assert not original.exists()


def test_note_picker_uses_original_format_across_folders_renames_and_scope(tmp_path):
    from test_document_files import add

    with client(tmp_path) as c:
        folder = c.post(PREFIX + '/nodes', json={'kind': 'folder', 'name': '课程'}).json()['resource_item_id']
        node, _, _ = add(c, tmp_path, '旧笔记.MARKDOWN', b'# old', parent=folder)
        c.patch(f'{PREFIX}/nodes/{node}', json={'name': '已改名没有后缀', 'parent_id': folder})
        add(c, tmp_path, 'not-a-note.txt', b'text')
        rows = c.get(URL + '?limit=1').json()
        assert len(rows) == 1 and rows[0]['resource_item_id'] == node
        assert rows[0]['name'] == '已改名没有后缀'
        assert c.get(URL + '?offset=1&limit=1').json() == []
        other = c.post('/api/workspaces', json={'name': '其他'}).json()['id']
        assert c.get(f'/api/workspaces/{other}/markdown-notes').json() == []
        c.delete(f'{PREFIX}/nodes/{folder}')
        assert c.get(URL).json() == []
