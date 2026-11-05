from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import event, select
from sqlalchemy.orm import Session
from study_workbench.db import Attempt, AttemptReview
from study_workbench.learning import study_rows
from test_imports import SCOPE, client, confirm, upload
from test_question_protocol import question


def seed(c, kind):
    q = question(kind)
    q['id'] = 'study-' + kind
    raw = {'schema_version': 1, 'questions': [q], 'passages': []}
    if kind == 'reading_question':
        raw['passages'] = [{'id': q['passage_id'], 'content': [{'type': 'text', 'text': '共享文章'}], 'source': q['source']}]
    job = upload(c, raw).json()
    assert job['status'] == 'preview'
    assert confirm(c, job).status_code == 200
    return q


@pytest.mark.parametrize('kind,response,score', [
    ('single_choice', {'selected': ['a']}, 1),
    ('multiple_choice', {'selected': ['b', 'a']}, 1),
    ('multiple_choice', {'selected': ['a']}, 0),
    ('fill_blank', {'blanks': {'blank-1': ' 1/3 '}}, 1),
    ('calculation', {'text': '过程'}, None),
    ('proof', {'text': '证明'}, None),
    ('subjective', {'text': '主观作答'}, None),
    ('reading_question', {'selected': ['a']}, 1),
])
def test_grading_all_kinds_and_idempotency(tmp_path, kind, response, score):
    with client(tmp_path) as c:
        q = seed(c, kind)
        body = {'question_id': q['id'], 'question_revision': 1, 'request_id': 'stable_submission_001', 'response': response}
        first = c.post(f'{SCOPE}/attempts', json=body)
        assert first.status_code == 200, first.text
        assert first.json()['score'] == score
        assert first.json()['status'] == ('pending_review' if score is None else 'graded')
        assert c.post(f'{SCOPE}/attempts', json=body).json()['id'] == first.json()['id']
        assert len(c.get(f'{SCOPE}/attempts').json()) == 1
        body['response'] = {'text': 'different'}
        assert c.post(f'{SCOPE}/attempts', json=body).status_code == 409


def test_append_only_reviews_and_workspace_isolation(tmp_path):
    with client(tmp_path) as c:
        result = c.post(f'{SCOPE}/attempts', json={'question_id': 'demo-proof', 'response': {'text': 'my answer'}}).json()
        for score in (0.3, 0.8):
            response = c.post(f"{SCOPE}/attempts/{result['id']}/reviews", json={'score': score, 'feedback': '人工修订', 'confirm': True})
            assert response.status_code == 200
        history = c.get(f'{SCOPE}/attempts').json()[0]
        assert history['score'] == 0.8 and len(history['reviews']) == 2
        assert history['response'] == {'text': 'my answer'}
        with Session(c.app.state.engine) as session:
            original = session.get(Attempt, result['id'])
            assert original.status == 'pending_review' and original.score is None
        other = c.post('/api/workspaces', json={'name': '另一个'}).json()['id']
        assert c.post(f"/api/workspaces/{other}/attempts/{result['id']}/reviews", json={'score': 1, 'feedback': '跨空间', 'confirm': True}).status_code == 404
        assert c.get(f'/api/workspaces/{other}/attempts').json() == []
        assert c.post(f"{SCOPE}/attempts/{result['id']}/reviews", json={'score': 0.5, 'feedback': 'no confirm'}).status_code == 422


def test_mastery_due_selection_and_task_progress_survive_restart(tmp_path):
    with client(tmp_path) as c:
        for _ in range(3):
            c.post(f'{SCOPE}/attempts', json={'question_id': 'demo-integral', 'response': {'selected': ['a']}})
        stats = c.get(f'{SCOPE}/statistics').json()
        assert stats['mastered'] == 1 and stats['attempts'] == 3
        due_ids = {r['id'] for r in c.get(f'{SCOPE}/study').json()}
        assert 'demo-integral' not in due_ids and 'demo-proof' in due_ids
        task = c.post(f'{SCOPE}/study-tasks', json={'title': '今日任务', 'count': 10}).json()
        assert task['question_ids'] == ['demo-proof']
        c.post(f'{SCOPE}/attempts', json={'question_id': 'demo-proof', 'response': {'text': '待批改作答'}})
        assert c.get(f'{SCOPE}/study-tasks').json()[0]['completed_question_ids'] == ['demo-proof']
        assert c.get(f'{SCOPE}/study').json() == []
        with Session(c.app.state.engine) as session:
            future = study_rows(session, 'default', now=datetime.now(timezone.utc) + timedelta(days=8))
            assert next(r for r in future if r['id'] == 'demo-integral')['due'] is True
    with client(tmp_path) as c:
        assert c.get(f'{SCOPE}/statistics').json()['attempts'] == 4
        assert c.get(f'{SCOPE}/study-tasks').json()[0]['id'] == task['id']


