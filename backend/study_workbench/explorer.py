"""Managed resource identities and bounded, cancellable local copying; no parsing or deletion."""
import hashlib
import mimetypes
import os
import re
import stat
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event
from urllib.parse import unquote, urlsplit
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import literal_column, select
from sqlalchemy.orm import Session

from .db import MediaEntry, Resource, ResourceAddJob, WorkspaceNode, write_transaction
from .imports import resource_path
from .media_library import media_mime
from .workspaces import Tab, require_workspace

NODE_LIMIT = 1000
TOTAL_LIMIT = 1024 * 1024 * 1024
FILE_LIMIT = 128 * 1024 * 1024


def normalized_name(value):
    value = unicodedata.normalize('NFC', value)
    if (not value or len(value) > 200 or value[-1] in ' .' or
            re.search(r'[\x00-\x1f<>:"/\\|?*]', value) or value in {'.', '..'} or
            re.fullmatch(r'(?i)(CON|PRN|AUX|NUL|COM[1-9¹²³]|LPT[1-9¹²³])(?:\..*)?', value)):
        raise ValueError('名称须为1–200字符，不含Windows保留名称、路径字符或结尾空格/点')
    return value


class NodeCreate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    parent_id: str | None = None
    name: str
    kind: str = Field(pattern='^(folder|link)$')
    url: str | None = None
    _name = field_validator('name')(normalized_name)


class NodeMove(BaseModel):
    model_config = ConfigDict(extra='forbid')
    parent_id: str | None
    name: str
    _name = field_validator('name')(normalized_name)


class CopyRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    parent_id: str | None = None
    source_path: str = Field(min_length=1, max_length=2048)


def node_in(session, workspace, identifier):
    item = session.get(WorkspaceNode, identifier)
    if item is None or item.workspace_id != workspace:
        raise HTTPException(404, '资源节点不存在')
    return item


def parent_in(session, workspace, identifier):
    require_workspace(session, workspace)
    if identifier is not None and node_in(session, workspace, identifier).kind != 'folder':
        raise HTTPException(422, '目标必须为同空间的文件夹')


def relative_node(session, workspace, node, value):
    value = unquote(value)
    try:
        uri = urlsplit(value)
    except ValueError as error:
        raise HTTPException(422, '相对地址无效') from error
    if uri.scheme or uri.netloc or uri.query or uri.fragment or value.startswith('/') or any(c in value for c in '\\:\x00'):
        raise HTTPException(422, '仅允许同工作空间的相对资源')
    parent, target = node.parent_id, None
    parts = value.split('/')
    for index, part in enumerate(parts):
        if part in {'', '.'}:
            continue
        if part == '..':
            if parent is None:
                raise HTTPException(422, '相对引用不能越过工作空间根目录')
            parent, target = node_in(session, workspace, parent).parent_id, None
            continue
        target = session.scalar(select(WorkspaceNode).where(
            WorkspaceNode.workspace_id == workspace, WorkspaceNode.parent_id == parent,
            WorkspaceNode.name_key == unicodedata.normalize('NFC', part).casefold()))
        if target is None:
            raise HTTPException(404, '相对文件未在资源树中找到')
        if index < len(parts) - 1 and target.kind != 'folder':
            raise HTTPException(422, '相对引用的中间节点必须是文件夹')
        parent = target.id
    if target is None or target.kind != 'resource':
        raise HTTPException(422, '相对引用不是文件资源')
    return target


def insert_node(session, workspace, parent, name, kind, **payload):
    name = normalized_name(name)
    base, number = name, 2
    while session.scalar(select(WorkspaceNode.id).where(
            WorkspaceNode.workspace_id == workspace, WorkspaceNode.parent_id == parent,
            WorkspaceNode.name_key == name.casefold())):
        name = f'{base[:180]} ({number})'
        number += 1
    item = WorkspaceNode(id=uuid4().hex, workspace_id=workspace, parent_id=parent,
                         kind=kind, name=name, name_key=name.casefold(), **payload)
    session.add(item)
    session.flush()
    return item


def describe_node(session, root, item):
    status = 'ready'
    target = None
    if item.kind in {'resource', 'media'}:
        target = session.get(Resource if item.kind == 'resource' else MediaEntry,
                             item.resource_id if item.kind == 'resource' else item.media_id)
        try:
            path = resource_path(root, target.relative_path)
            status = 'missing' if not path.is_file() else 'conflict' if path.stat().st_size != target.size else 'ready'
            if item.kind == 'media' and target.status != 'ready':
                status = target.status
        except (OSError, HTTPException):
            status = 'conflict'
    return dict(resource_item_id=item.id, parent_id=item.parent_id, name=item.name, kind=item.kind,
                resource_id=item.resource_id, media_id=item.media_id, url=item.url, status=status,
                sha256=target.sha256 if target else None, size=target.size if target else None)


