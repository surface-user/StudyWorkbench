import re

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from study_workbench.app import create_app
from study_workbench.document_files import VIEW_SLOTS

TOKEN = 'api-error-test-session-' * 3
AUTH = {'Authorization': 'Bearer ' + TOKEN}
PRIVATE = 'private-sentinel-https://fixture.invalid/?secret=never-return'


def check_error(response, status, code, *, detail_type=str):
    assert response.status_code == status
    value = response.json()
    assert isinstance(value['detail'], detail_type)
    assert value['error']['code'] == code
    identifier = value['error']['request_id']
    assert re.fullmatch('[0-9a-f]{32}', identifier)
    assert response.headers['x-request-id'] == identifier
    assert PRIVATE not in response.text and TOKEN not in response.text
    assert set(value['error']) == {'code', 'message', 'request_id'}
    return value


def client(path, **options):
    return TestClient(create_app(path, TOKEN), base_url='http://127.0.0.1', **options)


def test_boundary_errors_and_server_ids_do_not_trust_incoming_values(tmp_path):
    with client(tmp_path) as c:
        one = check_error(c.get('/api/health', headers={'X-Request-ID': PRIVATE}), 401, 'unauthorized')
        two = check_error(c.get('/api/health', headers={'X-Request-ID': 'a' * 32}), 401, 'unauthorized')
        assert one['detail'] == two['detail'] == 'Unauthorized'
        assert one['error']['request_id'] != two['error']['request_id'] != 'a' * 32
        check_error(c.get('/api/health', headers={**AUTH, 'Origin': PRIVATE}), 403, 'forbidden')
        for host in ('evil.example', 'localhost', '127.0.0.1.evil.example', '[::1]'):
            check_error(c.get('/api/health', headers={**AUTH, 'Host': host}), 400, 'bad_request')
        success = c.get('/api/health', headers={**AUTH, 'Host': '127.0.0.1:54321'})
        assert success.status_code == 200 and 'error' not in success.json()
        check_error(c.get('/api/missing', headers=AUTH), 404, 'not_found')
        method = c.post('/api/health', headers=AUTH)
        check_error(method, 405, 'method_not_allowed')
        assert 'GET' in method.headers['allow']


@pytest.mark.parametrize('body', [
    {'name': 123, PRIVATE: PRIVATE},
    {'name': PRIVATE, 'parent_id': {'secret': PRIVATE}},
    {'name': 'movie.mp4', 'url': PRIVATE, 'request_id': PRIVATE, 'rights_confirmed': False},
])
def test_validation_keeps_list_shape_without_input_keys_or_context(tmp_path, body):
    with client(tmp_path) as c:
        response = c.post('/api/workspaces/default/media-downloads', headers=AUTH, json=body)
        value = check_error(response, 422, 'validation_failed', detail_type=list)
        assert value['detail']
        for issue in value['detail']:
            assert set(issue) == {'loc', 'msg', 'type'}
            assert issue['msg'] == '请求参数无效' and issue['type'] == 'value_error'
            assert issue['loc'][0] == 'body'
            assert all(isinstance(part, int) or part in {'body', 'field'} for part in issue['loc'])


def test_invalid_json_query_and_validation_summary_are_bounded(tmp_path):
    with client(tmp_path) as c:
        check_error(c.post('/api/workspaces', headers=AUTH,
            content=('{' + PRIVATE).encode()), 422, 'validation_failed', detail_type=list)
        check_error(c.get('/api/workspaces/default/nodes', headers=AUTH,
            params={'limit': PRIVATE}), 422, 'validation_failed', detail_type=list)
        response = c.post('/api/workspaces', headers=AUTH, json={'name': 'valid', **{
            f'{PRIVATE}{i}': PRIVATE for i in range(120)}})
        assert len(check_error(response, 422, 'validation_failed', detail_type=list)['detail']) == 100


def test_actual_frame_budget_and_busy_view_keep_status_and_protection(tmp_path):
    with client(tmp_path) as c:
        response = c.post('/api/workspaces', headers=AUTH, content=(b'x' * 4096 for _ in range(17)))
        assert check_error(response, 413, 'payload_too_large')['detail'] == 'Request too large'
        VIEW_SLOTS.acquire()
        VIEW_SLOTS.acquire()
        try:
            check_error(c.get('/api/workspaces/default/learning-search?q=test', headers=AUTH), 429, 'resource_busy')
        finally:
            VIEW_SLOTS.release()
            VIEW_SLOTS.release()
        assert len(c.get('/api/workbench', headers=AUTH).json()['workspaces']) == 1


def test_idempotency_scope_and_conflict_do_not_change_business_receipts(tmp_path):
    with client(tmp_path) as c:
        url = '/api/workspaces/default/markdown-notes'
        body = {'name': 'kept.md', 'request_id': 'same-business-request'}
        first = c.post(url, headers=AUTH, json=body)
        again = c.post(url, headers=AUTH, json=body)
        assert first.status_code == again.status_code == 200 and first.json() == again.json()
        response = c.post(url, headers=AUTH, json={**body, 'name': 'changed.md'})
        value = check_error(response, 409, 'conflict')
        assert value['error']['request_id'] != body['request_id']
        other = c.post('/api/workspaces', headers=AUTH, json={'name': 'other'}).json()['id']
        check_error(c.get(f'/api/workspaces/{other}/nodes/{first.json()["resource_item_id"]}', headers=AUTH),
                    404, 'not_found')


@pytest.mark.parametrize('status,code', [(503, 'unavailable'), (507, 'insufficient_storage')])
def test_http_exception_preserves_detail_and_headers(tmp_path, status, code):
    with client(tmp_path) as c:
        @c.app.get('/api/fixture')
        def fixture():
            raise HTTPException(status, '原文件保留', headers={'Retry-After': '1'})
        response = c.get('/api/fixture', headers=AUTH)
        assert check_error(response, status, code)['detail'] == '原文件保留'
        assert response.headers['retry-after'] == '1'


def test_unexpected_error_is_safe_and_non_api_errors_keep_old_shape(tmp_path, caplog):
    with client(tmp_path) as c:
        @c.app.get('/api/fixture')
        def fixture():
            raise RuntimeError(PRIVATE + TOKEN)
        response = c.get('/api/fixture', headers=AUTH)
        value = check_error(response, 500, 'internal_error')
        assert value['detail'] == '请求未完成，请稍后重试'
        assert PRIVATE not in caplog.text and TOKEN not in caplog.text
        assert value['error']['request_id'] in caplog.text
        old = c.get('/media/demo')
        assert old.json() == {'detail': 'Invalid media capability'}
        assert 'x-request-id' not in old.headers
        host = c.get('/media/demo', headers={'Host': 'evil.example'})
        assert host.status_code == 400 and host.text == 'Invalid host header'
        assert c.get('/api/health', headers=AUTH).status_code == 200


def test_started_stream_does_not_get_a_second_error_response(tmp_path):
    from starlette.responses import StreamingResponse

    with client(tmp_path, raise_server_exceptions=False) as c:
        @c.app.get('/api/stream-fixture')
        def fixture():
            async def chunks():
                yield b'first'
                raise RuntimeError(PRIVATE)
            return StreamingResponse(chunks())
        response = c.get('/api/stream-fixture', headers=AUTH)
        assert response.status_code == 200
        assert 'error' not in response.text and PRIVATE not in response.text
        assert 'x-request-id' not in response.headers
