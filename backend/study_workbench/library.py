"""Lossless export and explicit recovery of retained workspace originals."""
import hashlib
import io
import json
import re
from datetime import datetime, timezone
from uuid import uuid4
from zipfile import ZIP_DEFLATED, ZipFile

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import ImportJob, MarkdownQuestion, Note, PassageRecord, Question, Resource, write_transaction
from .imports import (
    PARSER_VERSION,
    describe,
    note_revision,
    parse_original,
    persist_assets,
    read_resource,
    resource_path,
    validate_attachments,
)
from .question_protocol import Content
from .question_splitting import all_blocks
from .workspaces import require_workspace

EXPORT_METADATA_LIMIT = 32 * 1024 * 1024


class Recovery(BaseModel):
    model_config = ConfigDict(extra="forbid")
    resource_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    filename: str = Field(min_length=1, max_length=240)


class NoteEdit(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_revision: str = Field(pattern=r"^[a-f0-9]{64}$")
    title: str = Field(min_length=1, max_length=240, pattern=r"\S")
    content: Content


def reparse(session, job, resource, root, *, parsed=None):
    data = read_resource(root, resource)
    try:
        mime, preview = parsed if parsed is not None else parse_original(data, resource.original_name, resource.id)
        persist_assets(session, root, job.workspace_id, preview)
        if preview["kind"] == "questions":
            validate_attachments(session, job.workspace_id, preview["bundle"], root)
    except (ValueError, RecursionError, HTTPException) as error:
        raise HTTPException(422, "重新解析失败，旧预览和原件均保留") from error
    resource.mime = mime
    job.preview, job.error, job.status = preview, None, "preview"
    job.parser_version = PARSER_VERSION
    return describe(job, resource, preview=True)


def library_router(engine, root, question_files):
    router = APIRouter(prefix="/api/workspaces/{workspace_id}")

    @router.put("/notes/{note_id}")
    def edit_note(workspace_id: str, note_id: str, body: NoteEdit):
        with write_transaction(engine) as session:
            require_workspace(session, workspace_id)
            note = session.get(Note, note_id)
            if note is None or note.workspace_id != workspace_id:
                raise HTTPException(404, "笔记不存在")
            if body.expected_revision != note_revision(note):
                raise HTTPException(409, "笔记已在其他页面更新，请刷新后再编辑")
            blocks = [b.model_dump(mode="json") for b in body.content]
            validate_attachments(session, workspace_id, blocks, root)
            note.title, note.content = body.title.strip(), blocks
            return {"id": note.id, "title": note.title, "content": note.content,
                    "resource_id": note.resource_id, "revision": note_revision(note)}

    @router.get("/resources")
    def resources(workspace_id: str, offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100)):
        with Session(engine) as session:
            require_workspace(session, workspace_id)
            return [{"id": r.id, "filename": r.original_name, "size": r.size, "mime": r.mime, "sha256": r.sha256}
                    for r in session.scalars(select(Resource).where(Resource.workspace_id == workspace_id)
                                              .order_by(Resource.id).offset(offset).limit(limit))]

    @router.post("/imports/{job_id}/retry")
    def retry(workspace_id: str, job_id: str):
        with Session(engine) as session:
            require_workspace(session, workspace_id)
            job = session.get(ImportJob, job_id)
            if job is None or job.workspace_id != workspace_id:
                raise HTTPException(404, "导入记录不存在")
            if job.status in {"confirmed", "parsing"}:
                raise HTTPException(409, "已确认或正在解析的内容不能重新解析或覆盖")
            resource = session.get(Resource, job.resource_id)
            data = read_resource(root, resource)
            name, identifier = resource.original_name, resource.id
        try:
            parsed = parse_original(data, name, identifier)
        except (ValueError, RecursionError, HTTPException) as error:
            raise HTTPException(422, "重新解析失败，旧预览和原件均保留") from error
        with write_transaction(engine) as session:
            require_workspace(session, workspace_id)
            job = session.get(ImportJob, job_id)
            if job.status in {"confirmed", "parsing"}:
                raise HTTPException(409, "资料状态已改变，请刷新导入记录")
            return reparse(session, job, session.get(Resource, job.resource_id), root, parsed=parsed)

    @router.get("/recovery")
    def scan(workspace_id: str):
        with Session(engine) as session:
            require_workspace(session, workspace_id)
            known = set(session.scalars(select(Resource.id).where(Resource.workspace_id == workspace_id)))
            directory = resource_path(root, f"workspaces/{workspace_id}/originals")
            found = []
            if directory.exists():
                for path in directory.iterdir():
                    if re.fullmatch(r"[a-f0-9]{32}\.bin", path.name) and path.stem not in known:
                        safe = resource_path(root, path.relative_to(root).as_posix())
                        found.append({"resource_id": safe.stem, "size": safe.stat().st_size})
                        if len(found) >= 100:
                            break
            return found

    @router.post("/recovery")
    def recover(workspace_id: str, body: Recovery):
        if (body.filename in {".", ".."} or any(c in body.filename for c in '/\\:')
                or any(ord(c) < 32 for c in body.filename)):
            raise HTTPException(422, "请输入不含路径的原文件名")
        with write_transaction(engine) as session:
            require_workspace(session, workspace_id)
            if session.get(Resource, body.resource_id):
                raise HTTPException(409, "资源已登记，请刷新资料库")
            relative = f"workspaces/{workspace_id}/originals/{body.resource_id}.bin"
            path = resource_path(root, relative)
            if not path.is_file():
                raise HTTPException(404, "未找到保留的原件")
            if not 0 < path.stat().st_size <= 8 * 1024 * 1024:
                raise HTTPException(413, "原件大小超限，请保留文件并离线处理")
            data = path.read_bytes()
            checksum = hashlib.sha256(data).hexdigest()
            duplicate = session.scalar(select(Resource).where(Resource.workspace_id == workspace_id,
                                                              Resource.sha256 == checksum))
            if duplicate:
                raise HTTPException(409, "已有相同原件；孤立副本保留，不会删除")
            resource = Resource(id=body.resource_id, workspace_id=workspace_id, original_name=body.filename,
                                relative_path=relative, sha256=checksum, size=len(data), mime="application/octet-stream")
            session.add(resource)
            session.flush()
            job = ImportJob(id=uuid4().hex, workspace_id=workspace_id, resource_id=resource.id,
                            parser_version=PARSER_VERSION, status="failed", error="恢复的原件待重新解析", preview={},
                            created_at=datetime.now(timezone.utc).isoformat())
            session.add(job)
            session.flush()
            # Recovery itself succeeds even if this file format cannot be parsed.
            try:
                return reparse(session, job, resource, root)
            except HTTPException as error:
                if error.status_code != 422:
                    raise
                return describe(job, resource, preview=True)

    @router.get("/export")
    def export(workspace_id: str):
        with Session(engine) as session, session.begin():
            session.connection().exec_driver_sql("BEGIN")
            require_workspace(session, workspace_id)
            resources = list(session.scalars(select(Resource).where(Resource.workspace_id == workspace_id).limit(10001)))
            if len(resources) > 10000 or sum(r.size for r in resources) > 128 * 1024 * 1024:
                raise HTTPException(413, "导出超过 128 MiB，请分批导出单个原件")
            metadata_size = 0

            def records(model, describe):
                nonlocal metadata_size
                result = []
                query = select(model).where(model.workspace_id == workspace_id).execution_options(yield_per=100)
                for row in session.scalars(query):
                    value = describe(row)
                    metadata_size += len(json.dumps(value, ensure_ascii=False).encode())
                    if metadata_size > EXPORT_METADATA_LIMIT:
                        raise HTTPException(413, "题目与笔记导出超过 32 MiB，请按资料拆分后导出")
                    result.append(value)
                return result

            manifest = {"schema_version": 1, "workspace_id": workspace_id, "resources": [],
                        "markdown_questions": records(MarkdownQuestion, lambda q: {
                            'id': q.id, 'title': q.title, 'source_resource_id': q.source_resource_id,
                            'markdown_resource_id': q.markdown_resource_id, 'content': q.content}),
                        "notes": records(Note, lambda n: {"id": n.id, "title": n.title, "content": n.content,
                                                           "resource_id": n.resource_id})}
            bundle = {"schema_version": 1,
                      "questions": records(Question, lambda q: q.content),
                      "passages": records(PassageRecord, lambda p: p.content)}
            output = io.BytesIO()
            with ZipFile(output, "w", compression=ZIP_DEFLATED) as archive:
                written = 0

                def write(name, data):
                    nonlocal written
                    written += len(data)
                    if written > 128 * 1024 * 1024:
                        raise HTTPException(413, '导出内容超过128MiB，包含题目Markdown及关联图片副本')
                    archive.writestr(name, data)

                for r in resources:
                    write(f"resources/{r.id}.bin", read_resource(root, r))
                    manifest["resources"].append({"id": r.id, "filename": r.original_name, "mime": r.mime,
                                                  "size": r.size, "sha256": r.sha256})
                for item in manifest['markdown_questions']:
                    write(f"questions/{item['id']}/question.md", read_resource(
                        root, session.get(Resource, item['markdown_resource_id'])))
                    for identifier in {b['attachment_id'] for b in all_blocks(item['content']) if b['type'] == 'image'}:
                        write(f"questions/{item['id']}/assets/{identifier}.png", read_resource(
                            root, session.get(Resource, identifier)))
                manifest['question_files'] = question_files.export(session, workspace_id, write)
                if manifest['question_files']:
                    manifest['schema_version'] = bundle['schema_version'] = 2
                    manifest['question_bundle_scope'] = 'practice_cache_only; authoritative files and confirmed snapshots in question_files'
                if metadata_size + len(json.dumps(manifest['question_files'], ensure_ascii=False).encode()) > EXPORT_METADATA_LIMIT:
                    raise HTTPException(413, '导出元数据总量超过32MiB')
                archive.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False))
                archive.writestr("questions.json", json.dumps(bundle, ensure_ascii=False))
            return Response(output.getvalue(), media_type="application/zip", headers={
                "Content-Disposition": 'attachment; filename="study-export.zip"',
                "X-Content-Type-Options": "nosniff", "Cache-Control": "no-store"})

    return router
