"""Streamed local media import and per-media capabilities, never a business-token bridge."""
import hashlib
import html
import json
import os
import secrets
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from .db import MediaEntry, write_transaction
from .imports import resource_path
from .workspaces import require_workspace

MEDIA_LIMIT = 512 * 1024 * 1024


def media_mime(suffix, header, size):
    if not size or (suffix == '.webm' and not header.startswith(b'\x1aE\xdf\xa3') or
                    suffix != '.webm' and header[4:8] != b'ftyp'):
        raise HTTPException(422, '媒体容器头不匹配，文件已保留；请检查格式或在外部工具中转换')
    return 'video/webm' if suffix == '.webm' else 'audio/mp4' if suffix == '.m4a' else 'video/mp4'


class Playback(BaseModel):
    model_config = ConfigDict(extra='forbid')
    position: float = Field(ge=0, le=604800, allow_inf_nan=False)
    speed: float = Field(ge=.5, le=3, allow_inf_nan=False)
    subtitle: str = Field(default='', max_length=32768)

    @field_validator('subtitle')
    @classmethod
    def bounded_vtt(cls, value):
        if len(value.encode('utf-8')) > 32768 or value and not value.lstrip('\ufeff').startswith('WEBVTT'):
            raise ValueError('Subtitles must be bounded WebVTT text')
        return value


def describe(item):
    return {'id': item.id, 'title': item.title, 'size': item.size, 'mime': item.mime,
            'sha256': item.sha256, 'status': item.status, 'playback': item.playback}


def media_routers(engine, root):
    api = APIRouter(prefix='/api/workspaces/{workspace_id}')
    public = APIRouter(prefix='/media/library')
    grants = {}

    def entry(session, workspace_id, media_id):
        require_workspace(session, workspace_id)
        item = session.get(MediaEntry, media_id)
        if item is None or item.workspace_id != workspace_id:
            raise HTTPException(404, '媒体不存在')
        return item

    @api.post('/media/import')
    async def import_media(workspace_id: str, request: Request, filename: str = Query(min_length=1, max_length=240)):
        suffix = Path(filename).suffix.lower()
        if (suffix not in {'.mp4', '.webm', '.m4a'} or any(c in filename for c in '/\\:') or
                any(ord(c) < 32 for c in filename)):
            raise HTTPException(422, '请选择MP4、WebM或M4A文件；编码是否可播放仍需播放器验证')
        identifier = uuid4().hex
        relative = f'workspaces/{workspace_id}/media/{identifier}{suffix}'
        with write_transaction(engine) as session:
            require_workspace(session, workspace_id)
            session.add(MediaEntry(id=identifier, workspace_id=workspace_id, title=filename,
                                   relative_path=relative, mime='', size=0, sha256='', status='importing', playback={}))
        path = resource_path(root, relative)
        checksum = hashlib.sha256()
        size = 0
        header = b''
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open('xb') as handle:
                async for chunk in request.stream():
                    size += len(chunk)
                    if size > MEDIA_LIMIT:
                        raise HTTPException(413, '本地媒体最多512MiB；已接收部分保留，不会删除原文件')
                    header = (header + chunk[:32])[:32]
                    checksum.update(chunk)
                    await run_in_threadpool(handle.write, chunk)
                await run_in_threadpool(handle.flush)
                await run_in_threadpool(os.fsync, handle.fileno())
            mime = media_mime(suffix, header, size)
            with write_transaction(engine) as session:
                item = entry(session, workspace_id, identifier)
                item.status, item.size, item.sha256, item.mime = 'ready', size, checksum.hexdigest(), mime
                return describe(item)
        except BaseException as error:
            try:
                stored = path.stat().st_size
            except OSError:
                stored = 0
            with write_transaction(engine) as session:
                item = session.get(MediaEntry, identifier)
                item.status, item.size = 'failed', stored
            if isinstance(error, HTTPException):
                raise
            if isinstance(error, OSError):
                raise HTTPException(409, '媒体保存失败，记录及已接收部分保留') from error
            raise

    @api.get('/media')
    def listing(workspace_id: str, offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100)):
        with Session(engine) as session:
            require_workspace(session, workspace_id)
            return [describe(item) for item in session.scalars(select(MediaEntry).where(
                MediaEntry.workspace_id == workspace_id).order_by(MediaEntry.id).offset(offset).limit(limit))]

    @api.get('/media/{media_id}/player')
    def player_url(workspace_id: str, media_id: str, request: Request):
        with Session(engine) as session:
            item = entry(session, workspace_id, media_id)
            if item.status != 'ready':
                raise HTTPException(409, '媒体未完整入库，请重新选择原文件导入')
            path = resource_path(root, item.relative_path)
            try:
                with path.open('rb') as handle:
                    checksum = hashlib.file_digest(handle, 'sha256').hexdigest()
                stat = path.stat()
            except OSError as error:
                raise HTTPException(409, '媒体文件不可读取') from error
            if stat.st_size != item.size or checksum != item.sha256:
                raise HTTPException(409, '媒体校验失败，不会播放被修改的文件')
            cap = secrets.token_urlsafe(32)
            grants[cap] = (workspace_id, item.id, stat.st_size, stat.st_mtime_ns)
            # A session can open a bounded number of players; evicted capabilities need a new API grant.
            while len(grants) > 256:
                grants.pop(next(iter(grants)))
            return {'url': f'{str(request.base_url).rstrip("/")}/media/library/{item.id}/player?cap={cap}'}

    def allowed(session, media_id, cap):
        grant = grants.get(cap)
        if grant is None or grant[1] != media_id:
            raise HTTPException(403, '媒体访问凭证无效，请重新打开播放器')
        item = entry(session, grant[0], media_id)
        path = resource_path(root, item.relative_path)
        try:
            stat = path.stat()
        except OSError as error:
            raise HTTPException(409, '媒体文件不可读取') from error
        if item.status != 'ready' or (stat.st_size, stat.st_mtime_ns) != grant[2:]:
            raise HTTPException(409, '媒体文件已改变，请重新打开播放器')
        return item, path

    @public.get('/{media_id}/player')
    def player(media_id: str, cap: str = ''):
        with Session(engine) as session:
            item, _ = allowed(session, media_id, cap)
            template = (Path(__file__).parent / 'library_player.html').read_text(encoding='utf-8')
            prefix = f'/media/library/{media_id}'
            return HTMLResponse(template.replace('__TITLE__', html.escape(item.title)).replace(
                '__PREFIX__', json.dumps(prefix)).replace('__CAP__', json.dumps(cap)), headers={'Referrer-Policy': 'no-referrer'})

    @public.api_route('/{media_id}/content', methods=['GET', 'HEAD'])
    def content(media_id: str, cap: str = ''):
        with Session(engine) as session:
            item, path = allowed(session, media_id, cap)
            return FileResponse(path, media_type=item.mime, headers={'X-Content-Type-Options': 'nosniff',
                                'Cache-Control': 'no-store', 'Referrer-Policy': 'no-referrer'})

    @public.get('/{media_id}/state')
    def state(media_id: str, cap: str = ''):
        with Session(engine) as session:
            item, _ = allowed(session, media_id, cap)
            return item.playback

    @public.post('/{media_id}/state')
    def save_state(media_id: str, body: Playback, cap: str = ''):
        with write_transaction(engine) as session:
            item, _ = allowed(session, media_id, cap)
            item.playback = body.model_dump()
            return {'saved': True}

    return api, public
