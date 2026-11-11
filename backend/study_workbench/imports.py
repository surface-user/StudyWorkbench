"""Workspace-scoped import staging. No source paths, network requests or executable HTML."""
import base64
import hashlib
import json
import os
import stat
import struct
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import Response
from pydantic import TypeAdapter, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from .db import ImportJob, Note, PassageRecord, Question, QuestionFileRecord, Resource, write_transaction
from .question_protocol import Content, QuestionBundle
from .workspaces import require_workspace

PARSER_VERSION = "builtin-4-grouped-md-docling-2.142.1-pdfium-5.14.0"


class PlainHTML(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.hidden = []
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style", "iframe", "object", "template", "head"}:
            self.hidden.append(tag)
        if not self.hidden and tag in {"p", "div", "br", "li", "tr", "h1", "h2", "h3"}:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if self.hidden and self.hidden[-1] == tag:
            self.hidden.pop()
        if not self.hidden and tag in {"p", "div", "li", "tr"}:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)


def image_size(data):
    if data.startswith(b"\x89PNG\r\n\x1a\n") and len(data) >= 24 and data[12:16] == b"IHDR":
        width, height = struct.unpack(">II", data[16:24])
        mime = "image/png"
    elif data.startswith(b"\xff\xd8"):
        offset = 2
        width = height = 0
        while offset + 4 <= len(data):
            if data[offset] != 255:
                break
            marker = data[offset + 1]
            offset += 2
            if marker == 255:
                offset -= 1
                continue
            if marker in {0xD8, 0xD9} or 0xD0 <= marker <= 0xD7:
                continue
            length = int.from_bytes(data[offset:offset + 2], "big")
            if length < 2 or offset + length > len(data):
                break
            if marker in {0xC0, 0xC1, 0xC2} and length >= 8:
                height, width = struct.unpack(">HH", data[offset + 3:offset + 7])
                break
            offset += length
        mime = "image/jpeg"
    else:
        raise ValueError("图片必须为 PNG 或 JPEG")
    if not (0 < width <= 8192 and 0 < height <= 8192 and width * height <= 16000000):
        raise ValueError("图片尺寸无效或超过 1600 万像素限制")
    return mime


