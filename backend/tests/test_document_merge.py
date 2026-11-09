import json

import pytest
from sqlalchemy.orm import Session
from study_workbench import document_files
from study_workbench.db import DocumentWorkfile, write_transaction
from study_workbench.document_files import TEXT_LIMIT, digest
from test_document_files import add, working
from test_document_recovery import business, interrupted
from test_explorer import PREFIX, client


def setup(c, root, base=b'a\nb\nc\n', current=b'a\nb\nC\n', name='merge.md'):
    node, _, original = add(c, root, name, base)
    working(c, node)
    with Session(c.app.state.engine) as session:
        path = root / session.get(DocumentWorkfile, node).relative_path
    path.write_bytes(current)
    endpoint = f'{PREFIX}/nodes/{node}'
    request = dict(base='original', expected_base_sha256=digest(base),
                   expected_current_sha256=digest(current), text='A\nb\nc\n')
    return node, endpoint, path, original, request


@pytest.mark.parametrize('base,local,current,expected', [
    ('a\nb\nc\n', 'A\nb\nc\n', 'a\nb\nC\n', 'A\nb\nC\n'),
    ('a\n', 'A\n', 'B\n', None),
    ('', '', '', ''),
    ('甲\r\n乙\r\n丙', '```\r\n乙\r\n丙', '甲\r\n乙\r\n<script>', '```\r\n乙\r\n<script>'),
])
def test_preview_is_literal_and_preserves_all_business_bytes(tmp_path, base, local, current, expected):
    with client(tmp_path) as c:
        _, endpoint, _, _, request = setup(c, tmp_path, base.encode(), current.encode())
        request['text'] = local
        before = business(tmp_path)
        response = c.post(endpoint + '/document-merge-preview', json=request)
        assert response.status_code == 200, response.text
        assert response.json() == dict(text=expected, conflicted=expected is None,
                                       base_sha256=digest(base.encode()), local_sha256=digest(local.encode()),
                                       current_sha256=digest(current.encode()))
        assert business(tmp_path) == before


def test_preview_does_not_grant_save_permission_after_external_change(tmp_path):
    with client(tmp_path) as c:
        _, endpoint, path, original, request = setup(c, tmp_path)
        preview = c.post(endpoint + '/document-merge-preview', json=request).json()
        path.write_bytes(b'external after preview')
        before = business(tmp_path)
        save = dict(expected_sha256=preview['current_sha256'], text=preview['text'])
        assert c.put(endpoint + '/document', json=save).status_code == 409
        assert business(tmp_path) == before
        request['expected_current_sha256'] = digest(path.read_bytes())
        request['text'] = 'a\nb\nc\n'
        preview = c.post(endpoint + '/document-merge-preview', json=request).json()
        assert preview['text'] == 'external after preview'
        assert c.put(endpoint + '/document', json={
            'expected_sha256': preview['current_sha256'], 'text': preview['text']}).status_code == 200
        assert original.read_bytes() == b'a\nb\nc\n'
        rows = c.get(endpoint + '/document-saves').json()
        assert len(rows) == 1
        assert c.get(endpoint + f'/document-saves/{rows[0]["id"]}?version=before').json()['text'] == 'external after preview'


@pytest.mark.parametrize('version,base', [('before', b'old'), ('pending', b'pending')])
def test_receipt_baseline_is_scoped_hash_checked_and_readonly(tmp_path, monkeypatch, version, base):
    with client(tmp_path) as c:
        _, endpoint, identifier, paths, current, original = interrupted(c, tmp_path, monkeypatch)
    current.write_bytes(b'current')
    with client(tmp_path) as c:
        request = dict(base=version, save_id=identifier, expected_base_sha256=digest(base),
                       expected_current_sha256=digest(b'current'), text=base.decode())
        before = business(tmp_path)
        result = c.post(endpoint + '/document-merge-preview', json=request)
        assert result.status_code == 200, result.text
        assert result.json()['text'] == 'current'
        assert business(tmp_path) == before
        other, _, _, _, _ = setup(c, tmp_path)
        assert c.post(f'{PREFIX}/nodes/{other}/document-merge-preview', json={
            **request, 'expected_current_sha256': digest(b'a\nb\nC\n')}).status_code == 404
        paths['backup_path' if version == 'before' else 'pending_path'].write_bytes(b'tampered')
        changed = business(tmp_path)
        assert c.post(endpoint + '/document-merge-preview', json=request).status_code == 409
        assert business(tmp_path) == changed and original.read_bytes() == b'old'


