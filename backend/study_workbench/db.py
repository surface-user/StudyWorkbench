from contextlib import contextmanager

from sqlalchemy import (
    JSON,
    Boolean,
    Float,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    String,
    create_engine,
    event,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column


class Base(DeclarativeBase):
    pass


class Workspace(Base):
    __tablename__ = "workspaces"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    archived: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[str] = mapped_column(String)
    layout: Mapped[dict] = mapped_column(JSON)


class DesktopState(Base):
    __tablename__ = "desktop_state"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    active_workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"))


class Question(Base):
    __tablename__ = "questions"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), primary_key=True)
    content: Mapped[dict] = mapped_column(JSON)


class Attempt(Base):
    __tablename__ = "attempts"
    __table_args__ = (ForeignKeyConstraint(
        ["workspace_id", "question_id"], ["questions.workspace_id", "questions.id"]),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    workspace_id: Mapped[str] = mapped_column(String, index=True)
    question_id: Mapped[str] = mapped_column(String)
    response: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[str] = mapped_column(String)
    question_revision: Mapped[int | None] = mapped_column(Integer, nullable=True)
    request_id: Mapped[str | None] = mapped_column(String, nullable=True)
    question_version_id: Mapped[str | None] = mapped_column(String, nullable=True)


class AttemptReview(Base):
    __tablename__ = "attempt_reviews"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    attempt_id: Mapped[int] = mapped_column(ForeignKey("attempts.id"), index=True)
    score: Mapped[float] = mapped_column(Float)
    feedback: Mapped[str] = mapped_column(String)
    created_at: Mapped[str] = mapped_column(String)


class LearningEvent(Base):
    __tablename__ = 'learning_events'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    attempt_id: Mapped[int] = mapped_column(ForeignKey('attempts.id'))
    request_id: Mapped[str] = mapped_column(String)
    content: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[str] = mapped_column(String)


class StudyTask(Base):
    __tablename__ = "study_tasks"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), index=True)
    title: Mapped[str] = mapped_column(String)
    question_ids: Mapped[list] = mapped_column(JSON)
    created_at: Mapped[str] = mapped_column(String)


class Resource(Base):
    __tablename__ = "resources"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), index=True)
    original_name: Mapped[str] = mapped_column(String)
    relative_path: Mapped[str] = mapped_column(String)
    sha256: Mapped[str] = mapped_column(String)
    size: Mapped[int] = mapped_column(Integer)
    mime: Mapped[str] = mapped_column(String)


class ImportJob(Base):
    __tablename__ = "import_jobs"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), index=True)
    resource_id: Mapped[str] = mapped_column(ForeignKey("resources.id"))
    parser_version: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String)
    error: Mapped[str | None] = mapped_column(String, nullable=True)
    preview: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[str] = mapped_column(String)


class PassageRecord(Base):
    __tablename__ = "passages"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), primary_key=True)
    content: Mapped[dict] = mapped_column(JSON)


class Note(Base):
    __tablename__ = "notes"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), index=True)
    resource_id: Mapped[str] = mapped_column(ForeignKey("resources.id"))
    title: Mapped[str] = mapped_column(String)
    content: Mapped[list] = mapped_column(JSON)


class MarkdownQuestion(Base):
    __tablename__ = "markdown_questions"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), index=True)
    import_job_id: Mapped[str] = mapped_column(ForeignKey("import_jobs.id"), index=True)
    ordinal: Mapped[int] = mapped_column(Integer)
    source_resource_id: Mapped[str] = mapped_column(ForeignKey("resources.id"))
    markdown_resource_id: Mapped[str] = mapped_column(ForeignKey("resources.id"))
    title: Mapped[str] = mapped_column(String)
    content: Mapped[dict] = mapped_column(JSON)


class MediaEntry(Base):
    __tablename__ = 'media_entries'
    id: Mapped[str] = mapped_column(String, primary_key=True)
    workspace_id: Mapped[str] = mapped_column(ForeignKey('workspaces.id'), index=True)
    title: Mapped[str] = mapped_column(String)
    relative_path: Mapped[str] = mapped_column(String)
    mime: Mapped[str] = mapped_column(String)
    size: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String)
    playback: Mapped[dict] = mapped_column(JSON)