def resource_path(root, relative):
    root = root.resolve()
    candidate = root / relative
    if not candidate.resolve().is_relative_to(root) or Path(relative).is_absolute():
        raise HTTPException(409, "资源路径校验失败")
    current = root
    for part in Path(relative).parts:
        current = current / part
        if current.exists() or current.is_symlink():
            attributes = current.lstat()
            if stat.S_ISLNK(attributes.st_mode) or getattr(attributes, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT:
                raise HTTPException(409, "资源目录含重解析点，操作已停止")
    return candidate


def read_resource(root, resource):
    try:
        path = resource_path(root, resource.relative_path)
        with path.open("rb") as handle:
            data = handle.read(resource.size + 1)
    except OSError as error:
        raise HTTPException(409, "原件不可读取，请检查数据目录；任务记录已保留") from error
    if len(data) != resource.size or hashlib.sha256(data).hexdigest() != resource.sha256:
        raise HTTPException(409, "原件校验失败，文件可能已被修改")
    return data


def source_claims(value, resource_id):
    """Never trust a document's self-reported verification or official status."""
    if not isinstance(value, dict):
        return
    if value.get("kind") in {"official", "manual", "imported"}:
        value["kind"] = "imported"
    value["verification"] = "unverified"
    value["original_resource_id"] = resource_id


def parse_original(data, name, resource_id):
    suffix = Path(name).suffix.lower()
    if suffix in {".docx", ".pdf"}:
        from .documents import convert_document
        preview = convert_document(data, name)
        preview["title"] = name
        mime = ("application/pdf" if suffix == ".pdf" else
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
        return mime, preview
    if suffix in {".png", ".jpg", ".jpeg"}:
        mime = image_size(data)
        return mime, {"kind": "attachment", "blocks": [
            {"type": "image", "attachment_id": resource_id, "alt": name}]}
    if suffix == ".json":
        raw = json.loads(data.decode("utf-8-sig"))
        if not isinstance(raw, dict):
            raise ValueError("JSON 必须为题目或题目 bundle 对象")
        if raw.get("kind") == "note":
            if (set(raw) != {"schema_version", "kind", "title", "blocks"} or
                    type(raw["schema_version"]) is not int or raw["schema_version"] != 1 or
                    not isinstance(raw["title"], str) or not 0 < len(raw["title"].strip()) <= 240):
                raise ValueError("笔记格式或版本无效")
            blocks = TypeAdapter(Content).validate_python(raw["blocks"])
            return "application/json", {"kind": "note", "title": raw["title"].strip(),
                                        "blocks": [b.model_dump(mode="json") for b in blocks]}
        if "questions" not in raw:
            raw = {"schema_version": 1, "questions": [raw], "passages": []}
        for group in ("questions", "passages"):
            records = raw.get(group, [])
            if isinstance(records, list):
                for record in records:
                    if isinstance(record, dict):
                        source_claims(record.get("source"), resource_id)
        bundle = QuestionBundle.model_validate(raw)
        return "application/json", {"kind": "questions", "bundle": bundle.model_dump(mode="json")}
    if suffix in {".txt", ".md", ".markdown", ".html", ".htm"}:
        content = data.decode("utf-8-sig")
        if suffix in {".html", ".htm"}:
            parser = PlainHTML()
            parser.feed(content)
            content = "".join(parser.parts)
        if "\x00" in content or not content.strip():
            raise ValueError("文本为空或含二进制内容")
        if len(content) > 200000:
            raise ValueError("提取文本超过 20 万字符，请拆分资料")
        blocks = [{"type": "text", "text": content[i:i + 20000]} for i in range(0, len(content), 20000)]
        return "text/plain", {"kind": "note", "title": name, "blocks": blocks}
    if suffix == ".url":
        from .workspaces import Tab
        url = data.decode("utf-8-sig").strip()
        Tab(id="link", kind="web", url=url)
        return "text/plain", {"kind": "note", "title": name,
                              "blocks": [{"type": "text", "text": url}]}
    raise ValueError("此格式尚未接入解析；原件已保留，请使用 UTF-8 文本、Markdown、HTML、题目 JSON 或 PNG/JPEG")


def validate_attachments(session, workspace_id, bundle, root):
    def walk(value):
        if isinstance(value, dict):
            for key in ("attachment_id", "data_attachment_id"):
                identifier = value.get(key)
                if identifier is not None:
                    resource = session.get(Resource, identifier)
                    if resource is None or resource.workspace_id != workspace_id:
                        raise HTTPException(422, "附件不存在或不属于当前工作空间")
                    if resource.mime not in {"image/png", "image/jpeg", "text/plain", "application/json", "application/pdf",
                                             "application/vnd.openxmlformats-officedocument.wordprocessingml.document"}:
                        raise HTTPException(422, "附件格式尚未受支持，不能关联到正式题目")
                    data = read_resource(root, resource)
                    if key == "attachment_id" and value.get("type") in {"image", "chart"}:
                        image_size(data)
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)
    walk(bundle)


def note_revision(note):
    return hashlib.sha256(json.dumps([note.title, note.content], sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def persist_assets(session, root, workspace_id, preview):
    replacements = {}
    for asset in preview.pop("_assets", []):
        data = base64.b64decode(asset["data"], validate=True)
        checksum = hashlib.sha256(data).hexdigest()
        existing = session.scalar(select(Resource).where(Resource.workspace_id == workspace_id, Resource.sha256 == checksum))
        if existing:
            replacements[asset["id"]] = existing.id
            continue
        relative = f"workspaces/{workspace_id}/originals/{asset['id']}.bin"
        path = resource_path(root, relative)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("xb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        session.add(Resource(id=asset["id"], workspace_id=workspace_id, original_name=asset["name"],
                             relative_path=relative, sha256=checksum, size=len(data), mime=image_size(data)))
        session.flush()
    def replace(value):
        if isinstance(value, dict):
            if value.get('attachment_id') in replacements:
                value['attachment_id'] = replacements[value['attachment_id']]
            for child in value.values():
                replace(child)
        elif isinstance(value, list):
            for child in value:
                replace(child)
    replace(preview)


def describe(job, resource, *, preview=False):
    result = {"id": job.id, "resource_id": job.resource_id, "filename": resource.original_name,
              "sha256": resource.sha256, "size": resource.size, "mime": resource.mime,
              "parser_version": job.parser_version, "status": job.status, "error": job.error,
              "created_at": job.created_at}
    if preview:
        result["preview"] = job.preview
        from .question_splitting import draft_revision, markdown
        drafts = job.preview.get('question_drafts', [])
        if drafts:
            result['draft_revision'] = draft_revision(drafts)
            result['question_markdown'] = [markdown(draft) for draft in drafts]
    return result


def import_router(engine, root):
    router = APIRouter(prefix="/api/workspaces/{workspace_id}")

    def stage(workspace_id, data, filename):
        checksum = hashlib.sha256(data).hexdigest()
        with write_transaction(engine) as session:
            require_workspace(session, workspace_id)
            existing = session.scalar(select(Resource).where(
                Resource.workspace_id == workspace_id, Resource.sha256 == checksum))
            if existing:
                job = session.scalar(select(ImportJob).where(ImportJob.resource_id == existing.id))
                if job:
                    return {**describe(job, existing, preview=True), "duplicate": True}
                # Extracted images also have resource rows, but may not have an import job yet.
                resource = existing
                identifier = existing.id
            else:
                identifier = uuid4().hex
                relative = f"workspaces/{workspace_id}/originals/{identifier}.bin"
                path = resource_path(root, relative)
                path.parent.mkdir(parents=True, exist_ok=True)
                # No cleanup on later failure: originals are never silently discarded.
                with path.open("xb") as handle:
                    handle.write(data)
                    handle.flush()
                    os.fsync(handle.fileno())
                resource = Resource(id=identifier, workspace_id=workspace_id, original_name=filename,
                                    relative_path=relative, sha256=checksum, size=len(data), mime="application/octet-stream")
                session.add(resource)
                session.flush()
            job = ImportJob(id=uuid4().hex, workspace_id=workspace_id, resource_id=identifier,
                            parser_version=PARSER_VERSION, status="parsing", error=None, preview={},
                            created_at=datetime.now(timezone.utc).isoformat())
            session.add(job)
            session.flush()
            job_id = job.id
        # Original and job survive a crash; conversion holds no SQLite writer lock.
        try:
            parsed = parse_original(data, filename, identifier)
            failure = None
        except (ValueError, RecursionError, HTTPException) as error:
            parsed, failure = None, error
        with write_transaction(engine) as session:
            require_workspace(session, workspace_id)
            job = session.get(ImportJob, job_id)
            resource = session.get(Resource, identifier)
            try:
                if failure is not None:
                    raise failure
                resource.mime, job.preview = parsed
                persist_assets(session, root, workspace_id, job.preview)
                if job.preview["kind"] == "questions":
                    validate_attachments(session, workspace_id, job.preview["bundle"], root)
                job.status = "preview"
            except (ValueError, RecursionError, HTTPException) as error:
                job.status = "failed"
                # Do not include document values or tracebacks in errors/logs.
                if isinstance(error, ValidationError):
                    job.error = "题目协议校验失败，请检查字段、答案、版本和引用"
                elif isinstance(error, HTTPException):
                    job.error = str(error.detail)
                elif isinstance(error, (UnicodeError, json.JSONDecodeError, RecursionError)):
                    job.error = "文本编码或 JSON 结构无效，请使用 UTF-8 并检查嵌套深度"
                else:
                    job.error = str(error)[:300]
                job.preview = {}
            session.add(job)
            session.flush()
            return {**describe(job, resource, preview=True), "duplicate": False}

    @router.post("/imports")
    async def upload(workspace_id: str, request: Request,
                     filename: str = Query(min_length=1, max_length=240)):
        if (filename in {".", ".."} or any(char in filename for char in '/\\:')
                or any(ord(char) < 32 for char in filename)):
            raise HTTPException(422, "文件名必须是不含路径的可读名称")
        data = await request.body()
        if not data:
            raise HTTPException(422, "不能导入空文件")
        return await run_in_threadpool(stage, workspace_id, data, filename)

    @router.post("/resources/{resource_id}/analyze")
    def analyze(workspace_id: str, resource_id: str):
        with Session(engine) as session:
            require_workspace(session, workspace_id)
            resource = session.get(Resource, resource_id)
            if resource is None or resource.workspace_id != workspace_id:
                raise HTTPException(404, "资源不存在")
            if resource.size > 8 * 1024 * 1024:
                raise HTTPException(413, "内容处理最多8MiB；原件仍可在资源管理器中打开")
            data, filename = read_resource(root, resource), resource.original_name
        if not data:
            raise HTTPException(422, "空文件没有可提取内容")
        return stage(workspace_id, data, filename)

    @router.get("/imports")
    def history(workspace_id: str, offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100)):
        with Session(engine) as session:
            require_workspace(session, workspace_id)
            rows = session.execute(select(ImportJob, Resource).join(Resource).where(
                ImportJob.workspace_id == workspace_id).order_by(
                ImportJob.created_at.desc(), ImportJob.id).offset(offset).limit(limit))
            return [describe(job, resource) for job, resource in rows]

    def scoped_job(session, workspace_id, job_id):
        require_workspace(session, workspace_id)
        job = session.get(ImportJob, job_id)
        if job is None or job.workspace_id != workspace_id:
            raise HTTPException(404, "导入任务不存在")
        return job

    @router.get("/imports/{job_id}")
    def detail(workspace_id: str, job_id: str):
        with Session(engine) as session:
            job = scoped_job(session, workspace_id, job_id)
            return describe(job, session.get(Resource, job.resource_id), preview=True)

    @router.post("/imports/{job_id}/confirm")
    def confirm(workspace_id: str, job_id: str):
        with write_transaction(engine) as session:
            job = scoped_job(session, workspace_id, job_id)
            resource = session.get(Resource, job.resource_id)
            if job.status == "confirmed":
                return describe(job, resource, preview=True)
            if job.status != "preview":
                raise HTTPException(409, "解析失败的资料不能确认入库；原件已保留")
            read_resource(root, resource)
            preview = job.preview
            if preview["kind"] == "questions":
                bundle = QuestionBundle.model_validate(preview["bundle"])
                validate_attachments(session, workspace_id, preview["bundle"], root)
                for question in bundle.questions:
                    if session.get(Question, (question.id, workspace_id)) or session.get(QuestionFileRecord, (workspace_id, question.id)):
                        raise HTTPException(409, "题目 ID 已存在，本批未写入；不会覆盖标准答案")
                for passage in bundle.passages:
                    if session.get(PassageRecord, (passage.id, workspace_id)):
                        raise HTTPException(409, "阅读材料 ID 已存在，本批未写入")
                for passage in bundle.passages:
                    session.add(PassageRecord(id=passage.id, workspace_id=workspace_id,
                                              content=passage.model_dump(mode="json")))
                for question in bundle.questions:
                    session.add(Question(id=question.id, workspace_id=workspace_id,
                                         content=question.model_dump(mode="json")))
            elif preview["kind"] == "note":
                validate_attachments(session, workspace_id, preview["blocks"], root)
                session.add(Note(id=job.id, workspace_id=workspace_id, resource_id=resource.id,
                                 title=preview["title"], content=preview["blocks"]))
            job.status = "confirmed"
            return describe(job, resource, preview=True)

    @router.get("/resources/{resource_id}")
    def resource_bytes(workspace_id: str, resource_id: str):
        with Session(engine) as session:
            require_workspace(session, workspace_id)
            resource = session.get(Resource, resource_id)
            if resource is None or resource.workspace_id != workspace_id:
                raise HTTPException(404, "资源不存在")
            data = read_resource(root, resource)
            return Response(data, media_type=resource.mime, headers={
                "X-Content-Type-Options": "nosniff", "Content-Disposition": "attachment",
                "Cache-Control": "no-store", "Content-Security-Policy": "default-src 'none'; sandbox"})

    @router.get("/questions")
    def questions(workspace_id: str, offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100)):
        with Session(engine) as session:
            require_workspace(session, workspace_id)
            return [{"id": q.id, "subject": q.content["subject"], "kind": q.content["kind"]}
                    for q in session.scalars(select(Question).where(Question.workspace_id == workspace_id)
                                             .order_by(Question.id).offset(offset).limit(limit))]

    @router.get("/questions/{question_id}")
    def question(workspace_id: str, question_id: str):
        with Session(engine) as session:
            require_workspace(session, workspace_id)
            record = session.get(Question, (question_id, workspace_id))
            if record is None:
                raise HTTPException(404, "题目不存在")
            from .question_files import current_question_view
            return current_question_view(session, root, record)

    @router.get("/passages/{passage_id}")
    def passage(workspace_id: str, passage_id: str):
        with Session(engine) as session:
            require_workspace(session, workspace_id)
            record = session.get(PassageRecord, (passage_id, workspace_id))
            if record is None:
                raise HTTPException(404, "阅读材料不存在")
            return record.content

    @router.get("/notes")
    def notes(workspace_id: str, offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100)):
        with Session(engine) as session:
            require_workspace(session, workspace_id)
            return [{"id": note.id, "title": note.title, "content": note.content,
                     "resource_id": note.resource_id, "revision": note_revision(note)}
                    for note in session.scalars(select(Note).where(Note.workspace_id == workspace_id)
                                                .order_by(Note.id).offset(offset).limit(limit))]

    return router
