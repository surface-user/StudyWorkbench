"""Internal identities only: never interpret a learning link as a filesystem or network URL."""
import re
from urllib.parse import unquote

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from .db import Note
from .document_files import limited_view
from .explorer import describe_node, node_in
from .imports import note_revision
from .workspaces import require_workspace

ID = r'[A-Za-z0-9][A-Za-z0-9._-]{0,127}'
URI = re.compile(r'^studyworkbench://v1/workspaces/([^/?#]+)/(?P<kind>nodes|marks|notes)/([^/?#]+)$')


def parse_link(value):
    if len(value) > 2048 or any(ord(c) < 33 or ord(c) == 127 for c in value):
        raise HTTPException(422, '内部链接格式无效')
    match = URI.fullmatch(value)
    if match is None:
        raise HTTPException(422, '仅支持studyworkbench内部链接v1，无参数或额外路径')
    workspace, kind, identifier = match.groups()
    try:
        workspace, identifier = (unquote(part, errors='strict') for part in (workspace, identifier))
    except UnicodeError as error:
        raise HTTPException(422, '内部链接编码无效') from error
    if any(not re.fullmatch(ID, part) or part in {'.', '..'} for part in (workspace, identifier)):
        raise HTTPException(422, '内部链接标识无效')
    return workspace, kind, identifier


class ResolveLink(BaseModel):
    model_config = ConfigDict(extra='forbid')
    uri: str = Field(strict=True, min_length=1, max_length=2048)


def router(marks):
    routes = APIRouter(prefix='/api/workspaces/{workspace_id}/internal-links')

    @routes.post('/resolve')
    @limited_view
    def resolve(workspace_id: str, body: ResolveLink):
        workspace, kind, identifier = parse_link(body.uri)
        if workspace != workspace_id:
            raise HTTPException(404, '链接不属于当前工作空间，请先切换空间')
        target = dict(workspace_id=workspace, kind=kind, id=identifier,
                      uri=f'studyworkbench://v1/workspaces/{workspace}/{kind}/{identifier}')
        with Session(marks.engine) as session:
            require_workspace(session, workspace)
            if kind == 'marks':
                item = marks.mark_in(session, workspace, identifier)
                if item.removed_at:
                    return dict(target=target, status='removed', message='书签已移除')
                location = marks.resolve(session, workspace, item.anchor)
                return dict(location, target=target, title=item.title)
            if kind == 'nodes':
                node = node_in(session, workspace, identifier)
                if node.removed_at:
                    return dict(target=target, status='removed', message='来源已从资源树移除')
                if node.kind == 'folder':
                    return dict(target=target, status='unsupported', message='内部链接暂不打开文件夹')
                resource = describe_node(session, marks.root, node)
                if resource['status'] != 'ready':
                    return dict(target=target, status='missing_content', message='资源缺失、未就绪或校验失败')
                return dict(target=target, status='valid', message='资源链接有效', resource=resource)
            note = session.get(Note, identifier)
            if note is None or note.workspace_id != workspace:
                raise HTTPException(404, '笔记不存在')
            return dict(target=target, status='valid', message='笔记链接有效',
                        note=dict(id=note.id, title=note.title, content=note.content,
                                  resource_id=note.resource_id, revision=note_revision(note)))

    return routes
