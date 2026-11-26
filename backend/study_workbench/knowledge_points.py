"""Append-only changes to a subject's knowledge point tree."""
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query
from pydantic import Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import KnowledgePointRevision as Point
from .db import KnowledgeSubjectRevision as Subject
from .db import write_transaction
from .knowledge_subjects import Change, Create, Remove, Rename, active, active_points
from .workspaces import require_workspace


class CreatePoint(Create):
    parent_id: str | None = Field(None, min_length=1, max_length=32)


class Move(Change):
    expected_revision: int = Field(ge=1)
    parent_id: str | None = Field(min_length=1, max_length=32)


def view(row):
    return dict(id=row.point_id, subject_id=row.subject_id, parent_id=row.parent_id, name=row.name,
                revision=row.revision, removed=row.action == 'remove')


def validate_parent(session, current, parent_id, point_id):
    if parent_id is None:
        return
    if session.scalar(current.where(Point.point_id == parent_id)) is None:
        raise HTTPException(404, '目标上级知识点不存在')
    if point_id is None:
        return
    nodes = current.subquery()
    parents = select(nodes.c.point_id, nodes.c.parent_id).where(nodes.c.point_id == parent_id).cte(recursive=True)
    parents = parents.union(select(nodes.c.point_id, nodes.c.parent_id).join(parents, nodes.c.point_id == parents.c.parent_id))
    if session.scalar(select(parents.c.point_id).where(parents.c.point_id == point_id)):
        raise HTTPException(409, '不能移动到自身或后代')


def change_point(engine, workspace, subject, point, action, body):
    with write_transaction(engine) as session:
        require_workspace(session, workspace)
        if not session.get(Subject, (workspace, subject, 1)):
            raise HTTPException(404, '科目不存在')
        if point is not None and not session.get(Point, (workspace, subject, point, 1)):
            raise HTTPException(404, '知识点不存在')
        previous = None if action == 'create' else body.expected_revision
        if action == 'remove' and not body.confirm:
            raise HTTPException(422, '移除知识点需要确认')
        if session.scalar(select(Subject.request_id).where(Subject.workspace_id == workspace,
                                                          Subject.request_id == body.request_id)):
            raise HTTPException(409, '该请求已用于科目修订')
        saved = session.scalar(select(Point).where(Point.workspace_id == workspace, Point.request_id == body.request_id))
        if saved:
            if (saved.action != action or saved.subject_id != subject or saved.previous_revision != previous
                    or point is not None and saved.point_id != point
                    or action in {'rename', 'create'} and saved.name != body.name
                    or action in {'move', 'create'} and saved.parent_id != body.parent_id):
                raise HTTPException(409, '该请求已用于其他知识点修订')
            return view(saved)
        if session.scalar(active(workspace).where(Subject.subject_id == subject)) is None:
            raise HTTPException(404, '科目已移除')
        current = active_points(workspace, subject)
        old = None
        if point is not None:
            old = session.scalar(current.where(Point.point_id == point))
            if old is None:
                raise HTTPException(404, '知识点已移除')
            if old.revision != previous:
                raise HTTPException(409, '知识点已修订，请刷新')
        parent = body.parent_id if action in {'create', 'move'} else old.parent_id
        name = body.name if action in {'create', 'rename'} else old.name
        if action in {'create', 'move'}:
            validate_parent(session, current, parent, point)
        if action == 'remove':
            if session.scalar(current.where(Point.parent_id == point).limit(1)):
                raise HTTPException(409, '请先转移或移除下级知识点')
        elif session.scalar(current.where(Point.parent_id == parent, Point.name == name, Point.point_id != point).limit(1)):
            raise HTTPException(409, '同级已有同名知识点')
        row = Point(workspace_id=workspace, subject_id=subject, point_id=point or uuid4().hex,
                    revision=(previous or 0) + 1, previous_revision=previous, name=name, parent_id=parent,
                    request_id=body.request_id, action=action)
        session.add(row)
        session.flush()
        return view(row)


def points_router(engine):
    router = APIRouter(prefix='/api/workspaces/{workspace_id}/knowledge/subjects/{subject_id}/points')

    @router.get('')
    def listing(workspace_id: str, subject_id: str, parent_id: str | None = Query(None, min_length=1, max_length=32),
                after_id: str = Query('', max_length=32), limit: int = Query(50, ge=1, le=100)):
        with Session(engine) as session:
            require_workspace(session, workspace_id)
            if session.scalar(active(workspace_id).where(Subject.subject_id == subject_id)) is None:
                raise HTTPException(404, '科目不存在或已移除')
            current = active_points(workspace_id, subject_id)
            validate_parent(session, current, parent_id, None)
            rows = session.scalars(current.where(Point.parent_id == parent_id, Point.point_id > after_id)
                                   .order_by(Point.point_id).limit(limit))
            return [view(row) for row in rows]

    @router.get('/{point_id}/revisions')
    def history(workspace_id: str, subject_id: str, point_id: str, before: int | None = Query(None, ge=1),
                limit: int = Query(50, ge=1, le=100)):
        with Session(engine) as session:
            require_workspace(session, workspace_id)
            if not session.get(Point, (workspace_id, subject_id, point_id, 1)):
                raise HTTPException(404, '知识点不存在')
            query = select(Point).where(Point.workspace_id == workspace_id, Point.subject_id == subject_id,
                                        Point.point_id == point_id)
            if before is not None:
                query = query.where(Point.revision < before)
            return [dict(view(row), action=row.action) for row in session.scalars(query.order_by(Point.revision.desc()).limit(limit))]

    @router.post('')
    def create(workspace_id: str, subject_id: str, body: CreatePoint):
        return change_point(engine, workspace_id, subject_id, None, 'create', body)

    @router.post('/{point_id}/rename')
    def rename(workspace_id: str, subject_id: str, point_id: str, body: Rename):
        return change_point(engine, workspace_id, subject_id, point_id, 'rename', body)

    @router.post('/{point_id}/move')
    def move(workspace_id: str, subject_id: str, point_id: str, body: Move):
        return change_point(engine, workspace_id, subject_id, point_id, 'move', body)

    @router.post('/{point_id}/remove')
    def remove(workspace_id: str, subject_id: str, point_id: str, body: Remove):
        return change_point(engine, workspace_id, subject_id, point_id, 'remove', body)

    return router
