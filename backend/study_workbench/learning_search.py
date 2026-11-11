"""Bounded, read-only learning search. Results are identities, never file paths."""
from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import LargeBinary, cast, func, or_, select
from sqlalchemy.orm import Session

from .db import DocumentWorkfile, LearningMark, Note, Resource, WorkspaceNode
from .document_files import TEXT_LIMIT, digest, limited_view
from .imports import note_revision, resource_path
from .workspaces import require_workspace

FILE_LIMIT = 1000
BYTE_LIMIT = 16 * TEXT_LIMIT
DB_LIMIT = 10000


def note_text(value, depth=0):
    if depth > 16:
        raise ValueError('笔记结构过深')
    if isinstance(value, list):
        return '\n'.join(note_text(item, depth + 1) for item in value)
    if not isinstance(value, dict):
        raise ValueError('不支持的笔记结构')
    if value.get('type') not in {'text', 'latex', 'image', 'chart', 'table', 'attachment'}:
        raise ValueError('不支持的笔记块版本')
    pieces = [value[key] for key in ('text', 'tex', 'alt', 'caption', 'label') if isinstance(value.get(key), str)]
    pieces += [note_text(value[key], depth + 1) for key in ('headers', 'rows') if key in value]
    return '\n'.join(pieces)


def match_start(text, query):
    # Casefold may expand characters; map only until the first match for exact display offsets.
    folded = text.casefold()
    index = folded.find(query)
    if index < 0:
        return None
    consumed = start = 0
    for start, char in enumerate(text):
        consumed += len(char.casefold())
        if consumed > index:
            break
    return start


def snippet(text, query):
    start = match_start(text, query)
    if start is None:
        return None
    left, right = max(0, start - 60), min(len(text), start + 180)
    return ('…' if left else '') + text[left:right] + ('…' if right < len(text) else '')