def test_prepared_missing_current_and_consumed_pending_are_rejected(tmp_path, monkeypatch):
    with client(tmp_path) as c:
        _, endpoint, identifier, _, current, _ = interrupted(c, tmp_path, monkeypatch)
        request = dict(base='before', save_id=identifier, expected_base_sha256=digest(b'old'),
                       expected_current_sha256=digest(b'old'), text='local')
        before = business(tmp_path)
        assert c.post(endpoint + '/document-merge-preview', json=request).status_code == 409
        assert business(tmp_path) == before
    with client(tmp_path) as c:
        current.rename(current.with_name('retained.md'))
        before = business(tmp_path)
        assert c.post(endpoint + '/document-merge-preview', json=request).status_code == 409
        assert business(tmp_path) == before
        current.write_bytes(b'old')
        assert c.put(endpoint + '/document', json={'expected_sha256': digest(b'old'), 'text': 'saved'}).status_code == 200
        rows = c.get(endpoint + '/document-saves').json()
        committed = next(r for r in rows if r['status'] == 'committed')
        request.update(base='pending', save_id=committed['id'], expected_base_sha256=digest(b'saved'),
                       expected_current_sha256=digest(b'saved'))
        before = business(tmp_path)
        assert c.post(endpoint + '/document-merge-preview', json=request).status_code == 409
        assert business(tmp_path) == before


def test_auth_scope_versions_and_untrusted_original_fail_closed(tmp_path):
    with client(tmp_path) as c:
        node, endpoint, _, original, request = setup(c, tmp_path)
        before = business(tmp_path)
        assert c.post(endpoint + '/document-merge-preview', json=request, headers={'Authorization': 'Bearer wrong'}).status_code == 401
        assert c.post(endpoint + '/document-merge-preview', json=request, headers={'Origin': 'https://example.com'}).status_code == 403
        assert c.post(endpoint + '/document-merge-preview', json=request, headers={'Host': 'evil.example'}).status_code == 400
        assert c.post(endpoint + '/document-merge-preview', json={**request, 'expected_base_sha256': '0' * 64}).status_code == 409
        assert c.post(endpoint + '/document-merge-preview', json={**request, 'expected_current_sha256': '0' * 64}).status_code == 409
        assert business(tmp_path) == before
        space = c.post('/api/workspaces', json={'name': 'other'}).json()['id']
        assert c.post(f'/api/workspaces/{space}/nodes/{node}/document-merge-preview', json=request).status_code == 404
        raw, _, _ = add(c, tmp_path, 'readonly.md', b'raw')
        assert c.post(f'{PREFIX}/nodes/{raw}/document-merge-preview', json=request).status_code == 404
        original.write_bytes(b'modified original')
        before = business(tmp_path)
        assert c.post(endpoint + '/document-merge-preview', json=request).status_code == 409
        assert business(tmp_path) == before


@pytest.mark.parametrize('change', [
    {'base': 'current'}, {'base': 'before'}, {'save_id': 'a' * 32}, {'save_id': '../private'},
    {'expected_base_sha256': 'invalid'}, {'text': 12}, {'text': None}, {'arbitrary_path': 'private.md'},
    {'base_text': 'caller supplied'}, {'base': 'before', 'save_id': None},
])
def test_strict_request_validation(tmp_path, change):
    with client(tmp_path) as c:
        _, endpoint, _, _, request = setup(c, tmp_path)
        before = business(tmp_path)
        assert c.post(endpoint + '/document-merge-preview', json={**request, **change}).status_code == 422
        assert business(tmp_path) == before


