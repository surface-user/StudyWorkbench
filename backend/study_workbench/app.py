import secrets
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated

from alembic import command
from alembic.config import Config
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select, text
from sqlalchemy.orm import Session
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .content import DEMO, SUBJECTIVE
from .db import Attempt, Question, database


class Submission(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question_id: str
    response: dict = Field(default_factory=dict)


def create_app(data_dir: Path, token: str, media: Path | None = None):
    if len(token) < 32:
        raise ValueError("Session token must contain at least 32 characters")
    data_dir.mkdir(parents=True, exist_ok=True)
    engine = database(data_dir / "study.db")
    config = Config()
    config.set_main_option("script_location", str(Path(__file__).parent.parent / "migrations"))
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "head")
    with Session(engine) as session, session.begin():
        for content in (DEMO, SUBJECTIVE):
            if not session.get(Question, content["id"]):
                session.add(Question(id=content["id"], content=content))

    @asynccontextmanager
    async def lifespan(_):
        yield
        engine.dispose()

    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1"])
    capability = secrets.token_urlsafe(32)

    @app.middleware("http")
    async def boundaries(request: Request, call_next):
        if request.url.path.startswith("/api/") and request.headers.get("origin"):
            return JSONResponse({"detail": "Browser origin is not authorized"}, status_code=403)
        if request.headers.get("content-length", "0").isdigit():
            if int(request.headers.get("content-length", "0")) > 65536:
                return JSONResponse({"detail": "Request too large"}, status_code=413)
        return await call_next(request)

    def authorize(authorization: Annotated[str | None, Header()] = None):
        if not secrets.compare_digest(authorization or "", f"Bearer {token}"):
            raise HTTPException(401, "Unauthorized")

    auth = [Depends(authorize)]

    @app.get("/api/health", dependencies=auth)
    def health():
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return {"status": "ok", "api_version": 0, "database": "sqlite"}

    @app.get("/api/questions/demo", dependencies=auth)
    def demo():
        return DEMO

    @app.post("/api/attempts", dependencies=auth)
    def submit(body: Submission):
        with Session(engine) as session, session.begin():
            question = session.get(Question, body.question_id)
            if question is None:
                raise HTTPException(404, "Unknown question")
            score = None
            status = "pending_review"
            if question.content["kind"] == "single_choice":
                selected = body.response.get("selected")
                if (not isinstance(selected, list) or len(selected) != 1
                        or not isinstance(selected[0], str) or selected[0] not in {"a", "b"}):
                    raise HTTPException(422, "Select exactly one valid option")
                score = float(selected == question.content["answer"]["selected"])
                status = "graded"
            elif not isinstance(body.response.get("text"), str) or not body.response["text"].strip():
                raise HTTPException(422, "Written response required")
            attempt = Attempt(question_id=question.id, response=body.response, status=status,
                              score=score, created_at=datetime.now(timezone.utc).isoformat())
            session.add(attempt)
            session.flush()
            return {"id": attempt.id, "status": status, "score": score}

    @app.get("/api/attempts", dependencies=auth)
    def attempts():
        with Session(engine) as session:
            return [{"id": a.id, "question_id": a.question_id, "response": a.response,
                     "status": a.status, "score": a.score, "created_at": a.created_at}
                    for a in session.scalars(select(Attempt).order_by(Attempt.id))]

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

    return app
