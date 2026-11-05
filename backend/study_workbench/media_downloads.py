"""Scoped persistent downloads. Network work is disposable; publication is a local transaction."""
import hashlib
import json
import os
import queue
import re
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from threading import Event, Thread
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .db import MediaDownloadJob, MediaEntry, write_transaction
from .explorer import insert_node, normalized_name, parent_in
from .imports import resource_path
from .media_download_http import LIMIT, DownloadError, parse_url, strong_etag
from .media_library import media_mime
from .workspaces import require_workspace

JOB_SECONDS = 900
STOP_SECONDS = 2


class CreateDownload(BaseModel):
    model_config = ConfigDict(extra='forbid')
    url: str = Field(min_length=1, max_length=8192)
    name: str = Field(min_length=1, max_length=200)
    parent_id: str | None = None
    request_id: str = Field(pattern=r'^[A-Za-z0-9_-]{16,100}$')
    rights_confirmed: bool = Field(strict=True)

    @field_validator('url')
    @classmethod
    def url_value(cls, value):
        return parse_url(value)[0]

    @field_validator('name')
    @classmethod
    def media_name(cls, value):
        value = normalized_name(value)
        if Path(value).suffix.lower() not in {'.mp4', '.webm', '.m4a'}:
            raise ValueError('文件名须为MP4/WebM/M4A')
        return value

    @field_validator('rights_confirmed')
    @classmethod
    def consent(cls, value):
        if value is not True:
            raise ValueError('请确认有权下载此文件')
        return value


class RetryDownload(BaseModel):
    model_config = ConfigDict(extra='forbid')
    mode: str = Field(pattern='^(resume|restart)$')


def describe(job):
    received = job.progress.get('received', 0)
    resumable = (0 < received < LIMIT or received == LIMIT == job.progress.get('total'))
    return dict(id=job.id, name=job.name, source_host=parse_url(job.source_url)[1], parent_id=job.parent_id,
                status=job.status, attempt=job.attempt, progress={k: job.progress.get(k) for k in ('received', 'total')},
                can_resume=job.status in {'paused', 'interrupted', 'failed'} and strong_etag(job.progress.get('etag')) and resumable,
                result=job.result, error=job.error, created_at=job.created_at)


