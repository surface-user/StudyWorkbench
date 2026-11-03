from study_workbench import agent_access
from test_explorer import PREFIX, client


def test_grants_scope_revoke_expiry_restart_and_data_preservation(tmp_path, monkeypatch):
    now = [100.0]
    monkeypatch.setattr(agent_access, 'monotonic', lambda: now[0])
    with client(tmp_path) as c:
        attempt = c.post(PREFIX + '/attempts', json={
            'question_id': 'demo-integral', 'response': {'selected': ['a']}}).json()
        before = c.get(PREFIX + '/attempts').json()
        endpoint = PREFIX + '/agent-grants'
        body = dict(attempt_ids=[attempt['id']], purpose='analyze_attempts', confirm=True)
        for invalid in [dict(body, confirm=False), dict(body, confirm=1), dict(body, remote=True),
                        dict(body, attempt_ids=[True]), dict(body, attempt_ids=[1, 1]),
                        dict(body, expires_in_seconds=901)]:
            assert c.post(endpoint, json=invalid).status_code == 422
        grant = c.post(endpoint, json=body)
        assert grant.status_code == 200, grant.text
        path = endpoint + '/' + grant.json()['id']
        result = c.post(path + '/read-attempts').json()['attempts']
        assert [a['id'] for a in result] == [attempt['id']]
        assert 'response' not in result[0]
        other = c.post('/api/workspaces', json={'name': '其他'}).json()['id']
        foreign = f'/api/workspaces/{other}/agent-grants'
        assert c.post(foreign, json=body).status_code == 404
        assert c.post(foreign + '/' + grant.json()['id'] + '/read-attempts').status_code == 404
        assert c.delete(foreign + '/' + grant.json()['id']).status_code == 404
        assert c.post(path + '/read-attempts', headers={'Authorization': 'Bearer wrong'}).status_code == 401
        assert c.post(path + '/read-attempts', headers={'Origin': 'https://example.com'}).status_code == 403
        assert c.delete(path).status_code == 200
        assert c.post(path + '/read-attempts').status_code == 404
        expiring = c.post(endpoint, json=dict(body, expires_in_seconds=1)).json()['id']
        now[0] += 1
        assert c.post(endpoint + '/' + expiring + '/read-attempts').status_code == 404
        surviving = c.post(endpoint, json=body).json()['id']
        assert c.get(PREFIX + '/attempts').json() == before

    with client(tmp_path) as c:
        assert c.post(endpoint + '/' + surviving + '/read-attempts').status_code == 404
        assert c.get(PREFIX + '/attempts').json() == before


def test_grant_budget_and_archived_workspace(tmp_path, monkeypatch):
    monkeypatch.setattr(agent_access, 'monotonic', lambda: 100.0)
    with client(tmp_path) as c:
        attempt = c.post(PREFIX + '/attempts', json={
            'question_id': 'demo-integral', 'response': {'selected': ['a']}}).json()
        endpoint = PREFIX + '/agent-grants'
        body = dict(attempt_ids=[attempt['id']], purpose='analyze_attempts', confirm=True)
        grants = [c.post(endpoint, json=body) for _ in range(100)]
        assert all(g.status_code == 200 for g in grants)
        assert c.post(endpoint, json=body).status_code == 429
        assert c.delete(endpoint + '/' + grants[0].json()['id']).status_code == 200
        assert c.post(endpoint, json=body).status_code == 200
        c.post('/api/workspaces', json={'name': '保留空间'}).raise_for_status()
        name = c.get('/api/workbench').json()['workspaces'][0]['name']
        c.request('DELETE', '/api/workspaces/default', json={'confirm_name': name}).raise_for_status()
        assert c.post(endpoint, json=body).status_code == 404
        assert c.post(endpoint + '/' + grants[1].json()['id'] + '/read-attempts').status_code == 404
