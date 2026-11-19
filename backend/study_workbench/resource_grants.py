"""Closed, local-only resource projections; links and attachments never grant reads."""
import hashlib
import os
import stat
from pathlib import Path
from time import monotonic
from typing import Annotated, Literal

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, field_validator, model_validator
from sqlalchemy import LargeBinary, cast, func, select

from .backup_archive import archive_path
from .db import DocumentPreview, DocumentWorkfile, LearningMark, Note, Resource, WorkspaceNode
from .document_files import PLAIN_TEXT_SUFFIXES, TEXT_LIMIT
from .imports import note_revision, resource_path
from .learning_marks import ANCHOR
from .learning_search import note_text
from .office_previews import OPTIONS_HASH
from .question_protocol import Content, ResourceId
from .resource_pdf import SOURCE_BYTES, page_text

Hash = Annotated[str, Field(strict=True, pattern=r'^[a-f0-9]{64}$')]
Revision = Annotated[int, Field(strict=True, ge=1)]
TEXT_BYTES = 64 * 1024
CONTEXT_BYTES = 1024 * 1024
FILE_BYTES = 16 * TEXT_LIMIT
CONTENT = TypeAdapter(Content)
PDF_REPRESENTATIONS = {'original_pdf_text', 'office_pdf_text'}
PDF_SECONDS = 20


class ResourceSelection(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)
    kind: Literal['resource_node', 'legacy_note', 'learning_mark']
    id: ResourceId
    mode: Literal['metadata', 'text'] = 'metadata'
    representation: Literal['original_text', 'working_text', 'original_pdf_text', 'office_pdf_text'] | None = None
    expected_sha256: Hash | None = None
    expected_revision: Hash | Revision | None = None
    line: Annotated[int, Field(strict=True, ge=1, le=1048577)] | None = None
    page: Annotated[int, Field(strict=True, ge=1, le=2000)] | None = None
    preview_id: ResourceId | None = None
    expected_source_sha256: Hash | None = None

    @model_validator(mode='after')
    def scope_fields(self):
        if self.mode == 'metadata':
            if any(x is not None for x in (self.representation, self.expected_sha256, self.expected_revision,
                                           self.line, self.page, self.preview_id, self.expected_source_sha256)):
                raise ValueError('元数据选择不能带正文或位置参数')
        elif self.kind == 'resource_node':
            if self.representation is None or self.expected_sha256 is None or self.expected_revision is not None:
                raise ValueError('文本资源须明确权威和内容hash')
            if self.representation in PDF_REPRESENTATIONS:
                if self.page is None or self.line is not None:
                    raise ValueError('PDF文字须明确单页，不能指定原文行')
                office = self.representation == 'office_pdf_text'
                if (office != (self.preview_id is not None) or office != (self.expected_source_sha256 is not None)):
                    raise ValueError('Office页须绑定原件hash及派生预览')
            elif any(x is not None for x in (self.page, self.preview_id, self.expected_source_sha256)):
                raise ValueError('纯文本不能指定PDF页或派生版本')
        elif (self.representation is not None or self.expected_sha256 is not None or self.line is not None
              or any(x is not None for x in (self.page, self.preview_id, self.expected_source_sha256))
              or self.kind == 'legacy_note' and not isinstance(self.expected_revision, str)
              or self.kind == 'learning_mark' and type(self.expected_revision) is not int):
            raise ValueError('笔记或标记须明确对应修订，不能带文件参数')
        return self


class ResourceGrantInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    purpose: Literal['read_resources']
    selections: list[ResourceSelection] = Field(min_length=1, max_length=100)
    expires_in_seconds: int = Field(default=300, ge=1, le=900, strict=True)
    confirm: Literal[True]

    @field_validator('confirm', mode='before')
    @classmethod
    def confirmed(cls, value):
        if value is not True:
            raise ValueError('必须明确确认授权')
        return value

    @field_validator('selections')
    @classmethod
    def distinct(cls, value):
        if len({(s.kind, s.id) for s in value}) != len(value):
            raise ValueError('选择不能重复')
        return value