def router(documents):
    routes = APIRouter(prefix='/api/workspaces/{workspace_id}')

    @routes.get('/learning-search')
    @limited_view
    def search(workspace_id: str, q: str = Query(min_length=1, max_length=200),
               offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100)):
        if not q.strip():
            raise HTTPException(422, '搜索词不能为空白')
        query = q.casefold()
        rows, reasons = [], []
        scanned = dict(file_note=0, text_resource=0, legacy_note=0, mark=0, bytes=0, unreadable=0)

        def reason(value):
            if value not in reasons:
                reasons.append(value)

        def collect(kind, identifier, title, text, *, cost=None, **version):
            size = len(text.encode('utf-8')) if cost is None else cost
            if scanned['bytes'] + size > BYTE_LIMIT:
                reason('达到16MiB文字预算，结果不完整')
                return False
            scanned['bytes'] += size
            summary = snippet(text, query)
            if summary is not None:
                target_kind = {'file_note': 'nodes', 'text_resource': 'nodes', 'legacy_note': 'notes', 'mark': 'marks'}[kind]
                rows.append(dict(kind=kind, id=identifier, title=title, snippet=summary,
                                 uri=f'studyworkbench://v1/workspaces/{workspace_id}/{target_kind}/{identifier}', **version))
            return True

        with Session(documents.engine) as session:
            session.connection().exec_driver_sql('BEGIN')
            require_workspace(session, workspace_id)
            files = select(WorkspaceNode).join(Resource, WorkspaceNode.resource_id == Resource.id).where(
                WorkspaceNode.workspace_id == workspace_id, WorkspaceNode.removed_at.is_(None),
                Resource.workspace_id == workspace_id, WorkspaceNode.kind == 'resource',
                or_(func.lower(Resource.original_name).endswith('.md'),
                    func.lower(Resource.original_name).endswith('.markdown'),
                    func.lower(Resource.original_name).endswith('.txt'))).order_by(WorkspaceNode.id).limit(FILE_LIMIT + 1)
            for node in session.scalars(files):
                if scanned['file_note'] + scanned['text_resource'] >= FILE_LIMIT:
                    reason('达到1000份MD/TXT文件预算，结果不完整')
                    break
                original = session.get(Resource, node.resource_id)
                kind = 'text_resource' if original.original_name.lower().endswith('.txt') else 'file_note'
                scanned[kind] += 1
                title_size = len(node.name.encode('utf-8')) + 1
                remaining = BYTE_LIMIT - scanned['bytes'] - title_size
                if remaining <= 0:
                    reason('达到16MiB文字预算，结果不完整')
                    break
                try:
                    work = session.get(DocumentWorkfile, node.id) if kind == 'file_note' else None
                    relative = work.relative_path if work else original.relative_path
                    with resource_path(documents.root, relative).open('rb') as handle:
                        data = handle.read(min(TEXT_LIMIT, remaining) + 1)
                    # Include unreadable/corrupt bytes in the budget; one probe byte detects overflow.
                    scanned['bytes'] += min(len(data) + title_size, BYTE_LIMIT - scanned['bytes'])
                    if len(data) > remaining:
                        reason('达到16MiB文字预算，结果不完整')
                        break
                    if len(data) > TEXT_LIMIT:
                        raise ValueError('文件超过1MiB')
                    if not work and (len(data) != original.size or digest(data) != original.sha256):
                        raise ValueError('原件内容校验失败')
                    content = data.decode('utf-8')
                except (HTTPException, OSError, UnicodeError, ValueError):
                    scanned['unreadable'] += 1
                    reason('部分MD/TXT文件缺失、损坏、非UTF-8或超限，结果不完整')
                    continue
                version = dict(content_sha256=digest(data))
                searchable = node.name + '\n' + content
                if kind == 'text_resource':
                    position = match_start(content, query)
                    if position is not None:
                        searchable = content
                        line = content.count('\n', 0, position) + 1
                        line_text = content.split('\n')[line - 1].removesuffix('\r')
                        version['anchor'] = dict(version=1, kind='text_line', workspace_id=workspace_id,
                            resource_item_id=node.id, content_sha256=version['content_sha256'],
                            line=line, line_sha256=digest(line_text.encode('utf-8')))
                if not collect(kind, node.id, node.name, searchable, cost=0, **version):
                    break
            old_notes = select(Note.id, func.length(cast(Note.content, LargeBinary))).where(
                Note.workspace_id == workspace_id).order_by(Note.id).limit(DB_LIMIT + 1)
            for identifier, size in session.execute(old_notes):
                if scanned['legacy_note'] >= DB_LIMIT:
                    reason('达到10000条旧笔记/书签预算，结果不完整')
                    break
                if size > BYTE_LIMIT - scanned['bytes']:
                    reason('旧笔记超出剩余16MiB预算，结果不完整')
                    break
                scanned['legacy_note'] += 1
                note = session.get(Note, identifier)
                try:
                    content = note_text(note.content)
                except ValueError:
                    scanned['unreadable'] += 1
                    reason('部分旧笔记结构不支持，结果不完整')
                    continue
                if not collect('legacy_note', note.id, note.title, note.title + '\n' + content,
                               cost=size + len(note.title.encode('utf-8')), revision=note_revision(note)):
                    break
            marks = select(LearningMark.id, LearningMark.title, LearningMark.note, LearningMark.revision).where(
                LearningMark.workspace_id == workspace_id, LearningMark.removed_at.is_(None)
            ).order_by(LearningMark.id).limit(DB_LIMIT + 1)
            for identifier, title, text, revision in session.execute(marks):
                if scanned['legacy_note'] + scanned['mark'] >= DB_LIMIT:
                    reason('达到10000条旧笔记/书签预算，结果不完整')
                    break
                scanned['mark'] += 1
                if not collect('mark', identifier, title, title + '\n' + text, revision=revision):
                    break
        rows.sort(key=lambda row: (row['kind'], row['id']))
        return dict(query=q, items=rows[offset:offset + limit], total=len(rows), offset=offset, limit=limit,
                    has_more=offset + limit < len(rows), truncated=bool(reasons), reasons=reasons, scanned=scanned,
                    scope='活动MD笔记文件当前正文、TXT资料全文、旧富内容笔记、未移除书签标题/备注；不含OCR')

    return routes
