"""Explicit, idempotent per-question Markdown persistence from document previews."""
import hashlib
import json
import os
import re
import stat
from typing import Annotated, Literal
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .backup_archive import archive_path
from .db import ImportJob, MarkdownQuestion, PdfChunkJob, Resource, write_transaction
from .document_files import limited_view
from .imports import check_chunk_pdf, read_resource, resource_path, validate_attachments
from .question_splitting import all_blocks, draft_revision, markdown
from .workspaces import require_workspace


class ConfirmMarkdown(BaseModel):
    model_config = ConfigDict(extra='forbid')
    expected_revision: str = Field(pattern=r'^[a-f0-9]{64}$')
    selected: list[Annotated[int, Field(strict=True, ge=0)]] = Field(min_length=1, max_length=200)
    confirm: Literal[True]


class RecoverySelection(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    directory_id: str = Field(pattern=r'^[a-f0-9]{32}$')
    ordinal: int = Field(ge=0, lt=200)
    expected_revision: str = Field(pattern=r'^[a-f0-9]{64}$')


def describe(item):
    return {'id': item.id, 'title': item.title, 'source_resource_id': item.source_resource_id,
            'markdown_resource_id': item.markdown_resource_id, 'source_pages': item.content['source_pages']}


def question_bytes(draft, job, original, chunk_job):
    pages = ', '.join(str(p) for p in draft['source_pages']) or 'Word内容顺序（无可靠分页）'
    provenance = {'original_filename': original.original_name, 'original_sha256': original.sha256,
                  'original_resource_id': original.id, 'pages': draft['source_pages'],
                  'regions': draft['regions'], 'parser_version': job.parser_version,
                  'verification': 'unverified', 'answer_status': 'not_inferred'}
    if chunk_job is not None:
        provenance['selected_page_range'] = [chunk_job.first_page, chunk_job.last_page]
    provenance['shared_material_ids'] = [m['id'] for m in draft.get('shared_materials', [])]
    provenance['shared_materials'] = [
        {key: value for key, value in material.items() if key != 'blocks'}
        for material in draft.get('shared_materials', [])]
    provenance['text_status'] = draft.get('text_status', 'extracted')
    # JSON inside a fenced metadata section keeps arbitrary filenames out of Markdown syntax.
    content = markdown(draft) + f'\n---\n来源位置：{pages}\n\n```json\n' + json.dumps(
        provenance, ensure_ascii=False, indent=2) + '\n```\n'
    return content.encode('utf-8')


def check_recovery_resource(resource, workspace):
    if resource is None or resource.workspace_id != workspace:
        raise HTTPException(409, '恢复来源缺少同空间登记')
    try:
        path = archive_path(resource.relative_path)
    except ValueError as error:
        raise HTTPException(409, '登记的资源路径无效') from error
    if path.split('/')[:2] != ['workspaces', workspace]:
        raise HTTPException(409, '恢复来源超出当前工作空间')


def only_members(directory, names):
    missing = set(names)
    with os.scandir(directory) as items:
        for item in items:
            if item.name not in missing:
                raise HTTPException(409, '候选目录含额外文件')
            missing.remove(item.name)
    if missing:
        raise HTTPException(409, '候选目录缺少正文或附件')


def verify_copy(path, size, expected):
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_size != size:
        raise HTTPException(409, '候选文件类型或长度不符')
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        remaining = size
        while remaining:
            block = stream.read(min(remaining, 1024 * 1024))
            if not block:
                raise HTTPException(409, '候选文件读取期间发生变化')
            remaining -= len(block)
            digest.update(block)
        if stream.read(1) or digest.hexdigest() != expected:
            raise HTTPException(409, '候选文件摘要不符')


def markdown_router(engine, root):
    router = APIRouter(prefix='/api/workspaces/{workspace_id}')

    @router.post('/imports/{job_id}/question-markdown/recovery-preview')
    @limited_view
    def recovery_preview(workspace_id: str, job_id: str, body: RecoverySelection):
        with Session(engine) as session:
            require_workspace(session, workspace_id)
            job = session.get(ImportJob, job_id)
            if job is None or job.workspace_id != workspace_id:
                raise HTTPException(404, '导入记录不存在')
            drafts = job.preview.get('question_drafts', [])
            if (job.status != 'preview' or not body.ordinal < len(drafts) <= 200
                    or draft_revision(drafts) != body.expected_revision):
                raise HTTPException(409, '导入候选已变更或已确认')
            directory = f'workspaces/{workspace_id}/questions/{body.directory_id}'
            owned = select(Resource.id).where(Resource.relative_path.startswith(directory + '/', autoescape=True))
            saved = select(MarkdownQuestion.id).where(MarkdownQuestion.import_job_id == job.id)
            if session.get(MarkdownQuestion, body.directory_id) or session.scalar(owned.limit(1)) or session.scalar(saved.limit(1)):
                raise HTTPException(409, '目录或批次已有登记')
            original = session.get(Resource, job.resource_id)
            chunk = session.get(PdfChunkJob, job.id)
            check_recovery_resource(original, workspace_id)
            if chunk is None:
                if not 0 < original.size <= 8 * 1024 * 1024:
                    raise HTTPException(413, '旧题原件超过核对预算')
                try:
                    verify_copy(resource_path(root, original.relative_path), original.size, original.sha256)
                except OSError as error:
                    raise HTTPException(409, '恢复所需原件不可读取') from error
            else:
                if (chunk.workspace_id, chunk.resource_id, chunk.parser_version) != (
                        workspace_id, original.id, job.parser_version):
                    raise HTTPException(409, '分块来源与候选不符')
                check_chunk_pdf(session, root, workspace_id, original.id, chunk.source_sha256)
            draft = drafts[body.ordinal]
            expected = question_bytes(draft, job, original, chunk)
            if len(expected) > 8 * 1024 * 1024:
                raise HTTPException(413, '题目正文超过核对预算')
            if any(i != body.ordinal and question_bytes(other, job, original, chunk) == expected
                   for i, other in enumerate(drafts)):
                raise HTTPException(409, '同批多个候选生成相同的题目文件')
            md_hash = hashlib.sha256(expected).hexdigest()
            ids = sorted({b['attachment_id'] for b in all_blocks(draft) if b['type'] == 'image'})
            if any(not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,127}', identifier) for identifier in ids):
                raise HTTPException(409, '题目附件标识无效')
            try:
                for identifier in ids:
                    archive_path(identifier + '.png')
            except ValueError as error:
                raise HTTPException(409, '题目附件文件名无效') from error
            if len({key.casefold() for key in ids}) != len(ids):
                raise HTTPException(409, '题目附件文件名冲突')
            assets = []
            total = 0
            try:
                only_members(resource_path(root, directory), {'question.md', 'assets'} if ids else {'question.md'})
                verify_copy(resource_path(root, directory + '/question.md'), len(expected), md_hash)
                if ids:
                    only_members(resource_path(root, directory + '/assets'), {f'{key}.png' for key in ids})
                for identifier in ids:
                    asset = session.get(Resource, identifier)
                    check_recovery_resource(asset, workspace_id)
                    if asset.mime not in {'image/png', 'image/jpeg'} or asset.size <= 0:
                        raise HTTPException(409, '登记的题目图片无效')
                    total += asset.size
                    if total > 64 * 1024 * 1024:
                        raise HTTPException(413, '题目附件超过核对预算')
                    verify_copy(resource_path(root, asset.relative_path), asset.size, asset.sha256)
                    verify_copy(resource_path(root, f'{directory}/assets/{identifier}.png'), asset.size, asset.sha256)
                    assets.append(dict(id=identifier, size=asset.size, sha256=asset.sha256))
            except OSError as error:
                raise HTTPException(409, '候选文件缺失或不可读取') from error
            binding = dict(version=1, workspace_id=workspace_id, import_job_id=job.id, parser_version=job.parser_version,
                           source_resource_id=original.id, source_sha256=original.sha256, markdown_sha256=md_hash,
                           attachments=assets, **body.model_dump())
            serialized = json.dumps(binding, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()
            return {**binding, 'status': 'matched', 'title': draft['title'], 'attachment_count': len(assets),
                    'candidate_sha256': hashlib.sha256(serialized).hexdigest()}

    @router.post('/imports/{job_id}/question-markdown')
    def confirm(workspace_id: str, job_id: str, body: ConfirmMarkdown):
        with write_transaction(engine) as session:
            require_workspace(session, workspace_id)
            job = session.get(ImportJob, job_id)
            if job is None or job.workspace_id != workspace_id:
                raise HTTPException(404, '导入记录不存在')
            drafts = job.preview.get('question_drafts', [])
            revision = draft_revision(drafts)
            if body.expected_revision != revision:
                raise HTTPException(409, '拆题预览已更新，请重新检查')
            if (job.status not in {'preview', 'confirmed'} or not drafts or
                    any(type(i) is not int or i < 0 or i >= len(drafts) for i in body.selected) or
                    len(body.selected) != len(set(body.selected))):
                raise HTTPException(422, '请选择当前预览中有效且不重复的题目')
            existing = list(session.scalars(select(MarkdownQuestion).where(
                MarkdownQuestion.import_job_id == job.id).order_by(MarkdownQuestion.ordinal)))
            if existing:
                if [item.ordinal for item in existing] != sorted(body.selected):
                    raise HTTPException(409, '本批题目已入库，不能用另一组选题重复确认')
                return [describe(item) for item in existing]
            original = session.get(Resource, job.resource_id)
            chunk_job = session.get(PdfChunkJob, job_id)
            if chunk_job is None:
                read_resource(root, original)
            else:
                if chunk_job.workspace_id != workspace_id or chunk_job.resource_id != job.resource_id:
                    raise HTTPException(409, '分块候选与原件关联不符')
                check_chunk_pdf(session, root, workspace_id, original.id, chunk_job.source_sha256)
            for ordinal in body.selected:
                validate_attachments(session, workspace_id, all_blocks(drafts[ordinal]), root)
            results = []
            for ordinal in sorted(body.selected):
                draft = drafts[ordinal]
                validate_attachments(session, workspace_id, all_blocks(draft), root)
                identifier = uuid4().hex
                directory = f'workspaces/{workspace_id}/questions/{identifier}'
                for block in all_blocks(draft):
                    if block['type'] != 'image':
                        continue
                    resource = session.get(Resource, block['attachment_id'])
                    data = read_resource(root, resource)
                    path = resource_path(root, f"{directory}/assets/{resource.id}.png")
                    path.parent.mkdir(parents=True, exist_ok=True)
                    if not path.exists():
                        path.write_bytes(data)
                data = question_bytes(draft, job, original, chunk_job)
                path = resource_path(root, f'{directory}/question.md')
                path.parent.mkdir(parents=True, exist_ok=True)
                with path.open('xb') as handle:
                    handle.write(data)
                    handle.flush()
                    os.fsync(handle.fileno())
                resource = Resource(id=uuid4().hex, workspace_id=workspace_id,
                                    original_name=f'{identifier}.md', relative_path=f'{directory}/question.md',
                                    sha256=hashlib.sha256(data).hexdigest(), size=len(data), mime='text/markdown')
                session.add(resource)
                session.flush()
                item = MarkdownQuestion(id=identifier, workspace_id=workspace_id, import_job_id=job.id,
                                        ordinal=ordinal, title=draft['title'], source_resource_id=original.id,
                                        markdown_resource_id=resource.id, content=draft)
                session.add(item)
                results.append(describe(item))
            job.status = 'confirmed'
            return results

    @router.get('/question-markdown')
    def listing(workspace_id: str, offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100),
                search: str = Query('', max_length=240)):
        with Session(engine) as session:
            require_workspace(session, workspace_id)
            query = select(MarkdownQuestion).where(MarkdownQuestion.workspace_id == workspace_id)
            if search:
                query = query.where(MarkdownQuestion.title.contains(search, autoescape=True))
            return [describe(item) for item in session.scalars(query.order_by(
                MarkdownQuestion.id).offset(offset).limit(limit))]

    @router.get('/question-markdown/{question_id}')
    def detail(workspace_id: str, question_id: str):
        with Session(engine) as session:
            require_workspace(session, workspace_id)
            item = session.get(MarkdownQuestion, question_id)
            if item is None or item.workspace_id != workspace_id:
                raise HTTPException(404, 'Markdown题目不存在')
            data = read_resource(root, session.get(Resource, item.markdown_resource_id))
            return {**describe(item), 'markdown': data.decode('utf-8'), 'blocks': all_blocks(item.content)}

    return router
