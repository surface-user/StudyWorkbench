"""Offline grading, append-only human review and reproducible spaced practice."""
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .db import Attempt, AttemptReview, Question, StudyTask, write_transaction
from .workspaces import require_workspace


def grade(document, response):
    kind = document.response_kind if document.kind == "reading_question" else document.kind
    if kind in {"single_choice", "multiple_choice"}:
        selected = response.get("selected")
        if (set(response) != {"selected"} or not isinstance(selected, list) or not selected
                or any(not isinstance(s, str) for s in selected) or len(set(selected)) != len(selected)
                or not set(selected) <= {o.id for o in document.options}
                or kind == "single_choice" and len(selected) != 1):
            raise HTTPException(422, "请选择有效且不重复的选项")
        return ("pending_review", None) if document.answer is None else (
            "graded", float(set(selected) == set(document.answer.selected)))
    if kind == "fill_blank":
        values = response.get("blanks")
        ids = document.blank_ids if document.answer is None else [b.id for b in document.answer.blanks]
        if (set(response) != {"blanks"} or not isinstance(values, dict)
                or set(values) != set(ids)
                or any(not isinstance(v, str) or not v.strip() or len(v) > 20000 for v in values.values())):
            raise HTTPException(422, "请填写全部空格，使用题目声明的空格编号")
        if document.answer is None:
            return "pending_review", None
        correct = 0
        for blank in document.answer.blanks:
            value = values[blank.id]
            normalize = str.strip if blank.normalization == "trim" else lambda s: s
            correct += normalize(value) in [normalize(s) for s in blank.accepted]
        return "graded", correct / len(document.answer.blanks)
    if (set(response) != {"text"} or not isinstance(response.get("text"), str)
            or not response["text"].strip() or len(response["text"]) > 20000):
        raise HTTPException(422, "请填写非空解题过程，最多两万字符")
    return "pending_review", None


def attempt_view(attempt, reviews=()):
    revisions = [r for r in reviews if r.attempt_id == attempt.id]
    latest = revisions[-1] if revisions else None
    return {"id": attempt.id, "question_id": attempt.question_id, "response": attempt.response,
            "question_revision": attempt.question_revision, "request_id": attempt.request_id,
            "question_version_id": attempt.question_version_id,
            "status": "graded" if latest else attempt.status, "score": latest.score if latest else attempt.score,
            "created_at": attempt.created_at, "reviews": [
                {"id": r.id, "score": r.score, "feedback": r.feedback, "created_at": r.created_at} for r in revisions]}


def workspace_history(session, workspace_id, *, limit=None, before_id=None):
    query = select(Attempt).where(Attempt.workspace_id == workspace_id)
    if before_id is not None:
        query = query.where(Attempt.id < before_id)
    query = query.order_by(Attempt.id.desc() if limit is not None else Attempt.id)
    if limit is not None:
        query = query.limit(limit)
    attempts = list(session.scalars(query))
    reviews = defaultdict(list)
    # A subquery avoids SQLite's parameter limit for the legacy unpaged reader.
    ids = [a.id for a in attempts] if limit is not None else query.with_only_columns(Attempt.id)
    for review in session.scalars(select(AttemptReview).where(
            AttemptReview.attempt_id.in_(ids)).order_by(AttemptReview.id)):
        reviews[review.attempt_id].append(review)
    return [attempt_view(a, reviews[a.id]) for a in attempts]


def study_rows(session, workspace_id, *, now=None):
    now = now or datetime.now(timezone.utc)
    latest_review = select(func.max(AttemptReview.id).label("id")).join(Attempt).where(
        Attempt.workspace_id == workspace_id).group_by(AttemptReview.attempt_id).subquery()
    scores = select(AttemptReview.attempt_id, AttemptReview.score).join(
        latest_review, AttemptReview.id == latest_review.c.id).subquery()
    query = select(Attempt.question_id, Attempt.created_at, Attempt.status, Attempt.score,
                   scores.c.score.label("review_score")).outerjoin(scores, scores.c.attempt_id == Attempt.id).where(
        Attempt.workspace_id == workspace_id).order_by(Attempt.id).execution_options(yield_per=500)
    history = {}
    for attempt in session.execute(query):
        previous = history.get(attempt.question_id)
        score = attempt.review_score if attempt.review_score is not None else attempt.score
        status = "graded" if attempt.review_score is not None else attempt.status
        streak = (previous["streak"] if previous else 0) + 1 if status == "graded" and score == 1 else 0
        history[attempt.question_id] = {"score": score, "status": status, "created_at": attempt.created_at,
                                        "streak": streak, "count": (previous["count"] if previous else 0) + 1}
    rows = []
    for q in session.scalars(select(Question).where(Question.workspace_id == workspace_id).order_by(Question.id)):
        latest = history.get(q.id)
        streak = latest["streak"] if latest else 0
        interval = [0, 1, 3, 7, 14, 30][min(streak, 5)]
        timestamp = datetime.fromisoformat(latest["created_at"]) if latest else now
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)
        due = timestamp + timedelta(days=interval)
        pending = latest is not None and latest["status"] == "pending_review"
        rows.append({"id": q.id, "subject": q.content["subject"], "kind": q.content["kind"],
                     "knowledge_points": q.content["knowledge_points"], "attempt_count": latest["count"] if latest else 0,
                     "score": latest["score"] if latest else None, "pending_review": pending,
                     "streak": streak, "mastered": streak >= 3, "due_at": due.isoformat(),
                     "due": not pending and due <= now,
                     "wrong": latest is not None and latest["status"] == "graded" and latest["score"] < 1})
    return rows


