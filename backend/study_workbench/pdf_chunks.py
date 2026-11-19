"""Workspace-scoped PDF extraction with durable, idempotent page checkpoints."""
import base64
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from threading import Timer
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import ImportJob, PdfChunk, PdfChunkJob, Resource, write_transaction
from .document_files import limited_view, raster
from .imports import describe, persist_assets, read_pdf_source
from .question_protocol import Content
from .question_splitting import START, DraftSplitter, all_blocks
from .workspaces import require_workspace

VERSION = 'pdf-chunks-v1'
OUTPUT_LIMIT = 96 * 1024 * 1024


class CreateJob(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    resource_id: str = Field(min_length=1, max_length=128)
    expected_sha256: str = Field(pattern=r'^[0-9a-f]{64}$')
    first_page: int = Field(ge=1, le=2000)
    last_page: int = Field(ge=1, le=2000)


class Advance(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    first_page: int = Field(ge=1, le=2000)


def details(job):
    return {key: getattr(job, key) for key in ('id', 'resource_id', 'source_sha256', 'parser_version',
            'first_page', 'last_page', 'page_count', 'next_page', 'status', 'asset_bytes',
            'question_count', 'material_count')} | {'completed_pages': job.next_page - job.first_page}


def scoped_job(session, workspace, job_id):
    require_workspace(session, workspace)
    job = session.get(PdfChunkJob, job_id)
    if job is None or job.workspace_id != workspace:
        raise HTTPException(404, '分块任务不存在')
    return job


def parse_pages(data, first, last):
    cmd = [sys.executable]
    if not getattr(sys, 'frozen', False):
        cmd.extend(['-m', 'study_workbench'])
    cmd.extend(['--parse-pdf-pages', str(first), str(last)])
    env = {**os.environ, 'PYTHONPATH': str(Path(__file__).resolve().parents[1]), 'PYTHONUTF8': '1'}
    # With stdin staged separately, a full input pipe cannot block draining bounded stdout.
    with tempfile.TemporaryFile() as input_file:
        input_file.write(data)
        input_file.seek(0)
        with subprocess.Popen(cmd, stdin=input_file, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                              env=env, creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0) as proc:
            timer = Timer(25, proc.kill)
            timer.start()
            try:
                raw = proc.stdout.read(OUTPUT_LIMIT + 1)
                if len(raw) > OUTPUT_LIMIT:
                    raise ValueError('PDF 分块输出超限')
                if proc.wait():
                    raise ValueError('PDF 分块解析中断或超时')
            finally:
                timer.cancel()
                if proc.poll() is None:
                    proc.kill()
                proc.wait()
                timer.join()
    result = json.loads(raw)
    if 'error' in result:
        raise ValueError('PDF 分块原件无效或解析超限')
    return result


def assemble(session, job, title):
    splitter = DraftSplitter()
    pages = []
    expected = job.first_page
    for piece in session.scalars(select(PdfChunk).where(PdfChunk.job_id == job.id).order_by(PdfChunk.first_page)):
        if piece.first_page != expected or piece.last_page > job.last_page:
            raise HTTPException(409, '已提交区块不连续')
        expected = piece.last_page + 1
        pages.extend(block for block in piece.result['blocks'] if block['type'] == 'image')
        for fragment in piece.result['fragments']:
            if fragment['ambiguous']:
                splitter.group = splitter.current = None
                splitter.warn('部分页面的题号位置不确定，已保留原页并停止自动接续。')
                continue
            marker = fragment['marker']
            if marker is not None:
                match = START.fullmatch(marker)
                if match is None:
                    raise HTTPException(409, '已保存的题目标记不匹配')
                splitter.begin(match)
            current = splitter.current
            if current is not None:
                for field in ('blocks', 'source_pages', 'regions'):
                    current[field].extend(fragment[field])
    if expected != job.last_page + 1:
        raise HTTPException(409, '所选区间尚未提交完整')
    drafts = splitter.finish()
    if job.first_page > 1:
        splitter.warn('选区起点之前可能有题干或材料，首题号前的内容保留在原页。')
    if job.last_page < job.page_count:
        splitter.warn('选区末尾可能截断题目或材料，请核对原件后确认。')
    if not drafts:
        splitter.warn('未识别到可靠题号，原页保留。')
    adapter = TypeAdapter(Content)
    try:
        for draft in drafts:
            adapter.validate_python(all_blocks(draft))
        adapter.validate_python(pages)
    except ValidationError:
        raise HTTPException(422, '候选内容超过题目协议预算，请缩小页段') from None
    preview = dict(kind='note', title=title, blocks=pages, question_drafts=drafts,
                   warnings=splitter.warnings, page_range=[job.first_page, job.last_page])
    # Shared material is serialized once per associated question in the legacy preview.
    byte_count = 0
    for part in json.JSONEncoder(ensure_ascii=False).iterencode(preview):
        byte_count += len(part.encode('utf8'))
        if byte_count > 8 * 1024 * 1024:
            raise HTTPException(413, '候选预览超过 8 MiB，请缩小页段')
    return preview


def pdf_chunk_router(engine, root):
    router = APIRouter(prefix='/api/workspaces/{workspace_id}/pdf-chunk-jobs')

    @router.post('')
    @limited_view
    def create(workspace_id: str, body: CreateJob):
        if not 0 <= body.last_page - body.first_page < 100:
            raise HTTPException(422, '请选择连续的 1 至 100 页')
        with Session(engine) as session:
            data = read_pdf_source(session, root, workspace_id, body.resource_id, body.expected_sha256)
        page_count = raster(data, 'pdf-info')['page_count']
        if body.last_page > page_count:
            raise HTTPException(422, '选择超出原件页数')
        key = dict(workspace_id=workspace_id, resource_id=body.resource_id, source_sha256=body.expected_sha256,
                   parser_version=VERSION, first_page=body.first_page, last_page=body.last_page)
        with write_transaction(engine) as session:
            read_pdf_source(session, root, workspace_id, body.resource_id, body.expected_sha256)
            job = session.scalar(select(PdfChunkJob).filter_by(**key))
            if job is None:
                job = PdfChunkJob(**key, id=uuid4().hex, status='ready', page_count=page_count,
                                  next_page=body.first_page, generation=0, asset_bytes=0,
                                  question_count=0, material_count=0)
                session.add(job)
            return details(job)

    @router.get('')
    def history(workspace_id: str, offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100)):
        with Session(engine) as session:
            require_workspace(session, workspace_id)
            jobs = select(PdfChunkJob).where(PdfChunkJob.workspace_id == workspace_id).order_by(PdfChunkJob.id)
            return [details(job) for job in session.scalars(jobs.offset(offset).limit(limit))]

    @router.get('/{job_id}')
    def get(workspace_id: str, job_id: str):
        with Session(engine) as session:
            return details(scoped_job(session, workspace_id, job_id))

    @router.post('/{job_id}/cancel')
    def cancel(workspace_id: str, job_id: str):
        with write_transaction(engine) as session:
            job = scoped_job(session, workspace_id, job_id)
            if job.status not in {'cancelled', 'parsed'}:
                job.generation += 1
                job.status = 'cancelled'
            return details(job)

    @router.post('/{job_id}/resume')
    def resume(workspace_id: str, job_id: str):
        with write_transaction(engine) as session:
            job = scoped_job(session, workspace_id, job_id)
            if job.status == 'running' or job.parser_version != VERSION:
                raise HTTPException(409, '任务正在解析或解析器版本已变')
            read_pdf_source(session, root, workspace_id, job.resource_id, job.source_sha256)
            if job.status != 'parsed':
                job.status = 'ready'
            return details(job)

    @router.post('/{job_id}/advance')
    @limited_view
    def advance(workspace_id: str, job_id: str, body: Advance):
        first = body.first_page
        with write_transaction(engine) as session:
            job = scoped_job(session, workspace_id, job_id)
            if session.get(PdfChunk, (job_id, first)) is not None:
                return details(job)
            if job.next_page != first or job.status != 'ready' or job.parser_version != VERSION:
                raise HTTPException(409, '任务进度或状态已变，请重新查看')
            data = read_pdf_source(session, root, workspace_id, job.resource_id, job.source_sha256)
            last = min(first + 19, job.last_page)
            job.generation += 1
            generation, job.status = job.generation, 'running'
        try:
            result = parse_pages(data, first, last)
            asset_bytes = sum(len(base64.b64decode(asset['data'], validate=True)) for asset in result['_assets'])
            markers = [START.fullmatch(f['marker']) for f in result['fragments'] if f['marker'] is not None]
            if any(m is None for m in markers):
                raise ValueError('题目标记无效')
            materials = sum(m['first'] is not None for m in markers)
            with write_transaction(engine) as session:
                job = scoped_job(session, workspace_id, job_id)
                if job.status != 'running' or job.generation != generation:
                    raise HTTPException(409, '任务已取消或执行批次已变')
                read_pdf_source(session, root, workspace_id, job.resource_id, job.source_sha256)
                if (result['first_page'], result['last_page'], result['page_count']) != (first, last, job.page_count):
                    raise ValueError('PDF 页区间发生变化')
                job.asset_bytes += asset_bytes
                job.material_count += materials
                job.question_count += len(markers) - materials
                if job.asset_bytes > 64 * 1024 * 1024 or max(job.question_count, job.material_count) > 200:
                    raise ValueError('PDF 任务累计图片、题目或材料超过预算')
                persist_assets(session, root, workspace_id, result)
                session.add(PdfChunk(job_id=job.id, first_page=first, last_page=last, result=result))
                job.next_page = last + 1
                job.status = 'parsed' if last == job.last_page else 'ready'
                return details(job)
        except Exception as error:
            with write_transaction(engine) as session:
                job = session.get(PdfChunkJob, job_id)
                if job and job.generation == generation and job.status == 'running':
                    job.status = 'failed'
            if isinstance(error, HTTPException):
                raise
            raise HTTPException(422, '分块解析失败或累计预算超限，已提交进度和原件保留') from error

    @router.post('/{job_id}/preview')
    def preview(workspace_id: str, job_id: str):
        with write_transaction(engine) as session:
            job = scoped_job(session, workspace_id, job_id)
            if job.status != 'parsed' or job.parser_version != VERSION:
                raise HTTPException(409, '需要先完成当前版本的全部所选页')
            read_pdf_source(session, root, workspace_id, job.resource_id, job.source_sha256)
            original = session.get(Resource, job.resource_id)
            batch = session.get(ImportJob, job.id)
            if batch is None:
                title = f'{original.original_name}（第 {job.first_page} 至 {job.last_page} 页）'
                batch = ImportJob(id=job.id, workspace_id=workspace_id, resource_id=original.id,
                                  parser_version=job.parser_version, status='preview', error=None,
                                  preview=assemble(session, job, title),
                                  created_at=datetime.now(timezone.utc).isoformat())
                session.add(batch)
            elif (batch.workspace_id, batch.resource_id, batch.parser_version) != (
                    workspace_id, job.resource_id, job.parser_version):
                raise HTTPException(409, '候选批次与分块任务的来源不符')
            return describe(batch, original, preview=True)

    @router.get('/{job_id}/chunks/{first_page}')
    def chunk(workspace_id: str, job_id: str, first_page: int):
        with Session(engine) as session:
            job = scoped_job(session, workspace_id, job_id)
            piece = session.get(PdfChunk, (job.id, first_page))
            if piece is None:
                raise HTTPException(404, '所选区块尚未提交')
            return piece.result

    return router
