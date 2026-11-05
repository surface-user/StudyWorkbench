import base64
import hashlib
import io
import sqlite3
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from PIL import Image
from sqlalchemy import event, select
from sqlalchemy.orm import Session
from study_workbench.db import (
    DocumentSave,
    DocumentWorkfile,
    Resource,
    WorkspaceNode,
    database,
    write_transaction,
)
from study_workbench.document_files import TEXT_LIMIT
from test_explorer import PREFIX, TOKEN, assert_preserved, client, snapshot


def add(c, root, name, data, parent=None):
    identifier, node = uuid4().hex, uuid4().hex
    relative = f'workspaces/default/originals/{identifier}.bin'
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    with write_transaction(c.app.state.engine) as session:
        session.add(Resource(id=identifier, workspace_id='default', original_name=name, relative_path=relative,
                             size=len(data), sha256=hashlib.sha256(data).hexdigest(), mime='application/octet-stream'))
        session.flush()
        session.add(WorkspaceNode(id=node, workspace_id='default', parent_id=parent, kind='resource', name=name,
                                  name_key=name.casefold(), resource_id=identifier))
    return node, identifier, path


def working(c, node):
    value = c.get(f'{PREFIX}/nodes/{node}/document').json()
    assert c.post(f'{PREFIX}/nodes/{node}/working-copy', json={'expected_sha256': value['sha256']}).status_code == 200
    return value


def test_markdown_workfile_conflicts_versions_and_original_never_changes(tmp_path):
    raw = '# 中文资料\n原始答案不会改写\n'.encode()
    with client(tmp_path) as c:
        node, resource, original = add(c, tmp_path, '讲义.md', raw)
        value = working(c, node)
        endpoint = f'{PREFIX}/nodes/{node}/document'
        changed = c.put(endpoint, json={'expected_sha256': value['sha256'], 'text': '# 工作副本\n新内容'})
        assert changed.status_code == 200, changed.text
        assert original.read_bytes() == raw
        assert c.get(PREFIX + f'/resources/{resource}').content == raw
        assert c.get(endpoint).json()['text'] == '# 工作副本\n新内容'
        assert c.put(endpoint, json={'expected_sha256': value['sha256'], 'text': '过时'}).status_code == 409
        with Session(c.app.state.engine) as session:
            work = session.get(DocumentWorkfile, node)
            relative = work.relative_path
            receipt = session.scalar(select(DocumentSave))
            assert receipt.status == 'committed'
            assert (tmp_path / receipt.backup_path).read_bytes() == raw
        (tmp_path / relative).write_text('外部修改', encoding='utf-8')
        assert c.get(endpoint).json()['external_change'] is True
        assert c.put(endpoint, json={'expected_sha256': changed.json()['sha256'], 'text': '不能覆盖外部'}).status_code == 409
        assert (tmp_path / relative).read_text(encoding='utf-8') == '外部修改'
    with client(tmp_path) as c:
        assert c.get(endpoint).json()['text'] == '外部修改'
        assert original.read_bytes() == raw


@pytest.mark.parametrize('failure', ['replace', 'finalize'])
def test_save_fault_recovers_without_replaying_file_writes(tmp_path, monkeypatch, failure):
    from study_workbench import document_files
    with client(tmp_path) as c:
        node, _, original = add(c, tmp_path, '笔记.md', b'old')
        value = working(c, node)
        endpoint = f'{PREFIX}/nodes/{node}/document'
        real_replace = document_files.os.replace

        def replace(*args):
            raise OSError('injected replacement failure')

        def fail_finalize(_, cursor, statement, parameters, context, many):
            if statement.startswith('UPDATE document_workfiles'):
                raise RuntimeError('injected finalize failure')

        if failure == 'replace':
            monkeypatch.setattr(document_files.os, 'replace', replace)
            assert c.put(endpoint, json={'expected_sha256': value['sha256'], 'text': 'new'}).status_code == 409
            monkeypatch.setattr(document_files.os, 'replace', real_replace)
        else:
            event.listen(c.app.state.engine, 'before_cursor_execute', fail_finalize)
            try:
                with pytest.raises(RuntimeError, match='finalize'):
                    c.put(endpoint, json={'expected_sha256': value['sha256'], 'text': 'new'})
            finally:
                event.remove(c.app.state.engine, 'before_cursor_execute', fail_finalize)
        with Session(c.app.state.engine) as session:
            receipt = session.scalar(select(DocumentSave))
            assert receipt.status == 'prepared'
            assert (tmp_path / receipt.backup_path).read_bytes() == b'old'
        assert original.read_bytes() == b'old'
    with client(tmp_path) as c:
        assert c.get(endpoint).json()['text'] == ('old' if failure == 'replace' else 'new')
        with Session(c.app.state.engine) as session:
            assert session.scalar(select(DocumentSave)).status == ('interrupted' if failure == 'replace' else 'committed')