class WorkspaceNode(Base):
    __tablename__ = 'workspace_nodes'
    id: Mapped[str] = mapped_column(String, primary_key=True)
    workspace_id: Mapped[str] = mapped_column(ForeignKey('workspaces.id'))
    parent_id: Mapped[str | None] = mapped_column(String, nullable=True)
    kind: Mapped[str] = mapped_column(String)
    name: Mapped[str] = mapped_column(String)
    name_key: Mapped[str] = mapped_column(String)
    resource_id: Mapped[str | None] = mapped_column(String, nullable=True)
    media_id: Mapped[str | None] = mapped_column(String, nullable=True)
    url: Mapped[str | None] = mapped_column(String, nullable=True)
    removed_at: Mapped[str | None] = mapped_column(String, nullable=True)


class ResourceAddJob(Base):
    __tablename__ = 'resource_add_jobs'
    id: Mapped[str] = mapped_column(String, primary_key=True)
    workspace_id: Mapped[str] = mapped_column(ForeignKey('workspaces.id'))
    parent_id: Mapped[str | None] = mapped_column(String, nullable=True)
    source_path: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String)
    cancel_requested: Mapped[bool] = mapped_column(Boolean, default=False)
    results: Mapped[list] = mapped_column(JSON, default=list)
    error: Mapped[str | None] = mapped_column(String, nullable=True)


class MediaDownloadJob(Base):
    __tablename__ = 'media_download_jobs'
    id: Mapped[str] = mapped_column(String, primary_key=True)
    workspace_id: Mapped[str] = mapped_column(ForeignKey('workspaces.id'))
    parent_id: Mapped[str | None] = mapped_column(String, nullable=True)
    request_id: Mapped[str] = mapped_column(String)
    source_url: Mapped[str] = mapped_column(String)
    name: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String)
    cancel_requested: Mapped[bool] = mapped_column(Boolean)
    attempt: Mapped[int] = mapped_column(Integer)
    relative_path: Mapped[str] = mapped_column(String)
    progress: Mapped[dict] = mapped_column(JSON)
    result: Mapped[dict] = mapped_column(JSON)
    error: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[str] = mapped_column(String)


class AnalysisReviewDraft(Base):
    __tablename__ = 'analysis_review_drafts'
    id: Mapped[str] = mapped_column(String, primary_key=True)
    workspace_id: Mapped[str] = mapped_column(ForeignKey('workspaces.id'))
    request_id: Mapped[str] = mapped_column(String)
    creation_content: Mapped[dict] = mapped_column(JSON)
    content: Mapped[dict] = mapped_column(JSON)
    payload_sha256: Mapped[str] = mapped_column(String)
    revision: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String)
    adoption: Mapped[dict] = mapped_column(JSON)
    result: Mapped[dict] = mapped_column(JSON)
    error: Mapped[str | None] = mapped_column(String, nullable=True)
    rejection_reason: Mapped[str] = mapped_column(String)
    created_at: Mapped[str] = mapped_column(String)


class AnalysisReviewRevision(Base):
    __tablename__ = 'analysis_review_revisions'
    draft_id: Mapped[str] = mapped_column(ForeignKey('analysis_review_drafts.id'), primary_key=True)
    revision: Mapped[int] = mapped_column(Integer, primary_key=True)
    snapshot: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[str] = mapped_column(String)


class DocumentWorkfile(Base):
    __tablename__ = 'document_workfiles'
    node_id: Mapped[str] = mapped_column(ForeignKey('workspace_nodes.id'), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(String)
    relative_path: Mapped[str] = mapped_column(String)
    indexed_sha256: Mapped[str] = mapped_column(String)


class MarkdownNoteCreation(Base):
    __tablename__ = 'markdown_note_creations'
    id: Mapped[str] = mapped_column(String, primary_key=True)
    workspace_id: Mapped[str] = mapped_column(ForeignKey('workspaces.id'))
    request_id: Mapped[str] = mapped_column(String)
    request: Mapped[dict] = mapped_column(JSON)
    resource_id: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String)
    error: Mapped[str | None] = mapped_column(String, nullable=True)