def valid_original(root, item):
    try:
        path = resource_path(root, item.relative_path)
        with path.open('rb') as handle:
            return os.fstat(handle.fileno()).st_size == item.size and hashlib.file_digest(handle, 'sha256').hexdigest() == item.sha256
    except (OSError, HTTPException):
        return False


def adapt_legacy(session, workspace):
    # Compatibility tools can still add originals/media after the one-time migration.
    for model, field, kind in [(Resource, WorkspaceNode.resource_id, 'resource'),
                               (MediaEntry, WorkspaceNode.media_id, 'media')]:
        missing = select(model).where(model.workspace_id == workspace, ~select(WorkspaceNode.id).where(
            field == model.id).exists())
        if model is MediaEntry:
            missing = missing.where(MediaEntry.status != 'importing')
        for item in session.scalars(missing.limit(200)):
            value = item.original_name if kind == 'resource' else item.title
            value = unicodedata.normalize('NFC', re.sub(r'[\x00-\x1f<>:"/\\|?*]', '_', value))[:180].rstrip(' .') or '资源'
            try:
                normalized_name(value)
            except ValueError:
                value = '_' + value
            insert_node(session, workspace, None, value, kind,
                        **({'resource_id': item.id} if kind == 'resource' else {'media_id': item.id}))


def source_path(value, root):
    path = Path(value)
    if not path.is_absolute() or str(path).startswith(('\\\\', '//')) or ':' in str(path)[3:]:
        raise HTTPException(422, '请选择本地绝对路径，不支持网络路径或设备路径')
    if os.name == 'nt':
        import ctypes
        if ctypes.windll.kernel32.GetDriveTypeW(ctypes.c_wchar_p(path.anchor)) == 4:
            raise HTTPException(422, '不支持映射网络驱动器，请选择本地文件或文件夹')
    # lstat every component before resolve; junctions must never become trusted roots.
    for component in [*reversed(path.parents), path]:
        info = component.lstat()
        if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT:
            raise HTTPException(422, '不跟随符号链接或重解析点')
    path, root = path.resolve(), root.resolve()
    if path == Path(path.anchor) or path.is_relative_to(root) or root.is_relative_to(path):
        raise HTTPException(422, '来源不能是磁盘根目录或与数据目录交叠')
    return path


class CopyStopped(Exception):
    pass


