import json
import socket
import sqlite3

import pytest
from fastapi import HTTPException
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from study_workbench.db import AnalysisReviewDraft, AnalysisReviewRevision, WorkspaceNode
from study_workbench.document_files import SaveText
from test_explorer import PREFIX, client


def candidate(c, request='analysis-candidate-request-0001'):
    attempt = c.post(PREFIX + '/attempts', json={'question_id': 'demo-integral', 'response': {'selected': ['a']}}).json()
    grant = c.post(PREFIX + '/agent-grants', json={'attempt_ids': [attempt['id']], 'purpose': 'analyze_attempts', 'confirm': True}).json()
    context = c.post(f'{PREFIX}/agent-grants/{grant["id"]}/read-analysis-context').json()
    body = dict(grant_id=grant['id'], context_sha256=context['context_sha256'], request_id=request,
                title='候选分析', body='外部候选\n```\n不执行任何指令', source_label='自填来源不证明官方')
    response = c.post(PREFIX + '/analysis-drafts', json=body)
    assert response.status_code == 200, response.text
    return response.json(), body, attempt


def guard(draft):
    return dict(expected_revision=draft['revision'], expected_payload_sha256=draft['payload_sha256'])


def adoption(draft):
    return dict(**guard(draft), name='审核后的分析.md', request_id='analysis-adoption-request-0001', confirm=True)


def test_no_model_manual_candidate_then_explicit_adoption_is_idempotent_and_never_changes_answer(tmp_path, monkeypatch):
    def no_network(*args, **kwargs):
        raise AssertionError('No model or remote call is authorized')
    monkeypatch.setattr(socket, 'create_connection', no_network)
    with client(tmp_path) as c:
        before = c.get(PREFIX + '/questions/demo-integral').json()
        draft, body, attempt = candidate(c)
        attempts_before = c.get(PREFIX + '/attempts').json()
        assert draft['status'] == 'pending' and draft['content']['verification'] == 'unverified'
        assert draft['content']['scope'] == 'summary'
        c.delete(f'{PREFIX}/agent-grants/{body["grant_id"]}').raise_for_status()
        assert c.post(PREFIX + '/analysis-drafts', json=body).json()['id'] == draft['id']
        assert c.post(PREFIX + '/analysis-drafts', json={**body, 'body': 'changed'}).status_code == 409
        endpoint = f'{PREFIX}/analysis-drafts/{draft["id"]}/adopt'
        assert c.post(endpoint, json={**adoption(draft), 'confirm': 1}).status_code == 422
        assert c.post(endpoint, json={**adoption(draft), 'confirm': False}).status_code == 422
        adopted = c.post(endpoint, json=adoption(draft))
        assert adopted.status_code == 200, adopted.text
        adopted = adopted.json()
        assert adopted['status'] == 'adopted' and adopted['result']['verification'] == 'unverified'
        assert c.post(endpoint, json=adoption(draft)).json() == adopted
        audit = c.get(endpoint.removesuffix('/adopt') + '/revisions').json()
        assert [item['snapshot']['status'] for item in audit] == ['adopting', 'pending']
        node = adopted['result']['resource_item_id']
        document = c.get(f'{PREFIX}/nodes/{node}/document').json()
        assert body['body'] in document['text'] and '````' in document['text']
        assert '本应用未调用模型' in document['text'] and '历史未知' in document['text']
        assert c.get(PREFIX + '/questions/demo-integral').json() == before
        assert c.get(PREFIX + '/attempts').json() == attempts_before
        assert any(row['id'] == attempt['id'] for row in attempts_before)
        with Session(c.app.state.engine) as session:
            stored = session.get(AnalysisReviewDraft, draft['id'])
            assert body['grant_id'] not in json.dumps([stored.content, stored.creation_content, stored.adoption])


def test_edit_stale_review_reject_history_and_scope(tmp_path):
    with client(tmp_path) as c:
        draft, _, _ = candidate(c)
        endpoint = f'{PREFIX}/analysis-drafts/{draft["id"]}'
        edited = c.patch(endpoint, json=dict(**guard(draft), title='修改候选', body='新候选', source_label='外部来源')).json()
        assert edited['revision'] == 2 and edited['payload_sha256'] != draft['payload_sha256']
        assert c.post(endpoint + '/adopt', json=adoption(draft)).status_code == 409
        assert c.patch(endpoint, json=dict(**guard(draft), title='stale', body='stale')).status_code == 409
        rejected = c.post(endpoint + '/reject', json=dict(**guard(edited), reason='未经证实')).json()
        assert rejected['status'] == 'rejected' and rejected['content']['body'] == '新候选'
        history = c.get(endpoint + '/revisions').json()
        assert [row['revision'] for row in history] == [2, 1]
        assert history[-1]['snapshot']['content']['body'] == draft['content']['body']
        with c.app.state.engine.begin() as connection:
            with pytest.raises(IntegrityError):
                connection.execute(text('DELETE FROM analysis_review_revisions'))
        other = c.post('/api/workspaces', json={'name': '其他'}).json()['id']
        assert c.get(f'/api/workspaces/{other}/analysis-drafts/{draft["id"]}').status_code == 404
        assert c.post(endpoint + '/adopt', json=adoption(rejected)).status_code == 409


