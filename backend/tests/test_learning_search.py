import hashlib
import json

import pytest
from study_workbench import learning_search
from test_document_files import add, working
from test_explorer import PREFIX, client
from test_internal_links import uri
from test_learning_marks import anchor, mark

URL = PREFIX + '/learning-search'


def find(c, q='拥塞', **params):
    response = c.get(URL, params={'q': q, **params})
    assert response.status_code == 200, response.text
    return response.json()


def test_search_current_text_rich_content_marks_literal_casefold_and_no_writes(tmp_path):
    with client(tmp_path) as c:
        node, resource, original = add(c, tmp_path, '课程.MD', '原版\n拥塞'.encode())
        working(c, node)
        point = anchor(c, node)
        identifier = mark(c, point, title='拥塞窗口', note='STRASSE 100%_ <b>不执行</b>').json()['id']
        changed = '当前正文：拥塞 中文 Straße 100%_\n'
        assert c.put(f'{PREFIX}/nodes/{node}/document', json={'expected_sha256': point['content_sha256'], 'text': changed}).status_code == 200
        add(c, tmp_path, '资料.txt', '拥塞 TXT不搜索'.encode())
        content = [{'type': 'text', 'text': '拥塞 旧笔记'}, {'type': 'table', 'headers': [[{'type': 'latex', 'tex': 'alpha'}]],
                    'rows': [[[{'type': 'attachment', 'attachment_id': 'secret-id', 'label': '附图说明'}]]]}]
        with c.app.state.engine.begin() as conn:
            conn.exec_driver_sql("INSERT INTO notes VALUES ('old','default',?,'历史',?)", (resource, json.dumps(content)))
        before = original.read_bytes()
        result = find(c)
        assert result['total'] == 3 and result['truncated'] is False
        assert [row['kind'] for row in result['items']] == ['file_note', 'legacy_note', 'mark']
        file = result['items'][0]
        assert file['id'] == node and file['content_sha256'] == hashlib.sha256(changed.encode()).hexdigest()
        assert all('relative_path' not in row and 'content' not in row for row in result['items'])
        assert len(find(c, 'strasse')['items']) == 2
        assert len(find(c, '100%_')['items']) == 2
        assert find(c, 'alpha')['items'][0]['kind'] == 'legacy_note'
        assert find(c, '附图说明')['items'][0]['kind'] == 'legacy_note'
        assert find(c, 'secret-id')['total'] == 0
        assert original.read_bytes() == before
        assert c.post(PREFIX + '/internal-links/resolve', json={'uri': uri('marks', identifier)}).json()['status'] == 'content_changed'
        assert find(c)['items'][-1]['id'] == identifier
        assert c.request('DELETE', f'{PREFIX}/nodes/{node}', json={'confirm_name': '课程.MD'}).status_code == 200
        assert [row['kind'] for row in find(c)['items']] == ['legacy_note', 'mark']
        assert c.request('DELETE', f'{PREFIX}/learning-marks/{identifier}', json={'expected_revision': 1}).status_code == 200
        assert find(c)['total'] == 1


def test_filter_entire_scan_before_stable_pagination_and_restart(tmp_path):
    with client(tmp_path) as c:
        ids = [add(c, tmp_path, f'笔记{i}.md', f'共同关键词{i}'.encode())[0] for i in range(5)]
        pages = [find(c, '关键词', offset=n, limit=2) for n in (0, 2, 4)]
        assert [row['id'] for page in pages for row in page['items']] == sorted(ids)
        assert [page['total'] for page in pages] == [5, 5, 5]
        assert [page['has_more'] for page in pages] == [True, True, False]
        assert find(c, '不存在')['total'] == 0
        other = c.post('/api/workspaces', json={'name': '其他空间'}).json()['id']
        assert c.get(f'/api/workspaces/{other}/learning-search', params={'q': '关键词'}).json()['total'] == 0
        assert c.get(URL, params={'q': '关键词'}, headers={'Authorization': ''}).status_code == 401
        assert c.get(URL, params={'q': '关键词'}, headers={'Origin': 'https://evil.example'}).status_code == 403
    with client(tmp_path) as c:
        assert [r['id'] for r in find(c, '关键词')['items']] == sorted(ids)