def read_resources(session, root, workspace, selections, encode):
    remaining, used, items, checks, versions = FILE_BYTES, 0, [], [], []
    deadline = monotonic() + PDF_SECONDS if any(s.representation in PDF_REPRESENTATIONS for s in selections) else None

    def checkpoint():
        if deadline is not None and monotonic() >= deadline:
            raise HTTPException(422, '资料正文处理超过20秒；原件保留')

    def row(statement):
        checkpoint()
        value = session.execute(statement).first()
        if value is None:
            raise HTTPException(404, '所选资料不存在或不在允许范围')
        versions.append((statement, tuple(value)))
        return value

    def read_file(relative, wanted, limit=TEXT_LIMIT, *, binary=False):
        nonlocal remaining
        checkpoint()
        if root is None:
            raise HTTPException(503, '当前未配置资料读取服务')
        try:
            normalized = archive_path(relative)
        except ValueError:
            raise HTTPException(409, '资料路径无效；原件保留') from None
        if not normalized.startswith(f'workspaces/{workspace}/'):
            raise HTTPException(409, '资料路径无效；原件保留')
        try:
            def opener(path, flags):
                return os.open(path, flags | getattr(os, 'O_NONBLOCK', 0) | getattr(os, 'O_NOFOLLOW', 0))

            with open(resource_path(root, relative), 'rb', opener=opener, buffering=0) as handle:
                before = os.fstat(handle.fileno())
                if not stat.S_ISREG(before.st_mode):
                    raise HTTPException(409, '资料不是普通文件')
                if before.st_size > min(limit, remaining) or remaining == 0:
                    raise HTTPException(413, '授权文件读取超过预算，请减少范围')
                raw = handle.read(min(limit, remaining))
                remaining -= len(raw)
                after = os.fstat(handle.fileno())
                if (len(raw) != before.st_size or (after.st_size, after.st_dev, after.st_ino)
                        != (before.st_size, before.st_dev, before.st_ino)):
                    raise HTTPException(409, '资料读取中发生变化，请重新查看授权')
            checkpoint()
            if hashlib.sha256(raw).hexdigest() != wanted:
                raise HTTPException(409, '资料版本变化，请重新查看授权')
            return raw if binary else raw.decode('utf-8')
        except (OSError, UnicodeError):
            raise HTTPException(409, '资料不可读取或不是UTF-8；原件保留') from None

    for selection in sorted(selections, key=lambda s: (s.kind, s.id)):
        item = dict(kind=selection.kind, id=selection.id, mode=selection.mode)
        citation = dict(kind=selection.kind, id=selection.id)
        if selection.kind == 'resource_node':
            node = row(select(WorkspaceNode.id, WorkspaceNode.name, WorkspaceNode.kind, WorkspaceNode.resource_id,
                              WorkspaceNode.removed_at).where(WorkspaceNode.id == selection.id,
                                                             WorkspaceNode.workspace_id == workspace))
            if node.removed_at:
                raise HTTPException(404, '所选资源已删除')
            item['metadata'] = dict(name=node.name, kind=node.kind)
            original = None
            if node.kind == 'resource':
                original = row(select(Resource.original_name, Resource.mime, Resource.size, Resource.sha256,
                                      Resource.relative_path).where(Resource.id == node.resource_id,
                                                                   Resource.workspace_id == workspace))
                item['metadata'].update(mime=original.mime, size=original.size, original_sha256=original.sha256)
            if selection.mode == 'text':
                suffix = Path(original.original_name).suffix.lower() if original else ''
                if selection.representation in PDF_REPRESENTATIONS:
                    if original is None:
                        raise HTTPException(422, '此目标不是PDF或Office原件')
                    citation['source_resource_id'] = node.resource_id
                    if selection.representation == 'original_pdf_text':
                        if suffix != '.pdf':
                            raise HTTPException(422, '此资源不是PDF原件')
                        if original.sha256 != selection.expected_sha256 or original.size > SOURCE_BYTES:
                            raise HTTPException(409 if original.sha256 != selection.expected_sha256 else 413,
                                                'PDF原件版本不符或超限')
                        relative, wanted = original.relative_path, original.sha256
                        citation['anchor'] = dict(version=1, workspace_id=workspace, resource_item_id=node.id,
                            kind='pdf_page', content_sha256=wanted, page=selection.page, representation='original')
                    else:
                        if suffix not in {'.docx', '.pptx'}:
                            raise HTTPException(422, '此资源不是Office分页原件')
                        preview = row(select(DocumentPreview.source_resource_id, DocumentPreview.source_sha256,
                            DocumentPreview.status, DocumentPreview.pdf_sha256, DocumentPreview.pdf_size,
                            DocumentPreview.page_count, DocumentPreview.relative_pdf, DocumentPreview.options_hash,
                            DocumentPreview.converter_version, DocumentPreview.runtime_fingerprint).where(
                                DocumentPreview.id == selection.preview_id, DocumentPreview.workspace_id == workspace,
                                DocumentPreview.node_id == node.id))
                        if (preview.status != 'ready' or preview.options_hash != OPTIONS_HASH
                                or preview.source_resource_id != node.resource_id or preview.source_sha256 != original.sha256
                                or preview.source_sha256 != selection.expected_source_sha256
                                or preview.pdf_sha256 != selection.expected_sha256):
                            raise HTTPException(409, 'Office源或所选派生版本不符，未自动转换')
                        if (preview.pdf_size is None or preview.pdf_size <= 0 or original.size + preview.pdf_size > SOURCE_BYTES):
                            raise HTTPException(413, 'Office原件和派生PDF组合超过8MiB')
                        required = f'workspaces/{workspace}/previews/{selection.preview_id}/output/source.pdf'
                        if preview.relative_pdf != required:
                            raise HTTPException(409, '派生PDF路径与所选预览不符')
                        source_limit = SOURCE_BYTES - preview.pdf_size
                        source = read_file(original.relative_path, original.sha256, source_limit, binary=True)
                        if len(source) != original.size:
                            raise HTTPException(409, 'Office原件大小与记录不符')
                        checks.append((original.relative_path, original.sha256, source_limit, True))
                        relative, wanted = preview.relative_pdf, preview.pdf_sha256
                        citation.update(converter_version=preview.converter_version,
                                        runtime_fingerprint=preview.runtime_fingerprint, options_hash=preview.options_hash)
                        citation['anchor'] = dict(version=1, workspace_id=workspace, resource_item_id=node.id,
                            kind='office_pdf_page', content_sha256=wanted, source_sha256=original.sha256,
                            preview_id=selection.preview_id, page=selection.page, representation='paginated')
                    pdf_limit = SOURCE_BYTES - len(source) if selection.representation == 'office_pdf_text' else SOURCE_BYTES
                    pdf = read_file(relative, wanted, pdf_limit, binary=True)
                    if selection.representation == 'original_pdf_text' and len(pdf) != original.size:
                        raise HTTPException(409, 'PDF原件大小与记录不符')
                    if selection.representation == 'office_pdf_text' and (len(source) + len(pdf) > SOURCE_BYTES or len(pdf) != preview.pdf_size):
                        raise HTTPException(409, 'Office派生文件大小变化')
                    checks.append((relative, wanted, pdf_limit, True))
                    value = page_text(pdf, selection.page, deadline)
                    if selection.representation == 'office_pdf_text' and value['page_count'] != preview.page_count:
                        raise HTTPException(409, 'Office派生页数与记录不符')
                    citation.update(authority=selection.representation, content_sha256=wanted,
                                    **{k: value[k] for k in ('extractor_version', 'pypdfium2_version', 'pdfium_version', 'text_sha256')})
                    item.update(text=value['text'], text_status=value['text_status'], source_binary_read=True)
                elif suffix not in {'.md', '.markdown'} | PLAIN_TEXT_SUFFIXES:
                    raise HTTPException(422, '此格式尚不支持授权正文，请选择元数据')
                elif selection.line is not None and suffix not in {'.md', '.markdown', '.txt'}:
                    raise HTTPException(422, '此格式尚不支持原文行位置')
                if selection.representation in PDF_REPRESENTATIONS:
                    pass
                elif selection.representation == 'working_text':
                    if suffix not in {'.md', '.markdown'}:
                        raise HTTPException(409, '当前没有对应的已保存Markdown工作文件')
                    work = row(select(DocumentWorkfile.relative_path).where(DocumentWorkfile.node_id == node.id,
                                                                          DocumentWorkfile.workspace_id == workspace))
                    relative = work.relative_path
                else:
                    if selection.expected_sha256 != original.sha256:
                        raise HTTPException(409, '原件hash与选择不符')
                    relative = original.relative_path
                if selection.representation not in PDF_REPRESENTATIONS:
                    text = read_file(relative, selection.expected_sha256)
                    checks.append((relative, selection.expected_sha256, TEXT_LIMIT, False))
                    citation.update(authority=selection.representation, content_sha256=selection.expected_sha256)
                    if selection.line is not None:
                        lines = [line.removesuffix('\r') for line in text.split('\n')]
                        if selection.line > len(lines):
                            raise HTTPException(409, '所选行超出当前文本')
                        text = lines[selection.line - 1]
                        citation.update(line=selection.line, line_sha256=hashlib.sha256(text.encode()).hexdigest())
                    item['text'] = text
        elif selection.kind == 'legacy_note':
            meta = row(select(Note.id, Note.title).where(Note.id == selection.id, Note.workspace_id == workspace))
            item['metadata'] = dict(title=meta.title)
            if selection.mode == 'text':
                size = session.scalar(select(func.length(cast(Note.content, LargeBinary))).where(
                    Note.id == meta.id, Note.workspace_id == workspace))
                if size is None or size > TEXT_BYTES:
                    raise HTTPException(413, '笔记结构超过64KiB，请另行整理')
                note = row(select(Note.title, Note.content).where(Note.id == meta.id, Note.workspace_id == workspace,
                    func.length(cast(Note.content, LargeBinary)) <= TEXT_BYTES))
                revision = note_revision(note)
                if revision != selection.expected_revision:
                    raise HTTPException(409, '笔记修订变化，请重新查看授权')
                blocks = CONTENT.dump_python(CONTENT.validate_python(note.content), mode='json')
                item['text'] = note_text(blocks)
                citation['revision'] = revision
        else:
            fields = [LearningMark.id, LearningMark.resource_item_id, LearningMark.anchor, LearningMark.title,
                      LearningMark.revision, LearningMark.removed_at]
            if selection.mode == 'text':
                fields.append(LearningMark.note)
            mark = row(select(*fields).where(LearningMark.id == selection.id, LearningMark.workspace_id == workspace,
                func.length(cast(LearningMark.anchor, LargeBinary)) <= 16 * 1024))
            if mark.removed_at:
                raise HTTPException(404, '标记不存在或已删除')
            anchor = ANCHOR.validate_python(mark.anchor)
            if anchor.workspace_id != workspace or anchor.resource_item_id != mark.resource_item_id:
                raise HTTPException(409, '标记来源不一致；未读取目标')
            target_query = select(WorkspaceNode.removed_at).where(WorkspaceNode.id == mark.resource_item_id,
                                                                WorkspaceNode.workspace_id == workspace)
            target = session.execute(target_query).first()
            if target is not None:
                versions.append((target_query, tuple(target)))
            status = 'missing' if target is None else 'removed' if target.removed_at else 'not_checked'
            item['metadata'] = dict(title=mark.title, revision=mark.revision, anchor=mark.anchor,
                                    position_status=status, position_verified=False)
            citation['revision'] = mark.revision
            if selection.mode == 'text':
                if selection.expected_revision != mark.revision:
                    raise HTTPException(409, '标记修订变化，请重新查看授权')
                item['text'] = mark.note
        if 'text' in item and len(item['text'].encode('utf-8')) > TEXT_BYTES:
            raise HTTPException(413, '单份授权正文超过64KiB，请缩小范围')
        item['citation'] = citation
        used += len(encode(item))
        if used > CONTEXT_BYTES:
            raise HTTPException(413, '授权上下文超过1MiB，请减少选择')
        items.append(item)
    for relative, wanted, limit, binary in checks:
        read_file(relative, wanted, limit, binary=binary)
    # Release the read snapshot before verifying mutable metadata in a fresh transaction.
    session.rollback()
    for statement, before in versions:
        current = session.execute(statement).first()
        if current is None or tuple(current) != before:
            raise HTTPException(409, '资料读取中发生变化，请重新查看授权')
    checkpoint()
    return dict(schema_version=1, purpose='read_resources', workspace_id=workspace, resources=items,
                binary_attachments_read=False, links_followed=False)
