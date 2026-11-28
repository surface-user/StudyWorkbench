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

from .db import MediaDownloadAttempt, MediaDownloadJob, MediaEntry, write_transaction
from .explorer import insert_node, normalized_name, parent_in
from .imports import resource_path
from .media_download_http import LIMIT, DownloadError, parse_url, strong_etag
from .media_inputs import inspect_media_input
from .media_library import media_mime
from .workspaces import require_workspace

JOB_SECONDS = 900
STOP_SECONDS = 2


class DownloadTarget(BaseModel):
    model_config = ConfigDict(extra='forbid')
    name: str = Field(min_length=1, max_length=200)
    parent_id: str | None = None
    request_id: str = Field(pattern=r'^[A-Za-z0-9_-]{16,100}$')
    rights_confirmed: bool = Field(strict=True)

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


class CreateDownload(DownloadTarget):
    url: str = Field(min_length=1, max_length=8192)

    @field_validator('url')
    @classmethod
    def url_value(cls, value):
        return parse_url(value)[0]

class ConfirmSiteDownload(DownloadTarget):
    format_id: str = Field(pattern=r'^legacy-[0-9]{1,2}$')


class ConfirmSitePair(DownloadTarget):
    selection_sha256: str = Field(pattern=r'^[a-f0-9]{64}$')


class RetryDownload(BaseModel):
    model_config = ConfigDict(extra='forbid')
    mode: str = Field(pattern='^(resume|restart)$')


def describe(job):
    received = job.progress.get('received', 0)
    resumable = (0 < received < LIMIT or received == LIMIT == job.progress.get('total'))
    pair_host = {'local_pair': '本地所选媒体', 'site_pair': 'www.bilibili.com'}.get(job.source_kind)
    result = dict(id=job.id, name=job.name, source_kind='site_progressive' if job.site_receipt else job.source_kind,
                source_host=pair_host or parse_url(job.source_url)[1], parent_id=job.parent_id,
                status=job.status, attempt=job.attempt, progress={k: job.progress.get(k) for k in ('received', 'total')},
                can_resume=pair_host is None and not job.site_receipt and job.status in {'paused', 'interrupted', 'failed'} and strong_etag(job.progress.get('etag')) and resumable,
                result=job.result, error=job.error, created_at=job.created_at)
    if pair_host is not None:
        from .media_sources import source_digest, source_snapshot
        try:
            source = source_snapshot(job.source_snapshot)
            if source_digest(source) != job.source_snapshot_sha256:
                raise ValueError('Source digest differs')
            result['source_snapshot'] = source.model_dump(mode='json')
            result['source_snapshot_sha256'] = job.source_snapshot_sha256
            result['run_generation'] = job.run_generation
        except (ValueError, TypeError) as error:
            raise HTTPException(409, '本地媒体来源记录无效，原件与记录保留') from error
        result['progress']['phase'] = job.progress.get('phase')
    return result


