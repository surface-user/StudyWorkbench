"""Ephemeral, local-only grants for the first R6 read tool."""
import hashlib
import json
import secrets
from threading import Lock
from time import monotonic
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.orm import Session

from .learning_records import scoped_attempt
from .question_files import version_read, version_view
from .workspaces import require_workspace


class GrantInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    attempt_ids: list[int] = Field(min_length=1, max_length=100)
    purpose: Literal['analyze_attempts']
    expires_in_seconds: int = Field(default=300, ge=1, le=900, strict=True)
    confirm: Literal[True]
    include_content: bool = Field(default=False, strict=True)

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


class AgentAccess:
    def __init__(self, engine, root=None):
        self.engine, self.root = engine, root
        self.grants, self.lock = {}, Lock()

    def purge(self):
        for identifier in list(self.grants):
            if self.grants[identifier][2] <= monotonic():
                del self.grants[identifier]

    def grant(self, session, workspace, identifier):
        require_workspace(session, workspace)
        self.purge()
        grant = self.grants.get(identifier)
        if grant is None or grant[0] != workspace:
            raise HTTPException(404, '授权不存在或已过期')
        return grant

    def create(self, workspace_id: str, body: GrantInput):
        with Session(self.engine) as session:
            require_workspace(session, workspace_id)
            for attempt_id in body.attempt_ids:
                scoped_attempt(session, workspace_id, attempt_id)
        with self.lock:
            self.purge()
            if len(self.grants) >= 100:
                raise HTTPException(429, '授权数量已达上限，请撤销或等待过期')
            identifier = secrets.token_hex(16)
            self.grants[identifier] = (workspace_id, tuple(body.attempt_ids), monotonic() + body.expires_in_seconds, body.include_content)
        return dict(id=identifier, purpose=body.purpose, attempt_ids=body.attempt_ids,
                    expires_in_seconds=body.expires_in_seconds, transport='local_only', include_content=body.include_content)

    def revoke(self, workspace_id: str, grant_id: str):
        with self.lock, Session(self.engine) as session:
            self.grant(session, workspace_id, grant_id)
            del self.grants[grant_id]
        return {'revoked': True}

    @staticmethod
    def summary(attempt):
        return dict(id=attempt.id, question_id=attempt.question_id, question_version_id=attempt.question_version_id,
                    status=attempt.status, score=attempt.score, created_at=attempt.created_at)

    def read(self, workspace_id: str, grant_id: str):
        with self.lock, Session(self.engine) as session:
            grant = self.grant(session, workspace_id, grant_id)
            result = [self.summary(scoped_attempt(session, workspace_id, identifier)) for identifier in grant[1]]
            self.grant(session, workspace_id, grant_id)
        return {'attempts': result}

    @staticmethod
    def encoded(value):
        try:
            return json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False).encode('utf-8')
        except (ValueError, UnicodeError, TypeError):
            raise HTTPException(409, '授权内容无法表示为受控UTF-8数据；原记录保留') from None

    def context(self, workspace_id: str, grant_id: str):
        with self.lock, Session(self.engine) as session:
            grant = self.grant(session, workspace_id, grant_id)
            attempts, versions, used = [], {}, 0
            for identifier in sorted(grant[1]):
                attempt = scoped_attempt(session, workspace_id, identifier)
                item = self.summary(attempt)
                if grant[3]:
                    if len(self.encoded(attempt.response)) > 64 * 1024:
                        raise HTTPException(413, '单份作答正文超过64KiB，请减少范围或另行整理；原记录保留')
                    item['response'] = attempt.response
                    item['historical_version_known'] = attempt.question_version_id is not None
                    version_id = attempt.question_version_id
                    if version_id is not None and version_id not in versions:
                        if self.root is None:
                            raise HTTPException(503, '当前未配置确认版读取服务')
                        version = version_read(session, self.root, workspace_id, version_id)
                        if version.question_id != attempt.question_id:
                            raise HTTPException(409, '作答与确认版题目不一致；未读取其他题目')
                        view = version_view(version)
                        view['attachments'] = [dict(id=key, mime=value.get('mime'), size=value.get('size'), sha256=value.get('sha256'))
                                               for key, value in version.attachments.items()]
                        versions[version_id] = view
                        used += len(self.encoded(view))
                    if version_id is not None and versions[version_id]['question_id'] != attempt.question_id:
                        raise HTTPException(409, '作答与确认版题目不一致；引用保留')
                used += len(self.encoded(item))
                if used > 1024 * 1024:
                    raise HTTPException(413, '授权上下文超过1MiB，请减少选择；未返回截断内容')
                attempts.append(item)
            result = dict(schema_version=1, workspace_id=workspace_id, scope='content' if grant[3] else 'summary',
                          attempts=attempts, question_versions=list(versions.values()), binary_attachments_read=False,
                          latest_reviews_included=False)
            raw = self.encoded(result)
            if len(raw) > 1024 * 1024:
                raise HTTPException(413, '授权上下文超过1MiB，请减少选择')
            self.grant(session, workspace_id, grant_id)
        result['context_sha256'] = hashlib.sha256(raw).hexdigest()
        if len(self.encoded(result)) > 1024 * 1024:
            raise HTTPException(413, '含校验字段的授权上下文超过1MiB，请减少选择')
        return result

    def router(self):
        router = APIRouter(prefix='/api/workspaces/{workspace_id}/agent-grants')
        router.post('')(self.create)
        router.delete('/{grant_id}')(self.revoke)
        router.post('/{grant_id}/read-attempts')(self.read)
        router.post('/{grant_id}/read-analysis-context')(self.context)
        return router


def agent_access_router(engine, root=None):
    return AgentAccess(engine, root).router()
