"""Local-pair API values and publication using the existing persistent download queue."""
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import media_probe_runtime as runtime
from .db import MediaDownloadAttempt, MediaDownloadJob, MediaEntry, write_transaction
from .explorer import insert_node, normalized_name, parent_in
from .imports import resource_path
from .media_download_http import DownloadError
from .media_inputs import inspect_media_input, managed_media_path
from .media_sources import (
    INPUT_LIMIT,
    RECIPE,
    attempt_context,
    attempt_record,
    source_digest,
    source_snapshot,
    stored_attempt,
    stored_source,
)

PHASES = ('copying', 'probing', 'muxing', 'validating', 'publishing', 'ready')


class SelectedTrack(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    media_id: str = Field(min_length=1, max_length=100)
    expected_sha256: str = Field(pattern=r'^[a-f0-9]{64}$')
    stream_index: int = Field(ge=0, le=1)


class CreateLocalPair(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    video: SelectedTrack
    audio: SelectedTrack
    name: str = Field(min_length=1, max_length=200)
    parent_id: str | None = None
    request_id: str = Field(pattern=r'^[A-Za-z0-9_-]{16,100}$')
    rights_confirmed: bool

    @field_validator('name')
    @classmethod
    def filename(cls, value):
        value = normalized_name(value)
        if Path(value).suffix.lower() != '.mp4':
            raise ValueError('合流副本的文件名须为MP4')
        return value

    @field_validator('rights_confirmed')
    @classmethod
    def consent(cls, value):
        if value is not True:
            raise ValueError('请确认有权使用所选媒体并保存副本')
        return value


def job_fields(job):
    return {key: getattr(job, key) for key in ('id', 'workspace_id', 'attempt', 'run_generation', 'source_kind',
        'source_url', 'source_snapshot', 'source_snapshot_sha256', 'relative_path', 'status')}


def inputs_in(session, workspace, source):
    if source.kind == 'site_pair':
        return []
    paths = []
    for track in source.tracks:
        item = session.get(MediaEntry, track.media_id)
        if (item is None or item.workspace_id != workspace or item.status != 'ready' or
                (item.sha256, item.size, item.mime) != (track.sha256, track.size, track.mime)):
            raise HTTPException(409, '所选媒体已改变或不属于此空间，请重新选择；旧执行保留')
        paths.append(managed_media_path(workspace, item.id, item.relative_path))
    return paths


def source_for_request(session, workspace, body):
    tracks = []
    for role, selected in [('video', body.video), ('audio', body.audio)]:
        item = session.get(MediaEntry, selected.media_id)
        if item is None or item.workspace_id != workspace:
            raise HTTPException(404, '所选媒体不存在')
        if item.status != 'ready' or item.sha256 != selected.expected_sha256 or item.mime not in ('video/mp4', 'audio/mp4'):
            raise HTTPException(409, '媒体状态、摘要或格式不符，请刷新后重新选择')
        managed_media_path(workspace, item.id, item.relative_path)
        tracks.append(dict(media_id=item.id, sha256=item.sha256, size=item.size, mime=item.mime,
                           role=role, stream_index=selected.stream_index))
    try:
        return source_snapshot(dict(schema_version=1, kind='local_pair', recipe_version=RECIPE,
                                    component_snapshot_sha256=runtime.SNAPSHOT, tracks=tracks))
    except (ValueError, TypeError) as error:
        raise HTTPException(422, '请选择不同的视频与音频轨道，合计最多512MiB') from error


def same_request(job, body):
    source = stored_source(job_fields(job))
    return (job.name, job.parent_id, [(t.media_id, t.sha256, t.stream_index) for t in source.tracks]) == (
        body.name, body.parent_id, [(s.media_id, s.expected_sha256, s.stream_index) for s in (body.video, body.audio)])


def checkpoint(downloads, identifier, deadline):
    downloads.check(identifier)
    if time.monotonic() >= deadline:
        raise DownloadError('合流超过15分钟；原件及已生成字节保留')


def worker_options(downloads, job, deadline, *, acquired=None):
    def check():
        checkpoint(downloads, job.id, deadline)
    source = stored_source(job_fields(job))
    try:
        component = runtime.verify_component(runtime.component_directory(), check)
    except (ValueError, OSError, KeyError, TypeError) as error:
        raise DownloadError('本机尚未准备已核验的媒体处理组件，原件与记录保留') from error
    with Session(downloads.engine) as session:
        paths = inputs_in(session, job.workspace_id, source)
    remaining = int((deadline - time.monotonic()) * 1000)
    if not 1 <= remaining <= 900000:
        raise DownloadError('合流超过资源或时间预算，原件与记录保留')
    options = dict(root=str(downloads.root.resolve()), workspace=job.workspace_id, job=job.id,
                attempt=job.attempt, generation=job.run_generation, snapshot=source.model_dump(mode='json'),
                inputs=paths, runtime=str(component), remaining_ms=remaining)
    if acquired is not None:
        options['record'] = acquired.model_dump(mode='json')
    return options


def progress(downloads, job, value):
    if not isinstance(value, dict) or set(value) != {'phase', 'received', 'total', 'record'}:
        raise DownloadError('合流工作进度无效')
    source = stored_source(job_fields(job))
    record = attempt_record(value['record'])
    attempt_context(job.workspace_id, job.id, job.attempt, job.run_generation, source, record)
    total = source.input_size
    if source.kind == 'site_pair' and value['phase'] != 'copying':
        if not all(t.received for t in record.tracks):
            raise DownloadError('尚未完整取得所选两条轨道')
        total = sum(t.received.size for t in record.tracks)
    if (value['phase'] not in PHASES[:4] or type(value['received']) is not int or
            value['total'] != total or value['total'] is not None and type(value['total']) is not int
            or not 0 <= value['received'] <= (total if total is not None else INPUT_LIMIT)):
        raise DownloadError('合流工作预算或阶段无效')
    if record.output is not None:
        raise DownloadError('合流工作进度不能提前发布结果')
    with write_transaction(downloads.engine) as session:
        current = session.get(MediaDownloadJob, job.id)
        receipt = session.get(MediaDownloadAttempt, (job.id, job.run_generation))
        if (current.status != 'running' or current.cancel_requested or downloads.stopping.is_set() or
                current.run_generation != job.run_generation or current.attempt != job.attempt or
                receipt is None or receipt.status != 'running' or
                value['received'] < current.progress.get('received', 0) or
                PHASES.index(value['phase']) < PHASES.index(receipt.phase)):
            raise DownloadError('合流已暂停或此结果已过期，已存部分保留')
        receipt.record, receipt.phase = record.model_dump(mode='json'), value['phase']
        current.progress = {'received': value['received'], 'total': total, 'phase': value['phase']}


def run_local(downloads, identifier, child, transfer=None):
    claim = {}
    try:
        _run_local(downloads, identifier, child, claim, transfer)
    except Exception as error:
        with write_transaction(downloads.engine) as session:
            current = session.get(MediaDownloadJob, identifier)
            if current is None or current.status == 'ready':
                return
            owned = claim.get('execution')
            if owned is not None and (current.attempt, current.run_generation) != owned:
                return
            if owned is None and current.status not in {'queued', 'paused'}:
                return
            current.status = 'interrupted' if downloads.stopping.is_set() else 'paused' if current.cancel_requested else 'failed'
            current.error = (str(error) if isinstance(error, DownloadError) else str(error.detail) if isinstance(error, HTTPException)
                             else '合流或入库未完成，原件及已生成字节保留')
            if owned is not None:
                receipt = session.get(MediaDownloadAttempt, (identifier, owned[1]))
                if receipt is not None and receipt.status != 'ready':
                    receipt.status = current.status


def _run_local(downloads, identifier, child, claim, transfer):
    deadline = transfer.deadline if transfer else time.monotonic() + 900
    def check():
        checkpoint(downloads, identifier, deadline)
    check()
    with write_transaction(downloads.engine) as session:
        job = session.get(MediaDownloadJob, identifier)
        if job.status != 'queued' or job.source_kind not in ('local_pair', 'site_pair'):
            return
        if (job.source_kind == 'site_pair') != bool(transfer) or transfer and time.monotonic() >= transfer.expires:
            raise DownloadError('所选站点轨道已失效，请重新预览')
        source = stored_source(job_fields(job))
        inputs_in(session, job.workspace_id, source)
        job.run_generation += 1
        job.status = 'running'
        total = source.input_size
        job.progress = {'received': 0, 'total': total, 'phase': 'copying'}
        directory = f'workspaces/{job.workspace_id}/downloads/{job.id}/{job.attempt}/{job.run_generation}'
        record = attempt_record(dict(schema_version=1, source_snapshot_sha256=source_digest(source), tracks=[
            dict(ordinal=i, state='pending', relative_path=f"{directory}/input{i}" +
                 ('.m4a' if track.mime == 'audio/mp4' else '.mp4'), metadata=None)
            for i, track in enumerate(source.tracks)], output=None))
        session.add(MediaDownloadAttempt(job_id=job.id, workspace_id=job.workspace_id, generation=job.run_generation,
            attempt=job.attempt, source_snapshot_sha256=source_digest(source), status='running', phase='copying',
            record=record.model_dump(mode='json'), created_at=datetime.now(timezone.utc).isoformat()))
        session.flush()
        session.expunge(job)
    claim['execution'] = job.attempt, job.run_generation
    runtime.local_path(downloads.root.resolve())
    operation = resource_path(downloads.root, directory)
    operation.mkdir(parents=True, exist_ok=False)
    runtime.local_path(operation)
    (operation / 'tmp').mkdir()
    if source.kind == 'site_pair':
        fetched = attempt_record(child(job, operation, deadline=deadline, transfer=transfer, acquired=record))
        attempt_context(job.workspace_id, job.id, job.attempt, job.run_generation, source, fetched)
        if fetched.output is not None or any(track.state != 'copied' for track in fetched.tracks):
            raise DownloadError('轨道传输记录不完整')
        for track, selection in zip(fetched.tracks, source.tracks, strict=True):
            inspect_media_input(downloads.root, track.relative_path, track.received.size, track.received.sha256, selection.mime, check)
        total = sum(t.received.size for t in fetched.tracks)
        result = child(job, operation, deadline=deadline, acquired=fetched)
    else:
        result = child(job, operation, deadline=deadline)
    record = attempt_record(result)
    if source.kind == 'site_pair' and [t.received for t in record.tracks] != [t.received for t in fetched.tracks]:
        raise DownloadError('合成结果与已取得的轨道身份不符')
    if record.output is None or record.output.state != 'prepared':
        raise DownloadError('合流工作结果缺少已校验输出')
    attempt_context(job.workspace_id, job.id, job.attempt, job.run_generation, source, record)
    for selected, frozen in zip(source.tracks, record.tracks, strict=True):
        content = frozen.received or selected
        inspect_media_input(downloads.root, frozen.relative_path, content.size, content.sha256, selected.mime, check)
    with Session(downloads.engine) as session:
        paths = inputs_in(session, job.workspace_id, source)
    for selected, relative in zip(source.tracks if source.kind == 'local_pair' else (), paths, strict=True):
        inspect_media_input(downloads.root, relative, selected.size, selected.sha256, selected.mime, check)
    output = record.output
    inspect_media_input(downloads.root, output.pending_path, output.size, output.sha256, 'video/mp4', check)
    with write_transaction(downloads.engine) as session:
        current = session.get(MediaDownloadJob, identifier)
        receipt = session.get(MediaDownloadAttempt, (identifier, job.run_generation))
        check_current(downloads, current, job, receipt)
        stored_attempt(job_fields(current), dict(job_id=identifier, workspace_id=job.workspace_id, attempt=job.attempt,
            generation=job.run_generation, source_snapshot_sha256=source_digest(source), status='running',
            phase='publishing', record=record.model_dump(mode='json')), source)
        receipt.record, receipt.phase = record.model_dump(mode='json'), 'publishing'
        current.progress = {'received': total, 'total': total, 'phase': 'publishing'}
    check()
    pending, final = resource_path(downloads.root, output.pending_path), resource_path(downloads.root, output.final_path)
    publish_output(pending, final)
    inspect_media_input(downloads.root, output.final_path, output.size, output.sha256, 'video/mp4', check)
    with write_transaction(downloads.engine) as session:
        current = session.get(MediaDownloadJob, identifier)
        receipt = session.get(MediaDownloadAttempt, (identifier, job.run_generation))
        check_current(downloads, current, job, receipt)
        parent_in(session, job.workspace_id, job.parent_id)
        inputs_in(session, job.workspace_id, source)
        existing = session.scalar(select(MediaEntry).where(MediaEntry.workspace_id == job.workspace_id,
            MediaEntry.status == 'ready', MediaEntry.sha256 == output.sha256, MediaEntry.size == output.size,
            MediaEntry.mime == 'video/mp4'))
        if existing is not None:
            managed_media_path(job.workspace_id, existing.id, existing.relative_path)
            inspect_media_input(downloads.root, existing.relative_path, output.size, output.sha256, 'video/mp4', check)
            media = existing
        else:
            media = MediaEntry(id=uuid4().hex, workspace_id=job.workspace_id, title=job.name,
                relative_path=output.final_path, mime='video/mp4', size=output.size, sha256=output.sha256,
                status='ready', playback={})
            session.add(media)
            session.flush()
        node = insert_node(session, job.workspace_id, job.parent_id, job.name, 'media', media_id=media.id)
        record.output.state = 'committed'
        receipt.record, receipt.status, receipt.phase = record.model_dump(mode='json'), 'ready', 'ready'
        current.status, current.error = 'ready', None
        current.progress = {'received': total, 'total': total, 'phase': 'ready'}
        current.result = {'media_id': media.id, 'resource_item_id': node.id, 'deduplicated': existing is not None,
                          'mux_version': RECIPE, 'native_mux_performed': True,
                          'output': {'size': output.size, 'sha256': output.sha256, 'metadata': output.metadata.model_dump()}}


def publish_output(pending, final):
    runtime.local_path(pending)
    runtime.local_path(final.parent)
    if os.name != 'nt' or final.exists() or final.is_symlink():
        raise DownloadError('目标已存在或此系统尚不支持受控发布，旧文件保留')
    os.rename(pending, final)  # Windows refuses replacement; the SQL commit remains a separate boundary.


def check_current(downloads, current, job, receipt):
    if (current is None or current.status != 'running' or current.cancel_requested or downloads.stopping.is_set() or
            (current.attempt, current.run_generation) != (job.attempt, job.run_generation) or
            receipt is None or receipt.status != 'running'):
        raise DownloadError('合流已暂停或执行已过期，旧文件与记录保留')
