"""User-defined knowledge subjects, scoped independently of question text labels."""
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, StringConstraints
from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from .db import KnowledgeSubjectRevision as Revision
from .db import write_transaction
from .workspaces import require_workspace


class Change(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    request_id: str = Field(min_length=16, max_length=100, pattern=r'^[A-Za-z0-9_-]+$')


class Create(Change):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500,
                                          pattern=r'^[^\x00]+$')]


class Rename(Create):
    expected_revision: int = Field(ge=1)


class Remove(Change):
    expected_revision: int = Field(ge=1)
    confirm: bool


def view(row):
    return dict(id=row.subject_id, name=row.name, revision=row.revision, removed=row.action == 'remove')


def active(workspace):
    latest = select(Revision.subject_id, func.max(Revision.revision).label('revision')).where(
        Revision.workspace_id == workspace).group_by(Revision.subject_id).subquery()
    return select(Revision).join(latest, and_(Revision.subject_id == latest.c.subject_id,
                                              Revision.revision == latest.c.revision)).where(
        Revision.workspace_id == workspace, Revision.action != 'remove')


def change(engine, workspace, subject_id, action, body):
    with write_transaction(engine) as session:
        require_workspace(session, workspace)
        previous = None if action == 'create' else body.expected_revision
        if subject_id is not None and not session.get(Revision, (workspace, subject_id, 1)):
            raise HTTPException(404, '科目不存在')
        if action == 'remove' and not body.confirm:
            raise HTTPException(422, '移除科目需要确认')
        saved = session.scalar(select(Revision).where(Revision.workspace_id == workspace,
                                                       Revision.request_id == body.request_id))
        if saved:
            if (saved.action != action or saved.previous_revision != previous
                    or subject_id is not None and saved.subject_id != subject_id
                    or action != 'remove' and saved.name != body.name):
                raise HTTPException(409, '该请求已用于其他科目修订')
            return view(saved)
        if subject_id is None:
            subject_id = uuid4().hex
            name = body.name
        else:
            current = session.scalar(active(workspace).where(Revision.subject_id == subject_id))
            if current is None:
                raise HTTPException(404, '科目不存在或已移除')
            if current.revision != previous:
                raise HTTPException(409, '科目已修订，请刷新')
            name = current.name if action == 'remove' else body.name
        if action != 'remove' and session.scalar(active(workspace).where(
                Revision.name == name, Revision.subject_id != subject_id).limit(1)):
            raise HTTPException(409, '本空间已有同名科目')
        row = Revision(workspace_id=workspace, subject_id=subject_id, revision=(previous or 0) + 1,
                       previous_revision=previous, request_id=body.request_id, name=name, action=action)
        session.add(row)
        session.flush()
        return view(row)


def subjects_router(engine):
    router = APIRouter(prefix='/api/workspaces/{workspace_id}/knowledge/subjects')

    @router.get('')
    def listing(workspace_id: str, after_id: str = Query('', max_length=32), limit: int = Query(50, ge=1, le=100)):
        with Session(engine) as session:
            require_workspace(session, workspace_id)
            rows = session.scalars(active(workspace_id).where(Revision.subject_id > after_id)
                                   .order_by(Revision.subject_id).limit(limit))
            return [view(row) for row in rows]

    @router.get('/{subject_id}/revisions')
    def history(workspace_id: str, subject_id: str, before: int | None = Query(None, ge=1),
                limit: int = Query(50, ge=1, le=100)):
        with Session(engine) as session:
            require_workspace(session, workspace_id)
            if not session.get(Revision, (workspace_id, subject_id, 1)):
                raise HTTPException(404, '科目不存在')
            query = select(Revision).where(Revision.workspace_id == workspace_id, Revision.subject_id == subject_id)
            if before is not None:
                query = query.where(Revision.revision < before)
            return [dict(view(row), action=row.action) for row in
                    session.scalars(query.order_by(Revision.revision.desc()).limit(limit))]

    @router.post('')
    def create(workspace_id: str, body: Create):
        return change(engine, workspace_id, None, 'create', body)

    @router.post('/{subject_id}/rename')
    def rename(workspace_id: str, subject_id: str, body: Rename):
        return change(engine, workspace_id, subject_id, 'rename', body)

    @router.post('/{subject_id}/remove')
    def remove(workspace_id: str, subject_id: str, body: Remove):
        return change(engine, workspace_id, subject_id, 'remove', body)

    return router