def test_wrong_filters_and_server_owned_answers(tmp_path):
    with client(tmp_path) as c:
        c.post(f'{SCOPE}/attempts', json={'question_id': 'demo-integral', 'response': {'selected': ['b']}})
        rows = c.get(f'{SCOPE}/study?mode=wrong').json()
        assert [r['id'] for r in rows] == ['demo-integral']
        assert c.get(f'{SCOPE}/study?mode=wrong&subject=absent').json() == []
        body = {'question_id': 'demo-integral', 'question_revision': 999, 'response': {'selected': ['a']}}
        assert c.post(f'{SCOPE}/attempts', json=body).status_code == 409
        body.pop('question_revision')
        for response in ({'selected': ['a', 'a']}, {'selected': ['missing']}, {'selected': ['a'], 'score': 1}):
            body['response'] = response
            assert c.post(f'{SCOPE}/attempts', json=body).status_code == 422
        assert len(c.get(f'{SCOPE}/attempts').json()) == 1
        with Session(c.app.state.engine) as session:
            assert len(list(session.scalars(select(Attempt)))) == 1


def test_m2_upgrade_keeps_notes_previews_and_old_attempts(tmp_path):
    import json
    import sqlite3
    from pathlib import Path

    from alembic import command
    from alembic.config import Config
    from study_workbench.content import DEMO
    from study_workbench.db import database

    engine = database(tmp_path / 'study.db')
    config = Config()
    config.set_main_option('script_location', str(Path(__file__).parents[1] / 'migrations'))
    with engine.begin() as connection:
        config.attributes['connection'] = connection
        command.upgrade(config, '0003')
        connection.exec_driver_sql('INSERT INTO questions VALUES (?, ?, ?)', (DEMO['id'], 'default', json.dumps(DEMO)))
        connection.exec_driver_sql("INSERT INTO attempts VALUES (7, 'default', ?, ?, 'graded', 1.0, '2026-10-24T00:00:00+00:00')",
                                   (DEMO['id'], json.dumps({'selected': ['a']})))
        connection.exec_driver_sql("INSERT INTO resources VALUES ('original', 'default', 'old.txt', 'old.bin', 'old-hash', 3, 'text/plain')")
        connection.exec_driver_sql("INSERT INTO notes VALUES ('old-note', 'default', 'original', '旧笔记', ?)",
                                   (json.dumps([{'type': 'text', 'text': '旧内容'}]),))
    engine.dispose()
    with client(tmp_path) as c:
        assert c.get(f'{SCOPE}/notes').json()[0]['content'][0]['text'] == '旧内容'
        attempt = c.get(f'{SCOPE}/attempts').json()[0]
        assert attempt['id'] == 7 and attempt['question_revision'] is None and attempt['reviews'] == []
        assert c.get(f'{SCOPE}/statistics').json()['attempts'] == 1
    backups = list((tmp_path / 'backups').glob('study-before-0016-*.db'))
    assert len(backups) == 1
    with sqlite3.connect(backups[0]) as backup:
        assert backup.execute('SELECT version_num FROM alembic_version').fetchone() == ('0003',)
        assert backup.execute('SELECT title FROM notes').fetchone() == ('旧笔记',)