def test_utf8_input_result_and_actual_frame_budgets(tmp_path):
    with client(tmp_path) as c:
        _, endpoint, current, _, request = setup(c, tmp_path, b'', b'')
        url = endpoint + '/document-merge-preview'
        request['text'] = '\0' * TEXT_LIMIT
        raw = json.dumps(request).encode()
        assert 6 * TEXT_LIMIT < len(raw) < 8 * TEXT_LIMIT
        before = business(tmp_path)
        response = c.post(url, content=raw, headers={'Content-Type': 'application/json'})
        assert response.status_code == 200, response.text
        assert response.json()['text'] == request['text']
        request['text'] = '甲' * (TEXT_LIMIT // 3 + 1)
        assert c.post(url, json=request).status_code == 413
        request['text'] = '\ud800'
        assert c.post(url, content=json.dumps(request).encode(), headers={'Content-Type': 'application/json'}).status_code == 422
        for field in ['expected_base_sha256', 'unexpected']:
            invalid = {**request, 'text': '', field: '\ud800'}
            response = c.post(url, content=json.dumps(invalid).encode(), headers={'Content-Type': 'application/json'})
            assert response.status_code == 422 and '\\ud800' not in response.text
        assert c.post(url, content=iter([b'x' * TEXT_LIMIT] * 9)).status_code == 413
        assert c.post(PREFIX + '/nodes', content=iter([b'x' * 65537])).status_code == 413
        assert business(tmp_path) == before
        current.write_bytes(b'x' * (TEXT_LIMIT + 1))
        assert c.post(url, json={**request, 'text': ''}).status_code == 413
        _, endpoint, _, _, request = setup(c, tmp_path, b'a\nb\nc\n', b'a\nb\n' + b'x' * (TEXT_LIMIT // 2),
                                            name='result-budget.md')
        request['text'] = 'x' * (TEXT_LIMIT // 2) + '\nb\nc\n'
        before = business(tmp_path)
        assert c.post(endpoint + '/document-merge-preview', json=request).status_code == 413
        assert business(tmp_path) == before


def test_busy_and_external_change_during_preview_preserve_bytes(tmp_path, monkeypatch):
    with client(tmp_path) as c:
        _, endpoint, current, _, request = setup(c, tmp_path)
        slots = document_files.VIEW_SLOTS
        assert slots.acquire(blocking=False) and slots.acquire(blocking=False)
        try:
            assert c.post(endpoint + '/document-merge-preview', json=request).status_code == 429
        finally:
            slots.release()
            slots.release()
        real = document_files.preview_merge

        def changed(*args):
            result = real(*args)
            current.write_bytes(b'external during preview')
            return result

        with monkeypatch.context() as patch:
            patch.setattr(document_files, 'preview_merge', changed)
            assert c.post(endpoint + '/document-merge-preview', json=request).status_code == 409
        assert current.read_bytes() == b'external during preview'
        assert c.get(endpoint + '/document-saves').json() == []
        request['expected_current_sha256'] = digest(current.read_bytes())
        assert c.post(endpoint + '/document-merge-preview', json=request).status_code == 200


def test_invalid_work_owner_never_reaches_file_read(tmp_path, monkeypatch):
    with client(tmp_path) as c:
        node, endpoint, _, _, request = setup(c, tmp_path)
        with write_transaction(c.app.state.engine) as session:
            session.get(DocumentWorkfile, node).relative_path = 'workspaces/default/working/../../private.md'
        monkeypatch.setattr(document_files, 'text_bytes', lambda *args: pytest.fail('Invalid path reached read'))
        assert c.post(endpoint + '/document-merge-preview', json=request).status_code == 409


def test_question_file_preview_preserves_confirmation_attempts_and_tombstone(tmp_path):
    from test_question_files import preview, publish

    with client(tmp_path) as c:
        proposal = c.get(PREFIX + '/questions/demo-integral/file-preview').json()
        created = c.post(PREFIX + '/questions/demo-integral/file', json={
            'expected_source_sha256': proposal['source_sha256'],
            'expected_preview_sha256': proposal['preview_sha256'], 'confirm': True}).json()
        node = created['resource_item_id']
        confirmed = publish(c, node, preview(c, node))
        assert confirmed.status_code == 200
        assert c.post(PREFIX + '/attempts', json={'question_id': 'demo-integral',
            'question_version_id': confirmed.json()['id'], 'response': {'selected': ['a']}}).status_code == 200
        endpoint = f'{PREFIX}/nodes/{node}'
        current = c.get(endpoint + '/document').json()
        assert c.put(endpoint + '/document', json={'expected_sha256': current['sha256'], 'text': current['text'] + '\n'}).status_code == 200
        row = c.get(endpoint + '/document-saves').json()[0]
        body = dict(base='before', save_id=row['id'], expected_base_sha256=current['sha256'],
                    expected_current_sha256=digest((current['text'] + '\n').encode()), text=current['text'])
        before = business(tmp_path)
        assert c.post(endpoint + '/document-merge-preview', json=body).json()['text'] == current['text'] + '\n'
        assert business(tmp_path) == before
        assert c.delete(endpoint).status_code == 200
        before = business(tmp_path)
        assert c.post(endpoint + '/document-merge-preview', json=body).status_code == 200
        assert business(tmp_path) == before