class Explorer:
    def __init__(self, engine, root):
        self.engine, self.root = engine, root
        self.stopping = Event()
        self.pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix='resource-copy')
        with write_transaction(engine) as session:
            for job in session.scalars(select(ResourceAddJob).where(ResourceAddJob.status.in_(['queued', 'running']))):
                job.status, job.error = 'interrupted', '上次复制中断；已登记资源和复制字节保留，请重新选择来源'
                job.results = [dict(row, status='interrupted') if row['status'] == 'copying' else row for row in job.results]

    def close(self):
        self.stopping.set()
        self.pool.shutdown(wait=True)

    def check(self, job_id):
        with Session(self.engine) as session:
            job = session.get(ResourceAddJob, job_id)
            if self.stopping.is_set() or job.cancel_requested:
                raise CopyStopped()
            require_workspace(session, job.workspace_id)

    def result(self, job_id, value):
        with write_transaction(self.engine) as session:
            job = session.get(ResourceAddJob, job_id)
            previous = job.results
            if previous and previous[-1]['status'] == 'copying' and previous[-1].get('copied_path') == value.get('copied_path'):
                previous = previous[:-1]
            job.results = [*previous, value]

    def run(self, job_id):
        with write_transaction(self.engine) as session:
            job = session.get(ResourceAddJob, job_id)
            workspace, parent, source = job.workspace_id, job.parent_id, job.source_path
            job.status = 'running'
        total, count = 0, 0

        def visit(path, parent, depth):
            nonlocal count, total
            self.check(job_id)
            count += 1
            if count > NODE_LIMIT or depth > 32:
                raise HTTPException(413, '导入最多1000节点、32层；已完成部分保留')
            relative = None
            try:
                path = source_path(str(path), self.root)
                name = normalized_name(path.name)
                before = path.stat()
                if path.is_dir():
                    with write_transaction(self.engine) as session:
                        parent_in(session, workspace, parent)
                        node = insert_node(session, workspace, parent, name, 'folder')
                        folder_id, display = node.id, node.name
                    self.result(job_id, dict(name=name, status='renamed' if display != name else 'added',
                                             resource_item_id=folder_id))
                    # scandir is incremental: do not allocate an unbounded directory listing.
                    with os.scandir(path) as children:
                        for child in children:
                            visit(Path(child.path), folder_id, depth + 1)
                    return
                if not stat.S_ISREG(before.st_mode):
                    raise HTTPException(422, '仅支持普通文件与文件夹')
                media = path.suffix.lower() in {'.mp4', '.webm', '.m4a'}
                limit = 512 * 1024 * 1024 if media else FILE_LIMIT
                if before.st_size > limit or total + before.st_size > TOTAL_LIMIT:
                    raise HTTPException(413, '超过文件大小或单任务1GiB预算；已完成部分保留')
                identifier = uuid4().hex
                relative = f'workspaces/{workspace}/' + ('media/' if media else 'originals/') + identifier + path.suffix.lower()
                destination = resource_path(self.root, relative)
                destination.parent.mkdir(parents=True, exist_ok=True)
                self.result(job_id, dict(name=name, status='copying', copied_path=relative))
                digest, size, header = hashlib.sha256(), 0, b''
                with path.open('rb') as incoming, destination.open('xb') as outgoing:
                    opened = os.fstat(incoming.fileno())
                    if not stat.S_ISREG(opened.st_mode) or (opened.st_ino, opened.st_size, opened.st_mtime_ns) != (
                            before.st_ino, before.st_size, before.st_mtime_ns):
                        raise HTTPException(409, '来源在打开时变化；复制停止')
                    while chunk := incoming.read(1024 * 1024):
                        self.check(job_id)
                        size += len(chunk)
                        total += len(chunk)
                        if size > limit or total > TOTAL_LIMIT:
                            raise HTTPException(413, '复制期间超过大小预算，已复制字节保留')
                        header = (header + chunk[:32])[:32]
                        digest.update(chunk)
                        outgoing.write(chunk)
                    outgoing.flush()
                    os.fsync(outgoing.fileno())
                self.check(job_id)
                source_path(str(path), self.root)
                after = path.stat()
                if (before.st_size, before.st_mtime_ns, before.st_ino) != (after.st_size, after.st_mtime_ns, after.st_ino) or size != before.st_size:
                    raise HTTPException(409, '来源在复制时变化；副本保留但不登记为可用资源')
                mime = media_mime(path.suffix.lower(), header, size) if media else mimetypes.guess_type(name)[0] or 'application/octet-stream'
                with write_transaction(self.engine) as session:
                    parent_in(session, workspace, parent)
                    checksum = digest.hexdigest()
                    existing = None if media else session.scalar(select(Resource).where(
                        Resource.workspace_id == workspace, Resource.sha256 == checksum))
                    if existing:
                        if not valid_original(self.root, existing):
                            raise HTTPException(409, '相同原件的旧文件缺失或冲突；新副本和旧关系保留，未覆盖')
                        identifier = existing.id
                    elif media:
                        session.add(MediaEntry(id=identifier, workspace_id=workspace, title=name, relative_path=relative,
                                               mime=mime, size=size, sha256=checksum, status='ready', playback={}))
                    else:
                        session.add(Resource(id=identifier, workspace_id=workspace, original_name=name,
                                             relative_path=relative, mime=mime, size=size, sha256=checksum))
                    session.flush()
                    node = insert_node(session, workspace, parent, name, 'media' if media else 'resource',
                                       **({'media_id': identifier} if media else {'resource_id': identifier}))
                    job = session.get(ResourceAddJob, job_id)
                    job.results = [*job.results[:-1], dict(name=name, resource_item_id=node.id,
                                   status='duplicate' if existing else 'renamed' if node.name != name else 'added',
                                   stored_name=node.name, copied_path=relative)]
            except (ValueError, OSError, HTTPException) as error:
                self.result(job_id, dict(name=path.name[:200], status='failed',
                                         copied_path=relative,
                                         error=str(error.detail) if isinstance(error, HTTPException) else '名称无效或文件不可读取'))
                if isinstance(error, HTTPException) and error.status_code == 413:
                    raise

        status, error = 'completed', None
        try:
            visit(Path(source), parent, 0)
            with Session(self.engine) as session:
                if any(row['status'] == 'failed' for row in session.get(ResourceAddJob, job_id).results):
                    status = 'partial'
        except CopyStopped:
            status, error = 'cancelled', '复制已停止；已登记资源及复制字节保留'
        except Exception:
            status, error = 'failed', '复制未完成；原目录、已登记资源和复制字节保留'
        with write_transaction(self.engine) as session:
            job = session.get(ResourceAddJob, job_id)
            job.status, job.error = status, error
            job.results = [dict(row, status=status) if row['status'] == 'copying' else row for row in job.results]

    def router(self):
        router = APIRouter(prefix='/api/workspaces/{workspace_id}')

        @router.get('/nodes')
        def listing(workspace_id: str, parent_id: str | None = None,
                    offset: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=200)):
            with write_transaction(self.engine) as session:
                parent_in(session, workspace_id, parent_id)
                if parent_id is None:
                    adapt_legacy(session, workspace_id)
                return [describe_node(session, self.root, node) for node in session.scalars(select(WorkspaceNode).where(
                    WorkspaceNode.workspace_id == workspace_id, WorkspaceNode.parent_id == parent_id
                ).order_by(WorkspaceNode.kind, WorkspaceNode.name_key, WorkspaceNode.id).offset(offset).limit(limit))]

        @router.post('/nodes')
        def create(workspace_id: str, body: NodeCreate):
            if body.kind == 'link':
                try:
                    if not body.url:
                        raise ValueError('Missing URL')
                    Tab(id='link', kind='web', url=body.url)
                except ValueError as error:
                    raise HTTPException(422, '链接须为不含凭证的外部HTTPS地址') from error
            elif body.url is not None:
                raise HTTPException(422, '文件夹不能携带链接')
            with write_transaction(self.engine) as session:
                parent_in(session, workspace_id, body.parent_id)
                node = insert_node(session, workspace_id, body.parent_id, body.name, body.kind, url=body.url)
                return describe_node(session, self.root, node)

        @router.get('/nodes/{node_id}')
        def details(workspace_id: str, node_id: str):
            with Session(self.engine) as session:
                require_workspace(session, workspace_id)
                node = node_in(session, workspace_id, node_id)
                result = describe_node(session, self.root, node)
                if result['status'] == 'ready' and node.kind in {'resource', 'media'}:
                    item = session.get(Resource if node.kind == 'resource' else MediaEntry,
                                       node.resource_id if node.kind == 'resource' else node.media_id)
                    if not valid_original(self.root, item):
                        result['status'] = 'conflict'
                return result

        @router.patch('/nodes/{node_id}')
        def move(workspace_id: str, node_id: str, body: NodeMove):
            with write_transaction(self.engine) as session:
                parent_in(session, workspace_id, body.parent_id)
                node = node_in(session, workspace_id, node_id)
                cursor, depth = body.parent_id, 0
                while cursor is not None:
                    if cursor == node.id or depth > 1000:
                        raise HTTPException(409, '不能把文件夹移动到自身或其后代')
                    cursor = node_in(session, workspace_id, cursor).parent_id
                    depth += 1
                if session.scalar(select(WorkspaceNode.id).where(
                        WorkspaceNode.workspace_id == workspace_id, WorkspaceNode.parent_id == body.parent_id,
                        WorkspaceNode.name_key == body.name.casefold(), WorkspaceNode.id != node.id)):
                    raise HTTPException(409, '目标文件夹已有同名资源，请改名')
                node.parent_id, node.name, node.name_key = body.parent_id, body.name, body.name.casefold()
                return describe_node(session, self.root, node)

        def job_in(session, workspace, identifier):
            require_workspace(session, workspace)
            job = session.get(ResourceAddJob, identifier)
            if job is None or job.workspace_id != workspace:
                raise HTTPException(404, '添加任务不存在')
            return job

        def describe_job(job):
            return dict(id=job.id, status=job.status, results=job.results, error=job.error,
                        cancel_requested=job.cancel_requested)

        @router.post('/resource-add-jobs')
        def start(workspace_id: str, body: CopyRequest):
            try:
                path = source_path(body.source_path, self.root)
            except OSError as error:
                raise HTTPException(422, '所选来源不可读取') from error
            with write_transaction(self.engine) as session:
                parent_in(session, workspace_id, body.parent_id)
                pending = list(session.scalars(select(ResourceAddJob.id).where(ResourceAddJob.status.in_(['queued', 'running']))))
                if len(pending) >= 4:
                    raise HTTPException(409, '最多排队4个添加任务，请等待或取消')
                job = ResourceAddJob(id=uuid4().hex, workspace_id=workspace_id, parent_id=body.parent_id,
                                     source_path=str(path), status='queued', cancel_requested=False, results=[])
                session.add(job)
                session.flush()
                result = describe_job(job)
            self.pool.submit(self.run, result['id'])
            return result

        @router.get('/resource-add-jobs')
        def jobs(workspace_id: str, offset: int = Query(0, ge=0)):
            with Session(self.engine) as session:
                require_workspace(session, workspace_id)
                return [describe_job(job) for job in session.scalars(select(ResourceAddJob).where(
                    ResourceAddJob.workspace_id == workspace_id).order_by(
                        literal_column('resource_add_jobs.rowid').desc()).offset(offset).limit(20))]

        @router.get('/resource-add-jobs/{job_id}')
        def job(workspace_id: str, job_id: str):
            with Session(self.engine) as session:
                return describe_job(job_in(session, workspace_id, job_id))

        @router.post('/resource-add-jobs/{job_id}/cancel')
        def cancel(workspace_id: str, job_id: str):
            with write_transaction(self.engine) as session:
                item = job_in(session, workspace_id, job_id)
                if item.status in {'queued', 'running'}:
                    item.cancel_requested = True
                return describe_job(item)

        return router