@pytest.mark.parametrize('params', [{'q': ''}, {'q': '   '}, {'q': 'x' * 201}, {'q': 'x', 'limit': 0},
                                    {'q': 'x', 'limit': 101}, {'q': 'x', 'offset': -1}])
def test_invalid_queries_are_not_silent_empty_results(tmp_path, params):
    with client(tmp_path) as c:
        assert c.get(URL, params=params).status_code == 422


def test_budget_truncation_and_bad_files_are_explicit(tmp_path, monkeypatch):
    with client(tmp_path) as c:
        ids = [add(c, tmp_path, f'n{i}.md', (f'keyword{i}' * 3).encode()) for i in range(3)]
        monkeypatch.setattr(learning_search, 'MD_LIMIT', 1)
        result = find(c, 'keyword')
        assert result['truncated'] is True and result['scanned']['file_note'] == 1
        monkeypatch.setattr(learning_search, 'MD_LIMIT', 1000)
        monkeypatch.setattr(learning_search, 'BYTE_LIMIT', 10)
        result = find(c, 'keyword')
        assert result['truncated'] is True and result['total'] == 0
        monkeypatch.setattr(learning_search, 'BYTE_LIMIT', 16 * 1024 * 1024)
        ids[0][2].write_bytes(b'corrupted')
        result = find(c, 'keyword')
        assert result['total'] == 2 and result['truncated'] is True
        assert result['scanned']['unreadable'] == 1 and result['reasons']


def test_database_budget_is_shared_and_raw_note_bytes_are_bounded(tmp_path, monkeypatch):
    with client(tmp_path) as c:
        node, resource, _ = add(c, tmp_path, 'source.txt', b'source')
        identifier = mark(c, anchor(c, node), title='keyword').json()['id']
        with c.app.state.engine.begin() as conn:
            for i in range(3):
                conn.exec_driver_sql('INSERT INTO notes VALUES (?,\'default\',?,\'keyword\',\'[]\')', (f'n{i}', resource))
        monkeypatch.setattr(learning_search, 'DB_LIMIT', 2)
        result = find(c, 'keyword')
        assert result['scanned']['legacy_note'] == 2 and result['scanned']['mark'] == 0
        assert result['truncated'] and identifier not in [row['id'] for row in result['items']]
        monkeypatch.setattr(learning_search, 'DB_LIMIT', 10000)
        monkeypatch.setattr(learning_search, 'BYTE_LIMIT', 50)
        with c.app.state.engine.begin() as conn:
            conn.exec_driver_sql('UPDATE notes SET content=? WHERE id=\'n0\'', (json.dumps([{'type': 'image', 'attachment_id': 'x' * 200, 'alt': 'small'}]),))
        result = find(c, 'keyword')
        assert result['truncated'] and result['scanned']['bytes'] <= 50


def test_snippet_casefold_expansion_has_exact_plain_text_position():
    summary = learning_search.snippet('前' * 100 + 'Straße' + '后' * 300, 'strasse')
    assert summary.startswith('…') and 'Straße' in summary and summary.endswith('…')


def test_invalid_utf8_bytes_consume_budget_and_future_note_blocks_are_reported(tmp_path, monkeypatch):
    with client(tmp_path) as c:
        for i in range(3):
            add(c, tmp_path, f'坏文件{i}.md', b'\xff' + b'a' * 30 + str(i).encode())
        monkeypatch.setattr(learning_search, 'BYTE_LIMIT', 70)
        result = find(c, 'anything')
        assert result['truncated'] and result['scanned']['unreadable'] >= 1
        assert result['scanned']['bytes'] <= 70 and result['scanned']['file_note'] < 3
        monkeypatch.setattr(learning_search, 'BYTE_LIMIT', 16 * 1024 * 1024)
        _, resource, _ = add(c, tmp_path, 'plain.txt', b'none')
        with c.app.state.engine.begin() as conn:
            conn.exec_driver_sql("INSERT INTO notes VALUES ('future','default',?,'future',?)",
                                 (resource, json.dumps([{'type': 'future-block', 'body': 'anything'}])))
        result = find(c, 'anything')
        assert result['truncated'] and any('旧笔记结构' in reason for reason in result['reasons'])
