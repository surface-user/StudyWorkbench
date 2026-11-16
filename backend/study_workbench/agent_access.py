"""Ephemeral, local-only grants for the first R6 read tool."""
import secrets
from threading import Lock
from time import monotonic
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.orm import Session

from .learning_records import scoped_attempt
from .workspaces import require_workspace


class GrantInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    attempt_ids: list[int] = Field(min_length=1, max_length=100)
    purpose: Literal['analyze_attempts']
    expires_in_seconds: int = Field(default=300, ge=1, le=900, strict=True)
    confirm: Literal[True]

    @field_validator('confirm', mode='before')
    @classmethod
    def explicit_confirmation(cls, value):
        if value is not True:
            raise ValueError('必须明确确认授权')
        return value

    @field_validator('attempt_ids', mode='before')
    @classmethod
    def identifiers(cls, value):
        if not isinstance(value, list) or any(type(i) is not int or i < 1 for i in value):
            raise ValueError('作答编号必须为正整数')
        if len(set(value)) != len(value):
            raise ValueError('作答编号不能重复')
        return value


def agent_access_router(engine):
    router = APIRouter(prefix='/api/workspaces/{workspace_id}/agent-grants')
    grants = {}
    lock = Lock()

    def purge():
        for identifier in list(grants):
            if grants[identifier][2] <= monotonic():
                del grants[identifier]

    @router.post('')
    def create(workspace_id: str, body: GrantInput):
        with Session(engine) as session:
            require_workspace(session, workspace_id)
            for attempt_id in body.attempt_ids:
                scoped_attempt(session, workspace_id, attempt_id)
        with lock:
            purge()
            if len(grants) >= 100:
                raise HTTPException(429, '授权数量已达上限，请撤销或等待过期')
            identifier = secrets.token_hex(16)
            grants[identifier] = (workspace_id, tuple(body.attempt_ids), monotonic() + body.expires_in_seconds)
        return dict(id=identifier, purpose=body.purpose, attempt_ids=body.attempt_ids,
                    expires_in_seconds=body.expires_in_seconds, transport='local_only')

    @router.delete('/{grant_id}')
    def revoke(workspace_id: str, grant_id: str):
        with lock, Session(engine) as session:
            require_workspace(session, workspace_id)
            purge()
            if grant_id not in grants or grants[grant_id][0] != workspace_id:
                raise HTTPException(404, '授权不存在或已过期')
            del grants[grant_id]
        return {'revoked': True}

    @router.post('/{grant_id}/read-attempts')
    def read(workspace_id: str, grant_id: str):
        # Serialize revocation with reads so a completed revoke prevents later reads.
        with lock, Session(engine) as session:
            require_workspace(session, workspace_id)
            purge()
            grant = grants.get(grant_id)
            if grant is None or grant[0] != workspace_id:
                raise HTTPException(404, '授权不存在或已过期')
            result = []
            for attempt_id in grant[1]:
                attempt = scoped_attempt(session, workspace_id, attempt_id)
                result.append(dict(id=attempt.id, question_id=attempt.question_id,
                                   question_version_id=attempt.question_version_id,
                                   status=attempt.status, score=attempt.score,
                                   created_at=attempt.created_at))
        return {'attempts': result}

    return router