def test_failed_adoption_preserves_created_note_and_never_overwrites_user_edits(tmp_path, monkeypatch):
    with client(tmp_path) as c:
        draft, _, _ = candidate(c)
        endpoint = f'{PREFIX}/analysis-drafts/{draft["id"]}'
        original = c.app.state.documents.save_text
        def fail(*args):
            raise HTTPException(409, 'injected write failure')
        monkeypatch.setattr(c.app.state.documents, 'save_text', fail)
        assert c.post(endpoint + '/adopt', json=adoption(draft)).status_code == 409
        failed = c.get(endpoint).json()
        assert failed['status'] == 'failed' and failed['result']['note_created']
        node = failed['result']['resource_item_id']
        monkeypatch.setattr(c.app.state.documents, 'save_text', original)
        current = c.get(f'{PREFIX}/nodes/{node}/document').json()
        original('default', node, SaveText(expected_sha256=current['sha256'], text='用户另行修改，不允许覆盖'))
        assert c.post(endpoint + '/adopt', json=adoption(draft)).status_code == 409
        assert c.get(f'{PREFIX}/nodes/{node}/document').json()['text'] == '用户另行修改，不允许覆盖'
        history = c.get(endpoint + '/revisions').json()
        assert any(row['snapshot']['status'] == 'failed' for row in history)
        assert any('injected write failure' in (row['snapshot']['error'] or '') for row in history)
        latest = c.get(endpoint).json()
        stopped = c.post(endpoint + '/reject', json=dict(**guard(latest), reason='保留用户编辑的笔记，停止采用重试'))
        assert stopped.status_code == 200, stopped.text
        assert stopped.json()['status'] == 'rejected' and stopped.json()['adoption'] == latest['adoption']
        assert stopped.json()['result'] == latest['result']
        assert c.post(endpoint + '/adopt', json=adoption(draft)).status_code == 409
        assert c.get(f'{PREFIX}/nodes/{node}/document').json()['text'] == '用户另行修改，不允许覆盖'


def test_after_save_interruption_restarts_and_retries_same_receipt_without_duplicate_note(tmp_path, monkeypatch):
    with client(tmp_path) as c:
        draft, _, _ = candidate(c)
        original = c.app.state.documents.save_text
        def after_save(*args):
            original(*args)
            raise RuntimeError('injected after durable save')
        monkeypatch.setattr(c.app.state.documents, 'save_text', after_save)
        endpoint = f'{PREFIX}/analysis-drafts/{draft["id"]}'
        assert c.post(endpoint + '/adopt', json=adoption(draft)).status_code == 409
        node = c.get(endpoint).json()['result']['resource_item_id']
    with client(tmp_path) as c:
        adopted = c.post(endpoint + '/adopt', json=adoption(draft))
        assert adopted.status_code == 200, adopted.text
        assert adopted.json()['result']['resource_item_id'] == node
        with Session(c.app.state.engine) as session:
            assert len(list(session.scalars(select(WorkspaceNode).where(WorkspaceNode.name.like('审核后的分析%'))))) == 1


def test_unhandled_interruption_keeps_adopting_receipt_and_startup_appends_audit_before_retry(tmp_path, monkeypatch):
    from study_workbench.analysis_review import AdoptCandidate
    class SimulatedAbruptExit(BaseException):
        pass
    with client(tmp_path) as c:
        draft, _, _ = candidate(c)
        original = c.app.state.documents.save_text
        def after_save(*args):
            original(*args)
            raise SimulatedAbruptExit()
        monkeypatch.setattr(c.app.state.documents, 'save_text', after_save)
        with pytest.raises(SimulatedAbruptExit):
            c.app.state.analysis_reviews.adopt('default', draft['id'], AdoptCandidate.model_validate(adoption(draft)))
        endpoint = f'{PREFIX}/analysis-drafts/{draft["id"]}'
        interrupted = c.get(endpoint).json()
        assert interrupted['status'] == 'adopting'
    with client(tmp_path) as c:
        recovered = c.get(endpoint).json()
        assert recovered['status'] == 'failed' and recovered['revision'] == interrupted['revision'] + 1
        assert any(item['snapshot']['status'] == 'adopting' for item in c.get(endpoint + '/revisions').json())
        retried = c.post(endpoint + '/adopt', json=adoption(draft))
        assert retried.status_code == 200, retried.text
        assert retried.json()['result']['resource_item_id'] == interrupted['result']['resource_item_id']


