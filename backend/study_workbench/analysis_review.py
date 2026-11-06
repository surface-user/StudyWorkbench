"""Human review of external candidate text. No model, credential, tool execution or answer writes."""
import hashlib
import re
from datetime import datetime, timezone
from threading import RLock
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .db import (
    AnalysisReviewDraft,
    AnalysisReviewRevision,
    WorkspaceNode,
    write_transaction,
)
from .document_files import SaveText, digest
from .markdown_notes import CreateNote
from .workspaces import require_workspace


class CandidateText(BaseModel):
    model_config = ConfigDict(extra='forbid')
    title: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=16000)
    source_label: str = Field(default='外部候选', max_length=200)

    @field_validator('title', 'body')
    @classmethod
    def bounded_text(cls, value):
        if not value.strip() or len(value.encode('utf-8')) > 64 * 1024:
            raise ValueError('候选须为非空UTF-8文字且不超过64KiB')
        return value


class CreateCandidate(CandidateText):
    grant_id: str = Field(pattern='^[a-f0-9]{32}$')
    context_sha256: str = Field(pattern='^[a-f0-9]{64}$')
    request_id: str = Field(pattern='^[A-Za-z0-9_-]{16,100}$')


class ReviewGuard(BaseModel):
    model_config = ConfigDict(extra='forbid')
    expected_revision: int = Field(ge=1, strict=True)
    expected_payload_sha256: str = Field(pattern='^[a-f0-9]{64}$')


class EditCandidate(CandidateText, ReviewGuard):
    pass


class RejectCandidate(ReviewGuard):
    reason: str = Field(default='', max_length=2000)


class AdoptCandidate(CreateNote, ReviewGuard):
    confirm: bool = Field(strict=True)

    @field_validator('confirm')
    @classmethod
    def explicit_confirmation(cls, value):
        if value is not True:
            raise ValueError('必须单独确认采用')
        return value


