import pytest
from fastapi import HTTPException
from study_workbench.internal_links import parse_link
from test_document_files import add, working
from test_explorer import PREFIX, client
from test_learning_marks import anchor, mark

RESOLVE = PREFIX + '/internal-links/resolve'


def uri(kind, identifier, workspace='default'):
    return f'studyworkbench://v1/workspaces/{workspace}/{kind}/{identifier}'


@pytest.mark.parametrize('value', [
    'file:///C:/secret', 'https://example.com', 'javascript:alert(1)',
    uri('nodes', 'x') + '?token=x', uri('nodes', 'x') + '#x', uri('nodes', 'x') + '/',
    uri('nodes', 'a/b'), uri('nodes', '..'), uri('nodes', '%2e%2e'), uri('nodes', '%252f'),
    uri('nodes', '%2f'), uri('nodes', '%5c'), uri('nodes', '%00'), uri('nodes', '%0a'),
    uri('nodes', '%FF'), uri('nodes', '%xx'), uri('nodes', 'a\\b'), uri('nodes', 'a\nb'),
    uri('nodes', 'a') + '\n', uri('nodes', 'a', '%252e'), uri('nodes', 'x', '..'),
    'studyworkbench://v1:80/workspaces/default/nodes/x',
    'studyworkbench://u@v1/workspaces/default/nodes/x',
    uri('nodes', 'x').replace('://v1/', '://v2/'), uri('nodes', 'x' * 2049),
    uri('other', 'x'), uri('nodes', ''),
])
def test_untrusted_uri_rejected(value):
    with pytest.raises(HTTPException) as failure:
        parse_link(value)
    assert failure.value.status_code == 422


def test_legacy_ids_and_single_decode():
    assert parse_link(uri('notes', 'old.note-1_%32')) == ('default', 'notes', 'old.note-1_2')


def test_resolve_rechecks_identity_version_tombstones_and_restart(tmp_path):
    with client(tmp_path) as c:
        node, resource, _ = add(c, tmp_path, '原名.md', b'line one\nline two')
        working(c, node)
        point = anchor(c, node, 2)
        identifier = mark(c, point).json()['id']
        with c.app.state.engine.begin() as conn:
            conn.exec_driver_sql("INSERT INTO notes VALUES ('old.note','default',?,'旧笔记','[]')", (resource,))
        def resolve(kind, item):
            return c.post(RESOLVE, json={'uri': uri(kind, item)})
        assert resolve('nodes', node).json()['resource']['name'] == '原名.md'
        assert resolve('marks', identifier).json()['anchor']['line'] == 2
        old_note = resolve('notes', 'old.note').json()
        assert old_note['note']['title'] == '旧笔记' and 'revision' in old_note['note']
        assert c.patch(f'{PREFIX}/nodes/{node}', json={'name': '新名.md', 'parent_id': None}).status_code == 200
        assert resolve('nodes', node).json()['resource']['name'] == '新名.md'
        assert c.put(f'{PREFIX}/nodes/{node}/document', json={'expected_sha256': point['content_sha256'], 'text': 'changed'}).status_code == 200
        assert resolve('marks', identifier).json()['status'] == 'content_changed'
        assert c.post(RESOLVE, json={'uri': uri('nodes', node), 'extra': 1}).status_code == 422
        assert c.post(RESOLVE, json={'uri': True}).status_code == 422
        assert c.post(RESOLVE, content=b'x' * 65537, headers={'Content-Type': 'application/json'}).status_code == 413
        assert c.request('DELETE', f'{PREFIX}/learning-marks/{identifier}', json={'expected_revision': 1}).status_code == 200
        assert resolve('marks', identifier).json()['status'] == 'removed'
        assert c.request('DELETE', f'{PREFIX}/nodes/{node}', json={'confirm_name': '新名.md'}).status_code == 200
        assert resolve('nodes', node).json()['status'] == 'removed'
    with client(tmp_path) as c:
        assert c.post(RESOLVE, json={'uri': uri('nodes', node)}).json()['status'] == 'removed'
        assert c.post(RESOLVE, json={'uri': uri('marks', identifier)}).json()['status'] == 'removed'


def test_scope_archived_unknown_and_no_private_paths(tmp_path):
    with client(tmp_path) as c:
        node, _, _ = add(c, tmp_path, '私有.txt', b'secret')
        other = c.post('/api/workspaces', json={'name': '另一个空间'}).json()['id']
        for kind in ['nodes', 'notes', 'marks']:
            response = c.post(f'/api/workspaces/{other}/internal-links/resolve', json={'uri': uri(kind, node)})
            assert response.status_code == 404 and '私有' not in response.text
            assert c.post(RESOLVE, json={'uri': uri(kind, 'missing')}).status_code == 404
        response = c.post(RESOLVE, json={'uri': uri('nodes', node)})
        assert response.status_code == 200
        assert all(word not in response.text for word in ['relative_path', str(tmp_path), 'token', 'capability'])
        assert c.post(RESOLVE, json={'uri': uri('nodes', node)}, headers={'Authorization': 'Bearer invalid'}).status_code == 401
        assert c.post(RESOLVE, json={'uri': uri('nodes', node)}, headers={'Origin': 'https://evil.example'}).status_code == 403
        name = c.get('/api/workbench').json()['workspaces']
        for item in name:
            if item['id'] == 'default':
                assert c.request('DELETE', '/api/workspaces/default', json={'confirm_name': item['name']}).status_code == 200
        assert c.post(RESOLVE, json={'uri': uri('nodes', node)}).status_code == 404
