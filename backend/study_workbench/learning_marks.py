"""Scoped, version-checked bookmarks. Mutable current rows retain immutable prior revisions."""
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated, Literal
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    TypeAdapter,
    ValidationError,
    field_validator,
    model_validator,
)
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from .db import (
    LearningMark,
    LearningMarkNote,
    LearningMarkRevision,
    MediaEntry,
    Note,
    Resource,
    WorkspaceNode,
    write_transaction,
)
from .document_files import digest, limited_view, raster
from .explorer import describe_node, node_in, valid_original
from .imports import note_revision, resource_path
from .media_duration import MAX_DURATION_MS, duration_ms
from .question_protocol import ResourceId
from .workspaces import require_workspace

Hash = Annotated[str, Field(strict=True, pattern=r'^[a-f0-9]{64}$')]
Revision = Annotated[int, Field(strict=True, ge=1)]


class Contract(BaseModel):
    model_config = ConfigDict(extra='forbid')


class AnchorBase(Contract):
    version: Literal[1]
    workspace_id: ResourceId
    resource_item_id: ResourceId
    content_sha256: Hash | None

    @field_validator('version', mode='before')
    @classmethod
    def strict_version(cls, value):
        if type(value) is not int:
            raise ValueError('Version must be an integer')
        return value


class ResourceAnchor(AnchorBase):
    kind: Literal['resource']


class PdfAnchor(AnchorBase):
    kind: Literal['pdf_page']
    content_sha256: Hash
    page: Annotated[int, Field(strict=True, ge=1, le=2000)]
    representation: Literal['original']


class OfficeAnchor(AnchorBase):
    kind: Literal['office_pdf_page']
    content_sha256: Hash
    page: Annotated[int, Field(strict=True, ge=1, le=2000)]
    representation: Literal['paginated']
    preview_id: ResourceId
    source_sha256: Hash


class TextAnchor(AnchorBase):
    kind: Literal['text_line']
    content_sha256: Hash
    line: Annotated[int, Field(strict=True, ge=1, le=1048577)]
    line_sha256: Hash


class MediaAnchor(AnchorBase):
    kind: Literal['media_time']
    content_sha256: Hash
    position_ms: Annotated[int, Field(strict=True, ge=0, le=MAX_DURATION_MS)]


Anchor = Annotated[ResourceAnchor | PdfAnchor | OfficeAnchor | TextAnchor | MediaAnchor, Field(discriminator='kind')]
ANCHOR = TypeAdapter(Anchor)


class Capture(Contract):
    kind: Literal['resource', 'pdf_page', 'office_pdf_page', 'text_line', 'media_time']
    expected_sha256: Hash | None = None
    page: Annotated[int, Field(strict=True, ge=1, le=2000)] | None = None
    preview_id: ResourceId | None = None
    line: Annotated[int, Field(strict=True, ge=1, le=1048577)] | None = None
    position_ms: Annotated[int, Field(strict=True, ge=0, le=MAX_DURATION_MS)] | None = None

    @model_validator(mode='after')
    def position_fields(self):
        fields = {'resource': set(), 'pdf_page': {'page'}, 'office_pdf_page': {'page', 'preview_id'},
                  'text_line': {'line'}, 'media_time': {'position_ms'}}[self.kind]
        if self.model_fields_set - fields - {'kind', 'expected_sha256'} or any(getattr(self, f) is None for f in fields):
            raise ValueError('Position fields do not match kind')
        if self.kind != 'resource' and self.expected_sha256 is None:
            raise ValueError('Positional capture must specify the displayed version')
        return self


class NoteTarget(Contract):
    kind: Literal['file_note', 'legacy_note']
    id: ResourceId


class CreateMark(Contract):
    request_id: str = Field(pattern=r'^[A-Za-z0-9_-]{16,100}$')
    anchor: Anchor
    title: str = Field(min_length=1, max_length=240, pattern=r'\S')
    note: str = Field(default='', max_length=4000)
    targets: list[NoteTarget] = Field(default_factory=list, max_length=100)


