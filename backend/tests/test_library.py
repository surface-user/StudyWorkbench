import io
import json
from zipfile import ZipFile

from test_imports import SCOPE, client, confirm, upload


def test_export_retains_original_hash_and_scope(tmp_path):
    with client(tmp_path) as c:
        job = upload(c, '中文笔记'.encode(), 'note.txt').json()
        confirm(c, job)
        result = c.get(f'{SCOPE}/export')
        assert result.status_code == 200
        with ZipFile(io.BytesIO(result.content)) as archive:
            manifest = json.loads(archive.read('manifest.json'))
            assert manifest['resources'][0]['sha256'] == job['sha256']
            assert archive.read(f"resources/{job['resource_id']}.bin") == '中文笔记'.encode()
            assert manifest['notes'][0]['content'][0]['text'] == '中文笔记'
            assert len(json.loads(archive.read('questions.json'))['questions']) == 2
        other = c.post('/api/workspaces', json={'name': '其他空间'}).json()['id']
        assert c.get(f'/api/workspaces/{other}/resources').json() == []
        assert c.get(f'{SCOPE}/resources').json()[0]['id'] == job['resource_id']
        assert c.get(f'{SCOPE}/export', headers={'Authorization': 'bad'}).status_code == 401
        path = tmp_path / f"workspaces/default/originals/{job['resource_id']}.bin"
        path.write_bytes(b'corrupt')
        assert c.get(f'{SCOPE}/export').status_code == 409


def test_reparse_preserves_failed_data_and_confirmed_is_immutable(tmp_path):
    with client(tmp_path) as c:
        failed = upload(c, b'invalid', 'bad.json').json()
        assert c.post(f"{SCOPE}/imports/{failed['id']}/retry").status_code == 422
        assert c.get(f"{SCOPE}/imports/{failed['id']}").json()['status'] == 'failed'
        job = upload(c, b'note', 'note.md').json()
        assert c.post(f"{SCOPE}/imports/{job['id']}/retry").json()['status'] == 'preview'
        confirm(c, job)
        assert c.post(f"{SCOPE}/imports/{job['id']}/retry").status_code == 409


def test_orphan_recovery_never_autoconfirms_or_deletes(tmp_path):
    with client(tmp_path) as c:
        directory = tmp_path / 'workspaces/default/originals'
        directory.mkdir(parents=True)
        identifier = 'a' * 32
        path = directory / (identifier + '.bin')
        path.write_bytes('中断时的原件'.encode())
        assert c.get(f'{SCOPE}/recovery').json() == [{'resource_id': identifier, 'size': path.stat().st_size}]
        body = {'resource_id': identifier, 'filename': '../note.txt'}
        assert c.post(f'{SCOPE}/recovery', json=body).status_code == 422
        body['filename'] = '恢复.txt'
        job = c.post(f'{SCOPE}/recovery', json=body).json()
        assert job['status'] == 'preview'
        assert c.get(f'{SCOPE}/notes').json() == []
        assert c.get(f'{SCOPE}/recovery').json() == []
        assert path.exists()
        assert c.post(f'{SCOPE}/recovery', json=body).status_code == 409
        confirm(c, job)
        assert c.get(f'{SCOPE}/notes').json()[0]['content'][0]['text'] == '中断时的原件'


def test_manual_note_edit_checks_revision_and_keeps_original(tmp_path):
    raw = {'schema_version': 1, 'kind': 'note', 'title': '手动笔记',
           'blocks': [{'type': 'text', 'text': '第一版'}]}
    with client(tmp_path) as c:
        job = upload(c, raw).json()
        assert job['status'] == 'preview'
        confirm(c, job)
        note = c.get(f'{SCOPE}/notes').json()[0]
        body = {'expected_revision': note['revision'], 'title': '新标题',
                'content': [{'type': 'text', 'text': '修订内容'}]}
        saved = c.put(f"{SCOPE}/notes/{note['id']}", json=body).json()
        assert saved['title'] == '新标题' and saved['revision'] != note['revision']
        assert c.put(f"{SCOPE}/notes/{note['id']}", json=body).status_code == 409
        assert json.loads(c.get(f"{SCOPE}/resources/{job['resource_id']}").content) == raw
        body['expected_revision'] = saved['revision']
        body['content'] = [{'type': 'image', 'attachment_id': 'missing', 'alt': '缺失图片'}]
        assert c.put(f"{SCOPE}/notes/{note['id']}", json=body).status_code == 422
        assert c.get(f'{SCOPE}/notes').json()[0]['content'][0]['text'] == '修订内容'