def test_history_cursor_keeps_reviews_and_is_stable_during_append(tmp_path):
    with client(tmp_path) as c:
        ids = [c.post(f'{SCOPE}/attempts', json={
            'question_id': 'demo-proof', 'response': {'text': f'作答{i}'}}).json()['id'] for i in range(5)]
        for score in (0.4, 0.9):
            c.post(f'{SCOPE}/attempts/{ids[3]}/reviews', json={
                'score': score, 'feedback': '评分修订', 'confirm': True}).raise_for_status()
        other = c.post('/api/workspaces', json={'name': '隔离历史'}).json()['id']
        c.post(f'/api/workspaces/{other}/attempts', json={
            'question_id': 'demo-proof', 'response': {'text': '其他空间'}}).raise_for_status()
        first = c.get(f'{SCOPE}/attempt-history?limit=2').json()
        assert [a['id'] for a in first] == ids[::-1][:2]
        assert first[1]['response'] == {'text': '作答3'}
        assert first[1]['score'] == 0.9 and [r['score'] for r in first[1]['reviews']] == [0.4, 0.9]
        c.post(f'{SCOPE}/attempts', json={
            'question_id': 'demo-proof', 'response': {'text': '分页期间新增'}}).raise_for_status()
        second = c.get(f"{SCOPE}/attempt-history?limit=2&before_id={first[-1]['id']}").json()
        third = c.get(f"{SCOPE}/attempt-history?limit=2&before_id={second[-1]['id']}").json()
        assert [a['id'] for a in first + second + third] == ids[::-1]
        assert c.get(f"{SCOPE}/attempt-history?before_id={ids[0]}").json() == []
        # The demo compatibility route still returns ascending, unpaged history.
        assert len(c.get('/api/attempts').json()) == 6
        assert c.get('/api/attempts').json()[0]['id'] == ids[0]
        for query in ('limit=0', 'limit=101', 'before_id=0', 'before_id=x'):
            assert c.get(f'{SCOPE}/attempt-history?{query}').status_code == 422
        assert c.get('/api/workspaces/missing/attempt-history').status_code == 404
        assert c.get(f'{SCOPE}/attempt-history', headers={'Origin': 'https://example.com'}).status_code == 403
        assert c.get(f'{SCOPE}/attempt-history', headers={'Authorization': 'Bearer wrong'}).status_code == 401
    with client(tmp_path) as c:
        assert c.get(f"{SCOPE}/attempt-history?limit=1&before_id={ids[4]}").json()[0]['score'] == 0.9


def test_large_history_reads_only_page_and_lightweight_statistics(tmp_path):
    with client(tmp_path) as c:
        engine = c.app.state.engine
        timestamp = datetime.now(timezone.utc).isoformat()
        with Session(engine) as session, session.begin():
            session.add_all([Attempt(id=i, workspace_id='default', question_id='demo-proof',
                                    response={'text': '正文' * 1000}, status='pending_review', score=None,
                                    created_at=timestamp) for i in range(1, 1201)])
            session.flush()
            session.add_all([AttemptReview(attempt_id=i, score=score, feedback='说明' * 1000, created_at=timestamp)
                             for i in range(1, 1201) for score in (0.5, 1)])
        loaded = []

        def remember(_session, instance):
            loaded.append(instance)

        event.listen(Session, 'loaded_as_persistent', remember)
        try:
            page = c.get(f'{SCOPE}/attempt-history?limit=50').json()
            assert len(page) == 50 and page[0]['id'] == 1200 and page[-1]['id'] == 1151
            assert all(a['score'] == 1 and len(a['reviews']) == 2 for a in page)
            assert sum(isinstance(row, Attempt) for row in loaded) == 50
            assert sum(isinstance(row, AttemptReview) for row in loaded) == 100
            loaded.clear()
            stats = c.get(f'{SCOPE}/statistics').json()
            assert stats['attempts'] == 1200 and stats['mastered'] == 1 and stats['pending_review'] == 0
            assert c.get(f'{SCOPE}/study?mode=wrong').json() == []
            c.post(f'{SCOPE}/study-tasks', json={'title': '性能回归', 'mode': 'all'}).raise_for_status()
            assert c.get(f'{SCOPE}/study-tasks').status_code == 200
            assert not any(isinstance(row, (Attempt, AttemptReview)) for row in loaded)
        finally:
            event.remove(Session, 'loaded_as_persistent', remember)


def test_zero_review_breaks_mastery_and_pending_attempt_stops_streak(tmp_path):
    with client(tmp_path) as c:
        ids = [c.post(f'{SCOPE}/attempts', json={
            'question_id': 'demo-integral', 'response': {'selected': ['a']}}).json()['id'] for _ in range(3)]
        c.post(f'{SCOPE}/attempts/{ids[-1]}/reviews', json={
            'score': 0, 'feedback': '更正为零分', 'confirm': True}).raise_for_status()
        assert c.get(f'{SCOPE}/statistics').json()['mastered'] == 0
        wrong = c.get(f'{SCOPE}/study?mode=wrong').json()
        assert wrong[0]['score'] == 0 and wrong[0]['streak'] == 0
        for _ in range(3):
            result = c.post(f'{SCOPE}/attempts', json={
                'question_id': 'demo-proof', 'response': {'text': '主观'}}).json()
            c.post(f"{SCOPE}/attempts/{result['id']}/reviews", json={
                'score': 1, 'feedback': '正确', 'confirm': True}).raise_for_status()
        assert c.get(f'{SCOPE}/statistics').json()['mastered'] == 1
        c.post(f'{SCOPE}/attempts', json={'question_id': 'demo-proof', 'response': {'text': '新作答'}})
        stats = c.get(f'{SCOPE}/statistics').json()
        assert stats['mastered'] == 0 and stats['pending_review'] == 1