class Review(BaseModel):
    model_config = ConfigDict(extra="forbid")
    score: float = Field(ge=0, le=1, allow_inf_nan=False)
    feedback: str = Field(min_length=1, max_length=20000, pattern=r"\S")
    confirm: Literal[True]


class Plan(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=240, pattern=r"\S")
    count: int = Field(default=10, ge=1, le=100, strict=True)
    subject: str | None = Field(default=None, max_length=500)
    knowledge_point: str | None = Field(default=None, max_length=500)
    kind: str | None = Field(default=None, max_length=50)
    mode: Literal["due", "wrong", "all"] = "due"


def filtered(rows, subject, knowledge_point, kind, mode):
    result = [r for r in rows if (subject is None or r["subject"] == subject)
              and (knowledge_point is None or knowledge_point in r["knowledge_points"])
              and (kind is None or r["kind"] == kind)
              and (mode == "all" or mode == "due" and r["due"] or mode == "wrong" and r["wrong"])]
    return sorted(result, key=lambda r: (r["mastered"], not r["wrong"], r["due_at"], r["attempt_count"], r["id"]))


def learning_router(engine):
    router = APIRouter(prefix="/api/workspaces/{workspace_id}")

    @router.get("/attempt-history")
    def history(workspace_id: str, limit: int = Query(50, ge=1, le=100),
                before_id: int | None = Query(None, ge=1)):
        with Session(engine) as session:
            require_workspace(session, workspace_id)
            return workspace_history(session, workspace_id, limit=limit, before_id=before_id)

    @router.get("/study")
    def study(workspace_id: str, subject: str | None = None, knowledge_point: str | None = None,
              kind: str | None = None, mode: Literal["due", "wrong", "all"] = "due",
              limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0)):
        with Session(engine) as session:
            require_workspace(session, workspace_id)
            rows = filtered(study_rows(session, workspace_id), subject, knowledge_point, kind, mode)
            return rows[offset:offset + limit]

    @router.get("/statistics")
    def statistics(workspace_id: str):
        with Session(engine) as session:
            require_workspace(session, workspace_id)
            rows = study_rows(session, workspace_id)
            points = defaultdict(list)
            for row in rows:
                for point in row["knowledge_points"]:
                    points[(row["subject"], point)].append(row)
            return {"questions": len(rows), "attempts": sum(r["attempt_count"] for r in rows),
                    "due": sum(r["due"] for r in rows), "wrong": sum(r["wrong"] for r in rows),
                    "mastered": sum(r["mastered"] for r in rows), "pending_review": sum(r["pending_review"] for r in rows),
                    "subjects": sorted({r["subject"] for r in rows}),
                    "knowledge_points": [{"subject": s, "name": p, "questions": len(group),
                                          "mastered": sum(r["mastered"] for r in group),
                                          "wrong": sum(r["wrong"] for r in group)}
                                         for (s, p), group in sorted(points.items())]}

    @router.post("/attempts/{attempt_id}/reviews")
    def review(workspace_id: str, attempt_id: int, body: Review):
        with write_transaction(engine) as session:
            require_workspace(session, workspace_id)
            attempt = session.get(Attempt, attempt_id)
            if attempt is None or attempt.workspace_id != workspace_id:
                raise HTTPException(404, "作答不存在")
            revision = AttemptReview(attempt_id=attempt.id, score=body.score, feedback=body.feedback,
                                     created_at=datetime.now(timezone.utc).isoformat())
            session.add(revision)
            session.flush()
            return attempt_view(attempt, list(session.scalars(select(AttemptReview).where(
                AttemptReview.attempt_id == attempt.id).order_by(AttemptReview.id))))

    @router.post("/study-tasks")
    def plan(workspace_id: str, body: Plan):
        with write_transaction(engine) as session:
            require_workspace(session, workspace_id)
            rows = filtered(study_rows(session, workspace_id), body.subject, body.knowledge_point, body.kind, body.mode)
            ids = [r["id"] for r in rows[:body.count]]
            if not ids:
                raise HTTPException(409, "没有符合条件的题目；已掌握且未到期题目不会反复加入复习")
            task = StudyTask(id=uuid4().hex, workspace_id=workspace_id, title=body.title,
                             question_ids=ids, created_at=datetime.now(timezone.utc).isoformat())
            session.add(task)
            return {"id": task.id, "title": task.title, "question_ids": ids, "created_at": task.created_at}

    @router.get("/study-tasks")
    def tasks(workspace_id: str, offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100)):
        with Session(engine) as session:
            require_workspace(session, workspace_id)
            latest = dict(session.execute(select(Attempt.question_id, func.max(Attempt.created_at)).where(
                Attempt.workspace_id == workspace_id).group_by(Attempt.question_id)).all())
            return [{"id": t.id, "title": t.title, "question_ids": t.question_ids, "created_at": t.created_at,
                     "completed_question_ids": sorted({q for q in t.question_ids
                                                       if q in latest and latest[q] >= t.created_at})}
                    for t in session.scalars(select(StudyTask).where(StudyTask.workspace_id == workspace_id)
                                              .order_by(StudyTask.created_at.desc()).offset(offset).limit(limit))]

    return router
