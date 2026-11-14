"""Short-lived, workspace-scoped metadata previews; never a persistent download queue."""
import json
import os
import queue
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event, RLock, Thread
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.orm import Session

from .bilibili_preview import OUTPUT_LIMIT, VERSION, page_url
from .media_download_http import DownloadError
from .office_runtime import WindowsProcessJob
from .workspaces import require_workspace

SECONDS = 45
STOP_SECONDS = 2
PUBLIC_FORMAT = ('format_id', 'delivery', 'source_format_id', 'container', 'codecs', 'width', 'height',
                 'fps', 'size_bytes', 'requires_merge', 'download_supported', 'limitation')


class CreateSitePreview(BaseModel):
    model_config = ConfigDict(extra='forbid')
    url: str = Field(min_length=1, max_length=8192)
    request_id: str = Field(pattern=r'^[A-Za-z0-9_-]{16,100}$')
    rights_confirmed: bool = Field(strict=True)

    @field_validator('url')
    @classmethod
    def canonical(cls, value):
        return page_url(value)

    @field_validator('rights_confirmed')
    @classmethod
    def consent(cls, value):
        if value is not True:
            raise ValueError('请确认有权获取该视频')
        return value


class MediaSitePreviews:
    def __init__(self, engine):
        self.engine, self.entries = engine, {}
        self.lock, self.stopping = RLock(), Event()
        self.pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix='site-preview')
        self.expiry = None

    def close(self):
        with self.lock:
            self.stopping.set()
            expiry = self.expiry
            for entry in self.entries.values():
                entry['cancel'].set()
        self.pool.shutdown(wait=True, cancel_futures=True)
        if expiry is not None:
            expiry.join(timeout=2)
        with self.lock:
            self.entries.clear()

    def workspace(self, identifier):
        with Session(self.engine) as session:
            require_workspace(session, identifier)

    def prune(self):
        for identifier in [key for key, entry in self.entries.items() if time.monotonic() >= entry['expires']]:
            self.entries.pop(identifier)['cancel'].set()

    def expire(self):
        while not self.stopping.wait(1):
            with self.lock:
                self.prune()
                if not self.entries:
                    self.expiry = None
                    return

    def describe(self, entry):
        result = entry['result']
        public = None if result is None else {
            key: result[key] for key in ('title', 'video_id', 'source_host', 'extractor_version',
                                        'duration_seconds', 'returned_formats_only')}
        if public is not None:
            public['formats'] = [{key: item[key] for key in PUBLIC_FORMAT} for item in result['formats']]
        return dict(id=entry['id'], status=entry['status'], result=public, error=entry['error'],
                    expires_in_seconds=max(0, int(entry['expires'] - time.monotonic())), extractor_version=VERSION)

    def start(self, workspace, body):
        self.workspace(workspace)
        with self.lock:
            self.prune()
            if self.stopping.is_set():
                raise HTTPException(503, '后端正在关闭，未开始预览')
            for entry in self.entries.values():
                if (entry['workspace'], entry['request']) == (workspace, body.request_id):
                    if entry['url'] != body.url:
                        raise HTTPException(409, '预览请求参数变化，请重新确认')
                    return self.describe(entry)
            if len(self.entries) >= 32 or sum(e['status'] == 'running' for e in self.entries.values()) >= 2:
                raise HTTPException(429, '预览繁忙，请取消已有预览或稍后重试')
            identifier = uuid4().hex
            entry = dict(id=identifier, workspace=workspace, request=body.request_id, url=body.url,
                         expires=time.monotonic() + 600, cancel=Event(), status='running', result=None, error=None)
            self.entries[identifier] = entry
            if self.expiry is None:
                self.expiry = Thread(target=self.expire, daemon=True)
                self.expiry.start()
            self.pool.submit(self.run, entry)
            return self.describe(entry)

    def get(self, workspace, identifier):
        self.workspace(workspace)
        with self.lock:
            self.prune()
            entry = self.entries.get(identifier)
            if entry is None or entry['workspace'] != workspace:
                raise HTTPException(404, '预览已失效或不存在，请重新预览')
            return self.describe(entry)

    def cancel(self, workspace, identifier):
        self.workspace(workspace)
        with self.lock:
            self.prune()
            entry = self.entries.get(identifier)
            if entry is None or entry['workspace'] != workspace:
                raise HTTPException(404, '预览已失效或不存在')
            entry['cancel'].set()
            entry.update(status='cancelled', result=None, error=None)
            return self.describe(entry)

    def child(self, entry):
        if self.stopping.is_set() or entry['cancel'].is_set():
            raise DownloadError('预览已取消')
        command = [sys.executable]
        if not getattr(sys, 'frozen', False):
            command += ['-m', 'study_workbench']
        environment = {name: value for name, value in os.environ.items()
                       if name.upper() in {'SYSTEMROOT', 'WINDIR', 'TEMP', 'TMP'}}
        environment.update(PYTHONUTF8='1', PYTHONIOENCODING='utf-8', PYTHONNOUSERSITE='1',
                           PYTHONPATH=str(Path(__file__).resolve().parents[1]))
        if os.name == 'nt':
            environment['PATH'] = str(Path(os.environ['SystemRoot']) / 'System32')
        messages = queue.Queue(maxsize=1)
        deadline = time.monotonic() + SECONDS
        job, process, reader, result = None, None, None, None
        with tempfile.TemporaryDirectory(prefix='study-site-preview-') as directory:
            try:
                job = WindowsProcessJob() if os.name == 'nt' else None
                process = subprocess.Popen(command + ['--preview-media'], cwd=directory, env=environment,
                    stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
                if job is not None:
                    job.attach(process)

                def read():
                    try:
                        line = process.stdout.readline(OUTPUT_LIMIT + 1)
                        if not line or len(line) > OUTPUT_LIMIT:
                            raise ValueError()
                        messages.put(json.loads(line), timeout=1)
                    except Exception:
                        messages.put({'error': '预览工作进程未返回有界结果'}, timeout=1)

                reader = Thread(target=read, daemon=True)
                reader.start()
                # The fixed worker waits for this input; no request can begin before Job ownership.
                if self.stopping.is_set() or entry['cancel'].is_set():
                    raise DownloadError('预览已取消')
                process.stdin.write(json.dumps({'url': entry['url']}).encode('utf-8') + b'\n')
                process.stdin.flush()
                while True:
                    if self.stopping.is_set() or entry['cancel'].is_set():
                        raise DownloadError('预览已取消')
                    if time.monotonic() > deadline:
                        raise DownloadError('预览超过45秒')
                    try:
                        message = messages.get(timeout=.1)
                    except queue.Empty:
                        if process.poll() is not None and not reader.is_alive():
                            raise DownloadError('预览工作进程提前结束')
                        continue
                    if not isinstance(message, dict) or 'result' not in message:
                        raise DownloadError(str(message.get('error', '预览未完成'))[:300] if isinstance(message, dict) else '预览响应无效')
                    result = message['result']
                    if (not isinstance(result, dict) or result.get('extractor_version') != VERSION
                            or not isinstance(result.get('formats'), list) or not 0 < len(result['formats']) <= 64):
                        raise DownloadError('预览工作结果格式无效')
                    break
            finally:
                try:
                    if process is not None:
                        if process.stdin and not process.stdin.closed:
                            try:
                                process.stdin.close()
                            except OSError:
                                pass
                        try:
                            process.wait(timeout=STOP_SECONDS)
                        except subprocess.TimeoutExpired:
                            process.kill()
                            process.wait(timeout=5)
                finally:
                    if job is not None:
                        job.close()
                    if process is not None and process.stdout:
                        process.stdout.close()
                    if reader is not None:
                        reader.join(timeout=2)
        if process.returncode or result is None:
            raise DownloadError('预览工作进程异常结束')
        return result

    def run(self, entry):
        try:
            with self.lock:
                if self.stopping.is_set() or entry['cancel'].is_set() or self.entries.get(entry['id']) is not entry:
                    return
            result = self.child(entry)
            with self.lock:
                if not entry['cancel'].is_set() and self.entries.get(entry['id']) is entry:
                    entry.update(status='ready', result=result)
                    self.describe(entry)
        except Exception as error:
            with self.lock:
                if not entry['cancel'].is_set() and self.entries.get(entry['id']) is entry:
                    entry.update(status='failed', result=None,
                                 error=str(error)[:300] if isinstance(error, DownloadError) else '预览未完成：站点或工作进程异常')

    def router(self):
        router = APIRouter(prefix='/api/workspaces/{workspace_id}/media-site-previews', tags=['media'])

        @router.post('')
        def start(workspace_id: str, body: CreateSitePreview):
            return self.start(workspace_id, body)

        @router.get('/{identifier}')
        def get(workspace_id: str, identifier: str):
            return self.get(workspace_id, identifier)

        @router.post('/{identifier}/cancel')
        def cancel(workspace_id: str, identifier: str):
            return self.cancel(workspace_id, identifier)

        return router
