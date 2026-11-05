import hashlib
import io
import json
import sqlite3
import struct
from pathlib import Path

import pypdfium2 as pdfium
import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from study_workbench.db import DocumentPreview, database
from study_workbench.media_duration import duration_ms
from test_document_files import add, working
from test_explorer import PREFIX, TOKEN, assert_preserved, client, make_0006, snapshot

URL = PREFIX + '/learning-marks'


def capture(c, node, **position):
    return c.post(f'{PREFIX}/nodes/{node}/learning-anchor', json=position)


def anchor(c, node, line=1):
    doc = c.get(f'{PREFIX}/nodes/{node}/document').json()
    response = capture(c, node, kind='text_line', line=line, expected_sha256=doc['sha256'])
    assert response.status_code == 200, response.text
    return response.json()


def mark(c, location, request='learning-mark-request-1', **extra):
    return c.post(URL, json={'request_id': request, 'anchor': location, 'title': '我的疑问', 'note': '需要回看', **extra})


def test_bookmarks_revisions_rename_move_content_change_and_restart(tmp_path):
    with client(tmp_path) as c:
        node, _, original = add(c, tmp_path, '笔记.md', '首行\r\n中文第二行\n'.encode())
        working(c, node)
        point = anchor(c, node, 2)
        assert point['line_sha256'] == hashlib.sha256('中文第二行'.encode()).hexdigest()
        saved = mark(c, point)
        assert saved.status_code == 200, saved.text
        saved = saved.json()
        identifier = saved['id']
        assert mark(c, point).json()['id'] == identifier
        assert mark(c, point, title='其他请求内容').status_code == 409
        assert mark(c, point, request='learning-mark-request-2').status_code == 200
        assert len(c.get(URL).json()) == 2
        folder = c.post(PREFIX + '/nodes', json={'kind': 'folder', 'name': '移动目标'}).json()['resource_item_id']
        assert c.patch(f'{PREFIX}/nodes/{node}', json={'name': '重命名', 'parent_id': folder}).status_code == 200
        detail = c.get(URL + '/' + identifier).json()
        assert detail['location']['status'] == 'valid'
        assert detail['location']['resource']['name'] == '重命名'
        edited = c.patch(URL + '/' + identifier, json={'expected_revision': 1, 'title': '已改标题'})
        assert edited.status_code == 200 and edited.json()['revision'] == 2
        assert c.patch(URL + '/' + identifier, json={'expected_revision': 1, 'note': '陈旧'}).status_code == 409
        assert c.put(f'{PREFIX}/nodes/{node}/document', json={'expected_sha256': point['content_sha256'], 'text': '首行\n修改后'}).status_code == 200
        assert c.get(URL + '/' + identifier).json()['location']['status'] == 'content_changed'
        assert mark(c, point, request='learning-mark-request-3').status_code == 409
        newer = anchor(c, node, 2)
        assert c.patch(URL + '/' + identifier, json={'expected_revision': 2, 'anchor': newer}).status_code == 200
        history = c.get(URL + '/' + identifier + '/revisions').json()
        assert [r['revision'] for r in history] == [2, 1]
        assert all(r['content']['anchor'] == point for r in history)
        assert original.read_bytes() == '首行\r\n中文第二行\n'.encode()
    with client(tmp_path) as c:
        assert c.get(URL + '/' + identifier).json()['location']['status'] == 'valid'
        assert c.delete(f'{PREFIX}/nodes/{node}').status_code == 200
        assert c.get(URL + '/' + identifier).json()['location']['status'] == 'removed'
        assert len(c.get(URL).json()) == 2
        assert c.request('DELETE', URL + '/' + identifier, json={'expected_revision': 3}).status_code == 200
        assert len(c.get(URL).json()) == 1
        assert mark(c, point).json()['removed_at'] is not None
        with c.app.state.engine.begin() as conn:
            with pytest.raises(IntegrityError):
                conn.exec_driver_sql('DELETE FROM learning_marks WHERE id=?', (identifier,))
            with pytest.raises(IntegrityError):
                conn.exec_driver_sql('DELETE FROM learning_mark_revisions WHERE mark_id=?', (identifier,))


