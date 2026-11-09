"""Identity-scoped viewers and optimistic Markdown saves with durable recovery receipts."""
import hashlib
import json
import os
import re
import subprocess
import sys
from functools import wraps
from pathlib import Path, PurePosixPath
from threading import BoundedSemaphore, RLock
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import office_runtime
from .backup_archive import archive_path
from .db import DocumentSave, DocumentWorkfile, Resource, write_transaction
from .documents import convert_document
from .explorer import node_in, relative_node
from .imports import read_resource, resource_path
from .markdown_merge import preview_merge
from .office_previews import OfficePreviews
from .workspaces import require_workspace

TEXT_LIMIT = 1024 * 1024
PLAIN_TEXT_SUFFIXES = {'.txt', '.json', '.csv', '.log', '.vtt', '.srt'}
VIEW_SLOTS = BoundedSemaphore(2)


def limited_view(operation):
    @wraps(operation)
    def bounded(*args, **kwargs):
        if not VIEW_SLOTS.acquire(blocking=False):
            raise HTTPException(429, '已有两个文件正在处理，请稍后重试')
        try:
            return operation(*args, **kwargs)
        finally:
            VIEW_SLOTS.release()
    return bounded


def digest(data):
    return hashlib.sha256(data).hexdigest()


def text_bytes(root, relative):
    try:
        with resource_path(root, relative).open('rb') as handle:
            data = handle.read(TEXT_LIMIT + 1)
        if len(data) > TEXT_LIMIT:
            raise HTTPException(413, 'Markdown编辑最多1MiB；文件保留，可在外部处理')
        data.decode('utf-8')
        return data
    except (OSError, UnicodeError) as error:
        raise HTTPException(409, '工作文件不可读取或不是UTF-8；文件与恢复点保留') from error


def write_new(path, data):
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('xb') as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
    except OSError as error:
        raise HTTPException(409, '写入失败，原件、草稿及已写入字节保留') from error


def raster(data, mode, page=1):
    command = [sys.executable]
    if not getattr(sys, 'frozen', False):
        command.extend(['-m', 'study_workbench'])
    command.extend(['--view-document', mode])
    try:
        result = subprocess.run(command, input=json.dumps({'page': page}).encode() + b'\n' + data,
                                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=20,
                                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
                                env={**os.environ, 'PYTHONUTF8': '1', 'PYTHONIOENCODING': 'utf-8',
                                     'PYTHONPATH': str(Path(__file__).resolve().parents[1])})
        if result.returncode or len(result.stdout) > 24 * 1024 * 1024:
            raise ValueError('Worker failed')
        value = json.loads(result.stdout)
        if 'error' in value:
            raise ValueError('Invalid document')
        return value
    except (subprocess.TimeoutExpired, ValueError) as error:
        if mode == 'xlsx':
            raise HTTPException(422, 'XLSX只读解析失败或超过20秒：可能损坏、加密、含外部关系或超出预算；原件保留') from error
        raise HTTPException(422, '文档渲染失败或超过20秒；可能损坏、加密或超限，原件保留') from error


class SaveText(BaseModel):
    model_config = ConfigDict(extra='forbid')
    expected_sha256: str = Field(pattern=r'^[a-f0-9]{64}$')
    text: str = Field(max_length=TEXT_LIMIT)


class CreateCopy(BaseModel):
    model_config = ConfigDict(extra='forbid')
    expected_sha256: str = Field(pattern=r'^[a-f0-9]{64}$')