class MediaDownloads:
    def __init__(self, engine, root):
        self.engine, self.root = engine, root
        self.stopping = Event()
        self.pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix='media-download')
        with write_transaction(engine) as session:
            for job in session.scalars(select(MediaDownloadJob).where(MediaDownloadJob.status.in_(['queued', 'running']))):
                job.status, job.error = 'interrupted', '上次下载被中断；请显式选择断点恢复或保留旧部分重新开始'

    def close(self):
        self.stopping.set()
        self.pool.shutdown(wait=True, cancel_futures=True)

    def check(self, identifier):
        if self.stopping.is_set():
            raise DownloadError('后端正在关闭，下载部分保留')
        with Session(self.engine) as session:
            job = session.get(MediaDownloadJob, identifier)
            parent_in(session, job.workspace_id, job.parent_id)
            if job.cancel_requested:
                raise DownloadError('下载已暂停，已存部分保留')

    def progress(self, identifier, value):
        received, total = value.get('received'), value.get('total')
        if (type(received) is not int or not 0 <= received <= LIMIT
                or total is not None and (type(total) is not int or not received <= total <= LIMIT)
                or not re.fullmatch('[a-f0-9]{64}', value.get('partial_sha256', ''))
                or value.get('etag') is not None and not strong_etag(value['etag'])):
            raise DownloadError('下载工作进度无效，已存部分保留')
        if shutil.disk_usage(self.root).free < (total - received if total else LIMIT - received) + 16 * 1024 * 1024:
            raise DownloadError('下载空间不足，已存部分保留')
        with write_transaction(self.engine) as session:
            session.get(MediaDownloadJob, identifier).progress = value

    def child(self, job, path):
        command = [sys.executable]
        if not getattr(sys, 'frozen', False):
            command += ['-m', 'study_workbench']
        process = subprocess.Popen(command + ['--download-media'], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
            env={**os.environ, 'PYTHONUTF8': '1', 'PYTHONIOENCODING': 'utf-8',
                 'PYTHONPATH': str(Path(__file__).resolve().parents[1])})
        messages, finished = queue.Queue(maxsize=16), Event()
        def read():
            try:
                while not finished.is_set():
                    line = process.stdout.readline(16385)
                    if not line:
                        break
                    value = json.loads(line) if len(line) <= 16384 else {'error': '下载工作响应超限'}
                    while not finished.is_set():
                        try:
                            messages.put(value, timeout=.2)
                            break
                        except queue.Full:
                            pass
            except Exception:
                pass
        reader = Thread(target=read, daemon=True)
        reader.start()
        result = None
        try:
            options = dict(url=job.source_url, path=str(path), suffix=Path(job.name).suffix.lower(),
                           offset=job.progress.get('received', 0), etag=job.progress.get('etag'),
                           partial_sha256=job.progress.get('partial_sha256'))
            process.stdin.write(json.dumps(options).encode('utf-8') + b'\n')
            process.stdin.flush()
            deadline = time.monotonic() + JOB_SECONDS
            while True:
                self.check(job.id)
                if time.monotonic() > deadline:
                    raise DownloadError('下载超过15分钟，已存部分保留')
                try:
                    message = messages.get(timeout=.2)
                except queue.Empty:
                    if process.poll() is not None and not reader.is_alive():
                        raise DownloadError('下载工作进程提前结束，已存部分保留')
                    continue
                if 'progress' in message:
                    self.progress(job.id, message['progress'])
                elif 'result' in message:
                    result = message['result']
                    break
                else:
                    # Remote text is never reflected; only the trusted fixed worker's bounded error is accepted.
                    raise DownloadError(str(message.get('error', '下载未完成'))[:300])
        finally:
            finished.set()
            process.stdin.close()
            try:
                process.wait(timeout=STOP_SECONDS)
            except subprocess.TimeoutExpired:
                process.kill()  # Only this job's own disposable child, including blocked DNS.
                process.wait(timeout=5)
            process.stdout.close()
            reader.join(timeout=1)
        if process.returncode or result is None:
            raise DownloadError('下载工作进程异常，已存部分保留')
        return result

    def run(self, identifier):
        try:
            self.check(identifier)
            with write_transaction(self.engine) as session:
                job = session.get(MediaDownloadJob, identifier)
                if job.status != 'queued':
                    return
                job.status = 'running'
                session.flush()
                session.expunge(job)
            path = resource_path(self.root, job.relative_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            if shutil.disk_usage(self.root).free < 16 * 1024 * 1024:
                raise DownloadError('下载需要足够的可用空间，已存部分保留')
            received = job.progress.get('received', 0)
            if received > 0 and received == job.progress.get('total'):
                result = dict(size=received, sha256=job.progress.get('partial_sha256'), etag=job.progress.get('etag'))
            else:
                result = self.child(job, path)
            self.check(identifier)
            size = path.stat().st_size
            def checked_hash(filename, expected):
                digest, count = hashlib.sha256(), 0
                with filename.open('rb') as source:
                    while chunk := source.read(1024 * 1024):
                        self.check(identifier)
                        count += len(chunk)
                        if count > expected or count > LIMIT:
                            raise DownloadError('媒体实际大小变化，文件保留')
                        digest.update(chunk)
                if count != expected:
                    raise DownloadError('媒体实际大小变化，文件保留')
                return digest.hexdigest()
            with path.open('rb') as source:
                header = source.read(32)
            checksum = checked_hash(path, result['size'])
            mime = media_mime(Path(job.name).suffix.lower(), header, size)
            if checksum != result['sha256'] or size != result['size']:
                raise DownloadError('下载文件在入库前变化，已存部分保留')
            with write_transaction(self.engine) as session:
                item = session.get(MediaDownloadJob, identifier)
                if item.cancel_requested or self.stopping.is_set():
                    raise DownloadError('下载已暂停，已存部分保留')
                parent_in(session, job.workspace_id, job.parent_id)
                existing = session.scalar(select(MediaEntry).where(MediaEntry.workspace_id == job.workspace_id,
                    MediaEntry.status == 'ready', MediaEntry.sha256 == checksum, MediaEntry.size == size))
                if existing:
                    if checked_hash(resource_path(self.root, existing.relative_path), size) != checksum:
                        raise DownloadError('相同媒体的旧文件变化，新下载与旧记录均保留')
                    media = existing
                else:
                    media = MediaEntry(id=uuid4().hex, workspace_id=job.workspace_id, title=job.name,
                        relative_path=job.relative_path, mime=mime, size=size, sha256=checksum, status='ready', playback={})
                    session.add(media)
                    session.flush()
                node = insert_node(session, job.workspace_id, job.parent_id, job.name, 'media', media_id=media.id)
                item.status, item.error = 'ready', None
                item.progress = {'received': size, 'total': size, 'etag': result.get('etag'), 'partial_sha256': checksum}
                item.result = {'resource_item_id': node.id, 'media_id': media.id, 'deduplicated': existing is not None}
        except Exception as error:
            with write_transaction(self.engine) as session:
                job = session.get(MediaDownloadJob, identifier)
                if job is not None and job.status != 'ready':
                    job.status = 'interrupted' if self.stopping.is_set() else 'paused' if job.cancel_requested else 'failed'
                    job.error = str(error) if isinstance(error, DownloadError) else '下载或入库未完成，文件保留；请检查目标目录、网络和磁盘'

    def router(self):
        router = APIRouter(prefix='/api/workspaces/{workspace_id}/media-downloads')
        def job_in(session, workspace, identifier):
            require_workspace(session, workspace)
            job = session.get(MediaDownloadJob, identifier)
            if job is None or job.workspace_id != workspace:
                raise HTTPException(404, '下载任务不存在')
            return job
        def capacity(session):
            if session.scalar(select(func.count()).select_from(MediaDownloadJob).where(MediaDownloadJob.status.in_(['queued', 'running']))) >= 32:
                raise HTTPException(429, '已有32个待完成下载，请先暂停或等待')
        @router.post('')
        def create(workspace_id: str, body: CreateDownload):
            with write_transaction(self.engine) as session:
                parent_in(session, workspace_id, body.parent_id)
                old = session.scalar(select(MediaDownloadJob).where(MediaDownloadJob.workspace_id == workspace_id,
                    MediaDownloadJob.request_id == body.request_id))
                if old:
                    if (old.source_url, old.name, old.parent_id) != (body.url, body.name, body.parent_id):
                        raise HTTPException(409, '同一请求的下载参数变化')
                    return describe(old)
                capacity(session)
                identifier = uuid4().hex
                item = MediaDownloadJob(id=identifier, workspace_id=workspace_id, parent_id=body.parent_id,
                    request_id=body.request_id, source_url=body.url, name=body.name, status='queued', cancel_requested=False,
                    attempt=1, relative_path=f'workspaces/{workspace_id}/downloads/{identifier}/1{Path(body.name).suffix.lower()}',
                    progress={'received': 0}, result={}, error=None, created_at=datetime.now(timezone.utc).isoformat())
                session.add(item)
                session.flush()
                result = describe(item)
            self.pool.submit(self.run, identifier)
            return result
        @router.get('')
        def listing(workspace_id: str, offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100)):
            with Session(self.engine) as session:
                require_workspace(session, workspace_id)
                return [describe(item) for item in session.scalars(select(MediaDownloadJob).where(
                    MediaDownloadJob.workspace_id == workspace_id).order_by(MediaDownloadJob.status.in_(['queued', 'running']).desc(),
                        MediaDownloadJob.created_at.desc(), MediaDownloadJob.id).offset(offset).limit(limit))]
        @router.get('/{identifier}')
        def get(workspace_id: str, identifier: str):
            with Session(self.engine) as session:
                return describe(job_in(session, workspace_id, identifier))
        @router.post('/{identifier}/pause')
        def pause(workspace_id: str, identifier: str):
            with write_transaction(self.engine) as session:
                job = job_in(session, workspace_id, identifier)
                if job.status == 'ready':
                    raise HTTPException(409, '下载已完成')
                job.cancel_requested = True
                if job.status != 'running':
                    job.status = 'paused'
                return describe(job)
        @router.post('/{identifier}/retry')
        def retry(workspace_id: str, identifier: str, body: RetryDownload):
            with write_transaction(self.engine) as session:
                job = job_in(session, workspace_id, identifier)
                if job.status in {'queued', 'running', 'ready'}:
                    raise HTTPException(409, '此任务当前不能重试')
                parent_in(session, workspace_id, job.parent_id)
                capacity(session)
                if body.mode == 'restart':
                    job.attempt += 1
                    job.relative_path = f'workspaces/{workspace_id}/downloads/{job.id}/{job.attempt}{Path(job.name).suffix.lower()}'
                    job.progress = {'received': 0}
                elif (not strong_etag(job.progress.get('etag')) or not job.progress.get('partial_sha256')
                      or not (0 < job.progress.get('received', 0) < LIMIT
                              or job.progress.get('received') == LIMIT == job.progress.get('total'))):
                    raise HTTPException(409, '没有可验证的断点，请选择保留旧部分重新开始')
                job.status, job.cancel_requested, job.error = 'queued', False, None
                result = describe(job)
            self.pool.submit(self.run, identifier)
            return result
        return router
