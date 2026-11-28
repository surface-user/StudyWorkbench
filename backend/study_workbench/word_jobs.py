"""Durable and cancellable range jobs for a managed Word source."""
import base64
import json
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query
from pydantic import Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import ImportJob, Resource, write_transaction
from .document_files import WordRange, limited_view, raster
from .documents import parse_word_range
from .imports import describe, persist_assets, read_word_source
from .question_splitting import split_blocks
from .word_outline import (
    WORD_BATCH_VERSION,
    WORD_JOB_PREFIX,
    WORD_JOB_VERSION,
    WORD_JOB_VERSIONS,
    word_job_id,
)
from .workspaces import require_workspace


class CreateWordRange(WordRange):
    node_id: str = Field(min_length=1, max_length=128)


def scoped_job(session, workspace, job_id):
    require_workspace(session, workspace)
    job = session.get(ImportJob, job_id)
    if job is None or job.workspace_id != workspace or not job.parser_version.startswith(WORD_JOB_PREFIX):
        raise HTTPException(404, 'Word 选区任务不存在')
    if (job.parser_version in WORD_JOB_VERSIONS
            and word_job_id(workspace, job.resource_id, job.preview['word_range'], job.parser_version) != job.id):
        raise HTTPException(409, 'Word 选区绑定信息已变化')
    return job


def details(job, state=None):
    state = job.preview['word_range'] if state is None else state
    count = state['last_position'] - state['first_position'] + 1
    result = dict(id=job.id, resource_id=job.resource_id, workspace_id=job.workspace_id, parser_version=job.parser_version,
                  status=job.status, error=job.error, **state)
    result.setdefault('completed_positions', count if job.status in {'preview', 'confirmed'} else 0)
    return result


def check_source(session, root, job):
    state = job.preview['word_range']
    return read_word_source(session, root, job.workspace_id, state['node_id'], state['source_sha256'], job.resource_id)[1]


def invalidate(job, status):
    state = dict(job.preview['word_range'])
    state['generation'] += 1
    job.preview = {**job.preview, 'word_range': state}
    job.status = status
    return state['generation']


def checked_preview(result, state):
    if (not result.get('available') or result.get('parser_version') != 'docx-body-candidates-v1'
            or any(result.get(k) != state[k] for k in ('first_position', 'last_position', 'total_positions'))):
        raise ValueError('Word 选区未能生成与原件位置一致的预览')
    positions, drafts, blocks = result['block_positions'], result['question_drafts'], result['blocks']
    if (len(positions) != len(blocks) or len(blocks) > 200 or len(drafts) > 200
            or any(type(p) is not int or not state['first_position'] <= p <= state['last_position'] for p in positions)):
        raise ValueError('Word 选区候选或位置超限')
    for key in ('table_positions', 'uncertain_positions'):
        if any(type(p) is not int or not state['first_position'] <= p <= state['last_position'] for p in result[key]):
            raise ValueError('Word 选区表格或不确定编号位置超限')
    allowed_positions = set(positions)
    for draft in drafts:
        for portion in (draft, *draft.get('shared_materials', [])):
            indexes = portion.get('block_positions', [])
            if (len(indexes) != len(portion['blocks']) or not set(indexes) <= allowed_positions
                    or portion.get('source_positions', []) != sorted(set(indexes))):
                raise ValueError('Word 选区候选片段与原件位置不一致')
    result['_assets'] = result.pop('assets')
    asset_bytes = sum(len(base64.b64decode(asset['data'], validate=True)) for asset in result['_assets'])
    if asset_bytes > 64 * 1024 * 1024:
        raise ValueError('Word 选区图片超限')
    check_metadata_size({k: v for k, v in result.items() if k != '_assets'})
    return {**result, 'kind': 'note', 'word_range': state}, asset_bytes


def check_metadata_size(metadata):
    size = 0
    for part in json.JSONEncoder(ensure_ascii=False).iterencode(metadata):
        size += len(part.encode('utf8'))
        if size > 8 * 1024 * 1024:
            raise ValueError('Word 候选预览超过 8 MiB')