class MergeText(BaseModel):
    model_config = ConfigDict(extra='forbid')
    base: Literal['original', 'before', 'pending']
    save_id: str | None = Field(default=None, pattern=r'^[a-f0-9]{32}$')
    expected_base_sha256: str = Field(pattern=r'^[a-f0-9]{64}$')
    expected_current_sha256: str = Field(pattern=r'^[a-f0-9]{64}$')
    text: str = Field(max_length=TEXT_LIMIT)

    @model_validator(mode='wrap')
    @classmethod
    def safe_validation(cls, values, handler):
        try:
            return handler(values)
        except ValidationError as error:
            # Raw invalid Unicode cannot be echoed by the default JSON validation response.
            raise HTTPException(422, '合并请求字段或UTF-8文字无效；草稿保留') from error

    @model_validator(mode='after')
    def baseline_reference(self):
        if (self.base == 'original') != (self.save_id is None):
            raise ValueError('Original base must omit save_id; recovery base requires save_id')
        return self


class DocumentFiles:
    def __init__(self, engine, root):
        self.engine, self.root = engine, root
        self.lock = RLock()
        self.recover()
        self.previews = OfficePreviews(engine, root)

    def close(self):
        self.previews.close()

    def recover(self):
        with self.lock, write_transaction(self.engine) as session:
            for operation in session.scalars(select(DocumentSave).where(DocumentSave.status == 'prepared')):
                work = session.get(DocumentWorkfile, operation.node_id)
                try:
                    current = digest(text_bytes(self.root, work.relative_path))
                except HTTPException:
                    operation.status = 'conflict'
                    continue
                if current == operation.new_sha256:
                    work.indexed_sha256, operation.status = current, 'committed'
                elif current == operation.old_sha256:
                    operation.status = 'interrupted'
                else:
                    operation.status = 'conflict'

    def locate(self, session, workspace, identifier):
        require_workspace(session, workspace)
        node = node_in(session, workspace, identifier)
        if node.kind != 'resource':
            raise HTTPException(422, '此资源应使用网页或媒体查看器')
        resource = session.get(Resource, node.resource_id)
        suffix = Path(resource.original_name).suffix.lower()
        return node, resource, suffix

    def source(self, session, workspace, identifier):
        node, original, suffix = self.locate(session, workspace, identifier)
        work = session.get(DocumentWorkfile, node.id)
        if work:
            data = text_bytes(self.root, work.relative_path)
        else:
            limit = TEXT_LIMIT if suffix in {'.md', '.markdown'} | PLAIN_TEXT_SUFFIXES else 32 * TEXT_LIMIT if suffix in {'.docx', '.pptx'} else 16 * TEXT_LIMIT if suffix in {'.png', '.jpg', '.jpeg', '.xlsx'} else 128 * TEXT_LIMIT
            if original.size > limit:
                raise HTTPException(413, f'此格式查看预算为{limit // TEXT_LIMIT}MiB，原件已保留')
            data = read_resource(self.root, original)
        return node, original, suffix, work, data

    def save_text(self, workspace_id: str, node_id: str, body: SaveText):
        data = body.text.encode('utf-8')
        if len(data) > TEXT_LIMIT:
            raise HTTPException(413, 'Markdown最多1MiB UTF-8字节；草稿保留')
        with self.lock:
            with write_transaction(self.engine) as session:
                node, _, suffix, work, before = self.source(session, workspace_id, node_id)
                if work is None or suffix not in {'.md', '.markdown'}:
                    raise HTTPException(409, '请先显式创建Markdown工作副本，原件不会改写')
                if digest(before) != body.expected_sha256:
                    raise HTTPException(409, '文件已在外部或其他页面修改；草稿保留，请核对冲突')
                if session.scalar(select(DocumentSave.id).where(DocumentSave.node_id == node.id, DocumentSave.status == 'prepared')):
                    raise HTTPException(409, '上次保存尚待重启对账；文件和草稿保留')
                identifier = uuid4().hex
                relative = work.relative_path
                directory = Path(relative).parent.as_posix()
                backup, pending = f'{directory}/{identifier}.before.md', f'{directory}/{identifier}.pending.md'
                write_new(resource_path(self.root, backup), before)
                write_new(resource_path(self.root, pending), data)
                session.add(DocumentSave(id=identifier, node_id=node.id, old_sha256=digest(before),
                                         new_sha256=digest(data), backup_path=backup, pending_path=pending, status='prepared'))
            # A receipt is committed before replacement; recovery never blindly replays writes.
            if digest(text_bytes(self.root, relative)) != body.expected_sha256:
                with write_transaction(self.engine) as session:
                    session.get(DocumentSave, identifier).status = 'conflict'
                raise HTTPException(409, '文件在保存期间变化，草稿及恢复点保留')
            try:
                os.replace(resource_path(self.root, pending), resource_path(self.root, relative))
            except OSError as error:
                raise HTTPException(409, '文件替换未完成，草稿及恢复点保留；重启后对账再保存') from error
            with write_transaction(self.engine) as session:
                session.get(DocumentWorkfile, node_id).indexed_sha256 = digest(data)
                session.get(DocumentSave, identifier).status = 'committed'
        return {'sha256': digest(data), 'working_copy': True}

    def recovery_work(self, session, workspace, identifier):
        node, original, suffix = self.locate(session, workspace, identifier)
        work = session.get(DocumentWorkfile, node.id)
        if original.workspace_id != workspace or work is None or work.workspace_id != workspace:
            raise HTTPException(404, '此资源没有可用的工作副本恢复记录')
        if suffix not in {'.md', '.markdown'}:
            raise HTTPException(422, '仅Markdown支持保存恢复点')
        try:
            parts = PurePosixPath(archive_path(work.relative_path)).parts
            if len(parts) < 5 or parts[:2] != ('workspaces', workspace) or parts[2] not in {'working', 'question-files'}:
                raise ValueError('Invalid workfile owner')
            if parts[2] == 'working' and (len(parts) != 6 or parts[3] != identifier or parts[5] != 'current.md'):
                raise ValueError('Invalid working directory')
            if parts[2] == 'question-files' and (len(parts) != 5 or parts[4] != 'current.md'):
                raise ValueError('Invalid question workfile')
        except ValueError as error:
            raise HTTPException(409, '工作副本路径与空间不符；恢复点保留') from error
        return work

    def recovery_text(self, workspace, identifier, save_id, version):
        with self.lock, Session(self.engine) as session:
            work = self.recovery_work(session, workspace, identifier)
            row = session.get(DocumentSave, save_id)
            if row is None or row.node_id != work.node_id:
                raise HTTPException(404, '保存恢复记录不存在')
            if not re.fullmatch(r'[a-f0-9]{32}', row.id):
                raise HTTPException(409, '保存恢复记录标识无效；文件保留')
            relative = row.backup_path if version == 'before' else row.pending_path
            expected = row.old_sha256 if version == 'before' else row.new_sha256
            required = f'{PurePosixPath(work.relative_path).parent}/{row.id}.{version}.md'
            if relative != required:
                raise HTTPException(409, '保存恢复点路径与收据不符；文件保留')
            data = text_bytes(self.root, relative)
            if digest(data) != expected:
                raise HTTPException(409, '保存恢复点内容与收据不符；文件保留')
            current, unavailable = None, None
            if session.scalar(select(DocumentSave.id).where(
                    DocumentSave.node_id == work.node_id, DocumentSave.status == 'prepared')):
                unavailable = '上次保存尚待重启对账，暂不能载入恢复草稿'
            else:
                try:
                    current = digest(text_bytes(self.root, work.relative_path))
                except HTTPException:
                    unavailable = '当前工作文件不可读取；恢复点可查看，暂不能载入草稿'
            return dict(id=row.id, status=row.status, version=version, text=data.decode('utf-8'),
                        sha256=expected, current_sha256=current, unavailable_reason=unavailable)

    def merge_preview(self, workspace, identifier, body: MergeText):
        try:
            local = body.text.encode('utf-8')
        except UnicodeError as error:
            raise HTTPException(422, '合并草稿必须是UTF-8文字；草稿保留') from error
        if len(local) > TEXT_LIMIT:
            raise HTTPException(413, '合并草稿最多1MiB UTF-8字节；草稿保留')
        with self.lock, Session(self.engine) as session:
            work = self.recovery_work(session, workspace, identifier)
            if session.scalar(select(DocumentSave.id).where(
                    DocumentSave.node_id == identifier, DocumentSave.status == 'prepared')):
                raise HTTPException(409, '上次保存尚待重启对账；暂不能合并，草稿保留')
            current = text_bytes(self.root, work.relative_path)
            current_hash = digest(current)
            if current_hash != body.expected_current_sha256:
                raise HTTPException(409, '当前工作文件已变化，请重新核对；草稿保留')
            if body.base == 'original':
                _, original, _ = self.locate(session, workspace, identifier)
                if original.size > TEXT_LIMIT:
                    raise HTTPException(413, '合并基线最多1MiB；原件保留')
                base = read_resource(self.root, original)
            else:
                saved = self.recovery_text(workspace, identifier, body.save_id, body.base)
                base = saved['text'].encode('utf-8')
            if digest(base) != body.expected_base_sha256:
                raise HTTPException(409, '合并基线与草稿版本不符；请保留草稿并重新核对')
            try:
                base_text = base.decode('utf-8')
            except UnicodeError as error:
                raise HTTPException(409, '合并基线不是UTF-8文字；原件和草稿保留') from error
            try:
                result = preview_merge(base_text, body.text, current.decode('utf-8'))
            except ValueError as error:
                raise HTTPException(413, '合并结果超过1MiB；原件和草稿保留') from error
            # External editors are not covered by the service lock. Saving still needs this exact hash.
            if digest(text_bytes(self.root, work.relative_path)) != current_hash:
                raise HTTPException(409, '工作文件在预览期间变化；草稿保留，请重新核对')
            return dict(conflicted=result.conflicted, text=result.text, base_sha256=digest(base),
                        local_sha256=digest(local), current_sha256=current_hash)

    def router(self):
        router = APIRouter(prefix='/api/workspaces/{workspace_id}/nodes/{node_id}')

        @router.post('/document-merge-preview')
        @limited_view
        def merge(workspace_id: str, node_id: str, body: MergeText):
            return self.merge_preview(workspace_id, node_id, body)

        @router.get('/document-saves')
        def saves(workspace_id: str, node_id: str, offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100)):
            with self.lock, Session(self.engine) as session:
                self.recovery_work(session, workspace_id, node_id)
                return [dict(id=row.id, status=row.status, old_sha256=row.old_sha256, new_sha256=row.new_sha256)
                        for row in session.scalars(select(DocumentSave).where(DocumentSave.node_id == node_id)
                            .order_by(DocumentSave.id).offset(offset).limit(limit))]

        @router.get('/document-saves/{save_id}')
        @limited_view
        def saved_text(workspace_id: str, node_id: str, save_id: str, version: Literal['before', 'pending']):
            return self.recovery_text(workspace_id, node_id, save_id, version)

        @router.get('/document')
        @limited_view
        def document(workspace_id: str, node_id: str):
            with Session(self.engine) as session:
                node, original, suffix, work, data = self.source(session, workspace_id, node_id)
                result = dict(resource_item_id=node.id, source_resource_id=original.id,
                              source_sha256=original.sha256, sha256=digest(data), working_copy=work is not None,
                              external_change=work is not None and digest(data) != work.indexed_sha256)
            if suffix in {'.md', '.markdown'} | PLAIN_TEXT_SUFFIXES:
                try:
                    result.update(type='markdown' if suffix in {'.md', '.markdown'} else 'text', text=data.decode('utf-8'))
                    if suffix in PLAIN_TEXT_SUFFIXES:
                        result.update(source_format=suffix[1:], position_kind='text_line' if suffix == '.txt' else 'resource')
                except UnicodeError as error:
                    raise HTTPException(422, '文本不是UTF-8；原件保留，不进行有损替换') from error
            elif suffix == '.pdf':
                result.update(type='pdf', **raster(data, 'pdf-info'))
            elif suffix in {'.png', '.jpg', '.jpeg'}:
                result.update(type='image', **raster(data, 'image'))
            elif suffix == '.xlsx':
                result.update(type='spreadsheet', **raster(data, 'xlsx'))
            elif suffix == '.docx' and len(data) <= 8 * TEXT_LIMIT:
                try:
                    preview = convert_document(data, original.original_name)
                    result.update(type='word', blocks=preview['blocks'], assets=preview.get('_assets', []),
                                  warnings=preview['warnings'], converter_version='docling-structure-v1')
                except ValueError as error:
                    raise HTTPException(422, 'Word结构预览失败或超限；原件保留，可在外部转PDF后添加') from error
            elif suffix in {'.docx', '.pptx'}:
                result.update(type='office', message='可显式生成分页PDF预览。静态PDF不保留幻灯片动画/嵌入视频；原件保持不变。')
            else:
                result.update(type='unsupported', message='此格式的文件查看器尚未接入。旧DOC/PPT请先在外部转PDF后添加；原件保留。')
            if suffix in {'.docx', '.pptx'}:
                result.update(preview_capability=office_runtime.capability(),
                              preview=self.previews.latest(workspace_id, node_id, original.sha256))
            return result

        @router.get('/previews/{preview_id}/page')
        @limited_view
        def preview_page(workspace_id: str, node_id: str, preview_id: str, page: int = Query(1, ge=1, le=2000)):
            data, info = self.previews.read_pdf(workspace_id, node_id, preview_id)
            return dict(source_resource_id=info['source_resource_id'], source_sha256=info['source_sha256'],
                        pdf_sha256=info['pdf_sha256'], **raster(data, 'pdf-page', page))

        @router.get('/document-page')
        @limited_view
        def page(workspace_id: str, node_id: str, page: int = Query(1, ge=1, le=2000)):
            with Session(self.engine) as session:
                _, original, suffix, _, data = self.source(session, workspace_id, node_id)
                if suffix != '.pdf':
                    raise HTTPException(422, '此资源不是PDF')
            return dict(source_resource_id=original.id, source_sha256=original.sha256, **raster(data, 'pdf-page', page))

        @router.get('/relative-image')
        @limited_view
        def relative_image(workspace_id: str, node_id: str, path: str = Query(min_length=1, max_length=2048)):
            with Session(self.engine) as session:
                node, _, _ = self.locate(session, workspace_id, node_id)
                target = relative_node(session, workspace_id, node, path)
                _, original, suffix, _, data = self.source(session, workspace_id, target.id)
                if suffix not in {'.png', '.jpg', '.jpeg'}:
                    raise HTTPException(422, '相对图片仅支持PNG/JPEG')
            return dict(source_resource_id=original.id, source_sha256=original.sha256, **raster(data, 'image'))

        @router.post('/working-copy')
        def create_copy(workspace_id: str, node_id: str, body: CreateCopy):
            with self.lock, write_transaction(self.engine) as session:
                node, _, suffix, work, data = self.source(session, workspace_id, node_id)
                if suffix not in {'.md', '.markdown'}:
                    raise HTTPException(422, '仅Markdown支持工作副本编辑')
                if digest(data) != body.expected_sha256:
                    raise HTTPException(409, '内容已变化，请刷新核对后再创建工作副本')
                try:
                    data.decode('utf-8')
                except UnicodeError as error:
                    raise HTTPException(422, 'Markdown必须为UTF-8，原件保留') from error
                if work is None:
                    relative = f'workspaces/{workspace_id}/working/{node.id}/{uuid4().hex}/current.md'
                    write_new(resource_path(self.root, relative), data)
                    session.add(DocumentWorkfile(node_id=node.id, workspace_id=workspace_id,
                                                 relative_path=relative, indexed_sha256=digest(data)))
            return {'working_copy': True, 'sha256': digest(data)}

        @router.put('/document')
        def save(workspace_id: str, node_id: str, body: SaveText):
            return self.save_text(workspace_id, node_id, body)

        return router