class MediaDownloads:
    def __init__(self, engine, root):
        self.engine, self.root = engine, root
        self.stopping = Event()
        self.pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix='media-download')
        with write_transaction(engine) as session:
            for job in session.scalars(select(MediaDownloadJob).where(MediaDownloadJob.status.in_(['queued', 'running']))):
                job.status, job.error = 'interrupted', '上次下载被中断；请显式选择断点恢复或保留旧部分重新开始'
                if job.source_kind in ('local_pair', 'site_pair'):
                    attempt = session.get(MediaDownloadAttempt, (job.id, job.run_generation))
                    if attempt is not None and attempt.status == 'running':
                        attempt.status = 'interrupted'

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

    def child(self, job, path, *, deadline=None, transfer=None, acquired=None):
        from . import media_mux, media_probe_runtime
        paired = job.source_kind in ('local_pair', 'site_pair')
        fetching = job.source_kind == 'site_pair' and transfer is not None
        local = paired and not fetching
        deadline = deadline if deadline is not None else time.monotonic() + JOB_SECONDS
        if paired:
            options = media_mux.worker_options(self, job, deadline, acquired=acquired)
            if fetching:
                options.update(mode='site_pair', urls=list(transfer.url), deadline=deadline,
                               site_budget=vars(transfer.budget))
                options.pop('runtime')
                options.pop('inputs')
        else:
            options = dict(url=transfer.url if transfer else job.source_url, path=str(path), suffix=Path(job.name).suffix.lower(),
                           offset=job.progress.get('received', 0), etag=job.progress.get('etag'),
                           partial_sha256=job.progress.get('partial_sha256'))
        if job.site_receipt:
            options['site_host'] = job.site_receipt['cdn_host']
            options['expected_size'] = job.site_receipt['size']
            options['site_budget'] = {'requests_left': transfer.budget.requests_left, 'bytes_left': transfer.budget.bytes_left}
            options['deadline'] = transfer.deadline
        environment = (media_probe_runtime.environment(path) if paired else dict(os.environ))
        environment.update(PYTHONUTF8='1', PYTHONIOENCODING='utf-8',
                           PYTHONPATH=str(Path(__file__).resolve().parents[1]))
        command = [sys.executable]
        if not getattr(sys, 'frozen', False):
            command += ['-m', 'study_workbench']
        process = subprocess.Popen(command + ['--mux-media' if local else '--download-media'], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
            cwd=path if paired else None, env=environment)
        messages, finished = queue.Queue(maxsize=16), Event()
        def read():
            try:
                while not finished.is_set():
                    line = process.stdout.readline(16385)
                    if not line:
                        break
                    value = (media_probe_runtime.strict_json(line, 16384) if local else json.loads(line)) if len(line) <= 16384 else {'error': '下载工作响应超限'}
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
            process.stdin.write(json.dumps(options).encode('utf-8') + b'\n')
            process.stdin.flush()
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
                if paired and (not isinstance(message, dict) or len(message) != 1):
                    raise DownloadError('合流工作响应无效，文件保留')
                if 'progress' in message:
                    if paired:
                        media_mux.progress(self, job, message['progress'])
                    else:
                        self.progress(job.id, message['progress'])
                elif 'result' in message:
                    result = message['result']
                    break
                else:
                    if local:
                        raise DownloadError({'cancelled': '合流已暂停，已存部分保留', 'budget': '合流超过资源或时间预算，已存部分保留'}
                                            .get(message.get('error_code'), '此媒体无法完成受控合流，原件及已生成字节保留'))
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

    def run(self, identifier, transfer=None):
        def check():
            if transfer and time.monotonic() >= transfer.deadline:
                raise DownloadError('站点确认与传输超过共用时限，已存文件保留')
            self.check(identifier)

        try:
            with Session(self.engine) as session:
                current = session.get(MediaDownloadJob, identifier)
                paired = current is not None and current.source_kind in ('local_pair', 'site_pair')
            if paired:
                from .media_mux import run_local
                run_local(self, identifier, self.child, transfer)
                return
            check()
            with write_transaction(self.engine) as session:
                job = session.get(MediaDownloadJob, identifier)
                if job.status != 'queued':
                    return
                if job.source_kind != 'direct_https':
                    raise DownloadError('下载任务来源类型无效，现有文件保留')
                if bool(job.site_receipt) != bool(transfer) or transfer and time.monotonic() >= transfer.expires:
                    raise DownloadError('站点媒体地址已失效，请重新预览并确认')
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
                result = (self.child(job, path, deadline=transfer.deadline, transfer=transfer)
                          if transfer else self.child(job, path))
            check()
            size = path.stat().st_size
            def checked_hash(filename, expected):
                digest, count = hashlib.sha256(), 0
                with filename.open('rb') as source:
                    while chunk := source.read(1024 * 1024):
                        check()
                        count += len(chunk)
                        if count > expected or count > LIMIT:
                            raise DownloadError('媒体实际大小变化，文件保留')
                        digest.update(chunk)
                if count != expected:
                    raise DownloadError('媒体实际大小变化，文件保留')
                return digest.hexdigest()
            with path.open('rb') as source:
                header = source.read(32)
            if job.site_receipt and size != job.site_receipt['size']:
                raise DownloadError('实际媒体大小与已确认格式不符，请重新预览')
            checksum = checked_hash(path, result['size'])
            mime = media_mime(Path(job.name).suffix.lower(), header, size)
            if checksum != result['sha256'] or size != result['size']:
                raise DownloadError('下载文件在入库前变化，已存部分保留')
            if job.site_receipt:
                next_check = 0.0
                def inspect_check():
                    nonlocal next_check
                    if time.monotonic() >= next_check:
                        check()
                        next_check = time.monotonic() + .05
                try:
                    inspection = inspect_media_input(self.root, job.relative_path, size, checksum, mime, inspect_check)
                except HTTPException:
                    raise DownloadError('实际媒体不符合受支持的完整MP4结构，文件保留') from None
                if {stream['role'] for stream in inspection['streams']} != {'video', 'audio'}:
                    raise DownloadError('实际媒体缺少完整音视频轨道，文件保留')
            with write_transaction(self.engine) as session:
                item = session.get(MediaDownloadJob, identifier)
                if transfer and time.monotonic() >= transfer.deadline:
                    raise DownloadError('站点确认与发布超过共用时限，已存文件保留')
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
                if job is not None and job.source_kind == 'local_pair':
                    return  # Local terminal handling checks its exact claimed generation; never overwrite a newer run.
                if job is not None and job.status != 'ready':
                    job.status = 'interrupted' if self.stopping.is_set() else 'paused' if job.cancel_requested else 'failed'
                    job.error = str(error) if isinstance(error, DownloadError) else '下载或入库未完成，文件保留；请检查目标目录、网络和磁盘'

    @staticmethod
    def capacity(session):
        if session.scalar(select(func.count()).select_from(MediaDownloadJob).where(MediaDownloadJob.status.in_(['queued', 'running']))) >= 32:
            raise HTTPException(429, '已有32个待完成下载，请先暂停或等待')

    def site_retry(self, workspace, preview, body):
        with Session(self.engine) as session:
            require_workspace(session, workspace)
            old = session.scalar(select(MediaDownloadJob).where(MediaDownloadJob.workspace_id == workspace,
                                                                 MediaDownloadJob.request_id == body.request_id))
            if old:
                self.match_request(old, body, preview)
                return describe(old)
        return None

    @staticmethod
    def match_request(old, body, preview):
        if isinstance(body, ConfirmSitePair):
            same_source = (old.source_kind == 'site_pair' and old.source_snapshot.get('preview_id') == preview
                           and old.source_snapshot.get('selection_sha256') == body.selection_sha256)
        elif preview:
            same_source = (old.site_receipt and old.site_receipt['preview_id'] == preview
                           and old.site_receipt['format_id'] == body.format_id)
        else:
            same_source = old.site_receipt is None and old.source_kind == 'direct_https' and old.source_url == body.url
        if not same_source or (old.name, old.parent_id) != (body.name, body.parent_id):
            raise HTTPException(409, '同一请求的下载参数变化')

    def insert_pair(self, session, workspace, body, source):
        from .media_sources import source_digest
        self.capacity(session)
        identifier = uuid4().hex
        item = MediaDownloadJob(id=identifier, workspace_id=workspace, parent_id=body.parent_id,
            request_id=body.request_id, source_url=None, source_kind=source.kind,
            source_snapshot=source.model_dump(mode='json'), source_snapshot_sha256=source_digest(source),
            run_generation=0, name=body.name, status='queued', cancel_requested=False, attempt=1,
            relative_path=f'workspaces/{workspace}/downloads/{identifier}/1.mp4',
            progress={'received': 0, 'total': source.input_size, 'phase': 'copying'}, result={}, error=None,
            created_at=datetime.now(timezone.utc).isoformat())
        session.add(item)
        session.flush()
        return describe(item)

    def enqueue_site_pair(self, workspace, body, source, transfer):
        with write_transaction(self.engine) as session:
            parent_in(session, workspace, body.parent_id)
            old = session.scalar(select(MediaDownloadJob).where(MediaDownloadJob.workspace_id == workspace,
                                                                 MediaDownloadJob.request_id == body.request_id))
            if old:
                self.match_request(old, body, source.preview_id)
                return describe(old)
            if session.scalar(select(MediaDownloadJob.id).where(MediaDownloadJob.workspace_id == workspace,
                    MediaDownloadJob.source_kind == 'site_pair',
                    MediaDownloadJob.source_snapshot['preview_id'].as_string() == source.preview_id)):
                raise HTTPException(409, '此预览已有双轨任务，请查看原下载任务')
            result = self.insert_pair(session, workspace, body, source)
        self.pool.submit(self.run, result['id'], transfer)
        return result

    def enqueue(self, workspace, body, source_url, *, receipt=None, transfer=None):
        with write_transaction(self.engine) as session:
            parent_in(session, workspace, body.parent_id)
            old = session.scalar(select(MediaDownloadJob).where(MediaDownloadJob.workspace_id == workspace,
                                                                 MediaDownloadJob.request_id == body.request_id))
            if old:
                self.match_request(old, body, receipt['preview_id'] if receipt else None)
                return describe(old)
            if receipt and session.scalar(select(MediaDownloadJob.id).where(
                    MediaDownloadJob.workspace_id == workspace,
                    MediaDownloadJob.site_receipt['preview_id'].as_string() == receipt['preview_id'],
                    MediaDownloadJob.site_receipt['format_id'].as_string() == receipt['format_id'])):
                raise HTTPException(409, '此候选已确认，请查看原下载任务')
            self.capacity(session)
            identifier = uuid4().hex
            item = MediaDownloadJob(id=identifier, workspace_id=workspace, parent_id=body.parent_id,
                request_id=body.request_id, source_url=source_url, site_receipt=receipt, name=body.name, status='queued',
                cancel_requested=False, attempt=1,
                relative_path=f'workspaces/{workspace}/downloads/{identifier}/1{Path(body.name).suffix.lower()}',
                progress={'received': 0}, result={}, error=None, created_at=datetime.now(timezone.utc).isoformat())
            session.add(item)
            session.flush()
            result = describe(item)
        if transfer:
            self.pool.submit(self.run, identifier, transfer)
        else:
            self.pool.submit(self.run, identifier)
        return result

    def router(self):
        from .media_mux import CreateLocalPair, same_request, source_for_request
        router = APIRouter(prefix='/api/workspaces/{workspace_id}/media-downloads')
        def job_in(session, workspace, identifier):
            require_workspace(session, workspace)
            job = session.get(MediaDownloadJob, identifier)
            if job is None or job.workspace_id != workspace:
                raise HTTPException(404, '下载任务不存在')
            return job
        @router.post('/local-pair')
        def local_pair(workspace_id: str, body: CreateLocalPair):
            with write_transaction(self.engine) as session:
                parent_in(session, workspace_id, body.parent_id)
                old = session.scalar(select(MediaDownloadJob).where(MediaDownloadJob.workspace_id == workspace_id,
                    MediaDownloadJob.request_id == body.request_id))
                if old:
                    try:
                        equal = old.source_kind == 'local_pair' and same_request(old, body)
                    except (ValueError, TypeError):
                        equal = False
                    if not equal:
                        raise HTTPException(409, '同一请求的合流参数变化')
                    return describe(old)
                source = source_for_request(session, workspace_id, body)
                result = self.insert_pair(session, workspace_id, body, source)
            self.pool.submit(self.run, result['id'])
            return result
        @router.post('')
        def create(workspace_id: str, body: CreateDownload):
            return self.enqueue(workspace_id, body, body.url)
        @router.get('')
        def listing(workspace_id: str, offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100),
                    history: bool = False, newest_id: str | None = Query(None, pattern=r'^[a-f0-9]{32}$')):
            with Session(self.engine) as session:
                require_workspace(session, workspace_id)
                statement = select(MediaDownloadJob).where(MediaDownloadJob.workspace_id == workspace_id)
                if newest_id is not None:
                    if not history:
                        raise HTTPException(422, '历史边界仅适用于历史排序')
                    newest = job_in(session, workspace_id, newest_id)
                    statement = statement.where((MediaDownloadJob.created_at < newest.created_at)
                        | ((MediaDownloadJob.created_at == newest.created_at) & (MediaDownloadJob.id >= newest.id)))
                if not history:
                    statement = statement.order_by(MediaDownloadJob.status.in_(['queued', 'running']).desc())
                statement = statement.order_by(MediaDownloadJob.created_at.desc(), MediaDownloadJob.id)
                return [describe(item) for item in session.scalars(statement.offset(offset).limit(limit))]
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
                if job.site_receipt or job.source_kind == 'site_pair':
                    raise HTTPException(409, '此站点任务须重新预览并确认，原部分保留')
                if job.source_kind == 'local_pair' and body.mode != 'restart':
                    raise HTTPException(409, '合流不追加中断片段，请保留旧执行并重新开始')
                parent_in(session, workspace_id, job.parent_id)
                self.capacity(session)
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