def test_validation_scope_pagination_unknown_versions_and_missing_files(tmp_path):
    with client(tmp_path) as c:
        node, _, path = add(c, tmp_path, '行.txt', b'one\ntwo')
        point = anchor(c, node)
        other = c.post('/api/workspaces', json={'name': '其他空间'}).json()['id']
        for field, value in [('version', True), ('version', 2), ('line', True), ('line', 0), ('kind', 'unsupported')]:
            assert mark(c, {**point, field: value}).status_code == 422
        assert mark(c, {**point, 'page': 1}).status_code == 422
        assert capture(c, node, kind='text_line', line=True, expected_sha256=point['content_sha256']).status_code == 422
        assert capture(c, node, kind='text_line', line=99, expected_sha256=point['content_sha256']).status_code == 422
        assert capture(c, node, kind='text_line', line=1, page=None, expected_sha256=point['content_sha256']).status_code == 422
        assert mark(c, {**point, 'workspace_id': other}).status_code == 404
        assert c.post(f'/api/workspaces/{other}/learning-marks', json={'request_id': 'learning-mark-request-1', 'anchor': point, 'title': 'x'}).status_code == 404
        identifier = mark(c, point).json()['id']
        assert c.get(f'/api/workspaces/{other}/learning-marks/{identifier}').status_code == 404
        assert c.get(f'/api/workspaces/{other}/learning-marks?resource_item_id={node}').status_code == 404
        assert c.get(URL + '?limit=101').status_code == 422
        assert c.get(URL + '?offset=-1').status_code == 422
        assert c.get(URL + '?limit=1&offset=1').json() == []
        assert c.patch(URL + '/' + identifier, json={'expected_revision': True, 'title': 'x'}).status_code == 422
        assert c.patch(URL + '/' + identifier, json={'expected_revision': 1, 'anchor': None}).status_code == 422
        assert c.get(URL, headers={'Authorization': 'bad'}).status_code == 401
        assert c.post(URL, json={}, headers={'Origin': 'https://example.com'}).status_code == 403
        path.rename(path.with_suffix('.retained'))
        assert c.get(URL + '/' + identifier).json()['location']['status'] == 'missing_content'
        assert c.patch(URL + '/' + identifier, json={'expected_revision': 1, 'note': '来源失效仍可补备注'}).status_code == 200
        with c.app.state.engine.begin() as conn:
            conn.exec_driver_sql('UPDATE learning_marks SET anchor=? WHERE id=?', (json.dumps({**point, 'version': 88}), identifier))
        assert c.get(URL + '/' + identifier).json()['location']['status'] == 'unsupported'


def test_explicit_note_relations_revisions_and_no_cross_workspace_links(tmp_path):
    with client(tmp_path) as c:
        node, resource, _ = add(c, tmp_path, '来源.txt', b'source')
        note = c.post(PREFIX + '/markdown-notes', json={'name': '笔记.md', 'request_id': 'note-create-request-1'}).json()
        with c.app.state.engine.begin() as conn:
            conn.exec_driver_sql("INSERT INTO notes VALUES ('old-note','default',?,'旧笔记','[]')", (resource,))
        targets = [{'kind': 'file_note', 'id': note['resource_item_id']}, {'kind': 'legacy_note', 'id': 'old-note'}]
        point = anchor(c, node)
        created = mark(c, point, targets=targets)
        assert created.status_code == 200, created.text
        identifier = created.json()['id']
        assert len(c.get(URL + '?note_resource_item_id=' + note['resource_item_id']).json()) == 1
        assert c.get(f'{URL}/{identifier}/notes/legacy_note/old-note').json()['title'] == '旧笔记'
        assert c.get(f"{URL}/{identifier}/notes/file_note/{note['resource_item_id']}").status_code == 200
        assert c.put(f'{URL}/{identifier}/notes', json={'expected_revision': 1, 'targets': targets + targets}).status_code == 422
        assert c.put(f'{URL}/{identifier}/notes', json={'expected_revision': 1, 'targets': []}).status_code == 200
        assert len(c.get(f'{URL}/{identifier}/revisions').json()[0]['content']['targets']) == 2
        assert c.get(f'{URL}/{identifier}/notes/legacy_note/old-note').status_code == 404
        other = c.post('/api/workspaces', json={'name': '其他'}).json()['id']
        assert c.post(f'/api/workspaces/{other}/learning-marks', json={
            'request_id': 'learning-mark-request-2', 'anchor': {**point, 'workspace_id': other},
            'title': 'x', 'targets': targets}).status_code == 404
        assert c.get(PREFIX + '/attempts').json() == []


def pdf_bytes():
    pdf = pdfium.PdfDocument.new()
    for _ in range(2):
        pdf.new_page(200, 200)
    output = io.BytesIO()
    pdf.save(output)
    pdf.close()
    return output.getvalue()