def accumulate(previous, output, state, first, last):
    if output.get('reason') == 'no_extractable_content' and output.get('available') is False:
        output = dict(output, available=True, blocks=[], block_positions=[], question_drafts=[], assets=[])
    checked, cost = checked_preview(output, dict(state, first_position=first, last_position=last))
    chunks = [*previous, {k: checked[k] for k in ('first_position', 'last_position', 'blocks', 'block_positions',
                                                   'table_positions', 'uncertain_positions')}]
    chunks[-1]['asset_bytes'] = cost
    state = {**state, 'completed_positions': last - state['first_position'] + 1, 'asset_bytes': state['asset_bytes'] + cost}
    if state['asset_bytes'] > 64 * 1024 * 1024 or sum(len(chunk['blocks']) for chunk in chunks) > 200:
        raise ValueError('Word 整个选区的图片或内容块超限')
    if last < state['last_position']:
        check_metadata_size(chunks)
        return dict(word_range=state, word_chunks=chunks, _assets=checked['_assets']), 'ready'
    content = {key: [item for chunk in chunks for item in chunk[key]] for key in (
        'blocks', 'block_positions', 'table_positions', 'uncertain_positions')}
    if not content['blocks']:
        raise ValueError('Word 选区没有可提取内容')
    warnings = []
    if state['first_position'] > 1:
        warnings.append('选区起点之前可能有题干或材料')
    if last < state['total_positions']:
        warnings.append('选区末尾可能截断题目或材料')
    if content['uncertain_positions']:
        warnings.append('选区存在无法可靠恢复的自动编号，请核对标记的位置。')
        drafts = []
    else:
        drafts = split_blocks(content['blocks'], warnings, positions=content['block_positions'],
                              table_positions=content['table_positions'])
        if not drafts:
            warnings.append('选区内没有识别到可靠题号，请核对原件。')
    result = {**content, **{k: state[k] for k in ('first_position', 'last_position', 'total_positions')},
              'kind': 'note', 'available': True, 'parser_version': checked['parser_version'],
              'question_drafts': drafts, 'warnings': warnings, 'word_range': state}
    check_metadata_size(result)
    return {**result, '_assets': checked['_assets']}, 'preview'


