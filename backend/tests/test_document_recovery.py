import sqlite3

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session
from study_workbench import document_files
from study_workbench.db import DocumentSave, DocumentWorkfile, write_transaction
from study_workbench.document_files import TEXT_LIMIT, digest
from test_document_files import add, working
from test_explorer import PREFIX, client, snapshot


def interrupted(c, root, monkeypatch):
    node, _, original = add(c, root, '恢复.md', b'old')
    working(c, node)
    endpoint = f'{PREFIX}/nodes/{node}'
    with monkeypatch.context() as patch:
        patch.setattr(document_files.os, 'replace', lambda *args: (_ for _ in ()).throw(OSError('interrupted')))
        assert c.put(endpoint + '/document', json={'expected_sha256': digest(b'old'), 'text': 'pending'}).status_code == 409
    with Session(c.app.state.engine) as session:
        row = session.scalar(select(DocumentSave).where(DocumentSave.node_id == node))
        paths = {key: root / getattr(row, key) for key in ('backup_path', 'pending_path')}
        current = root / session.get(DocumentWorkfile, node).relative_path
        return node, endpoint, row.id, paths, current, original


def business(root):
    return snapshot(root / 'study.db'), {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob('*.md')}


def test_prepared_preview_is_read_only_and_requires_reconciliation(tmp_path, monkeypatch):
    with client(tmp_path) as c:
        node, endpoint, identifier, paths, current, original = interrupted(c, tmp_path, monkeypatch)
        before = business(tmp_path)
        rows = c.get(endpoint + '/document-saves').json()
        assert rows == [dict(id=identifier, status='prepared', old_sha256=digest(b'old'), new_sha256=digest(b'pending'))]
        for version, content in [('before', 'old'), ('pending', 'pending')]:
            result = c.get(endpoint + f'/document-saves/{identifier}?version={version}')
            assert result.status_code == 200, result.text
            assert result.json()['text'] == content
            assert result.json()['sha256'] == digest(content.encode())
            assert result.json()['current_sha256'] is None
            assert '重启' in result.json()['unavailable_reason']
            assert set(result.json()) == {'id', 'status', 'version', 'text', 'sha256', 'current_sha256', 'unavailable_reason'}
        assert business(tmp_path) == before
        assert c.put(endpoint + '/document', json={'expected_sha256': digest(b'old'), 'text': 'pending'}).status_code == 409
    current.write_bytes(b'external')
    with client(tmp_path) as c:
        before = business(tmp_path)
        preview = c.get(endpoint + f'/document-saves/{identifier}?version=pending').json()
        assert preview['status'] == 'conflict'
        assert preview['current_sha256'] == digest(b'external')
        assert preview['unavailable_reason'] is None
        assert business(tmp_path) == before
        # Preview grants no overwrite privilege: the ordinary optimistic save still guards later edits.
        current.write_bytes(b'external after preview')
        request = {'expected_sha256': preview['current_sha256'], 'text': preview['text']}
        assert c.put(endpoint + '/document', json=request).status_code == 409
        assert current.read_bytes() == b'external after preview'
        preview = c.get(endpoint + f'/document-saves/{identifier}?version=pending').json()
        request['expected_sha256'] = preview['current_sha256']
        assert c.put(endpoint + '/document', json=request).status_code == 200
        assert current.read_bytes() == b'pending'
        assert original.read_bytes() == b'old'
        assert paths['backup_path'].read_bytes() == b'old'
        assert paths['pending_path'].read_bytes() == b'pending'
        with Session(c.app.state.engine) as session:
            assert session.get(DocumentSave, identifier).status == 'conflict'
            receipts = list(session.scalars(select(DocumentSave)))
            assert len(receipts) == 2
            saved = next(r for r in receipts if r.id != identifier)
            assert saved.status == 'committed'
            assert (tmp_path / saved.backup_path).read_bytes() == b'external after preview'


