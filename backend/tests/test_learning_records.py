import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from test_explorer import PREFIX, client
from test_imports import confirm, upload
from test_question_files import convert, preview, publish


def test_events_append_idempotency_scope_pagination_and_restart(tmp_path):
    with client(tmp_path) as c:
        attempt = c.post(PREFIX + '/attempts', json={
            'question_id': 'demo-integral', 'response': {'selected': ['a']}}).json()
        endpoint = f"{PREFIX}/attempts/{attempt['id']}"
        before = c.get(PREFIX + '/attempts').json()
        body = dict(request_id='learning_event_0001', kind='annotation', note='概念混淆', error_type='概念', self_rating='hard')
        first = c.post(endpoint + '/events', json=body)
        assert first.status_code == 200, first.text
        assert c.post(endpoint + '/events', json=body).json() == first.json()
        assert c.post(endpoint + '/events', json=dict(body, note='不同')).status_code == 409
        second = c.post(endpoint + '/events', json=dict(body, request_id='learning_event_0002', kind='reviewed')).json()
        record = c.get(endpoint + '/record?limit=1').json()
        assert record['version_status'] == 'unknown' and record['knowledge_points'] is None
        assert record['events'] == [second]
        assert c.get(endpoint + f"/record?before_id={second['id']}").json()['events'] == [first.json()]
        other = c.post('/api/workspaces', json={'name': '其他'}).json()['id']
        for method, suffix, kwargs in [('GET', '/record', {}), ('POST', '/events', {'json': body})]:
            assert c.request(method, f"/api/workspaces/{other}/attempts/{attempt['id']}" + suffix, **kwargs).status_code == 404
        assert c.post(endpoint + '/events', json=dict(body, command='delete')).status_code == 422
        with c.app.state.engine.begin() as connection:
            for operation in ["DELETE FROM learning_events", "UPDATE learning_events SET content='{}'"]:
                with pytest.raises(IntegrityError):
                    connection.execute(text(operation))
        assert c.get(PREFIX + '/attempts').json() == before
    with client(tmp_path) as c:
        assert len(c.get(endpoint + '/record').json()['events']) == 2


def test_record_uses_attempt_version_and_stable_current_resource(tmp_path):
    with client(tmp_path) as c:
        node = convert(c, 'demo-integral')
        version = publish(c, node, preview(c, node)).json()
        attempt = c.post(PREFIX + '/attempts', json={
            'question_id': 'demo-integral', 'question_version_id': version['id'],
            'response': {'selected': ['a']}}).json()
        c.patch(f'{PREFIX}/nodes/{node}', json={'name': '改名.md', 'parent_id': None}).raise_for_status()
        result = c.get(f"{PREFIX}/attempts/{attempt['id']}/record").json()
        assert result['resource_item_id'] == node and result['version_status'] == 'known'
        assert result['question_version_id'] == version['id']
        assert result['knowledge_points'] == version['question']['knowledge_points']
        assert result['projection_algorithm'] == 'attempt-review-streak-v1'


def test_note_links_and_corrections_are_scoped_append_only_projections(tmp_path):
    with client(tmp_path) as c:
        job = upload(c, '复习笔记内容'.encode(), '笔记.txt').json()
        assert confirm(c, job).status_code == 200
        note = c.get(PREFIX + '/notes').json()[0]
        attempt = c.post(PREFIX + '/attempts', json={'question_id': 'demo-integral', 'response': {'selected': ['a']}}).json()
        endpoint = f"{PREFIX}/attempts/{attempt['id']}"
        stats = c.get(PREFIX + '/statistics').json()
        body = dict(request_id='note_link_request_001', kind='annotation', note='关联笔记并修订标签', note_id=note['id'], knowledge_points=['极限', '积分'])
        first = c.post(endpoint + '/events', json=body)
        assert first.status_code == 200, first.text
        assert c.get(endpoint + '/notes/' + note['id']).json()['content'] == note['content']
        assert c.post(endpoint + '/events', json=dict(body, request_id='clear_points_00001', knowledge_points=[])).status_code == 200
        record = c.get(endpoint + '/record?limit=1').json()
        assert record['knowledge_points'] is None and record['effective_knowledge_points'] == []
        assert record['related_notes'][0]['id'] == note['id']
        assert len(record['events']) == 1
        other = c.post('/api/workspaces', json={'name': '隔离'}).json()['id']
        # A note from another space is rejected even if a local attempt exists.
        from sqlalchemy.orm import Session
        from study_workbench.db import Note
        with Session(c.app.state.engine) as session, session.begin():
            session.add(Note(id='foreign-note', workspace_id=other, resource_id=note['resource_id'], title='外空间笔记', content=[]))
        assert c.post(endpoint + '/events', json=dict(body, request_id='foreign_note_00001', note_id='foreign-note')).status_code == 404
        for points in [['重复', '重复'], [' '], ['a' * 501]]:
            assert c.post(endpoint + '/events', json=dict(body, knowledge_points=points)).status_code == 422
        assert c.get(PREFIX + '/statistics').json() == stats
        assert c.get(endpoint + '/notes/unlinked-note').status_code == 404
        with c.app.state.engine.begin() as connection:
            connection.execute(text('DELETE FROM notes WHERE id=:id'), {'id': note['id']})
        record = c.get(endpoint + '/record?limit=1').json()
        assert record['related_notes'][0]['available'] is False
        assert c.get(endpoint + '/notes/' + note['id']).status_code == 404
        assert c.post(endpoint + '/events', json=body).json() == first.json()
    with client(tmp_path) as c:
        assert c.get(endpoint + '/record').json()['effective_knowledge_points'] == []
