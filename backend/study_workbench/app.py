import secrets
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select, text
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .agent_access import AgentAccess
from .analysis_review import AnalysisReviews
from .content import DEMO, SUBJECTIVE
from .db import (
    Attempt,
    ImportJob,
    MediaEntry,
    Question,
    QuestionFileRecord,
    Workspace,
    database,
    write_transaction,
)
from .document_files import DocumentFiles
from .draft_editing import draft_router
from .explorer import Explorer
from .imports import import_router
from .internal_links import router as internal_links_router
from .learning import grade, learning_router, workspace_history
from .learning_marks import LearningMarks
from .learning_records import records_router
from .learning_search import router as learning_search_router
from .library import library_router
from .markdown_notes import MarkdownNotes
from .markdown_questions import markdown_router
from .media_downloads import MediaDownloads
from .media_library import media_routers
from .migrate import migrate
from .question_files import QuestionFiles, current_question_view, verify_version_assets, version_read
from .question_files_format import FileQuestion
from .question_protocol import QuestionDocument
from .request_limits import RequestLimits
from .workspaces import initial_layout, require_workspace, workspace_router


class Submission(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question_id: str
    response: dict = Field(default_factory=dict)
    question_revision: int | None = Field(default=None, ge=1, strict=True)
    request_id: str | None = Field(default=None, pattern=r"^[A-Za-z0-9_-]{16,80}$")
    question_version_id: str | None = Field(default=None, pattern=r'^[a-f0-9]{32}$')


def create_app(data_dir: Path, token: str, media: Path | None = None):
    if len(token) < 32:
        raise ValueError("Session token must contain at least 32 characters")
    fresh_database = not (data_dir / 'study.db').exists()
    data_dir.mkdir(parents=True, exist_ok=True)
    engine = database(data_dir / "study.db")
    try:
        migrate(engine, (data_dir / "study.db").resolve())
    except Exception:
        engine.dispose()
        raise
    with write_transaction(engine) as session:
        if fresh_database:
            workspace = session.get(Workspace, 'default')
            workspace.name, workspace.layout = '我的学习空间', initial_layout()
        for item in session.scalars(select(MediaEntry).where(MediaEntry.status == 'importing')):
            item.status = 'failed'
        for job in session.scalars(select(ImportJob).where(ImportJob.status == "parsing")):
            job.status, job.error = "failed", "上次解析被中断；原件保留，可重新解析"
        for content in (DEMO, SUBJECTIVE):
            QuestionDocument.model_validate(content)
            if not session.get(Question, (content["id"], "default")):
                session.add(Question(id=content["id"], workspace_id="default", content=content))

    explorer = Explorer(engine, data_dir)
    documents = DocumentFiles(engine, data_dir)
    markdown_notes = MarkdownNotes(engine, data_dir)
    learning_marks = LearningMarks(documents)
    question_files = QuestionFiles(documents)
    downloads = MediaDownloads(engine, data_dir)
    agent_access = AgentAccess(engine, data_dir)
    analysis_reviews = AnalysisReviews(engine, data_dir, agent_access, markdown_notes, documents)

    @asynccontextmanager
    async def lifespan(_):
        yield
        await run_in_threadpool(downloads.close)
        await run_in_threadpool(documents.close)
        await run_in_threadpool(explorer.close)
        engine.dispose()

    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)
    app.state.engine = engine
    app.state.explorer = explorer
    app.state.documents = documents
    app.state.markdown_notes = markdown_notes
    app.state.learning_marks = learning_marks
    app.state.question_files = question_files
    app.state.downloads = downloads
    app.state.agent_access = agent_access
    app.state.analysis_reviews = analysis_reviews
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1"])
    app.add_middleware(RequestLimits)
    capability = secrets.token_urlsafe(32)

    @app.middleware("http")
    async def boundaries(request: Request, call_next):
        if request.url.path.startswith("/api/") and request.headers.get("origin"):
            return JSONResponse({"detail": "Browser origin is not authorized"}, status_code=403)
        return await call_next(request)

    def authorize(authorization: Annotated[str | None, Header()] = None):
        if not secrets.compare_digest(authorization or "", f"Bearer {token}"):
            raise HTTPException(401, "Unauthorized")

    auth = [Depends(authorize)]
    app.include_router(agent_access.router(), dependencies=auth)
    app.include_router(analysis_reviews.router(), dependencies=auth)
    app.include_router(workspace_router(engine), dependencies=auth)
    app.include_router(explorer.router(), dependencies=auth)
    app.include_router(downloads.router(), dependencies=auth)
    app.include_router(documents.router(), dependencies=auth)
    app.include_router(documents.previews.router(), dependencies=auth)
    app.include_router(question_files.router(), dependencies=auth)
    # Keep the explicit /questions/demo route ahead of the parameterized reader.

    @app.get("/api/health", dependencies=auth)
    def health():
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return {"status": "ok", "api_version": 0, "database": "sqlite"}

    @app.get("/api/questions/demo", dependencies=auth)
    def default_demo():
        return demo("default")

    @app.get("/api/workspaces/{workspace_id}/questions/demo", dependencies=auth)
    def demo(workspace_id: str):
        with Session(engine) as session:
            require_workspace(session, workspace_id)
            return current_question_view(session, data_dir, session.get(Question, (DEMO["id"], workspace_id)))

    @app.post("/api/attempts", dependencies=auth)
    def default_submit(body: Submission):
        return submit(body, "default")

    @app.post("/api/workspaces/{workspace_id}/attempts", dependencies=auth)
    def submit(body: Submission, workspace_id: str):
        with write_transaction(engine) as session:
            require_workspace(session, workspace_id)
            question = session.get(Question, (body.question_id, workspace_id))
            if question is None:
                raise HTTPException(404, "Unknown question")
            if body.request_id:
                existing = session.scalar(select(Attempt).where(Attempt.workspace_id == workspace_id,
                                                                Attempt.request_id == body.request_id))
                if existing:
                    if (existing.question_id != body.question_id or existing.response != body.response
                            or body.question_revision is not None and existing.question_revision != body.question_revision
                            or existing.question_version_id != body.question_version_id):
                        raise HTTPException(409, "提交编号已用于其他作答")
                    return {"id": existing.id, "status": existing.status, "score": existing.score}
            mapping = session.get(QuestionFileRecord, (workspace_id, body.question_id))
            if mapping and mapping.confirmed_version_id:
                if body.question_version_id != mapping.confirmed_version_id:
                    raise HTTPException(409, '请按当前不可变确认版重新载入作答')
                version = version_read(session, data_dir, workspace_id, mapping.confirmed_version_id)
                verify_version_assets(data_dir, version)
                document = FileQuestion.model_validate(version.content['question'])
            else:
                if body.question_version_id is not None:
                    raise HTTPException(409, '该题尚无此确认版，不能提交')
                document = QuestionDocument.model_validate(question.content)
            if body.question_revision is not None and body.question_revision != document.revision:
                raise HTTPException(409, "题目版本已改变，请重新载入题目")
            status, score = grade(document, body.response)
            attempt = Attempt(workspace_id=workspace_id, question_id=question.id, response=body.response, status=status,
                              score=score, created_at=datetime.now(timezone.utc).isoformat(),
                              question_revision=document.revision, request_id=body.request_id,
                              question_version_id=body.question_version_id)
            session.add(attempt)
            session.flush()
            return {"id": attempt.id, "status": status, "score": score}

    @app.get("/api/attempts", dependencies=auth)
    def default_attempts():
        return attempts("default")

    @app.get("/api/workspaces/{workspace_id}/attempts", dependencies=auth)
    def attempts(workspace_id: str):
        with Session(engine) as session:
            require_workspace(session, workspace_id)
            return workspace_history(session, workspace_id)

    @app.get("/api/player", dependencies=auth)
    def player():
        template = (Path(__file__).parent / "player.html").read_text(encoding="utf-8")
        return HTMLResponse(template.replace("__CAPABILITY__", capability))

    @app.api_route("/media/demo", methods=["GET", "HEAD"])
    def video(cap: str = ""):
        if not secrets.compare_digest(cap, capability):
            raise HTTPException(403, "Invalid media capability")
        if media is None or not media.is_file():
            raise HTTPException(404, "No local video configured")
        return FileResponse(media)

    app.include_router(import_router(engine, data_dir), dependencies=auth)
    app.include_router(markdown_notes.router(), dependencies=auth)
    app.include_router(learning_marks.router(), dependencies=auth)
    app.include_router(internal_links_router(learning_marks), dependencies=auth)
    app.include_router(learning_search_router(documents), dependencies=auth)
    app.include_router(library_router(engine, data_dir, question_files), dependencies=auth)
    app.include_router(learning_router(engine), dependencies=auth)
    app.include_router(records_router(engine), dependencies=auth)
    app.include_router(markdown_router(engine, data_dir), dependencies=auth)
    app.include_router(draft_router(engine, data_dir), dependencies=auth)
    media_api, media_public = media_routers(engine, data_dir)
    app.include_router(media_api, dependencies=auth)
    app.include_router(media_public)
    return app