def test_committed_history_pagination_missing_pending_and_scope(tmp_path):
    with client(tmp_path) as c:
        node, _, original = add(c, tmp_path, '记录.md', b'original')
        working(c, node)
        endpoint = f'{PREFIX}/nodes/{node}'
        old = b'original'
        for content in ['one', 'two', 'three']:
            assert c.put(endpoint + '/document', json={'expected_sha256': digest(old), 'text': content}).status_code == 200
            old = content.encode()
        before = business(tmp_path)
        first = c.get(endpoint + '/document-saves?offset=0&limit=2').json()
        second = c.get(endpoint + '/document-saves?offset=2&limit=2').json()
        ids = [row['id'] for row in first + second]
        assert len(first) == 2 and len(second) == 1 and ids == sorted(set(ids))
        assert c.get(endpoint + '/document-saves?offset=3').json() == []
        for query in ['limit=0', 'limit=101', 'offset=-1']:
            assert c.get(endpoint + '/document-saves?' + query).status_code == 422
        identifier = ids[0]
        assert c.get(endpoint + f'/document-saves/{identifier}?version=before').status_code == 200
        assert c.get(endpoint + f'/document-saves/{identifier}?version=pending').status_code == 409
        for version in ['current', '../before', '']:
            assert c.get(endpoint + f'/document-saves/{identifier}', params={'version': version}).status_code == 422
        assert c.get(endpoint + '/document-saves/missing?version=before').status_code == 404
        assert business(tmp_path) == before
        other, _, _ = add(c, tmp_path, '其他.md', b'other')
        working(c, other)
        assert c.get(f'{PREFIX}/nodes/{other}/document-saves/{identifier}?version=before').status_code == 404
        space = c.post('/api/workspaces', json={'name': '其他空间'}).json()['id']
        foreign = f'/api/workspaces/{space}/nodes/{node}/document-saves'
        assert c.get(foreign).status_code == 404
        assert c.get(foreign + f'/{identifier}?version=before').status_code == 404
        raw, _, _ = add(c, tmp_path, '只读.md', b'read only')
        assert c.get(f'{PREFIX}/nodes/{raw}/document-saves').status_code == 404
        assert original.read_bytes() == b'original'


@pytest.mark.parametrize('target', ['backup_path', 'work_owner', 'work_path', 'foreign_node', 'id'])
def test_untrusted_receipt_paths_never_read_foreign_content(tmp_path, monkeypatch, target):
    with client(tmp_path) as c:
        node, endpoint, identifier, _, _, _ = interrupted(c, tmp_path, monkeypatch)
        other = c.post('/api/workspaces', json={'name': '其他空间'}).json()['id']
        with write_transaction(c.app.state.engine) as session:
            row = session.get(DocumentSave, identifier)
            work = session.get(DocumentWorkfile, node)
            if target == 'backup_path':
                row.backup_path = 'workspaces/other/working/private/current.md'
            elif target == 'work_owner':
                pass  # Damaged ownership is injected below without this connection's FK enforcement.
            elif target == 'work_path':
                work.relative_path = 'workspaces/default/working/../../other/private.md'
            elif target == 'foreign_node':
                work.relative_path = f'workspaces/default/working/{"f" * 32}/note/current.md'
            else:
                row.id = identifier = 'invalid-id'
        if target == 'work_owner':
            with sqlite3.connect(tmp_path / 'study.db') as db:
                db.execute('UPDATE document_workfiles SET workspace_id=? WHERE node_id=?', (other, node))
        with monkeypatch.context() as patch:
            patch.setattr(document_files, 'text_bytes', lambda *args: pytest.fail('Invalid ownership/path reached file read'))
            response = c.get(endpoint + f'/document-saves/{identifier}?version=before')
        assert response.status_code in {404, 409}


