"""One bounded conversion worker; retain original bytes, failures and derived provenance."""
import hashlib
import shutil
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from threading import Event
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import office_runtime
from .db import DocumentPreview, Resource, write_transaction
from .explorer import node_in
from .imports import read_resource, resource_path
from .office_inputs import MAX_SOURCE, validate_office
from .workspaces import require_workspace

PDF_LIMIT = 128 * 1024 * 1024
OPTIONS_HASH = hashlib.sha256(office_runtime.OPTIONS.encode()).hexdigest()


class PreviewRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    expected_source_sha256: str = Field(pattern=r'^[a-f0-9]{64}$')


def describe(item):
    return dict(id=item.id, resource_item_id=item.node_id, status=item.status, error=item.error,
                source_resource_id=item.source_resource_id, source_sha256=item.source_sha256,
                converter='LibreOffice', converter_version=item.converter_version,
                runtime_fingerprint=item.runtime_fingerprint, options_hash=item.options_hash,
                pdf_sha256=item.pdf_sha256, pdf_size=item.pdf_size, page_count=item.page_count,
                cancel_requested=item.cancel_requested)


class OfficePreviews:
    def __init__(self, engine, root):
        self.engine, self.root = engine, root
        self.stopping = Event()
        with write_transaction(engine) as session:
            for item in session.scalars(select(DocumentPreview).where(DocumentPreview.status.in_(['queued', 'running']))):
                item.status, item.error = 'interrupted', '上次转换中断；原件与已生成字节保留，请显式重试'
        self.pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix='office-preview')

    def close(self):
        self.stopping.set()
        self.pool.shutdown(wait=True)

    def source(self, session, workspace, identifier):
        require_workspace(session, workspace)
        node = node_in(session, workspace, identifier)
        if node.kind != 'resource':
            raise HTTPException(422, '此节点不是Office原件')
        original = session.get(Resource, node.resource_id)
        if Path(original.original_name).suffix.lower() not in {'.docx', '.pptx'}:
            raise HTTPException(422, '分页转换仅支持DOCX/PPTX；旧DOC/PPT请先在外部转PDF')
        if original.size > MAX_SOURCE:
            raise HTTPException(413, 'Office分页转换最多32MiB，原件保留')
        return original

    def job_in(self, session, workspace, node_id, identifier):
        require_workspace(session, workspace)
        node_in(session, workspace, node_id)
        item = session.get(DocumentPreview, identifier)
        if item is None or item.workspace_id != workspace or item.node_id != node_id:
            raise HTTPException(404, '分页预览任务不存在')
        return item

    def latest(self, workspace, node_id, source_hash):
        with Session(self.engine) as session:
            require_workspace(session, workspace)
            node_in(session, workspace, node_id)
            item = session.scalar(select(DocumentPreview).where(
                DocumentPreview.workspace_id == workspace, DocumentPreview.node_id == node_id,
                DocumentPreview.source_sha256 == source_hash, DocumentPreview.options_hash == OPTIONS_HASH
            ).order_by(DocumentPreview.created_at.desc(), DocumentPreview.id.desc()).limit(1))
            return describe(item) if item else None

    def run(self, identifier):
        last_check = 0

        def check():
            nonlocal last_check
            if self.stopping.is_set():
                raise office_runtime.ConversionStopped()
            if time.monotonic() - last_check < .1:
                return
            last_check = time.monotonic()
            with Session(self.engine) as session:
                item = session.get(DocumentPreview, identifier)
                require_workspace(session, item.workspace_id)
                if item.cancel_requested:
                    raise office_runtime.ConversionStopped()
                output = resource_path(self.root, item.relative_pdf)
                if output.exists() and output.stat().st_size > PDF_LIMIT:
                    raise ValueError('派生PDF超过128MiB，转换已停止，原件保留')

        status, error = 'failed', '转换未完成；原件和已生成字节保留'
        try:
            check()
            with write_transaction(self.engine) as session:
                item = session.get(DocumentPreview, identifier)
                item.status = 'running'
                workspace, node_id, expected, relative = item.workspace_id, item.node_id, item.source_sha256, item.relative_pdf
                fingerprint = item.runtime_fingerprint
                original = self.source(session, workspace, node_id)
                name, resource_id = original.original_name, original.id
            with Session(self.engine) as session:
                data = read_resource(self.root, session.get(Resource, resource_id))
            if hashlib.sha256(data).hexdigest() != expected:
                raise ValueError('原件已变化，转换已停止；请刷新资源')
            validate_office(data, Path(name).suffix.lower())
            runtime = office_runtime.runtime()
            if runtime.fingerprint != fingerprint:
                raise ValueError('离线运行时在排队期间变化，请重新发起转换')
            directory = resource_path(self.root, str(Path(relative).parent.parent))
            directory.mkdir(parents=True, exist_ok=True)
            source = directory / ('source' + Path(name).suffix.lower())
            with source.open('xb') as handle:
                handle.write(data)
                handle.flush()
                import os
                os.fsync(handle.fileno())
            output = runtime.convert(source, directory, check)
            check()
            expected_output = resource_path(self.root, relative)
            if output != expected_output or not output.is_file() or not 0 < output.stat().st_size <= PDF_LIMIT:
                raise ValueError('转换未生成有效大小的PDF，原件保留')
            # Validate in the same disposable renderer used by the PDF reader.
            from .document_files import raster
            pdf_data = output.read_bytes()
            info = raster(pdf_data, 'pdf-info')
            with Session(self.engine) as session:
                current = self.source(session, workspace, node_id)
                if current.id != resource_id or hashlib.sha256(read_resource(self.root, current)).hexdigest() != expected:
                    raise ValueError('原件在转换期间变化，派生文件保留但不作为可用预览')
            check()
            with write_transaction(self.engine) as session:
                item = session.get(DocumentPreview, identifier)
                if item.cancel_requested or self.stopping.is_set():
                    raise office_runtime.ConversionStopped()
                item.pdf_sha256, item.pdf_size, item.page_count = hashlib.sha256(pdf_data).hexdigest(), len(pdf_data), info['page_count']
                item.status, item.error = 'ready', None
            return
        except office_runtime.ConversionStopped:
            status = 'interrupted' if self.stopping.is_set() else 'cancelled'
            error = '转换已停止；原件及已生成字节保留'
        except ValueError as failure:
            error = str(failure)[:240]
        except (OSError, HTTPException):
            error = '源文件、离线组件或输出不可读取/校验；原件及失败字节保留，请核对后重试'
        except Exception:
            error = '转换任务异常；原件及失败字节保留，可显式重试'
        with write_transaction(self.engine) as session:
            item = session.get(DocumentPreview, identifier)
            item.status, item.error = status, error

    def read_pdf(self, workspace, node_id, identifier):
        with Session(self.engine) as session:
            item = self.job_in(session, workspace, node_id, identifier)
            original = self.source(session, workspace, node_id)
            if item.status != 'ready' or item.options_hash != OPTIONS_HASH:
                raise HTTPException(409, '分页预览尚未就绪或选项已变化，请重新生成')
            if original.id != item.source_resource_id or hashlib.sha256(read_resource(self.root, original)).hexdigest() != item.source_sha256:
                raise HTTPException(409, '原件已变化，旧派生预览不可使用')
            path = resource_path(self.root, item.relative_pdf)
            try:
                with path.open('rb') as handle:
                    data = handle.read(PDF_LIMIT + 1)
            except OSError as error:
                raise HTTPException(409, '派生PDF缺失，原件保留，可重新生成') from error
            if len(data) != item.pdf_size or hashlib.sha256(data).hexdigest() != item.pdf_sha256:
                raise HTTPException(409, '派生PDF校验失败，原件与旧关系保留，可重新生成')
            return data, describe(item)

    def router(self):
        router = APIRouter(prefix='/api/workspaces/{workspace_id}/nodes/{node_id}/previews')

        @router.get('/{preview_id}')
        def status(workspace_id: str, node_id: str, preview_id: str):
            with Session(self.engine) as session:
                return describe(self.job_in(session, workspace_id, node_id, preview_id))

        @router.post('')
        def start(workspace_id: str, node_id: str, body: PreviewRequest):
            with write_transaction(self.engine) as session:
                original = self.source(session, workspace_id, node_id)
                if original.sha256 != body.expected_source_sha256:
                    raise HTTPException(409, '原件版本已变化，请刷新资源')
                pending = session.scalar(select(DocumentPreview).where(
                    DocumentPreview.workspace_id == workspace_id, DocumentPreview.node_id == node_id,
                    DocumentPreview.status.in_(['queued', 'running'])))
                if pending:
                    return describe(pending)
            capability = office_runtime.capability()
            if not capability['available']:
                raise HTTPException(409, capability['reason'])
            with write_transaction(self.engine) as session:
                original = self.source(session, workspace_id, node_id)
                if original.sha256 != body.expected_source_sha256:
                    raise HTTPException(409, '原件版本已变化，请刷新资源')
                jobs = list(session.scalars(select(DocumentPreview).where(DocumentPreview.status.in_(['queued', 'running']))))
                same = next((item for item in jobs if item.workspace_id == workspace_id and item.node_id == node_id), None)
                if same:
                    return describe(same)
                if len(jobs) >= 4:
                    raise HTTPException(409, '最多排队4个分页转换，请等待或取消')
                if shutil.disk_usage(self.root).free < 256 * 1024 * 1024:
                    raise HTTPException(507, '分页转换至少需要256MiB可用空间，原件保留')
                cached = session.scalar(select(DocumentPreview).where(
                    DocumentPreview.workspace_id == workspace_id, DocumentPreview.node_id == node_id,
                    DocumentPreview.source_sha256 == original.sha256,
                    DocumentPreview.runtime_fingerprint == capability['fingerprint'],
                    DocumentPreview.options_hash == OPTIONS_HASH, DocumentPreview.status == 'ready'
                ).order_by(DocumentPreview.created_at.desc()).limit(1))
                if cached:
                    # Read under a separate read session only; no recursive write transaction.
                    try:
                        self.read_pdf(workspace_id, node_id, cached.id)
                        return describe(cached)
                    except HTTPException:
                        cached.status, cached.error = 'failed', '缓存缺失或校验失败，旧文件保留；已创建新任务'
                identifier = uuid4().hex
                item = DocumentPreview(id=identifier, workspace_id=workspace_id, node_id=node_id,
                                       source_resource_id=original.id, source_sha256=original.sha256,
                                       runtime_fingerprint=capability['fingerprint'], converter_version=office_runtime.VERSION,
                                       options_hash=OPTIONS_HASH, status='queued', cancel_requested=False,
                                       relative_pdf=f'workspaces/{workspace_id}/previews/{identifier}/output/source.pdf',
                                       created_at=datetime.now(timezone.utc).isoformat())
                session.add(item)
                session.flush()
                value = describe(item)
            self.pool.submit(self.run, identifier)
            return value

        @router.post('/{preview_id}/cancel')
        def cancel(workspace_id: str, node_id: str, preview_id: str):
            with write_transaction(self.engine) as session:
                item = self.job_in(session, workspace_id, node_id, preview_id)
                if item.status in {'queued', 'running'}:
                    item.cancel_requested = True
                return describe(item)

        return router