class DocumentSave(Base):
    __tablename__ = 'document_saves'
    id: Mapped[str] = mapped_column(String, primary_key=True)
    node_id: Mapped[str] = mapped_column(ForeignKey('document_workfiles.node_id'))
    old_sha256: Mapped[str] = mapped_column(String)
    new_sha256: Mapped[str] = mapped_column(String)
    backup_path: Mapped[str] = mapped_column(String)
    pending_path: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String)


class LearningMark(Base):
    __tablename__ = 'learning_marks'
    id: Mapped[str] = mapped_column(String, primary_key=True)
    workspace_id: Mapped[str] = mapped_column(String)
    resource_item_id: Mapped[str] = mapped_column(String)
    anchor: Mapped[dict] = mapped_column(JSON)
    title: Mapped[str] = mapped_column(String)
    note: Mapped[str] = mapped_column(String)
    revision: Mapped[int] = mapped_column(Integer)
    request_id: Mapped[str] = mapped_column(String)
    creation_content: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[str] = mapped_column(String)
    updated_at: Mapped[str] = mapped_column(String)
    removed_at: Mapped[str | None] = mapped_column(String, nullable=True)


class LearningMarkRevision(Base):
    __tablename__ = 'learning_mark_revisions'
    mark_id: Mapped[str] = mapped_column(String, primary_key=True)
    revision: Mapped[int] = mapped_column(Integer, primary_key=True)
    content: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[str] = mapped_column(String)


class LearningMarkNote(Base):
    __tablename__ = 'learning_mark_notes'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    workspace_id: Mapped[str] = mapped_column(String)
    mark_id: Mapped[str] = mapped_column(String)
    kind: Mapped[str] = mapped_column(String)
    file_node_id: Mapped[str | None] = mapped_column(String, nullable=True)
    legacy_note_id: Mapped[str | None] = mapped_column(String, nullable=True)


class DocumentPreview(Base):
    __tablename__ = 'document_previews'
    id: Mapped[str] = mapped_column(String, primary_key=True)
    workspace_id: Mapped[str] = mapped_column(String)
    node_id: Mapped[str] = mapped_column(ForeignKey('workspace_nodes.id'))
    source_resource_id: Mapped[str] = mapped_column(ForeignKey('resources.id'))
    source_sha256: Mapped[str] = mapped_column(String)
    runtime_fingerprint: Mapped[str] = mapped_column(String)
    converter_version: Mapped[str] = mapped_column(String)
    options_hash: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String)
    cancel_requested: Mapped[bool] = mapped_column(Boolean)
    relative_pdf: Mapped[str] = mapped_column(String)
    pdf_sha256: Mapped[str | None] = mapped_column(String, nullable=True)
    pdf_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[str] = mapped_column(String)


class QuestionFileRecord(Base):
    __tablename__ = 'question_files'
    workspace_id: Mapped[str] = mapped_column(String, primary_key=True)
    question_id: Mapped[str] = mapped_column(String, primary_key=True)
    node_id: Mapped[str] = mapped_column(String)
    origin_kind: Mapped[str] = mapped_column(String)
    origin_id: Mapped[str] = mapped_column(String)
    confirmed_version_id: Mapped[str | None] = mapped_column(String, nullable=True)


class QuestionVersion(Base):
    __tablename__ = 'question_versions'
    id: Mapped[str] = mapped_column(String, primary_key=True)
    workspace_id: Mapped[str] = mapped_column(String)
    question_id: Mapped[str] = mapped_column(String)
    revision: Mapped[int] = mapped_column(Integer)
    markdown_sha256: Mapped[str] = mapped_column(String)
    content_sha256: Mapped[str] = mapped_column(String)
    relative_path: Mapped[str] = mapped_column(String)
    content: Mapped[dict] = mapped_column(JSON)
    attachments: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[str] = mapped_column(String)


def database(path):
    engine = create_engine("sqlite:///" + path.as_posix(), connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def configure(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA busy_timeout=5000")

    return engine


@contextmanager
def write_transaction(engine):
    with Session(engine) as session, session.begin():
        # Acquire the SQLite writer before checking names, archive counts or scope.
        session.connection().exec_driver_sql("BEGIN IMMEDIATE")
        yield session