def test_pending_receipt_with_external_content_never_overwrites_it(tmp_path, monkeypatch):
    from study_workbench import document_files
    with client(tmp_path) as c:
        node, _, _ = add(c, tmp_path, '笔记.md', b'old')
        value = working(c, node)
        real = document_files.os.replace
        monkeypatch.setattr(document_files.os, 'replace', lambda *args: (_ for _ in ()).throw(OSError('injected')))
        assert c.put(f'{PREFIX}/nodes/{node}/document', json={'expected_sha256': value['sha256'], 'text': 'pending'}).status_code == 409
        monkeypatch.setattr(document_files.os, 'replace', real)
        with Session(c.app.state.engine) as session:
            relative = session.get(DocumentWorkfile, node).relative_path
        (tmp_path / relative).write_bytes(b'external')
    with client(tmp_path) as c:
        with Session(c.app.state.engine) as session:
            assert session.scalar(select(DocumentSave)).status == 'conflict'
        assert (tmp_path / relative).read_bytes() == b'external'


def test_budget_scope_invalid_text_and_layout_document_drafts(tmp_path):
    with client(tmp_path) as c:
        node, _, _ = add(c, tmp_path, '原文.md', b'# markdown')
        other = c.post('/api/workspaces', json={'name': '其他'}).json()['id']
        assert c.get(f'/api/workspaces/{other}/nodes/{node}/document').status_code == 404
        value = working(c, node)
        endpoint = f'{PREFIX}/nodes/{node}/document'
        assert c.put(endpoint, json={'expected_sha256': value['sha256'], 'text': '中' * (TEXT_LIMIT // 3 + 1)}).status_code == 413
        invalid, _, _ = add(c, tmp_path, 'invalid.md', b'\xff\xfe')
        assert c.get(f'{PREFIX}/nodes/{invalid}/document').status_code == 422
        tab = {'id': 'md', 'kind': 'resource', 'resource_item_id': node, 'view_kind': 'document',
               'draft': '中' * 30000, 'draft_base_sha256': value['sha256'],
               'document_state': {'version': 1, 'page': 2, 'zoom': 1.5, 'scroll': 120, 'mode': 'edit'}}
        layout = {'version': 2, 'tabs': [tab], 'closed_tabs': [], 'active_tab_id': 'md'}
        saved = c.put(PREFIX + '/layout', json=layout)
        assert saved.status_code == 200, saved.text
        assert c.get(PREFIX + '/layout').json()['tabs'][0]['draft'] == tab['draft']
        for change in [{'zoom': 10}, {'version': 2}, {'page': 0}, {'arbitrary_path': 'C:/secret'}]:
            tab['document_state'] = change
            assert c.put(PREFIX + '/layout', json=layout).status_code == 422


def test_pdf_reader_over_twenty_pages_images_and_relative_scope(tmp_path):
    import pypdfium2 as pdfium
    document = pdfium.PdfDocument.new()
    for _ in range(21):
        page = document.new_page(200, 300)
        page.close()
    data = io.BytesIO()
    document.save(data)
    document.close()
    picture = io.BytesIO()
    Image.new('RGB', (20, 20), 'blue').save(picture, 'PNG')
    with client(tmp_path) as c:
        node, _, original = add(c, tmp_path, '长文档.pdf', data.getvalue())
        info = c.get(f'{PREFIX}/nodes/{node}/document')
        assert info.status_code == 200 and info.json()['page_count'] == 21, info.text
        rendered = c.get(f'{PREFIX}/nodes/{node}/document-page?page=21')
        assert rendered.status_code == 200, rendered.text
        assert base64.b64decode(rendered.json()['image_base64']).startswith(b'\x89PNG')
        assert c.get(f'{PREFIX}/nodes/{node}/document-page?page=22').status_code == 422
        assert original.read_bytes() == data.getvalue()
        folder = c.post(PREFIX + '/nodes', json={'name': '图片', 'kind': 'folder'}).json()['resource_item_id']
        image, _, _ = add(c, tmp_path, '示例.png', picture.getvalue(), folder)
        md, _, _ = add(c, tmp_path, '文档.md', b'![picture](images/test.png)')
        assert c.get(f'{PREFIX}/nodes/{image}/document').json()['type'] == 'image'
        good = c.get(f'{PREFIX}/nodes/{md}/relative-image', params={'path': '图片/示例.png'})
        assert good.status_code == 200 and base64.b64decode(good.json()['image_base64']).startswith(b'\x89PNG'), good.text
        for path in ['https://example.com/a.png', 'file:///C:/secret', '../图片/示例.png', '//host/a.png', 'C:\\secret', '%2e%2e/secret', '//[invalid']:
            assert c.get(f'{PREFIX}/nodes/{md}/relative-image', params={'path': path}).status_code in {422, 404}
        invalid, _, _ = add(c, tmp_path, '损坏.pdf', b'not-a-pdf')
        assert c.get(f'{PREFIX}/nodes/{invalid}/document').status_code == 422


def test_viewer_busy_budget_is_retryable_and_releases_after_failure(tmp_path):
    from study_workbench.document_files import VIEW_SLOTS
    with client(tmp_path) as c:
        node, _, _ = add(c, tmp_path, '查看.md', b'content')
        assert VIEW_SLOTS.acquire(blocking=False)
        assert VIEW_SLOTS.acquire(blocking=False)
        try:
            assert c.get(f'{PREFIX}/nodes/{node}/document').status_code == 429
        finally:
            VIEW_SLOTS.release()
            VIEW_SLOTS.release()
        assert c.get(f'{PREFIX}/nodes/{node}/document').status_code == 200
        assert c.get(f'{PREFIX}/nodes/{"f" * 32}/document').status_code == 404
        assert c.get(f'{PREFIX}/nodes/{node}/document').status_code == 200


def test_0007_to_head_backup_preserves_all_old_rows_and_failure_rollback(tmp_path, monkeypatch):
    from study_workbench.content import DEMO, SUBJECTIVE
    root = tmp_path / 'old'
    root.mkdir()
    engine = database(root / 'study.db')
    config = Config()
    config.set_main_option('script_location', str(Path(__file__).parents[1] / 'migrations'))
    with engine.begin() as connection:
        config.attributes['connection'] = connection
        command.upgrade(config, '0007')
        import json

        from sqlalchemy import text
        for content in (DEMO, SUBJECTIVE):
            connection.execute(text("INSERT INTO questions VALUES (:id,'default',:content)"),
                               dict(id=content['id'], content=json.dumps(content)))
    engine.dispose()
    before = snapshot(root / 'study.db')
    upgrade = command.upgrade

    def fail(config, revision):
        upgrade(config, revision)
        raise RuntimeError('injected 0010 DDL failure')

    monkeypatch.setattr(command, 'upgrade', fail)
    from study_workbench.app import create_app
    with pytest.raises(RuntimeError, match='0010'):
        create_app(root, TOKEN)
    assert snapshot(root / 'study.db') == before
    monkeypatch.setattr(command, 'upgrade', upgrade)
    with client(root):
        after = snapshot(root / 'study.db')
        assert_preserved(before, after)
        with sqlite3.connect(root / 'study.db') as db:
            assert db.execute('PRAGMA integrity_check').fetchone() == ('ok',)
            assert db.execute('PRAGMA foreign_key_check').fetchall() == []
    backups = list((root / 'backups').glob('study-before-0016-*.db'))
    assert backups and all(snapshot(path) == before for path in backups)