def test_pdf_pages_and_resource_level_links(tmp_path):
    with client(tmp_path) as c:
        node, _, _ = add(c, tmp_path, '书.pdf', pdf_bytes())
        doc = c.get(f'{PREFIX}/nodes/{node}/document').json()
        point = capture(c, node, kind='pdf_page', page=2, expected_sha256=doc['sha256'])
        assert point.status_code == 200, point.text
        identifier = mark(c, point.json()).json()['id']
        assert c.get(URL + '/' + identifier).json()['location']['status'] == 'valid'
        assert capture(c, node, kind='pdf_page', page=3, expected_sha256=doc['sha256']).status_code == 422
        link = c.post(PREFIX + '/nodes', json={'kind': 'link', 'name': '课程', 'url': 'https://example.com'}).json()['resource_item_id']
        location = capture(c, link, kind='resource').json()
        assert location['content_sha256'] is None
        assert mark(c, location, request='learning-mark-request-2').status_code == 200


def mp4(duration=12500, version=0):
    def box(kind, data):
        return struct.pack('>I', len(data) + 8) + kind + data
    movie = (b'\x00' * 12 + struct.pack('>II', 1000, duration)) if version == 0 else (
        b'\x01' + b'\x00' * 19 + struct.pack('>IQ', 1000, duration))
    return box(b'ftyp', b'isom' + b'\x00' * 12) + box(b'moov', box(b'mvhd', movie))


@pytest.mark.parametrize('version', [0, 1])
def test_media_metadata_and_time_anchors_bound_to_original(tmp_path, version):
    path = tmp_path / 'fixture.mp4'
    path.write_bytes(mp4(version=version))
    assert duration_ms(path, 'video/mp4') == 12500
    with client(tmp_path / 'data') as c:
        media = c.post(PREFIX + '/media/import?filename=课堂.mp4', content=path.read_bytes()).json()
        node = c.get(PREFIX + '/nodes').json()[0]['resource_item_id']
        point = capture(c, node, kind='media_time', position_ms=3456, expected_sha256=media['sha256'])
        assert point.status_code == 200, point.text
        assert mark(c, point.json()).status_code == 200
        assert capture(c, node, kind='media_time', position_ms=12501, expected_sha256=media['sha256']).status_code == 422
        assert c.get(URL + '/' + c.get(URL).json()[0]['id']).json()['location']['status'] == 'valid'


def test_webm_duration_and_malformed_metadata_are_bounded(tmp_path):
    def element(identifier, data):
        assert len(data) < 127
        return identifier + bytes([0x80 | len(data)]) + data
    info = element(bytes.fromhex('2ad7b1'), (1000000).to_bytes(3, 'big')) + element(bytes.fromhex('4489'), struct.pack('>d', 1234.5))
    raw = element(bytes.fromhex('1a45dfa3'), b'') + element(bytes.fromhex('18538067'), element(bytes.fromhex('1549a966'), info))
    path = tmp_path / 'fixture.webm'
    path.write_bytes(raw)
    assert duration_ms(path, 'video/webm') == 1234
    for data in [b'', b'\x00' * 40, b'\x1aE\xdf\xa3\xff', mp4(0), mp4(0xffffffff), struct.pack('>I', 999999) + b'moov']:
        path.write_bytes(data)
        assert duration_ms(path, 'video/mp4') is None


def test_office_page_binds_derived_bytes_and_retains_record_after_corruption(tmp_path, monkeypatch):
    from study_workbench import office_runtime
    from test_office_previews import FakeRuntime, package, wait

    fake = FakeRuntime()
    monkeypatch.setattr(office_runtime, 'runtime', lambda: fake)
    monkeypatch.setattr(office_runtime, 'capability', lambda: dict(available=True, fingerprint=fake.fingerprint, version=office_runtime.VERSION))
    with client(tmp_path) as c:
        node, _, original = add(c, tmp_path, '课件.pptx', package('ppt/presentation.xml', '<presentation/>'))
        checksum = hashlib.sha256(original.read_bytes()).hexdigest()
        job = c.post(f'{PREFIX}/nodes/{node}/previews', json={'expected_source_sha256': checksum})
        assert job.status_code == 200, job.text
        job = wait(c, node, job.json()['id'])
        assert job['status'] == 'ready', job
        point = capture(c, node, kind='office_pdf_page', preview_id=job['id'], page=1, expected_sha256=job['pdf_sha256'])
        assert point.status_code == 200, point.text
        identifier = mark(c, point.json()).json()['id']
        assert c.get(URL + '/' + identifier).json()['location']['status'] == 'valid'
        with Session(c.app.state.engine) as session:
            stored = session.get(DocumentPreview, job['id'])
            fields = {column.name: getattr(stored, column.name) for column in DocumentPreview.__table__.columns}
        newer = pdf_bytes()
        relative = f'workspaces/default/new-derived-{node}.pdf'
        (tmp_path / relative).write_bytes(newer)
        fields.update(id='c' * 32, relative_pdf=relative, pdf_sha256=hashlib.sha256(newer).hexdigest(),
                      pdf_size=len(newer), page_count=2, created_at='2099-01-01T00:00:00+00:00')
        with Session(c.app.state.engine) as session, session.begin():
            session.add(DocumentPreview(**fields))
        resolved = c.get(URL + '/' + identifier).json()['location']
        assert resolved['status'] == 'valid' and '旧分页版本' in resolved['message']
        assert resolved['anchor']['preview_id'] == job['id']
        with Session(c.app.state.engine) as session:
            stored = session.get(DocumentPreview, job['id'])
            (tmp_path / stored.relative_pdf).write_bytes(b'corrupted derived data')
        assert c.get(URL + '/' + identifier).json()['location']['status'] == 'missing_content'
        assert c.get(URL).json()[0]['id'] == identifier


