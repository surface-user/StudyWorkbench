import base64
import hashlib
from datetime import datetime, timezone

import pytest
from sqlalchemy.orm import Session
from study_workbench import agent_access
from study_workbench.db import Attempt, QuestionFileRecord, QuestionVersion, write_transaction
from study_workbench.question_files_format import serialize_file
from test_document_files import add, working
from test_explorer import PREFIX, client
from test_question_files import file_for, preview, publish


def grant(c, ids, include=False, **extra):
    return c.post(PREFIX + '/agent-grants', json=dict(attempt_ids=ids, purpose='analyze_attempts',
        confirm=True, include_content=include, **extra))


def context(c, identifier):
    return c.post(PREFIX + '/agent-grants/' + identifier + '/read-analysis-context')


def confirmed_attempt(c, root):
    file = file_for()
    file.question.id = 'context-fixture-question'
    node, _, _ = add(c, root, '上下文题目.md', serialize_file(file).encode())
    version = publish(c, node, preview(c, node)).json()
    response = c.post(PREFIX + '/attempts', json={'question_id': file.question.id,
        'question_version_id': version['id'], 'response': {'selected': ['a']}})
    assert response.status_code == 200, response.text
    return response.json(), version


def test_default_grant_remains_summary_only_and_legacy_context_never_guesses_current_question(tmp_path):
    with client(tmp_path) as c:
        attempt = c.post(PREFIX + '/attempts', json={'question_id': 'demo-integral', 'response': {'selected': ['a']}}).json()
        basic = grant(c, [attempt['id']]).json()
        value = context(c, basic['id']).json()
        assert value['scope'] == 'summary' and 'response' not in value['attempts'][0]
        assert value['question_versions'] == [] and len(value['context_sha256']) == 64
        explicit = grant(c, [attempt['id']], True).json()
        detailed = context(c, explicit['id']).json()
        assert detailed['attempts'][0]['response'] == {'selected': ['a']}
        assert detailed['attempts'][0]['historical_version_known'] is False
        assert detailed['question_versions'] == [] and detailed['binary_attachments_read'] is False
        assert detailed['latest_reviews_included'] is False
        old_route = c.post(PREFIX + '/agent-grants/' + explicit['id'] + '/read-attempts').json()
        assert 'response' not in old_route['attempts'][0]
        for invalid in [1, 'true', None]:
            assert grant(c, [attempt['id']], invalid).status_code == 422


def test_confirmed_historical_snapshot_hash_scope_expiry_and_source_preservation(tmp_path, monkeypatch):
    clock = [100.0]
    monkeypatch.setattr(agent_access, 'monotonic', lambda: clock[0])
    with client(tmp_path) as c:
        attempt, version = confirmed_attempt(c, tmp_path)
        before = c.get(PREFIX + '/attempts').json()
        identifier = grant(c, [attempt['id']], True).json()['id']
        first = context(c, identifier).json()
        assert first['question_versions'][0]['id'] == version['id']
        assert first['question_versions'][0]['question']['answer']['selected'] == ['a']
        assert context(c, identifier).json()['context_sha256'] == first['context_sha256']
        other = c.post('/api/workspaces', json={'name': '其他'}).json()['id']
        assert c.post(f'/api/workspaces/{other}/agent-grants/{identifier}/read-analysis-context').status_code == 404
        assert context(c, identifier).status_code == 200
        c.delete(PREFIX + '/agent-grants/' + identifier).raise_for_status()
        assert context(c, identifier).status_code == 404
        expiring = grant(c, [attempt['id']], True, expires_in_seconds=1).json()['id']
        original = agent_access.version_read
        def slow(*args):
            result = original(*args)
            clock[0] += 2
            return result
        monkeypatch.setattr(agent_access, 'version_read', slow)
        assert context(c, expiring).status_code == 404
        assert c.get(PREFIX + '/attempts').json() == before


def test_corrupt_confirmed_md_is_not_replaced_by_current_question(tmp_path):
    with client(tmp_path) as c:
        attempt, version = confirmed_attempt(c, tmp_path)
        with Session(c.app.state.engine) as session:
            relative = session.get(QuestionVersion, version['id']).relative_path
        file = tmp_path / relative
        file.write_bytes(b'changed snapshot fixture')
        identifier = grant(c, [attempt['id']], True).json()['id']
        assert context(c, identifier).status_code == 409
        assert file.read_bytes() == b'changed snapshot fixture'


