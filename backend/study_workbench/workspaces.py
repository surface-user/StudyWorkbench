import ipaddress
import json
import re
from datetime import datetime, timezone
from typing import Literal
from urllib.parse import urlsplit
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from .content import DEMO, SUBJECTIVE
from .db import DesktopState, Question, Workspace, WorkspaceNode, write_transaction

KNOWN_KINDS = {'question', 'web', 'player', 'import', 'study', 'resource', 'welcome'}


class DocumentState(BaseModel):
    model_config = ConfigDict(extra='forbid')
    version: Literal[1] = 1
    page: int = Field(default=1, ge=1, le=2000, strict=True)
    zoom: float = Field(default=1, ge=.25, le=4, allow_inf_nan=False)
    scroll: float = Field(default=0, ge=0, le=10000000, allow_inf_nan=False)
    mode: Literal['read', 'edit', 'question'] = 'read'
    representation: Literal['original', 'paginated'] = 'original'


class Tab(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(pattern=r"^[a-zA-Z0-9_-]{1,64}$")
    kind: Literal["question", "web", "player", "import", "study", "resource", "welcome"]
    url: str | None = Field(default=None, max_length=4096)
    draft: str = Field(default="", max_length=1024 * 1024)
    resource_item_id: str | None = Field(default=None, pattern=r'^[a-f0-9]{32}$')
    view_kind: Literal['document', 'web', 'media'] | None = None
    resource_name: str | None = Field(default=None, min_length=1, max_length=200)
    draft_base_sha256: str | None = Field(default=None, pattern=r'^[a-f0-9]{64}$')
    document_state: DocumentState | None = None
    question_draft: str = Field(default='', max_length=64000)

    @model_validator(mode="after")
    def allowed_fields(self):
        if self.kind == 'resource':
            if self.resource_item_id is None or self.view_kind is None:
                raise ValueError('Resource tabs require identity and view kind')
        elif any(value is not None for value in (self.resource_item_id, self.view_kind, self.resource_name)):
            raise ValueError('Only resource tabs have resource identity')
        document = self.kind == 'resource' and self.view_kind == 'document'
        if self.question_draft and not document:
            raise ValueError('Only document resource tabs have confirmed-question drafts')
        if self.kind == 'question' and len(self.draft) > 16000:
            raise ValueError('Question draft exceeds 16000 characters')
        if self.draft and self.kind != 'question' and not (document and self.draft_base_sha256):
            raise ValueError('Only question or based document drafts are saved')
        if len(self.draft.encode('utf-8')) > 1024 * 1024:
            raise ValueError('Document draft exceeds 1MiB UTF-8')
        if not document and (self.draft_base_sha256 is not None or self.document_state is not None):
            raise ValueError('Only document tabs have file state')
        if self.kind != "web" and not (self.kind == 'resource' and self.view_kind == 'web') and self.url is not None:
            raise ValueError("Only web tabs may contain URLs")
        if self.url is not None:
            parsed = urlsplit(self.url)
            host = parsed.hostname or ""
            if (parsed.scheme != "https" or not host or parsed.username is not None
                    or parsed.password is not None or parsed.port not in (None, 443)
                    or "." not in host or host.endswith((".", ".local", ".localhost", ".internal"))
                    or re.fullmatch(r"[0-9.]+", host)):
                raise ValueError("Only public HTTPS URLs are saved")
            try:
                ipaddress.ip_address(host)
            except ValueError:
                pass
            else:
                raise ValueError("IP literal URLs are not saved")
        return self


class UnknownTab(BaseModel):
    # Forward-compatible payloads are inert data; never dispatch them as known pages.
    model_config = ConfigDict(extra='allow')
    id: str = Field(pattern=r'^[a-zA-Z0-9_-]{1,64}$')
    kind: str = Field(min_length=1, max_length=64)

    @model_validator(mode='after')
    def opaque(self):
        if self.kind in KNOWN_KINDS:
            raise ValueError('Known tab types must pass strict validation')
        if len(json.dumps(self.model_dump(), ensure_ascii=False).encode('utf-8')) > 65536:
            raise ValueError('Unknown tab state exceeds preservation budget')
        return self


class Layout(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: Literal[1, 2] = 1
    tabs: list[Tab | UnknownTab] = Field(max_length=16)
    closed_tabs: list[Tab | UnknownTab] = Field(default_factory=list, max_length=10)
    active_tab_id: str | None

    @model_validator(mode="after")
    def references(self):
        if self.version == 1 and any(tab.kind in {'resource', 'welcome'} for tab in self.tabs + self.closed_tabs):
            raise ValueError('Resource and welcome tabs require layout v2')
        identities = [(tab.resource_item_id, tab.view_kind) for tab in self.tabs if tab.kind == 'resource']
        if len(set(identities)) != len(identities):
            raise ValueError('Open resource identities must be unique')
        ids = [tab.id for tab in self.tabs + self.closed_tabs]
        if len(set(ids)) != len(ids):
            raise ValueError("Tab IDs must be unique")
        if self.tabs and self.active_tab_id not in {tab.id for tab in self.tabs}:
            raise ValueError("Active tab must be open")
        if not self.tabs and self.active_tab_id is not None:
            raise ValueError("An empty layout has no active tab")
        return self


def initial_layout():
    return Layout(tabs=[], active_tab_id=None).model_dump()


class WorkspaceName(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=80)

    @field_validator("name")
    @classmethod
    def clean(cls, value):
        value = value.strip()
        if not value or any(ord(char) < 32 for char in value):
            raise ValueError("Enter a readable workspace name")
        return value


class Removal(BaseModel):
    model_config = ConfigDict(extra="forbid")
    confirm_name: str


class Selection(BaseModel):
    model_config = ConfigDict(extra="forbid")
    workspace_id: str


def require_workspace(session, workspace_id, *, archived=False):
    workspace = session.get(Workspace, workspace_id)
    if workspace is None or workspace.archived != archived:
        raise HTTPException(404, "工作空间不存在或已移除")
    return workspace


def describe(workspace):
    return {"id": workspace.id, "name": workspace.name, "archived": workspace.archived}


def unique_name(session, name, excluding=None):
    for workspace in session.scalars(select(Workspace).where(Workspace.archived.is_(False))):
        if workspace.id != excluding and workspace.name.casefold() == name.casefold():
            raise HTTPException(409, "已有同名工作空间")


def workspace_router(engine):
    router = APIRouter()

    @router.get("/api/workbench")
    def workbench():
        with Session(engine) as session, session.begin():
            # sqlite3 legacy mode does not begin a transaction for SELECT.
            session.connection().exec_driver_sql("BEGIN")
            spaces = list(session.scalars(select(Workspace).order_by(Workspace.created_at, Workspace.id)))
            return {"workspaces": [describe(w) for w in spaces if not w.archived],
                    "archived_workspaces": [describe(w) for w in spaces if w.archived],
                    "active_workspace_id": session.get(DesktopState, 1).active_workspace_id}

    @router.post("/api/workspaces")
    def create(body: WorkspaceName):
        with write_transaction(engine) as session:
            unique_name(session, body.name)
            workspace = Workspace(id=uuid4().hex, name=body.name, archived=False,
                                  created_at=datetime.now(timezone.utc).isoformat(), layout=initial_layout())
            session.add(workspace)
            session.flush()
            for content in (DEMO, SUBJECTIVE):
                session.add(Question(id=content["id"], workspace_id=workspace.id, content=content))
            session.get(DesktopState, 1).active_workspace_id = workspace.id
            return describe(workspace)

    @router.patch("/api/workspaces/{workspace_id}")
    def rename(workspace_id: str, body: WorkspaceName):
        with write_transaction(engine) as session:
            workspace = require_workspace(session, workspace_id)
            unique_name(session, body.name, workspace_id)
            workspace.name = body.name
            return describe(workspace)

    @router.delete("/api/workspaces/{workspace_id}")
    def remove(workspace_id: str, body: Removal):
        with write_transaction(engine) as session:
            workspace = require_workspace(session, workspace_id)
            if body.confirm_name != workspace.name:
                raise HTTPException(409, "确认名称与当前工作空间不一致")
            remaining = list(session.scalars(select(Workspace).where(
                Workspace.archived.is_(False), Workspace.id != workspace_id).order_by(Workspace.created_at)))
            if not remaining:
                raise HTTPException(409, "请至少保留一个工作空间")
            workspace.archived = True
            state = session.get(DesktopState, 1)
            if state.active_workspace_id == workspace_id:
                state.active_workspace_id = remaining[0].id
            return {"archived": True, "data_preserved": True}

    @router.post("/api/workspaces/{workspace_id}/restore")
    def restore(workspace_id: str):
        with write_transaction(engine) as session:
            workspace = require_workspace(session, workspace_id, archived=True)
            unique_name(session, workspace.name, workspace_id)
            workspace.archived = False
            return describe(workspace)

    @router.put("/api/active-workspace")
    def activate(body: Selection):
        with write_transaction(engine) as session:
            require_workspace(session, body.workspace_id)
            session.get(DesktopState, 1).active_workspace_id = body.workspace_id
            return {"workspace_id": body.workspace_id}

    @router.get("/api/workspaces/{workspace_id}/layout")
    def get_layout(workspace_id: str):
        with Session(engine) as session:
            return require_workspace(session, workspace_id).layout

    @router.put("/api/workspaces/{workspace_id}/layout")
    def save_layout(workspace_id: str, body: Layout):
        with write_transaction(engine) as session:
            workspace = require_workspace(session, workspace_id)
            for tab in body.tabs + body.closed_tabs:
                if tab.kind == 'resource':
                    node = session.get(WorkspaceNode, tab.resource_item_id)
                    if node is not None:
                        if node.workspace_id != workspace_id:
                            raise HTTPException(422, '资源标签不属于当前工作空间')
                        expected = {'link': 'web', 'media': 'media', 'resource': 'document'}.get(node.kind)
                        if tab.view_kind != expected:
                            raise HTTPException(422, '资源查看类型与节点不符')
            value = body.model_dump()
            for tab in value['tabs'] + value['closed_tabs']:
                if tab['kind'] in KNOWN_KINDS:
                    for key in ('draft_base_sha256', 'document_state'):
                        if tab[key] is None:
                            tab.pop(key)
                    if tab['kind'] != 'resource':
                        for key in ('resource_item_id', 'view_kind', 'resource_name'):
                            tab.pop(key)
            workspace.layout = value
            return workspace.layout

    return router
