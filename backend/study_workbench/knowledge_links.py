"""Workspace knowledge links hold identifiers, never target content."""

from typing import Annotated, Literal
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import and_, exists, or_, select
from sqlalchemy.orm import Session, aliased

from .db import KnowledgeLinkRevision as Link
from .db import KnowledgePointRevision as Point
from .db import Question, WorkspaceNode, write_transaction
from .knowledge_subjects import Change, Name, Remove, require_unused_request
from .workspaces import require_workspace

Identifier = Annotated[str, Field(min_length=1, max_length=128)]


class Reference(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    id: Identifier


class PointRef(Reference):
    subject_id: Identifier


class Related(PointRef):
    kind: Literal['related']


class Directed(PointRef):
    kind: Literal['directed']
    label: Name


class Material(Reference):
    kind: Literal['resource']


class QuestionRef(Reference):
    kind: Literal['question']


class CreateLink(Change):
    source: PointRef
    target: Annotated[Related | Directed | Material | QuestionRef, Field(discriminator='kind')]


def endpoints(body):
    subject, point = body.source.subject_id, body.source.id
    target = body.target
    other_subject = other_point = None
    if isinstance(target, PointRef):
        other_subject, other_point = target.subject_id, target.id
        if target.kind == 'related' and (subject, point) > (other_subject, other_point):
            (subject, point), (other_subject, other_point) = (other_subject, other_point), (subject, point)
    return dict(
        subject_id=subject,
        point_id=point,
        kind=target.kind,
        target_subject_id=other_subject,
        target_point_id=other_point,
        label=target.label if isinstance(target, Directed) else None,
        node_id=target.id if target.kind == 'resource' else None,
        question_id=target.id if target.kind == 'question' else None,
    )


def receipt(row):
    if row.kind in {'related', 'directed'}:
        target = dict(kind=row.kind, id=row.target_point_id, subject_id=row.target_subject_id)
        if row.kind == 'directed':
            target['label'] = row.label
    else:
        target = dict(kind=row.kind, id=row.node_id if row.kind == 'resource' else row.question_id)
    return dict(
        id=row.link_id,
        revision=row.revision,
        removed=row.revision == 2,
        source=dict(subject_id=row.subject_id, id=row.point_id),
        target=target,
    )


def point_available(session, workspace, subject, point):
    return session.scalar(
        select(Point.action != 'remove')
        .where(Point.workspace_id == workspace, Point.subject_id == subject, Point.point_id == point)
        .order_by(Point.revision.desc())
        .limit(1)
    )


def available(session, row):
    source = point_available(session, row.workspace_id, row.subject_id, row.point_id)
    if row.kind in {'related', 'directed'}:
        target = point_available(session, row.workspace_id, row.target_subject_id, row.target_point_id)
    elif row.kind == 'resource':
        target = session.scalar(
            select(WorkspaceNode.removed_at.is_(None)).where(
                WorkspaceNode.workspace_id == row.workspace_id, WorkspaceNode.id == row.node_id
            )
        )
    else:
        target = session.scalar(
            select(Question.id).where(
                Question.workspace_id == row.workspace_id, Question.id == row.question_id
            )
        )
    if source is None or target is None:
        return None
    return bool(source and target)


def active(workspace):
    removed = aliased(Link)
    return select(Link).where(
        Link.workspace_id == workspace,
        Link.revision == 1,
        ~exists().where(
            removed.workspace_id == workspace, removed.link_id == Link.link_id, removed.revision == 2
        ),
    )


def links_router(engine):
    router = APIRouter(prefix='/api/workspaces/{workspace_id}/knowledge/links')

    @router.post('')
    def create(workspace_id: str, body: CreateLink):
        fields = endpoints(body)
        with write_transaction(engine) as session:
            require_workspace(session, workspace_id)
            row = Link(
                workspace_id=workspace_id,
                link_id=uuid4().hex,
                revision=1,
                request_id=body.request_id,
                **fields,
            )
            state = available(session, row)
            if state is None:
                raise HTTPException(404, '关联对象不存在')
            require_unused_request(session, workspace_id, body.request_id, Link)
            saved = session.scalar(
                select(Link).where(Link.workspace_id == workspace_id, Link.request_id == body.request_id)
            )
            if saved:
                if saved.revision != 1 or any(getattr(saved, key) != value for key, value in fields.items()):
                    raise HTTPException(409, '该请求已用于其他关联')
                return receipt(saved)
            if not state:
                raise HTTPException(404, '关联对象不存在或已移除')
            if (row.subject_id, row.point_id) == (row.target_subject_id, row.target_point_id):
                raise HTTPException(422, '不能关联知识点自身')
            if session.scalar(active(workspace_id).filter_by(**fields).limit(1)):
                raise HTTPException(409, '相同关联已存在')
            session.add(row)
            session.flush()
            return receipt(row)

    @router.get('')
    def listing(
        workspace_id: str,
        subject_id: str | None = Query(None, min_length=1, max_length=128),
        point_id: str | None = Query(None, min_length=1, max_length=128),
        after_id: str = Query('', max_length=32),
        limit: int = Query(50, ge=1, le=100),
    ):
        with Session(engine) as session:
            require_workspace(session, workspace_id)
            query = active(workspace_id)
            if (subject_id is None) != (point_id is None):
                raise HTTPException(422, '请同时指定科目和知识点')
            if point_id:
                if not session.get(Point, (workspace_id, subject_id, point_id, 1)):
                    raise HTTPException(404, '知识点不存在')
                query = query.where(
                    or_(
                        and_(Link.subject_id == subject_id, Link.point_id == point_id),
                        and_(Link.target_subject_id == subject_id, Link.target_point_id == point_id),
                    )
                )
            rows = session.scalars(query.where(Link.link_id > after_id).order_by(Link.link_id).limit(limit))
            return [dict(receipt(row), available=bool(available(session, row))) for row in rows]

    @router.get('/{link_id}/revisions')
    def history(workspace_id: str, link_id: str):
        with Session(engine) as session:
            require_workspace(session, workspace_id)
            rows = session.scalars(
                select(Link)
                .where(Link.workspace_id == workspace_id, Link.link_id == link_id)
                .order_by(Link.revision.desc())
            ).all()
            if not rows:
                raise HTTPException(404, '关联不存在')
            return [receipt(row) for row in rows]

    @router.post('/{link_id}/remove')
    def remove(workspace_id: str, link_id: str, body: Remove):
        with write_transaction(engine) as session:
            require_workspace(session, workspace_id)
            original = session.get(Link, (workspace_id, link_id, 1))
            if original is None:
                raise HTTPException(404, '关联不存在')
            if not body.confirm:
                raise HTTPException(422, '撤销关联需要确认')
            require_unused_request(session, workspace_id, body.request_id, Link)
            saved = session.scalar(
                select(Link).where(Link.workspace_id == workspace_id, Link.request_id == body.request_id)
            )
            if saved:
                if saved.link_id != link_id or saved.revision != 2 or body.expected_revision != 1:
                    raise HTTPException(409, '该请求已用于其他关联修订')
                return receipt(saved)
            if body.expected_revision != 1 or session.get(Link, (workspace_id, link_id, 2)):
                raise HTTPException(409, '关联已修订，请刷新')
            keys = (
                'subject_id',
                'point_id',
                'kind',
                'target_subject_id',
                'target_point_id',
                'node_id',
                'question_id',
                'label',
            )
            row = Link(
                workspace_id=workspace_id,
                link_id=link_id,
                revision=2,
                previous_revision=1,
                request_id=body.request_id,
                **{key: getattr(original, key) for key in keys},
            )
            session.add(row)
            session.flush()
            return receipt(row)

    return router
