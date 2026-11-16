"""Scoped append-only learning events and explicit historical resource relations."""
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import (
    Attempt,
    LearningEvent,
    Note,
    QuestionFileRecord,
    QuestionVersion,
    WorkspaceNode,
    write_transaction,
)
from .workspaces import require_workspace


class EventInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    request_id: str = Field(min_length=16, max_length=100, pattern=r'^[A-Za-z0-9_-]+$')
    kind: Literal['annotation', 'reviewed']
    note: str = Field(min_length=1, max_length=4000, pattern=r'\S')
    error_type: str | None = Field(default=None, max_length=100, pattern=r'\S')
    self_rating: Literal['again', 'hard', 'good', 'easy'] | None = None
    note_id: str | None = Field(default=None, min_length=1, max_length=100)
    knowledge_points: list[str] | None = Field(default=None, max_length=100)

    @field_validator('knowledge_points')
    @classmethod
    def points(cls, value):
        if value is not None and (len(set(value)) != len(value) or any(not p.strip() or len(p) > 500 for p in value)):
            raise ValueError('知识点必须非空、独立且每项不超过500字符')
        return value


def event_view(event):
    return dict(id=event.id, request_id=event.request_id, created_at=event.created_at, **event.content)


def scoped_attempt(session, workspace, identifier):
    require_workspace(session, workspace)
    attempt = session.get(Attempt, identifier)
    if attempt is None or attempt.workspace_id != workspace:
        raise HTTPException(404, '作答不存在')
    return attempt


def records_router(engine):
    router = APIRouter(prefix='/api/workspaces/{workspace_id}/attempts/{attempt_id}')

    @router.post('/events')
    def append(workspace_id: str, attempt_id: int, body: EventInput):
        with write_transaction(engine) as session:
            scoped_attempt(session, workspace_id, attempt_id)
            content = body.model_dump(exclude={'request_id'}, exclude_none=True)
            existing = session.scalar(select(LearningEvent).where(
                LearningEvent.attempt_id == attempt_id, LearningEvent.request_id == body.request_id))
            if existing:
                if {k: v for k, v in existing.content.items() if v is not None} != content:
                    raise HTTPException(409, '此请求已用于另一条学习事件')
                return event_view(existing)
            if body.note_id:
                linked = session.get(Note, body.note_id)
                if linked is None or linked.workspace_id != workspace_id:
                    raise HTTPException(404, '关联笔记不存在于本空间')
                note_ids = set(session.scalars(select(LearningEvent.content['note_id'].as_string()).where(
                    LearningEvent.attempt_id == attempt_id).distinct())) - {None}
                if body.note_id not in note_ids and len(note_ids) >= 100:
                    raise HTTPException(413, '每条作答最多关联100份笔记；已有事件保留')
            event = LearningEvent(attempt_id=attempt_id, request_id=body.request_id, content=content,
                                  created_at=datetime.now(timezone.utc).isoformat())
            session.add(event)
            session.flush()
            return event_view(event)

    @router.get('/record')
    def record(workspace_id: str, attempt_id: int, before_id: int | None = Query(None, ge=1),
               limit: int = Query(50, ge=1, le=100)):
        with Session(engine) as session:
            attempt = scoped_attempt(session, workspace_id, attempt_id)
            version = session.get(QuestionVersion, attempt.question_version_id) if attempt.question_version_id else None
            if version and (version.workspace_id != workspace_id or version.question_id != attempt.question_id):
                raise HTTPException(409, '历史版本关系无效，记录保留')
            mapping = session.get(QuestionFileRecord, (workspace_id, attempt.question_id))
            node = session.get(WorkspaceNode, mapping.node_id) if mapping else None
            query = select(LearningEvent).where(LearningEvent.attempt_id == attempt_id)
            if before_id is not None:
                query = query.where(LearningEvent.id < before_id)
            events = list(session.scalars(query.order_by(LearningEvent.id.desc()).limit(limit)))
            source = version.content['question']['source'].get('original_resource_id') if version else None
            sources = list(session.scalars(select(WorkspaceNode).where(
                WorkspaceNode.removed_at.is_(None),
                WorkspaceNode.workspace_id == workspace_id, WorkspaceNode.resource_id == source).limit(100))) if source else []
            # The projection must use the entire event stream, not just the visible page.
            correction = None
            linked_notes = {}
            reviewed_count = 0
            for event in session.scalars(select(LearningEvent).where(LearningEvent.attempt_id == attempt_id)
                                         .order_by(LearningEvent.id).execution_options(yield_per=100)):
                if event.content.get('knowledge_points') is not None:
                    correction = event.content['knowledge_points']
                reviewed_count += event.content['kind'] == 'reviewed'
                identifier = event.content.get('note_id')
                if identifier and identifier not in linked_notes:
                    linked = session.get(Note, identifier)
                    linked_notes[identifier] = dict(id=identifier, title=linked.title if linked and linked.workspace_id == workspace_id else '笔记已缺失',
                                                    available=bool(linked and linked.workspace_id == workspace_id))
            return dict(attempt_id=attempt.id, question_version_id=attempt.question_version_id,
                        version_status='known' if version else 'unavailable' if attempt.question_version_id else 'unknown',
                        knowledge_points=version.content['question']['knowledge_points'] if version else None,
                        effective_knowledge_points=correction if correction is not None else version.content['question']['knowledge_points'] if version else None,
                        knowledge_projection_algorithm='latest-explicit-annotation-v1',
                        related_notes=list(linked_notes.values()), reviewed_count=reviewed_count,
                        resource_item_id=node.id if node and node.workspace_id == workspace_id and node.removed_at is None else None,
                        source_resource_item_ids=[n.id for n in sources],
                        events=[event_view(e) for e in events],
                        next_before_id=events[-1].id if len(events) == limit else None,
                        projection_algorithm='attempt-review-streak-v1')

    @router.get('/notes/{note_id}')
    def linked_note(workspace_id: str, attempt_id: int, note_id: str):
        with Session(engine) as session:
            scoped_attempt(session, workspace_id, attempt_id)
            relation = session.scalar(select(LearningEvent.id).where(LearningEvent.attempt_id == attempt_id,
                LearningEvent.content['note_id'].as_string() == note_id).limit(1))
            note = session.get(Note, note_id)
            if relation is None or note is None or note.workspace_id != workspace_id:
                raise HTTPException(404, '关联笔记已缺失或不可访问，学习事件保留')
            return dict(id=note.id, title=note.title, content=note.content, resource_id=note.resource_id)
    return router