class AnalysisReviews:
    def __init__(self, engine, root, access, notes, documents):
        self.engine, self.root, self.access, self.notes, self.documents = engine, root, access, notes, documents
        self.lock = RLock()
        with write_transaction(engine) as session:
            for row in session.scalars(select(AnalysisReviewDraft).where(AnalysisReviewDraft.status == 'adopting')):
                self.history(session, row)
                row.status, row.error = 'failed', '上次采用中断，笔记和收据保留；请核对后重试原操作'

    def encoded(self, value):
        return self.access.encoded(value)

    def checksum(self, value):
        return hashlib.sha256(self.encoded(value)).hexdigest()

    @staticmethod
    def describe(row):
        return dict(id=row.id, workspace_id=row.workspace_id, content=row.content, payload_sha256=row.payload_sha256,
                    revision=row.revision, status=row.status, adoption=row.adoption, result=row.result,
                    error=row.error, rejection_reason=row.rejection_reason, created_at=row.created_at)

    @staticmethod
    def guard(row, body):
        if row.revision != body.expected_revision or row.payload_sha256 != body.expected_payload_sha256:
            raise HTTPException(409, '候选内容或审核状态已变化，请重新核对')

    def row(self, session, workspace, identifier):
        require_workspace(session, workspace)
        row = session.get(AnalysisReviewDraft, identifier)
        if row is None or row.workspace_id != workspace:
            raise HTTPException(404, '候选草稿不存在')
        if self.checksum(row.content) != row.payload_sha256:
            raise HTTPException(409, '候选草稿内容校验失败，原记录保留')
        return row

    def history(self, session, row):
        session.add(AnalysisReviewRevision(draft_id=row.id, revision=row.revision,
            snapshot=self.describe(row), created_at=datetime.now(timezone.utc).isoformat()))
        row.revision += 1

    def create(self, workspace, body):
        creation = body.model_dump(exclude={'grant_id', 'request_id'})
        with self.lock:
            with Session(self.engine) as session:
                require_workspace(session, workspace)
                old = session.scalar(select(AnalysisReviewDraft).where(AnalysisReviewDraft.workspace_id == workspace,
                    AnalysisReviewDraft.request_id == body.request_id))
                if old:
                    if old.creation_content != creation:
                        raise HTTPException(409, '同一创建请求的候选内容变化')
                    return self.describe(self.row(session, workspace, old.id))
            context = self.access.context(workspace, body.grant_id)
            if context['context_sha256'] != body.context_sha256:
                raise HTTPException(409, '授权上下文已变化，请重新读取核对')
            versions = {item['id']: item['content_sha256'] for item in context['question_versions']}
            references = [dict(attempt_id=item['id'], question_id=item['question_id'],
                question_version_id=item['question_version_id'], confirmed_metadata_sha256=versions.get(item['question_version_id']))
                for item in context['attempts']]
            content = dict(title=body.title, body=body.body, source_label=body.source_label,
                origin='external_candidate', verification='unverified', context_sha256=body.context_sha256,
                scope=context['scope'], references=references)
            with write_transaction(self.engine) as session:
                require_workspace(session, workspace)
                if session.scalar(select(func.count()).select_from(AnalysisReviewDraft).where(
                        AnalysisReviewDraft.workspace_id == workspace, AnalysisReviewDraft.status.in_(['pending', 'adopting', 'failed']))) >= 1000:
                    raise HTTPException(429, '当前空间待处理候选已达1000条')
                row = AnalysisReviewDraft(id=uuid4().hex, workspace_id=workspace, request_id=body.request_id,
                    creation_content=creation, content=content, payload_sha256=self.checksum(content), revision=1,
                    status='pending', adoption={}, result={}, error=None, rejection_reason='',
                    created_at=datetime.now(timezone.utc).isoformat())
                session.add(row)
                session.flush()
                return self.describe(row)

    @staticmethod
    def markdown(identifier, content):
        literal = f"标题：{content['title']}\n来源说明（自填）：{content['source_label']}\n\n{content['body']}"
        citations = '\n'.join(f"- 作答 #{r['attempt_id']}；题目 {r['question_id']}；确认版 {r['question_version_id'] or '历史未知'}"
                              for r in content['references'])
        literal += '\n\n授权引用：\n' + citations
        fence = '`' * max(3, 1 + max((len(run) for run in re.findall('`+', literal)), default=0))
        return ('# 分析候选（未经验证）\n\n> 人工采用仅保存笔记，不验证建议正确性；本应用未调用模型。\n\n'
                + fence + '\n' + literal + '\n' + fence
                + f"\n\n候选ID：{identifier}\n上下文SHA256：{content['context_sha256']}\n")

    def adopt(self, workspace, identifier, body):
        request = body.model_dump()
        with self.lock:
            with write_transaction(self.engine) as session:
                row = self.row(session, workspace, identifier)
                if row.status == 'rejected':
                    raise HTTPException(409, '此候选已拒绝，不再重试采用；旧笔记和收据保留')
                if row.adoption:
                    if row.adoption != request:
                        raise HTTPException(409, '已有采用收据，请重试原参数；不会覆盖已建笔记')
                    if row.status == 'adopted':
                        return self.describe(row)
                    self.history(session, row)
                else:
                    self.guard(row, body)
                    if row.status != 'pending':
                        raise HTTPException(409, '此候选当前不可采用')
                    self.history(session, row)
                    row.adoption = request
                row.status, row.error = 'adopting', None
                text = self.markdown(row.id, row.content)
            try:
                note = self.notes.create(workspace, CreateNote(name=body.name, parent_id=body.parent_id,
                                                              request_id='analysis_' + identifier))
                node_id, expected = note['resource_item_id'], digest(text.encode('utf-8'))
                with write_transaction(self.engine) as session:
                    row = self.row(session, workspace, identifier)
                    row.result = {'resource_item_id': node_id, 'note_created': True}
                with self.documents.lock:
                    with Session(self.engine) as session:
                        node, _, _, work, raw = self.documents.source(session, workspace, node_id)
                        if node.removed_at is not None:
                            raise HTTPException(409, '已建笔记已从树移除，未重新打开或覆盖')
                        actual = digest(raw)
                        if actual == expected:
                            if work.indexed_sha256 != expected:
                                raise HTTPException(409, '笔记保存尚待重启对账，请重启后重试')
                        elif actual != note['sha256']:
                            raise HTTPException(409, '已建笔记存在其他编辑，候选和笔记保留，未覆盖')
                    if actual != expected:
                        self.documents.save_text(workspace, node_id, SaveText(expected_sha256=note['sha256'], text=text))
                with write_transaction(self.engine) as session:
                    row = self.row(session, workspace, identifier)
                    node = session.get(WorkspaceNode, node_id)
                    if node is None or node.removed_at is not None:
                        raise HTTPException(409, '保存后的笔记已移除，收据保留')
                    self.history(session, row)
                    row.status, row.error = 'adopted', None
                    row.result = {'resource_item_id': node_id, 'sha256': expected, 'verification': 'unverified'}
                    return self.describe(row)
            except Exception as error:
                with write_transaction(self.engine) as session:
                    row = self.row(session, workspace, identifier)
                    self.history(session, row)
                    row.status = 'failed'
                    row.error = error.detail if isinstance(error, HTTPException) else '采用未完成，草稿/笔记与恢复收据保留'
                if isinstance(error, HTTPException):
                    raise
                raise HTTPException(409, '采用未完成，已建笔记和候选保留，请核对后重试') from None

    def router(self):
        router = APIRouter(prefix='/api/workspaces/{workspace_id}/analysis-drafts')
        @router.post('')
        def create(workspace_id: str, body: CreateCandidate):
            return self.create(workspace_id, body)
        @router.get('')
        def listing(workspace_id: str, offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100)):
            with Session(self.engine) as session:
                require_workspace(session, workspace_id)
                return [self.describe(row) for row in session.scalars(select(AnalysisReviewDraft).where(
                    AnalysisReviewDraft.workspace_id == workspace_id).order_by(AnalysisReviewDraft.created_at.desc(), AnalysisReviewDraft.id).offset(offset).limit(limit))]
        @router.get('/{identifier}')
        def get(workspace_id: str, identifier: str):
            with Session(self.engine) as session:
                return self.describe(self.row(session, workspace_id, identifier))
        @router.patch('/{identifier}')
        def edit(workspace_id: str, identifier: str, body: EditCandidate):
            with self.lock, write_transaction(self.engine) as session:
                row = self.row(session, workspace_id, identifier)
                self.guard(row, body)
                if row.status != 'pending' or row.adoption:
                    raise HTTPException(409, '仅未采用的待审核草稿可编辑')
                self.history(session, row)
                row.content = dict(row.content, title=body.title, body=body.body, source_label=body.source_label)
                row.payload_sha256 = self.checksum(row.content)
                return self.describe(row)
        @router.post('/{identifier}/reject')
        def reject(workspace_id: str, identifier: str, body: RejectCandidate):
            with self.lock, write_transaction(self.engine) as session:
                row = self.row(session, workspace_id, identifier)
                self.guard(row, body)
                if row.status not in {'pending', 'failed'}:
                    raise HTTPException(409, '仅待审核或失败候选可拒绝；已建笔记和收据保留')
                self.history(session, row)
                row.status, row.rejection_reason = 'rejected', body.reason
                return self.describe(row)
        @router.post('/{identifier}/adopt')
        def adopt(workspace_id: str, identifier: str, body: AdoptCandidate):
            return self.adopt(workspace_id, identifier, body)
        @router.get('/{identifier}/revisions')
        def revisions(workspace_id: str, identifier: str, offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100)):
            with Session(self.engine) as session:
                self.row(session, workspace_id, identifier)
                return [dict(revision=row.revision, snapshot=row.snapshot, created_at=row.created_at) for row in session.scalars(
                    select(AnalysisReviewRevision).where(AnalysisReviewRevision.draft_id == identifier)
                    .order_by(AnalysisReviewRevision.revision.desc()).offset(offset).limit(limit))]
        return router