def test_0013_upgrade_failure_rollback_and_success_preserve_old_data(tmp_path, monkeypatch):
    from study_workbench.app import create_app

    root = tmp_path / 'old'
    path = make_0006(root)
    engine = database(path)
    config = Config()
    config.set_main_option('script_location', str(Path(__file__).parents[1] / 'migrations'))
    with engine.begin() as connection:
        connection.exec_driver_sql('BEGIN')
        config.attributes['connection'] = connection
        command.upgrade(config, '0013')
    engine.dispose()
    before = snapshot(path)
    raw = (root / 'original.bin').read_bytes()
    upgrade = command.upgrade

    def fail(config, head):
        upgrade(config, head)
        raise RuntimeError('injected 0014 failure')

    monkeypatch.setattr(command, 'upgrade', fail)
    with pytest.raises(RuntimeError, match='0014'):
        create_app(root, TOKEN)
    assert snapshot(path) == before
    with sqlite3.connect(path) as db:
        assert db.execute('SELECT version_num FROM alembic_version').fetchone() == ('0013',)
    monkeypatch.setattr(command, 'upgrade', upgrade)
    with client(root) as c:
        assert_preserved(before, snapshot(path))
        node, _, _ = add(c, root, '升级后.txt', b'new')
        created = mark(c, anchor(c, node), targets=[{'kind': 'legacy_note', 'id': 'n'}])
        assert created.status_code == 200, created.text
        identifier = created.json()['id']
        assert c.patch(URL + '/' + identifier, json={'expected_revision': 1, 'note': '升级后仍可追溯'}).status_code == 200
        assert len(c.get(URL + '/' + identifier + '/revisions').json()) == 1
        assert snapshot(path)['notes'] == before['notes']
    assert (root / 'original.bin').read_bytes() == raw
    backups = list((root / 'backups').glob('study-before-0016-*.db'))
    assert backups and all(snapshot(p) == before for p in backups)
    with sqlite3.connect(path) as db:
        assert db.execute('SELECT version_num FROM alembic_version').fetchone() == ('0016',)
        assert db.execute('PRAGMA integrity_check').fetchone() == ('ok',)
        assert db.execute('PRAGMA foreign_key_check').fetchall() == []


def test_note_and_mark_database_constraints_reject_cross_scope_and_history_edits(tmp_path):
    with client(tmp_path) as c:
        node, _, _ = add(c, tmp_path, '资料.txt', b'hello')
        identifier = mark(c, anchor(c, node)).json()['id']
        other = c.post('/api/workspaces', json={'name': '其他'}).json()['id']
        foreign = c.post(f'/api/workspaces/{other}/markdown-notes', json={'request_id': 'note-create-request-1', 'name': '他空间.md'}).json()['resource_item_id']
        assert c.put(f'{URL}/{identifier}/notes', json={'expected_revision': 1, 'targets': [{'kind': 'file_note', 'id': foreign}]}).status_code == 404
        assert c.patch(f'{URL}/{identifier}', json={'expected_revision': 1, 'note': '保留旧版'}).status_code == 200
        with c.app.state.engine.begin() as conn:
            with pytest.raises(IntegrityError):
                conn.exec_driver_sql('INSERT INTO learning_mark_notes(workspace_id,mark_id,kind,file_node_id) VALUES (?,?,?,?)',
                                    ('default', identifier, 'file_note', foreign))
            with pytest.raises(IntegrityError):
                conn.exec_driver_sql('UPDATE learning_mark_revisions SET content=? WHERE mark_id=?', ('{}', identifier))