def test_link_import_is_offline_and_untrusted(tmp_path):
    with client(tmp_path) as c:
        job = upload(c, b'https://example.com/lesson', '课程.url').json()
        assert job['status'] == 'preview'
        confirm(c, job)
        assert c.get(f'{SCOPE}/notes').json()[0]['content'][0]['text'] == 'https://example.com/lesson'
        for url in (b'file:///secret', b'https://127.0.0.1/private', b'https://user:pass@example.com', b'javascript:alert(1)'):
            failed = upload(c, url, 'unsafe.url').json()
            assert failed['status'] == 'failed'
            assert confirm(c, failed).status_code == 409


def test_interrupted_parse_is_recoverable_after_restart(tmp_path):
    from sqlalchemy.orm import Session
    from study_workbench.db import ImportJob

    with client(tmp_path) as c:
        job = upload(c, b'interrupted note', 'recovered.txt').json()
        with Session(c.app.state.engine) as session, session.begin():
            session.get(ImportJob, job['id']).status = 'parsing'
    with client(tmp_path) as c:
        interrupted = c.get(f"{SCOPE}/imports/{job['id']}").json()
        assert interrupted['status'] == 'failed' and '中断' in interrupted['error']
        assert c.get(f'{SCOPE}/notes').json() == []
        assert c.post(f"{SCOPE}/imports/{job['id']}/retry").json()['status'] == 'preview'
        assert confirm(c, job).status_code == 200


def test_export_metadata_budget_fails_without_mutation(tmp_path, monkeypatch):
    import study_workbench.library as library
    monkeypatch.setattr(library, 'EXPORT_METADATA_LIMIT', 100)
    with client(tmp_path) as c:
        before = c.get(f'{SCOPE}/questions').json()
        assert c.get(f'{SCOPE}/export').status_code == 413
        assert c.get(f'{SCOPE}/questions').json() == before


def test_rich_note_edit_preserves_assets_conflicts_and_original(tmp_path):
    import base64

    # Use the existing real PNG fixture, not a network image.
    png = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+j4WQAAAAASUVORK5CYII=')
    with client(tmp_path) as c:
        image = upload(c, png, '图.png').json()['resource_id']
        attachment = upload(c, b'chart values', 'data.txt').json()['resource_id']
        raw = {'schema_version': 1, 'kind': 'note', 'title': '富内容', 'blocks': [
            {'type': 'text', 'text': '原文'}, {'type': 'latex', 'tex': 'x^2', 'display': True},
            {'type': 'image', 'attachment_id': image, 'alt': '图片', 'caption': '标题'},
            {'type': 'chart', 'attachment_id': image, 'data_attachment_id': attachment, 'alt': '图表'},
            {'type': 'attachment', 'attachment_id': attachment, 'label': '数据'},
            {'type': 'table', 'headers': [[{'type': 'text', 'text': '列名'}]],
             'rows': [[[{'type': 'text', 'text': '单元格'}, {'type': 'latex', 'tex': 'y', 'display': False}]]]},
        ]}
        job = upload(c, raw).json()
        assert confirm(c, job).status_code == 200
        note = c.get(f'{SCOPE}/notes').json()[0]
        blocks = json.loads(json.dumps(note['content']))
        blocks[0]['text'] = '新正文'
        blocks[5]['rows'][0][0][0]['text'] = '新单元格'
        body = {'expected_revision': note['revision'], 'title': '新富内容', 'content': blocks}
        saved = c.put(f"{SCOPE}/notes/{note['id']}", json=body).json()
        assert saved['content'] == blocks and saved['resource_id'] == job['resource_id']
        assert saved['revision'] != note['revision']
        assert c.put(f"{SCOPE}/notes/{note['id']}", json=body).status_code == 409
        other = c.post('/api/workspaces', json={'name': '其他笔记'}).json()['id']
        assert c.put(f"/api/workspaces/{other}/notes/{note['id']}", json=body).status_code == 404
        foreign = c.post(f'/api/workspaces/{other}/imports?filename=foreign.txt', content=b'foreign').json()['resource_id']
        body['expected_revision'] = saved['revision']
        for bad in ([{'type': 'attachment', 'attachment_id': foreign, 'label': '跨空间'}],
                    [{'type': 'latex', 'tex': r'\input{secret}'}],
                    [{'type': 'table', 'headers': [[{'type': 'text', 'text': '列'}]], 'rows': [[]]}]):
            body['content'] = bad
            assert c.put(f"{SCOPE}/notes/{note['id']}", json=body).status_code == 422
        assert c.get(f'{SCOPE}/notes').json()[0] == saved
        assert json.loads(c.get(f"{SCOPE}/resources/{job['resource_id']}").content) == raw
        assert c.get(f'{SCOPE}/resources/{image}').content == png
    with client(tmp_path) as c:
        assert c.get(f'{SCOPE}/notes').json()[0] == saved