def test_later_confirmation_review_and_event_do_not_expand_granted_historical_snapshot(tmp_path):
    with client(tmp_path) as c:
        attempt, version = confirmed_attempt(c, tmp_path)
        identifier = grant(c, [attempt['id']], True).json()['id']
        original = context(c, identifier).json()
        with Session(c.app.state.engine) as session:
            node = session.get(QuestionFileRecord, ('default', 'context-fixture-question')).node_id
        current = working(c, node)
        changed = file_for()
        changed.question.id = 'context-fixture-question'
        changed.question.stem[0].text = '后续版本新题干，不属于原作答确认版'
        c.put(f'{PREFIX}/nodes/{node}/document', json={'expected_sha256': current['sha256'], 'text': serialize_file(changed)}).raise_for_status()
        latest = publish(c, node, preview(c, node)).json()
        assert latest['id'] != version['id']
        c.post(f"{PREFIX}/attempts/{attempt['id']}/reviews", json={'score': 0.3, 'feedback': '不应读取的后续评分', 'confirm': True}).raise_for_status()
        c.post(f"{PREFIX}/attempts/{attempt['id']}/events", json={'request_id': 'later-context-event-0001', 'kind': 'annotation', 'note': '不应读取的后续备注'}).raise_for_status()
        assert context(c, identifier).json() == original


@pytest.mark.parametrize('count,length', [(1, 65537), (90, 12000)])
def test_single_and_total_context_budgets_refuse_instead_of_truncating(tmp_path, count, length):
    with client(tmp_path) as c:
        with write_transaction(c.app.state.engine) as session:
            rows = [Attempt(workspace_id='default', question_id='demo-integral', response={'text': 'x' * length},
                            status='pending_review', score=None, created_at=datetime.now(timezone.utc).isoformat()) for _ in range(count)]
            session.add_all(rows)
            session.flush()
            ids = [row.id for row in rows]
        identifier = grant(c, ids, True).json()['id']
        response = context(c, identifier)
        assert response.status_code == 413 and 'attempts' not in response.json()
        assert len(c.get(PREFIX + '/attempts?limit=100').json()) == count


def test_total_budget_includes_checksum_field_at_exact_boundary(tmp_path):
    with client(tmp_path) as c:
        with write_transaction(c.app.state.engine) as session:
            rows = [Attempt(workspace_id='default', question_id='demo-integral', response={'text': ''},
                            status='pending_review', score=None, created_at='2026-11-05') for _ in range(17)]
            session.add_all(rows)
            session.flush()
            ids = [row.id for row in rows]
        identifier = grant(c, ids, True).json()['id']
        value = context(c, identifier).json()
        value.pop('context_sha256')
        remaining = 1024 * 1024 - 1 - len(agent_access.AgentAccess.encoded(value))
        with write_transaction(c.app.state.engine) as session:
            for item in ids:
                length = min(64000, remaining)
                session.get(Attempt, item).response = {'text': 'x' * length}
                remaining -= length
        assert remaining == 0
        assert context(c, identifier).status_code == 413


def test_confirmed_attachment_is_metadata_only_without_binary_reads(tmp_path, monkeypatch):
    from study_workbench import question_files
    from test_imports import confirm, upload
    from test_question_files import convert, question
    png = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=')
    with client(tmp_path) as c:
        image = upload(c, png, 'scope-image.png').json()
        q = question()
        q['id'] = 'metadata-only-question'
        q['stem'].append({'type': 'image', 'attachment_id': image['resource_id'], 'alt': '只读元数据'})
        assert confirm(c, upload(c, q).json()).status_code == 200
        node = convert(c, q['id'])
        version = publish(c, node, preview(c, node)).json()
        attempt = c.post(PREFIX + '/attempts', json={'question_id': q['id'], 'question_version_id': version['id'], 'response': {'selected': ['a']}}).json()
        def forbid(*args, **kwargs):
            raise AssertionError('Binary attachment reads are outside this grant')
        monkeypatch.setattr(question_files, 'snapshot_asset', forbid)
        monkeypatch.setattr(question_files, 'read_resource', forbid)
        identifier = grant(c, [attempt['id']], True).json()['id']
        result = context(c, identifier)
        assert result.status_code == 200, result.text
        attachment = result.json()['question_versions'][0]['attachments'][0]
        assert attachment == dict(id=image['resource_id'], mime='image/png', size=len(png), sha256=hashlib.sha256(png).hexdigest())
        assert result.json()['binary_attachments_read'] is False
