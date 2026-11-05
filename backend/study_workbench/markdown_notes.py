"""Create editable MD resources without turning them into imported or confirmed questions."""
from pathlib import Path
from threading import RLock
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from .db import DocumentWorkfile, MarkdownNoteCreation, Resource, WorkspaceNode, write_transaction
from .document_files import digest, write_new
from .explorer import describe_node, insert_node, normalized_name, parent_in
from .imports import resource_path
from .workspaces import require_workspace


class CreateNote(BaseModel):
    model_config = ConfigDict(extra='forbid')
    request_id: str = Field(pattern=r'^[A-Za-z0-9_-]{16,100}$')
    parent_id: str | None = Field(default=None, max_length=128)
    name: str = Field(max_length=200)

    @field_validator('name')
    @classmethod
    def markdown_name(cls, value):
        value = normalized_name(value)
        if not value.lower().endswith('.md'):
            raise ValueError('笔记名称必须以.md结尾')
        return value


class InitialConflict(HTTPException):
    def __init__(self):
        super().__init__(409, '创建文件与收据不符；字节保留，不覆盖，请核对数据目录')


class MarkdownNotes:
    def __init__(self, engine, root):
        self.engine, self.root = engine, root
        self.lock = RLock()
        with write_transaction(engine) as session:
            for row in session.scalars(select(MarkdownNoteCreation).where(MarkdownNoteCreation.status == 'prepared')):
                row.status, row.error = 'interrupted', '上次创建中断；重试原请求可核对保留文件'

    @staticmethod
    def initial(row):
        title = Path(row.request['name']).stem
        return f'<!-- studyworkbench-note: {row.id} -->\n\n# {title}\n'.encode('utf-8')

    @staticmethod
    def paths(row):
        return (f'workspaces/{row.workspace_id}/originals/{row.resource_id}.md',
                f'workspaces/{row.workspace_id}/working/{row.id}/note/current.md')

    def ensure_initial(self, relative, data):
        path = resource_path(self.root, relative)
        if not path.exists():
            write_new(path, data)
        try:
            with path.open('rb') as handle:
                if handle.read(len(data) + 1) != data:
                    raise InitialConflict()
        except OSError as error:
            raise HTTPException(409, '创建文件回读失败，已写字节保留，可重试原请求') from error

    def describe(self, session, row):
        result = dict(request_id=row.request_id, status=row.status, creation_status=row.status, error=row.error,
                      requested_name=row.request['name'], requested_parent_id=row.request['parent_id'])
        if row.status == 'ready':
            node = session.get(WorkspaceNode, row.id)
            if node is None or node.workspace_id != row.workspace_id:
                raise HTTPException(409, '创建收据目标缺失，记录保留')
            result.update(describe_node(session, self.root, node))
            result.update(source_resource_id=row.resource_id, sha256=digest(self.initial(row)), working_copy=True)
            # Keep current missing/conflict/removed state distinct from completed creation.
        return result

    def create(self, workspace, body):
        request = body.model_dump(exclude={'request_id'})
        with self.lock:
            with write_transaction(self.engine) as session:
                require_workspace(session, workspace)
                row = session.scalar(select(MarkdownNoteCreation).where(
                    MarkdownNoteCreation.workspace_id == workspace, MarkdownNoteCreation.request_id == body.request_id))
                if row is not None:
                    if row.request != request:
                        raise HTTPException(409, '此创建请求已用于其他名称或目录，请恢复原请求')
                    if row.status == 'ready':
                        return self.describe(session, row)
                else:
                    parent_in(session, workspace, body.parent_id)
                    row = MarkdownNoteCreation(id=uuid4().hex, workspace_id=workspace, request_id=body.request_id,
                                               request=request, resource_id=uuid4().hex, status='prepared')
                    session.add(row)
                row.status, row.error = 'prepared', None
                identifier = row.id
                data = self.initial(row)
                original, work = self.paths(row)
            try:
                self.ensure_initial(original, data)
                self.ensure_initial(work, data)
                with write_transaction(self.engine) as session:
                    row = session.get(MarkdownNoteCreation, identifier)
                    parent_in(session, workspace, body.parent_id)
                    # Final readback precedes registration; no node becomes visible on partial writes.
                    self.ensure_initial(original, data)
                    self.ensure_initial(work, data)
                    session.add(Resource(id=row.resource_id, workspace_id=workspace, original_name=body.name,
                                         relative_path=original, sha256=digest(data), size=len(data), mime='text/markdown'))
                    session.flush()
                    insert_node(session, workspace, body.parent_id, body.name, 'resource',
                                identifier=row.id, resource_id=row.resource_id)
                    session.add(DocumentWorkfile(node_id=row.id, workspace_id=workspace,
                                                 relative_path=work, indexed_sha256=digest(data)))
                    row.status, row.error = 'ready', None
                    result = self.describe(session, row)
                return result
            except HTTPException as error:
                with write_transaction(self.engine) as session:
                    row = session.get(MarkdownNoteCreation, identifier)
                    row.status = 'conflict' if isinstance(error, InitialConflict) else 'interrupted'
                    row.error = str(error.detail)
                raise

    def router(self):
        router = APIRouter(prefix='/api/workspaces/{workspace_id}/markdown-notes')

        @router.post('')
        def create(workspace_id: str, body: CreateNote):
            return self.create(workspace_id, body)

        @router.get('')
        def notes(workspace_id: str, offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100)):
            with Session(self.engine) as session:
                require_workspace(session, workspace_id)
                rows = session.scalars(select(WorkspaceNode).join(Resource, Resource.id == WorkspaceNode.resource_id)
                    .where(WorkspaceNode.workspace_id == workspace_id, Resource.workspace_id == workspace_id,
                           WorkspaceNode.kind == 'resource', WorkspaceNode.removed_at.is_(None),
                           or_(func.lower(Resource.original_name).endswith('.md'),
                               func.lower(Resource.original_name).endswith('.markdown')))
                    .order_by(WorkspaceNode.id).offset(offset).limit(limit))
                return [describe_node(session, self.root, row) for row in rows]

        @router.get('/requests/{request_id}')
        def receipt(workspace_id: str, request_id: str):
            with Session(self.engine) as session:
                require_workspace(session, workspace_id)
                row = session.scalar(select(MarkdownNoteCreation).where(
                    MarkdownNoteCreation.workspace_id == workspace_id, MarkdownNoteCreation.request_id == request_id))
                if row is None:
                    raise HTTPException(404, '创建请求不存在')
                return self.describe(session, row)

        @router.get('/requests')
        def receipts(workspace_id: str, offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100)):
            with Session(self.engine) as session:
                require_workspace(session, workspace_id)
                return [self.describe(session, row) for row in session.scalars(select(MarkdownNoteCreation).where(
                    MarkdownNoteCreation.workspace_id == workspace_id).order_by(MarkdownNoteCreation.id)
                    .offset(offset).limit(limit))]

        return router