class EditMark(Contract):
    expected_revision: Revision
    title: str | None = Field(default=None, min_length=1, max_length=240, pattern=r'\S')
    note: str | None = Field(default=None, max_length=4000)
    anchor: Anchor | None = None

    @model_validator(mode='after')
    def changes(self):
        fields = self.model_fields_set - {'expected_revision'}
        if not fields or any(getattr(self, f) is None for f in fields):
            raise ValueError('Supply non-null edits')
        return self


class ExpectedRevision(Contract):
    expected_revision: Revision


class NoteTargets(ExpectedRevision):
    targets: list[NoteTarget] = Field(max_length=100)


class LearningMarks:
    def __init__(self, documents):
        self.documents, self.engine, self.root = documents, documents.engine, documents.root

    def current(self, session, workspace, node, kind, preview_id=None):
        if node.kind == 'link':
            if kind != 'resource':
                raise HTTPException(422, '网页仅支持资源级书签')
            return dict(content_sha256=None)
        if node.kind == 'media':
            item = session.get(MediaEntry, node.media_id)
            if item.status != 'ready' or not valid_original(self.root, item):
                raise HTTPException(409, '媒体缺失或校验失败')
            if kind not in {'resource', 'media_time'}:
                raise HTTPException(422, '此位置类型不适用于媒体')
            result = dict(content_sha256=item.sha256)
            if kind == 'media_time':
                result['duration_ms'] = duration_ms(resource_path(self.root, item.relative_path), item.mime)
                if result['duration_ms'] is None:
                    raise HTTPException(422, '无法验证媒体时长，请使用资源级书签')
            return result
        if node.kind != 'resource':
            raise HTTPException(422, '文件夹不能创建学习位置')
        _, original, suffix, _, data = self.documents.source(session, workspace, node.id)
        result = dict(content_sha256=digest(data))
        if kind == 'text_line':
            if suffix not in {'.md', '.markdown', '.txt'}:
                raise HTTPException(422, '此文件不支持原文行定位')
            try:
                result['lines'] = [line.removesuffix('\r') for line in data.decode('utf-8').split('\n')]
            except UnicodeError as error:
                raise HTTPException(409, '文本不是UTF-8') from error
        elif kind == 'pdf_page':
            if suffix != '.pdf':
                raise HTTPException(422, '此文件不是PDF')
            result['page_count'] = raster(data, 'pdf-info')['page_count']
        elif kind == 'office_pdf_page':
            if suffix not in {'.docx', '.pptx'}:
                raise HTTPException(422, '此文件不是Office分页资料')
            pdf, preview = self.documents.previews.read_pdf(workspace, node.id, preview_id)
            result = dict(content_sha256=digest(pdf), source_sha256=original.sha256,
                          page_count=preview['page_count'])
        elif kind != 'resource':
            raise HTTPException(422, '位置类型与文件不符')
        return result

    def capture(self, session, workspace, node_id, body):
        require_workspace(session, workspace)
        node = node_in(session, workspace, node_id)
        if node.removed_at:
            raise HTTPException(409, '来源已移除，不能创建新位置')
        current = self.current(session, workspace, node, body.kind, body.preview_id)
        if body.expected_sha256 is not None and current['content_sha256'] != body.expected_sha256:
            raise HTTPException(409, '显示内容已变化，请刷新资料后再创建位置')
        result = dict(version=1, workspace_id=workspace, resource_item_id=node.id,
                      kind=body.kind, content_sha256=current['content_sha256'])
        if body.kind in {'pdf_page', 'office_pdf_page'}:
            if body.page > current['page_count']:
                raise HTTPException(422, '页码超出资料范围')
            result.update(page=body.page, representation='original' if body.kind == 'pdf_page' else 'paginated')
            if body.kind == 'office_pdf_page':
                result.update(preview_id=body.preview_id, source_sha256=current['source_sha256'])
        elif body.kind == 'text_line':
            if body.line > len(current['lines']):
                raise HTTPException(422, '原文行超出资料范围')
            result.update(line=body.line, line_sha256=digest(current['lines'][body.line - 1].encode('utf-8')))
        elif body.kind == 'media_time':
            if body.position_ms > current['duration_ms']:
                raise HTTPException(422, '时间点超出媒体时长')
            result['position_ms'] = body.position_ms
        return ANCHOR.validate_python(result).model_dump(mode='json')

    def resolve(self, session, workspace, raw):
        try:
            anchor = ANCHOR.validate_python(raw)
        except ValidationError:
            return dict(status='unsupported', message='不支持的位置协议，原始记录保留')
        if anchor.workspace_id != workspace:
            raise HTTPException(404, '来源不存在')
        node = node_in(session, workspace, anchor.resource_item_id)
        result = dict(resource=describe_node(session, self.root, node), anchor=raw)
        if node.removed_at:
            return dict(result, status='removed', message='来源已从资源树移除，备注保留')
        try:
            current = self.current(session, workspace, node, anchor.kind, getattr(anchor, 'preview_id', None))
        except HTTPException as error:
            if error.status_code in {404, 429}:
                raise
            return dict(result, status='unsupported' if error.status_code in {413, 422} else 'missing_content',
                        message=str(error.detail))
        if current['content_sha256'] != anchor.content_sha256 or (
            anchor.kind == 'office_pdf_page' and current['source_sha256'] != anchor.source_sha256
        ):
            return dict(result, status='content_changed', message='内容版本已变化；请核对后显式重新关联')
        if anchor.kind in {'pdf_page', 'office_pdf_page'} and anchor.page > current['page_count'] or (
            anchor.kind == 'media_time' and anchor.position_ms > current['duration_ms']
        ) or (anchor.kind == 'text_line' and anchor.line > len(current['lines'])):
            return dict(result, status='out_of_range', message='位置超出当前资料范围')
        if anchor.kind == 'text_line' and digest(current['lines'][anchor.line - 1].encode('utf-8')) != anchor.line_sha256:
            return dict(result, status='content_changed', message='原文行内容与记录不符')
        if anchor.kind == 'office_pdf_page':
            latest = self.documents.previews.latest(workspace, node.id, current['source_sha256'])
            if latest and latest['status'] == 'ready' and latest['pdf_sha256'] != anchor.content_sha256:
                return dict(result, status='valid', message='书签对应旧分页版本；将打开保留的该版本')
        return dict(result, status='valid', message='位置有效')

    def require_anchor(self, session, workspace, raw):
        result = self.resolve(session, workspace, raw)
        if result['status'] != 'valid':
            raise HTTPException(409, result['message'])
        return result

    def mark_in(self, session, workspace, identifier):
        require_workspace(session, workspace)
        item = session.get(LearningMark, identifier)
        if item is None or item.workspace_id != workspace:
            raise HTTPException(404, '书签不存在')
        return item

    def targets(self, session, item):
        rows = session.scalars(select(LearningMarkNote).where(LearningMarkNote.mark_id == item.id)
                               .order_by(LearningMarkNote.kind, LearningMarkNote.file_node_id, LearningMarkNote.legacy_note_id))
        return [dict(kind=row.kind, id=row.file_node_id if row.kind == 'file_note' else row.legacy_note_id) for row in rows]

    def validate_targets(self, session, workspace, targets):
        canonical = sorted([t.model_dump() for t in targets], key=lambda t: (t['kind'], t['id']))
        if len({(t['kind'], t['id']) for t in canonical}) != len(canonical):
            raise HTTPException(422, '笔记关系不能重复')
        for target in canonical:
            if target['kind'] == 'file_note':
                node = node_in(session, workspace, target['id'])
                source = session.get(Resource, node.resource_id) if node.kind == 'resource' else None
                if node.removed_at or source is None or Path(source.original_name).suffix.lower() not in {'.md', '.markdown'}:
                    raise HTTPException(422, '只能关联当前同空间Markdown笔记')
            else:
                note = session.get(Note, target['id'])
                if note is None or note.workspace_id != workspace:
                    raise HTTPException(404, '笔记不存在')
        return canonical

    def replace_targets(self, session, item, targets):
        session.execute(delete(LearningMarkNote).where(LearningMarkNote.mark_id == item.id))
        for target in targets:
            session.add(LearningMarkNote(workspace_id=item.workspace_id, mark_id=item.id, kind=target['kind'],
                file_node_id=target['id'] if target['kind'] == 'file_note' else None,
                legacy_note_id=target['id'] if target['kind'] == 'legacy_note' else None))

    def describe(self, session, item):
        targets = self.targets(session, item)
        labels = []
        for target in targets:
            obj = session.get(WorkspaceNode if target['kind'] == 'file_note' else Note, target['id'])
            present = obj is not None and obj.workspace_id == item.workspace_id
            labels.append(dict(target, title=(obj.name if target['kind'] == 'file_note' else obj.title) if present else '笔记已缺失',
                               status='missing' if not present else 'removed' if getattr(obj, 'removed_at', None) else 'ready'))
        return dict(id=item.id, workspace_id=item.workspace_id, resource_item_id=item.resource_item_id,
                    anchor=item.anchor, title=item.title, note=item.note, revision=item.revision,
                    created_at=item.created_at, updated_at=item.updated_at, removed_at=item.removed_at,
                    targets=targets, target_details=labels)

    def advance(self, session, item, expected):
        if item.revision != expected or item.removed_at:
            raise HTTPException(409, '书签已更新或移除，请重新载入；当前草稿保留')
        session.add(LearningMarkRevision(mark_id=item.id, revision=item.revision,
                    content=self.describe(session, item), created_at=datetime.now(timezone.utc).isoformat()))
        item.revision += 1
        item.updated_at = datetime.now(timezone.utc).isoformat()

    def router(self):
        router = APIRouter(prefix='/api/workspaces/{workspace_id}')

        @router.post('/nodes/{node_id}/learning-anchor')
        @limited_view
        def capture(workspace_id: str, node_id: str, body: Capture):
            with Session(self.engine) as session:
                return self.capture(session, workspace_id, node_id, body)

        @router.post('/learning-marks')
        @limited_view
        def create(workspace_id: str, body: CreateMark):
            raw = body.anchor.model_dump(mode='json')
            if raw['workspace_id'] != workspace_id:
                raise HTTPException(404, '来源不存在')
            content = body.model_dump(mode='json', exclude={'request_id'})
            content['title'] = body.title.strip()
            content['targets'] = sorted(content['targets'], key=lambda t: (t['kind'], t['id']))
            with write_transaction(self.engine) as session:
                require_workspace(session, workspace_id)
                item = session.scalar(select(LearningMark).where(LearningMark.workspace_id == workspace_id,
                                                                 LearningMark.request_id == body.request_id))
                if item:
                    if item.creation_content != content:
                        raise HTTPException(409, '同一创建请求内容不一致')
                    return self.describe(session, item)
                self.require_anchor(session, workspace_id, raw)
                targets = self.validate_targets(session, workspace_id, body.targets)
                now = datetime.now(timezone.utc).isoformat()
                item = LearningMark(id=uuid4().hex, workspace_id=workspace_id, resource_item_id=raw['resource_item_id'],
                    anchor=raw, title=content['title'], note=body.note, revision=1, request_id=body.request_id,
                    creation_content=content, created_at=now, updated_at=now)
                session.add(item)
                session.flush()
                self.replace_targets(session, item, targets)
                return self.describe(session, item)

        @router.get('/learning-marks')
        def listing(workspace_id: str, resource_item_id: str | None = None, note_resource_item_id: str | None = None,
                    offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100)):
            with Session(self.engine) as session:
                require_workspace(session, workspace_id)
                query = select(LearningMark).where(LearningMark.workspace_id == workspace_id, LearningMark.removed_at.is_(None))
                if resource_item_id:
                    node_in(session, workspace_id, resource_item_id)
                    query = query.where(LearningMark.resource_item_id == resource_item_id)
                if note_resource_item_id:
                    node_in(session, workspace_id, note_resource_item_id)
                    query = query.where(select(LearningMarkNote.id).where(LearningMarkNote.mark_id == LearningMark.id,
                        LearningMarkNote.file_node_id == note_resource_item_id).exists())
                return [self.describe(session, item) for item in session.scalars(query.order_by(LearningMark.id).offset(offset).limit(limit))]

        @router.get('/learning-marks/{identifier}')
        @limited_view
        def detail(workspace_id: str, identifier: str):
            with Session(self.engine) as session:
                item = self.mark_in(session, workspace_id, identifier)
                return dict(self.describe(session, item), location=self.resolve(session, workspace_id, item.anchor))

        @router.patch('/learning-marks/{identifier}')
        @limited_view
        def edit(workspace_id: str, identifier: str, body: EditMark):
            with write_transaction(self.engine) as session:
                item = self.mark_in(session, workspace_id, identifier)
                changes = body.model_dump(mode='json', exclude_unset=True, exclude={'expected_revision'})
                if 'anchor' in changes:
                    if changes['anchor']['resource_item_id'] != item.resource_item_id:
                        raise HTTPException(422, '重新关联只能调整同一资料的位置，跨资料请新建书签')
                    self.require_anchor(session, workspace_id, changes['anchor'])
                self.advance(session, item, body.expected_revision)
                for key, value in changes.items():
                    setattr(item, key, value.strip() if key == 'title' else value)
                return self.describe(session, item)

        @router.delete('/learning-marks/{identifier}')
        def remove(workspace_id: str, identifier: str, body: ExpectedRevision):
            with write_transaction(self.engine) as session:
                item = self.mark_in(session, workspace_id, identifier)
                self.advance(session, item, body.expected_revision)
                item.removed_at = item.updated_at
                return self.describe(session, item)

        @router.put('/learning-marks/{identifier}/notes')
        def notes(workspace_id: str, identifier: str, body: NoteTargets):
            with write_transaction(self.engine) as session:
                item = self.mark_in(session, workspace_id, identifier)
                targets = self.validate_targets(session, workspace_id, body.targets)
                self.advance(session, item, body.expected_revision)
                self.replace_targets(session, item, targets)
                return self.describe(session, item)

        @router.get('/learning-marks/{identifier}/notes/{kind}/{target_id}')
        def note(workspace_id: str, identifier: str, kind: str, target_id: str):
            with Session(self.engine) as session:
                item = self.mark_in(session, workspace_id, identifier)
                if dict(kind=kind, id=target_id) not in self.targets(session, item):
                    raise HTTPException(404, '笔记关系不存在')
                if kind == 'file_note':
                    node = node_in(session, workspace_id, target_id)
                    if node.removed_at:
                        raise HTTPException(409, '笔记已从资源树移除')
                    return describe_node(session, self.root, node)
                old = session.get(Note, target_id)
                if old is None or old.workspace_id != workspace_id:
                    raise HTTPException(404, '笔记不存在')
                return dict(id=old.id, title=old.title, content=old.content, resource_id=old.resource_id,
                            revision=note_revision(old))

        @router.get('/learning-marks/{identifier}/revisions')
        def revisions(workspace_id: str, identifier: str, offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100)):
            with Session(self.engine) as session:
                self.mark_in(session, workspace_id, identifier)
                return [dict(revision=r.revision, content=r.content, created_at=r.created_at) for r in session.scalars(
                    select(LearningMarkRevision).where(LearningMarkRevision.mark_id == identifier)
                    .order_by(LearningMarkRevision.revision.desc()).offset(offset).limit(limit))]

        return router
