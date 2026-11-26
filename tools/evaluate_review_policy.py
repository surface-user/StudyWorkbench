"""Replay review predictions locally from scores available before each submission."""
import argparse
import json
import sqlite3
from bisect import bisect_left
from collections import defaultdict, deque
from contextlib import closing
from datetime import datetime, timezone
from operator import itemgetter
from pathlib import Path


def moment(text, *, require_zone=False):
    value = datetime.fromisoformat(text)
    if value.tzinfo is None:
        if require_zone:
            raise ValueError('评价截止时间必须带时区')
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def matrices():
    return {key: [[0, 0], [0, 0]] for key in ('attempt-review-streak-v1', 'previous_score')}


def grade(score):
    if not isinstance(score, (int, float)) or not 0 <= score <= 1:
        raise ValueError('遇到无效的已评分记录，已停止评价')
    return score


def evaluate(database, workspace, cutoff):
    cutoff = moment(cutoff, require_zone=True)
    reviews, undated_reviews = defaultdict(list), set()
    invalid_review_times = 0
    with closing(sqlite3.connect(database.resolve(strict=True).as_uri() + '?mode=ro', uri=True)) as db:
        db.execute('BEGIN')
        schema = db.execute('SELECT version_num FROM alembic_version').fetchall()
        oldest = schema == [('0001',)]
        if (oldest and workspace != 'default') or (not oldest and
                db.execute('SELECT 1 FROM workspaces WHERE id=?', (workspace,)).fetchone() is None):
            raise ValueError('学习空间不存在')
        columns = {row[1] for row in db.execute('PRAGMA table_info(attempts)')}
        version = 'question_version_id' if 'question_version_id' in columns else 'NULL'
        query = f'SELECT created_at,id,question_id,{version},status,score FROM attempts'
        if not oldest:
            query += ' WHERE workspace_id=?'
        attempts = db.execute(query + ' ORDER BY id', () if oldest else (workspace,))
        query = ('SELECT r.created_at,r.id,r.attempt_id,r.score FROM attempt_reviews r '
                 'JOIN attempts a ON a.id=r.attempt_id WHERE a.workspace_id=?')
        has_review_history = schema not in ([('0001',)], [('0002',)], [('0003',)])
        rows = db.execute(query, (workspace,)) if has_review_history else ()
        for raw, identifier, attempt, score in rows:
            try:
                graded = moment(raw)
            except (ValueError, TypeError, OverflowError):
                invalid_review_times += 1
                undated_reviews.add(attempt)
                continue
            if graded <= cutoff:
                reviews[attempt].append((graded, identifier, grade(score)))

        for changes in reviews.values():
            changes.sort()
        return replay(attempts, reviews, undated_reviews, cutoff, invalid_review_times)


def replay(attempts, reviews, undated_reviews, cutoff, invalid_review_times):
    invalid_attempt_times = 0
    missing = dict(no_history=0, target_ungraded=0, prior_ungraded=0, ambiguous_review_time=0,
                   undated_review=0, ambiguous_attempt_time=0)
    by_version = {key: matrices() for key in ('same', 'changed', 'unknown')}
    counts = matrices()
    compared = total = 0
    history = defaultdict(lambda: deque(maxlen=3))
    for raw, identifier, question, revision, status, score in attempts:
        prior = history[question]
        try:
            submitted = moment(raw)
        except (ValueError, TypeError, OverflowError):
            invalid_attempt_times += 1
            prior.append((identifier, revision, None, None))
            continue
        if submitted > cutoff:
            continue
        initial = grade(score) if status == 'graded' else None
        if reviews.get(identifier) and reviews[identifier][0][0] < submitted:
            undated_reviews.add(identifier)
        total += 1
        if not prior:
            missing['no_history'] += 1
        elif any(when is None or when > submitted for _, _, _, when in prior):
            missing['ambiguous_attempt_time'] += 1
        elif identifier in undated_reviews or any(a in undated_reviews for a, _, _, _ in prior):
            missing['undated_review'] += 1
        else:
            changes = reviews.get(identifier, ())
            actual = changes[-1][2] if changes else initial
            scores = []
            for previous, _, original_score, _ in prior:
                changes = reviews.get(previous, ())
                boundary = bisect_left(changes, submitted, key=itemgetter(0))
                if boundary < len(changes) and changes[boundary][0] == submitted:
                    break
                scores.append(changes[boundary - 1][2] if boundary else original_score)
            if actual is None:
                missing['target_ungraded'] += 1
            elif len(scores) != len(prior):
                missing['ambiguous_review_time'] += 1
            elif scores[-1] is None:
                missing['prior_ungraded'] += 1
            else:
                last_version = prior[-1][1]
                group = 'unknown'
                if revision and last_version:
                    group = 'same' if revision == last_version else 'changed'
                for policy, predicted in (('attempt-review-streak-v1', scores == [1, 1, 1]),
                                          ('previous_score', scores[-1] == 1)):
                    counts[policy][int(predicted)][int(actual == 1)] += 1
                    by_version[group][policy][int(predicted)][int(actual == 1)] += 1
                compared += 1
        prior.append((identifier, revision, initial, submitted))
    return dict(cutoff=cutoff.isoformat(), total=total, compared=compared,
                coverage=compared / total if total else None, excluded=missing,
                invalid_attempt_times=invalid_attempt_times, invalid_review_times=invalid_review_times,
                matrix_rows=['predicted_not_full', 'predicted_full'], matrix_columns=['actual_not_full', 'actual_full'],
                counts=counts, by_confirmed_version=by_version)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', type=Path, required=True)
    parser.add_argument('--workspace', required=True)
    parser.add_argument('--cutoff', required=True)
    args = parser.parse_args()
    try:
        result = evaluate(args.database, args.workspace, args.cutoff)
    except (OSError, ValueError, sqlite3.Error) as error:
        parser.exit(2, f'评价失败：{error}\n')
    print(json.dumps(result, ensure_ascii=True, sort_keys=True))


if __name__ == '__main__':
    main()