def word_job_router(engine, root):
    router = APIRouter(prefix='/api/workspaces/{workspace_id}/word-range-jobs')

    @router.post('')
    @limited_view
    def create(workspace_id: str, body: CreateWordRange):
        count = body.last_position - body.first_position + 1
        if not 1 <= count <= 100:
            raise HTTPException(422, '请选择 1 至 100 个连续正文位置')
        with Session(engine) as session:
            resource, data = read_word_source(session, root, workspace_id, body.node_id, body.expected_sha256)
        state = dict(node_id=body.node_id, source_sha256=body.expected_sha256, first_position=body.first_position,
                     last_position=body.last_position, generation=0, asset_bytes=0)
        version = WORD_JOB_VERSION if count <= 20 else WORD_BATCH_VERSION
        if version == WORD_BATCH_VERSION:
            state['completed_positions'] = 0
        identifier = word_job_id(workspace_id, resource, state, version)
        outline = raster(data, 'docx-outline', first_position=body.first_position)
        if not outline.get('available') or body.last_position > outline['total_positions']:
            raise HTTPException(422, 'Word 正文结构或所选区间无法定位')
        with write_transaction(engine) as session:
            read_word_source(session, root, workspace_id, body.node_id, body.expected_sha256, resource)
            job = session.get(ImportJob, identifier)
            if job is None:
                state['total_positions'] = outline['total_positions']
                job = ImportJob(id=identifier, resource_id=resource, workspace_id=workspace_id, parser_version=version,
                                status='ready', error=None, preview={'word_range': state},
                                created_at=datetime.now(timezone.utc).isoformat())
                session.add(job)
            else:
                job = scoped_job(session, workspace_id, identifier)
            return details(job)

    @router.get('')
    def history(workspace_id: str, offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100)):
        with Session(engine) as session:
            require_workspace(session, workspace_id)
            rows = select(ImportJob.id, ImportJob.workspace_id, ImportJob.resource_id, ImportJob.parser_version,
                          ImportJob.status, ImportJob.error, ImportJob.preview['word_range'].label('state')).where(
                              ImportJob.workspace_id == workspace_id, ImportJob.parser_version.startswith(WORD_JOB_PREFIX))
            return [details(row, row.state) for row in session.execute(
                rows.order_by(ImportJob.created_at.desc(), ImportJob.id).offset(offset).limit(limit))]

    @router.get('/{job_id}')
    def get(workspace_id: str, job_id: str):
        with Session(engine) as session:
            return details(scoped_job(session, workspace_id, job_id))

    @router.post('/{job_id}/cancel')
    def cancel(workspace_id: str, job_id: str):
        with write_transaction(engine) as session:
            job = scoped_job(session, workspace_id, job_id)
            if job.status not in {'cancelled', 'preview', 'confirmed'}:
                invalidate(job, 'cancelled')
            return details(job)

    @router.post('/{job_id}/resume')
    def resume(workspace_id: str, job_id: str):
        with write_transaction(engine) as session:
            job = scoped_job(session, workspace_id, job_id)
            if job.parser_version not in WORD_JOB_VERSIONS or job.status == 'running':
                raise HTTPException(409, 'Word 选区正在执行或解析器版本已变')
            if job.status != 'confirmed':
                check_source(session, root, job)
                if job.status != 'preview':
                    job.status, job.error = 'ready', None
            return details(job)

    @router.post('/{job_id}/advance')
    @limited_view
    def advance(workspace_id: str, job_id: str, expected_completed_positions: int | None = Query(None, ge=0, le=100)):
        with write_transaction(engine) as session:
            job = scoped_job(session, workspace_id, job_id)
            if job.parser_version not in WORD_JOB_VERSIONS:
                raise HTTPException(409, 'Word 选区解析器版本已变')
            batch = job.parser_version == WORD_BATCH_VERSION
            if batch:
                completed = job.preview['word_range']['completed_positions']
                if (expected_completed_positions is None or expected_completed_positions > completed
                        or expected_completed_positions < completed and expected_completed_positions % 20):
                    raise HTTPException(409, '请传入当前已完成的位置数')
                if expected_completed_positions < completed:
                    return details(job)
            if job.status in {'preview', 'confirmed'}:
                if job.status == 'preview':
                    check_source(session, root, job)
                return details(job)
            if job.status != 'ready':
                raise HTTPException(409, '请先恢复任务或刷新其状态')
            data = check_source(session, root, job)
            generation = invalidate(job, 'running')
            state = dict(job.preview['word_range'])
            first = state['first_position'] + state.get('completed_positions', 0)
            last = min(first + 19, state['last_position'])
            previous = job.preview.get('word_chunks', [])
        try:
            output = parse_word_range(data, first, last)
            if batch:
                result, status = accumulate(previous, output, state, first, last)
            else:
                result, asset_bytes = checked_preview(output, state)
                result['word_range'] = {**state, 'asset_bytes': asset_bytes}
                status = 'preview'
            with write_transaction(engine) as session:
                job = scoped_job(session, workspace_id, job_id)
                if job.status != 'running' or job.preview['word_range']['generation'] != generation:
                    raise HTTPException(409, '本次 Word 选区执行已失效')
                check_source(session, root, job)
                persist_assets(session, root, workspace_id, result)
                if status == 'preview':
                    result['title'] = session.get(Resource, job.resource_id).original_name
                job.preview, job.status, job.error = result, status, None
                return details(job)
        except Exception as error:
            with write_transaction(engine) as session:
                job = scoped_job(session, workspace_id, job_id)
                if job.status != 'running' or job.preview['word_range']['generation'] != generation:
                    raise HTTPException(409, '本次 Word 选区执行已失效') from error
                job.status, job.error = 'failed', 'Word 选区解析失败或原件已变化'
            if isinstance(error, HTTPException):
                raise
            raise HTTPException(422, 'Word 选区解析失败或超出预算，原件保留') from error

    @router.get('/{job_id}/preview')
    def preview(workspace_id: str, job_id: str):
        with Session(engine) as session:
            job = scoped_job(session, workspace_id, job_id)
            if job.status not in {'preview', 'confirmed'} or job.parser_version not in WORD_JOB_VERSIONS:
                raise HTTPException(409, 'Word 选区尚无当前版本的完整候选')
            if job.status != 'confirmed':
                check_source(session, root, job)
            return describe(job, session.get(Resource, job.resource_id), preview=True)

    return router