@pytest.mark.parametrize('fault', ['missing', 'modified', 'encoding', 'oversize'])
def test_invalid_recovery_bytes_fail_closed(tmp_path, monkeypatch, fault):
    with client(tmp_path) as c:
        _, endpoint, identifier, paths, _, _ = interrupted(c, tmp_path, monkeypatch)
        target = paths['backup_path']
        if fault == 'missing':
            target.rename(target.with_suffix('.retained'))
        else:
            target.write_bytes({'modified': b'tampered', 'encoding': b'\xff', 'oversize': b'x' * (TEXT_LIMIT + 1)}[fault])
            if fault == 'encoding':
                with write_transaction(c.app.state.engine) as session:
                    session.get(DocumentSave, identifier).old_sha256 = digest(b'\xff')
        before = business(tmp_path)
        response = c.get(endpoint + f'/document-saves/{identifier}?version=before')
        assert response.status_code == (413 if fault == 'oversize' else 409)
        assert 'text' not in response.json()
        assert business(tmp_path) == before


def test_missing_current_is_preview_only(tmp_path, monkeypatch):
    with client(tmp_path) as c:
        _, endpoint, identifier, _, current, _ = interrupted(c, tmp_path, monkeypatch)
    current.rename(current.with_suffix('.retained'))
    with client(tmp_path) as c:
        before = business(tmp_path)
        response = c.get(endpoint + f'/document-saves/{identifier}?version=before')
        assert response.status_code == 200
        assert response.json()['text'] == 'old'
        assert response.json()['current_sha256'] is None
        assert response.json()['unavailable_reason']
        assert business(tmp_path) == before


def test_recovery_junction_is_rejected(tmp_path, monkeypatch):
    import os
    import subprocess

    if os.name != 'nt':
        pytest.skip('Windows junction boundary')
    with client(tmp_path) as c:
        _, endpoint, identifier, paths, _, _ = interrupted(c, tmp_path, monkeypatch)
        target = paths['backup_path'].parents[2]
        relative = paths['backup_path'].relative_to(target)
        retained = target.with_name('retained-working')
        target.rename(retained)
        # Only our own temporary fixture; preserve the original directory and all bytes.
        linked = subprocess.run(['cmd', '/c', 'mklink', '/J', str(target), str(retained)], capture_output=True, timeout=15)
        assert linked.returncode == 0, linked.stderr.decode(errors='replace')
        response = c.get(endpoint + f'/document-saves/{identifier}?version=before')
        assert response.status_code == 409
        assert (retained / relative).read_bytes() == b'old'


def test_question_file_history_does_not_change_confirmed_version_or_old_attempt(tmp_path):
    from test_question_files import preview, publish

    with client(tmp_path) as c:
        proposal = c.get(PREFIX + '/questions/demo-integral/file-preview').json()
        created = c.post(PREFIX + '/questions/demo-integral/file', json={
            'expected_source_sha256': proposal['source_sha256'],
            'expected_preview_sha256': proposal['preview_sha256'], 'confirm': True})
        assert created.status_code == 200, created.text
        node = created.json()['resource_item_id']
        value = preview(c, node)
        assert publish(c, node, value).status_code == 200
        c.post(PREFIX + '/attempts', json={'question_id': 'demo-integral', 'response': {'selected': ['a']}})
        endpoint = f'{PREFIX}/nodes/{node}'
        current = c.get(endpoint + '/document').json()
        assert c.put(endpoint + '/document', json={'expected_sha256': current['sha256'], 'text': current['text'] + '\n'}).status_code == 200
        before = business(tmp_path)
        row = c.get(endpoint + '/document-saves').json()[0]
        saved = c.get(endpoint + f'/document-saves/{row["id"]}?version=before')
        assert saved.status_code == 200, saved.text
        assert saved.json()['text'] == current['text']
        assert business(tmp_path) == before
        # Existing tombstoned tabs retain access, without making the resource visible again.
        assert c.request('DELETE', endpoint, json={'confirm': True}).status_code == 200
        removed = business(tmp_path)
        assert c.get(endpoint + f'/document-saves/{row["id"]}?version=before').status_code == 200
        assert business(tmp_path) == removed
