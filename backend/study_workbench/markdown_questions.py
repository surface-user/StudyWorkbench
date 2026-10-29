"""Explicit, idempotent per-question Markdown persistence from document previews."""
import hashlib
import json
import os
from typing import Annotated, Literal
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import ImportJob, MarkdownQuestion, Resource, write_transaction
from .imports import read_resource, resource_path, validate_attachments
from .question_splitting import all_blocks, draft_revision, markdown
from .workspaces import require_workspace


class ConfirmMarkdown(BaseModel):
    model_config = ConfigDict(extra='forbid')
    expected_revision: str = Field(pattern=r'^[a-f0-9]{64}$')
    selected: list[Annotated[int, Field(strict=True, ge=0)]] = Field(min_length=1, max_length=200)
    confirm: Literal[True]


def describe(item):
    return {'id': item.id, 'title': item.title, 'source_resource_id': item.source_resource_id,
            'markdown_resource_id': item.markdown_resource_id, 'source_pages': item.content['source_pages']}


def markdown_router(engine, root):
    router = APIRouter(prefix='/api/workspaces/{workspace_id}')

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
            read_resource(root, original)
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
                pages = ', '.join(str(p) for p in draft['source_pages']) or 'Word内容顺序（无可靠分页）'
                provenance = {'original_filename': original.original_name, 'original_sha256': original.sha256,
                              'original_resource_id': original.id, 'pages': draft['source_pages'],
                              'regions': draft['regions'], 'parser_version': job.parser_version,
                              'verification': 'unverified', 'answer_status': 'not_inferred'}
                provenance['shared_material_ids'] = [m['id'] for m in draft.get('shared_materials', [])]
                provenance['text_status'] = draft.get('text_status', 'extracted')
                # JSON inside a fenced metadata section keeps arbitrary filenames out of Markdown syntax.
                content = markdown(draft) + f'\n---\n来源位置：{pages}\n\n```json\n' + json.dumps(
                    provenance, ensure_ascii=False, indent=2) + '\n```\n'
                data = content.encode('utf-8')
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
