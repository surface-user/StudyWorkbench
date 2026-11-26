import hashlib
import json
import sqlite3
import subprocess
import sys
from contextlib import closing
from pathlib import Path

import pytest
from test_explorer import PREFIX, client

TOOLS = Path(__file__).resolve().parents[2] / 'tools'


@pytest.fixture
def evaluate(monkeypatch):
    monkeypatch.syspath_prepend(str(TOOLS))
    from evaluate_review_policy import evaluate
    return evaluate


def stamp(day):
    return f'2026-01-{day:02d}T12:00:00+00:00'


def store(path, marks):
    with closing(sqlite3.connect(path)) as db:
        db.executescript("""
            CREATE TABLE alembic_version(version_num); INSERT INTO alembic_version VALUES ('0021');
            CREATE TABLE workspaces(id); INSERT INTO workspaces VALUES ('demo'),('elsewhere');
            CREATE TABLE attempts (id INTEGER PRIMARY KEY, workspace_id, question_id, question_version_id,
                                   status, score, created_at);
            CREATE TABLE attempt_reviews(id INTEGER PRIMARY KEY, attempt_id, score, created_at);
        """)
        for i, (score, version) in enumerate(marks, 1):
            db.execute('INSERT INTO attempts VALUES (?,?,?,?,?,?,?)',
                       (i, 'demo', 'question', version, 'pending_review' if score is None else 'graded', score, stamp(i)))
        db.commit()


def test_comparison_uses_shared_targets_and_keeps_version_cohorts(tmp_path, evaluate):
    path = tmp_path / 'study.db'
    store(path, [(1, 'v1'), (1, 'v1'), (1, 'v1'), (.5, 'v1'), (1, 'v2'), (1, None)])
    base = evaluate(path, 'demo', stamp(7))
    assert (base['total'], base['compared'], base['excluded']['no_history']) == (6, 5, 1)
    assert base['counts'] == {'attempt-review-streak-v1': [[0, 4], [1, 0]], 'previous_score': [[0, 1], [1, 3]]}
    assert base['by_confirmed_version']['changed']['previous_score'] == [[0, 1], [0, 0]]
    assert base['by_confirmed_version']['unknown']['previous_score'] == [[0, 0], [0, 1]]
    with closing(sqlite3.connect(path)) as db:
        db.execute('INSERT INTO attempt_reviews VALUES (1,3,0,?)', (stamp(8),))
        db.execute('INSERT INTO attempts VALUES (7,?,?,?,?,?,?)', ('elsewhere', 'question', 'v1', 'graded', 0, stamp(7)))
        db.commit()
    assert evaluate(path, 'demo', stamp(7)) == base
    assert evaluate(path, 'elsewhere', stamp(1))['coverage'] is None


def test_late_and_simultaneous_review_are_not_prior_scores(tmp_path, evaluate):
    path = tmp_path / 'study.db'
    store(path, [(None, None), (1, None), (1, None)])
    with closing(sqlite3.connect(path)) as db:
        db.execute('INSERT INTO attempt_reviews VALUES (1,1,1,?)', (stamp(3),))
        db.commit()
    result = evaluate(path, 'demo', stamp(4))
    assert result['compared'] == 0 and result['total'] == 3
    assert result['excluded']['prior_ungraded'] == result['excluded']['ambiguous_review_time'] == 1
    with closing(sqlite3.connect(path)) as db:
        db.execute('UPDATE attempt_reviews SET created_at=?', (stamp(4),))
        db.commit()
    result = evaluate(path, 'demo', stamp(4))
    assert result['compared'] == 1 and result['counts']['attempt-review-streak-v1'] == [[0, 1], [0, 0]]


def test_later_grade_labels_target_without_rewriting_the_prediction(tmp_path, evaluate):
    path = tmp_path / 'study.db'
    store(path, [(1, 'v1'), (1, 'v1'), (1, 'v1'), (None, 'v1')])
    with closing(sqlite3.connect(path)) as db:
        db.executemany('INSERT INTO attempt_reviews VALUES (?,?,?,?)',
                       [(1, 4, .5, stamp(5)), (2, 4, 1, stamp(6)), (3, 1, 0, stamp(7))])
        db.commit()
    at_five = evaluate(path, 'demo', stamp(5))
    assert at_five['counts']['attempt-review-streak-v1'] == [[0, 2], [1, 0]]
    later = evaluate(path, 'demo', stamp(8))
    assert later['counts']['attempt-review-streak-v1'] == [[0, 2], [0, 1]]
    assert later['counts']['previous_score'] == [[0, 0], [0, 3]]


def test_old_unversioned_library_and_invalid_times(tmp_path, evaluate):
    path = tmp_path / 'old.db'
    with closing(sqlite3.connect(path)) as db:
        db.executescript("""
            CREATE TABLE alembic_version(version_num); INSERT INTO alembic_version VALUES ('0001');
            CREATE TABLE attempts (id INTEGER PRIMARY KEY, question_id, status, score, created_at);
        """)
        db.executemany("INSERT INTO attempts VALUES (?, 'q', 'graded', 1, ?)",
                       [(1, stamp(1)), (2, stamp(2)), (3, 'unknown'), (4, stamp(4))])
        db.commit()
    result = evaluate(path, 'default', stamp(5))
    assert result['invalid_attempt_times'] == 1 and result['excluded']['ambiguous_attempt_time'] == 1
    assert result['by_confirmed_version']['unknown']['previous_score'] == [[0, 0], [0, 1]]
    with pytest.raises(ValueError):
        evaluate(path, 'foreign', stamp(5))
    with pytest.raises(ValueError):
        evaluate(path, 'default', '2026-01-06')


def test_cli_reads_real_managed_attempts_without_changing_the_database(tmp_path):
    with client(tmp_path) as c:
        for _ in range(2):
            c.post(PREFIX + '/attempts', json={'question_id': 'demo-integral',
                                              'response': {'selected': ['a']}}).raise_for_status()
    path = tmp_path / 'study.db'
    digest = hashlib.sha256(path.read_bytes()).digest()
    command = [sys.executable, str(TOOLS / 'evaluate_review_policy.py'), '--database', str(path),
               '--workspace', 'default', '--cutoff', '2090-01-01T00:00:00Z']
    first = subprocess.check_output(command)
    assert first == subprocess.check_output(command)
    result = json.loads(first)
    assert result['total'] == 2 and result['compared'] == 1 and b'demo-integral' not in first
    assert hashlib.sha256(path.read_bytes()).digest() == digest


def test_impossible_grades_and_undated_reviews_are_not_scored_as_mistakes(tmp_path, evaluate):
    path = tmp_path / 'study.db'
    store(path, [(1, 'v1'), (0, 'v1')])
    with closing(sqlite3.connect(path)) as db:
        db.execute("INSERT INTO attempt_reviews VALUES (1,1,1,'unknown')")
        db.commit()
    result = evaluate(path, 'demo', stamp(3))
    assert result['invalid_review_times'] == 1 and result['compared'] == 0
    assert result['excluded']['undated_review'] == 1
    with closing(sqlite3.connect(path)) as db:
        db.execute('UPDATE attempts SET score=2 WHERE id=2')
        db.commit()
    with pytest.raises(ValueError, match='无效的已评分记录'):
        evaluate(path, 'demo', stamp(3))