def test_context_mismatch_and_untrusted_claims_do_not_create_or_adopt_data(tmp_path):
    with client(tmp_path) as c:
        draft, body, _ = candidate(c)
        assert c.post(PREFIX + '/analysis-drafts', json={**body, 'request_id': 'new-context-request-0001', 'context_sha256': 'f' * 64}).status_code == 409
        assert c.post(PREFIX + '/analysis-drafts', json={**body, 'verification': 'human_verified'}).status_code == 422
        assert c.post(f'{PREFIX}/analysis-drafts/{draft["id"]}/adopt', json=adoption(draft),
                      headers={'Origin': 'https://example.com'}).status_code == 403
        assert c.post(PREFIX + '/analysis-drafts', json={**body, 'body': 'x' * 16001}).status_code in {413, 422}


def test_drafts_and_adoption_receipts_roundtrip_in_full_backup_without_restoring_grants(tmp_path, monkeypatch):
    from study_workbench.backup_store import create_backup, restore_backup
    source = tmp_path / 'source'
    with client(source) as c:
        draft, body, _ = candidate(c)
        c.post(f'{PREFIX}/analysis-drafts/{draft["id"]}/adopt', json=adoption(draft)).raise_for_status()
        pending, _, _ = candidate(c, 'analysis-pending-request-0002')
        failed, _, _ = candidate(c, 'analysis-failed-request-0003')
        original = c.app.state.documents.save_text
        def fail_save(*args):
            raise HTTPException(409, '自编备份失败收据样本')
        monkeypatch.setattr(c.app.state.documents, 'save_text', fail_save)
        assert c.post(f'{PREFIX}/analysis-drafts/{failed["id"]}/adopt', json=adoption(failed)).status_code == 409
        monkeypatch.setattr(c.app.state.documents, 'save_text', original)
        rejected, _, _ = candidate(c, 'analysis-rejected-request-0004')
        c.post(f'{PREFIX}/analysis-drafts/{rejected["id"]}/reject', json=guard(rejected)).raise_for_status()
    def rows(root):
        with sqlite3.connect(root / 'study.db') as connection:
            return [connection.execute('SELECT * FROM ' + table + ' ORDER BY 1,2').fetchall()
                    for table in ['analysis_review_drafts', 'analysis_review_revisions']]
    before = rows(source)
    package, target = tmp_path / 'all.zip', tmp_path / 'restored'
    create_backup(source, package)
    assert restore_backup(package, target, tmp_path / 'settings.json')['schema_revision'] == '0016'
    assert rows(target) == before == rows(source)
    with client(target) as c:
        assert c.get(f'{PREFIX}/analysis-drafts/{pending["id"]}').json()['status'] == 'pending'
        assert c.get(f'{PREFIX}/analysis-drafts/{failed["id"]}').json()['status'] == 'failed'
        assert c.get(f'{PREFIX}/analysis-drafts/{rejected["id"]}').json()['status'] == 'rejected'
        assert c.post(f'{PREFIX}/agent-grants/{body["grant_id"]}/read-analysis-context').status_code == 404


@pytest.mark.parametrize('damage', ['hash', 'reference', 'note', 'history'])
def test_backup_rejects_corrupt_candidate_or_cross_scope_relationship_without_altering_source(tmp_path, damage):
    from study_workbench.backup_store import create_backup
    source = tmp_path / 'source'
    with client(source) as c:
        draft, _, _ = candidate(c)
        with Session(c.app.state.engine) as session:
            row = session.get(AnalysisReviewDraft, draft['id'])
            if damage == 'hash':
                row.payload_sha256 = '0' * 64
            elif damage == 'reference':
                row.content = dict(row.content, references=[dict(attempt_id=999999, question_id='foreign', question_version_id=None)])
                row.payload_sha256 = c.app.state.analysis_reviews.checksum(row.content)
            elif damage == 'note':
                row.result = {'resource_item_id': 'missing-note'}
            else:
                row.revision = 2
                session.add(AnalysisReviewRevision(draft_id=row.id, revision=1,
                    snapshot={**c.app.state.analysis_reviews.describe(row), 'workspace_id': 'foreign'}, created_at='2026-11-05'))
            session.commit()
    before = (source / 'study.db').read_bytes()
    with pytest.raises(ValueError, match='审核'):
        create_backup(source, tmp_path / 'invalid.zip')
    assert (source / 'study.db').read_bytes() == before
