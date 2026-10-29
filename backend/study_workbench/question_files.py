"""Explicit Markdown confirmation, immutable snapshots, and legacy file conversion."""
import base64
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .db import (
    DocumentWorkfile,
    ImportJob,
    MarkdownQuestion,
    PassageRecord,
    Question,
    QuestionFileRecord,
    QuestionVersion,
    Resource,
    write_transaction,
)
from .document_files import digest, text_bytes, write_new
from .explorer import describe_node, insert_node, node_in, relative_node
from .imports import image_size, read_resource, resource_path, source_claims, validate_attachments
from .question_files_format import FileQuestion, QuestionFile, parse_file, serialize_file
from .question_splitting import all_blocks
from .workspaces import require_workspace

ASSET_LIMIT = 64 * 1024 * 1024


def json_hash(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False).encode()).hexdigest()


def version_read(session, root, workspace, identifier):
    require_workspace(session, workspace)
    item = session.get(QuestionVersion, identifier)
    if item is None or item.workspace_id != workspace:
        raise HTTPException(404, '确认版本不存在')
    if json_hash({'content': item.content, 'attachments': item.attachments}) != item.content_sha256:
        raise HTTPException(409, '确认版元数据校验失败，历史保留')
    raw = text_bytes(root, item.relative_path)
    if digest(raw) != item.markdown_sha256:
        raise HTTPException(409, '确认版Markdown快照校验失败，历史保留')
    FileQuestion.model_validate(item.content['question'])
    return item


def version_view(item):
    return dict(id=item.id, question_id=item.question_id, revision=item.revision,
                markdown_sha256=item.markdown_sha256, content_sha256=item.content_sha256,
                created_at=item.created_at, **item.content)


def snapshot_asset(root, item, entry):
    path = resource_path(root, str(Path(item.relative_path).parent / entry['path']))
    try:
        with path.open('rb') as handle:
            data = handle.read(16 * 1024 * 1024 + 1)
    except OSError as error:
        raise HTTPException(409, '确认版附件缺失；历史关系保留') from error
    if len(data) != entry['size'] or digest(data) != entry['sha256']:
        raise HTTPException(409, '确认版附件校验失败；历史关系保留')
    return data


def verify_version_assets(root, item):
    for entry in item.attachments.values():
        snapshot_asset(root, item, entry)


def current_question_view(session, root, question):
    mapping = session.get(QuestionFileRecord, (question.workspace_id, question.id))
    if mapping is None or mapping.confirmed_version_id is None:
        return question.content
    item = version_read(session, root, question.workspace_id, mapping.confirmed_version_id)
    return dict(item.content['question'], confirmed_version_id=item.id, resource_item_id=mapping.node_id)


def explicit_true(value):
    if value is not True:
        raise ValueError('必须显式确认true')
    return value


class ConfirmFile(BaseModel):
    model_config = ConfigDict(extra='forbid')
    expected_sha256: str = Field(pattern=r'^[a-f0-9]{64}$')
    expected_version_id: str | None = Field(pattern=r'^[a-f0-9]{32}$')
    confirm: Literal[True]
    _confirm = field_validator('confirm', mode='before')(explicit_true)


class ConvertFile(BaseModel):
    model_config = ConfigDict(extra='forbid')
    expected_source_sha256: str = Field(pattern=r'^[a-f0-9]{64}$')
    expected_preview_sha256: str = Field(pattern=r'^[a-f0-9]{64}$')
    confirm: Literal[True]
    _confirm = field_validator('confirm', mode='before')(explicit_true)


def attachment_ids(value):
    result = set()
    def visit(node):
        if isinstance(node, dict):
            for key, child in node.items():
                if key in {'attachment_id', 'data_attachment_id'}:
                    result.add(child)
                else:
                    visit(child)
        elif isinstance(node, list):
            for child in node:
                visit(child)
    visit(value)
    return result


class QuestionFiles:
    def __init__(self, documents):
        self.documents = documents
        self.engine, self.root = documents.engine, documents.root

    def assets(self, session, workspace, file, node=None):
        values, total = {}, 0
        content = file.model_dump(mode='json')
        for identifier in attachment_ids([content['question'], content['passage']]):
            description = file.attachments.get(identifier)
            if description is None:
                raise HTTPException(422, '附件缺少相对路径/hash描述')
            target_id = relative_node(session, workspace, node, description.path).resource_id if node else identifier
            resource = session.get(Resource, target_id)
            if resource is None or resource.workspace_id != workspace:
                raise HTTPException(422, '附件不属于本工作空间')
            if resource.size > 16 * 1024 * 1024:
                raise HTTPException(413, '题目单个附件最多16MiB')
            total += resource.size
            if total > ASSET_LIMIT:
                raise HTTPException(413, '题目附件总量最多64MiB')
            if resource.sha256 != description.sha256 or resource.mime != description.mime:
                raise HTTPException(409, '附件内容/类型已变化，请重新核对')
            data = read_resource(self.root, resource)
            if resource.mime in {'image/png', 'image/jpeg'} and image_size(data) != resource.mime:
                raise HTTPException(422, '附件真实图片类型与登记类型不一致，请核对原文件')
            values[identifier] = (resource, data)
        replacements = {key: value[0].id for key, value in values.items()}
        def rebind(value):
            if isinstance(value, dict):
                return {key: replacements[child] if key in {'attachment_id', 'data_attachment_id'} else rebind(child)
                        for key, child in value.items()}
            return [rebind(child) for child in value] if isinstance(value, list) else value
        compiled = rebind({'question': content['question'], 'passage': content['passage']})
        compiled['title'] = file.title
        validate_attachments(session, workspace, compiled, self.root)
        return compiled, values

    def prepare(self, session, workspace, node_id):
        node, original, suffix, _, raw = self.documents.source(session, workspace, node_id)
        if suffix not in {'.md', '.markdown'}:
            raise HTTPException(422, '题目文件必须为Markdown')
        try:
            file = parse_file(raw.decode('utf-8-sig'))
        except (ValueError, UnicodeError) as error:
            raise HTTPException(422, '题目文件格式无效或暂不支持；原文件与草稿保留：' + str(error)[:180]) from error
        mapping = session.get(QuestionFileRecord, (workspace, file.question.id))
        other = session.scalar(select(QuestionFileRecord).where(
            QuestionFileRecord.workspace_id == workspace, QuestionFileRecord.node_id == node_id))
        if mapping and mapping.node_id != node_id or other and other.question_id != file.question.id:
            raise HTTPException(409, '题目ID已映射到另一文件，或映射后的ID已被改写；不会自动合并')
        existing = session.get(Question, (file.question.id, workspace))
        if existing and mapping is None:
            raise HTTPException(409, '已有同ID旧题目，请从该旧题目的显式转换入口建立映射')
        if existing and mapping and not mapping.confirmed_version_id and mapping.origin_kind != 'question-json':
            raise HTTPException(409, '另一旧题目占用了此ID，不能覆盖标准答案')
        compiled, assets = self.assets(session, workspace, file, node)
        warnings = ['文件中的来源验证声明不会授予官方/人工验证状态']
        for record in [compiled['question'], compiled['passage']]:
            if record:
                source = record['source']
                claimed = source.get('original_resource_id')
                resource = session.get(Resource, claimed) if claimed else None
                source_claims(source, resource.id if resource and resource.workspace_id == workspace else original.id)
        parent = file.question.parent_question_id
        visited = {file.question.id}
        while parent:
            if parent in visited:
                raise HTTPException(422, '题目来源关系成环')
            visited.add(parent)
            record = session.get(Question, (parent, workspace))
            if record is None:
                raise HTTPException(422, '父题必须已存在于同工作空间')
            parent = record.content.get('parent_question_id')
        FileQuestion.model_validate(compiled['question'])
        return node, file, raw, mapping, compiled, assets, warnings

    def inspect(self, workspace, node_id):
        with self.documents.lock, Session(self.engine) as session:
            require_workspace(session, workspace)
            node_in(session, workspace, node_id)
            known = session.scalar(select(QuestionFileRecord).where(
                QuestionFileRecord.workspace_id == workspace, QuestionFileRecord.node_id == node_id))
            previous = version_read(session, self.root, workspace, known.confirmed_version_id) if known and known.confirmed_version_id else None
            try:
                prepared = self.prepare(session, workspace, node_id)
            except HTTPException as error:
                if previous is None or error.status_code not in {404, 409, 413, 422}:
                    raise
                return dict(resource_item_id=node_id, title=previous.content.get('title', previous.content['question']['source']['title']), sha256=None,
                            question=previous.content['question'], passage=previous.content['passage'],
                            warnings=['当前文件未通过检查：' + str(error.detail)[:200],
                                      '仅显示上次确认版；当前文件/相对附件未被自动修复或重新发布'],
                            confirmed_version_id=previous.id, status='invalid_current', confirmed=version_view(previous))
            node, file, raw, mapping, compiled, _, warnings = prepared
            current = version_read(session, self.root, workspace, mapping.confirmed_version_id) if mapping and mapping.confirmed_version_id else None
            return dict(resource_item_id=node.id, title=file.title, sha256=digest(raw),
                        question=compiled['question'], passage=compiled['passage'], warnings=warnings,
                        confirmed_version_id=current.id if current else None,
                        status='confirmed' if current and current.markdown_sha256 == digest(raw) else 'unconfirmed',
                        confirmed=version_view(current) if current else None)

    def confirm(self, workspace, node_id, body):
        with self.documents.lock, write_transaction(self.engine) as session:
            node, file, raw, mapping, compiled, assets, _ = self.prepare(session, workspace, node_id)
            if digest(raw) != body.expected_sha256:
                raise HTTPException(409, '题目文件已改变，请重新预览确认')
            current = mapping.confirmed_version_id if mapping else None
            if current != body.expected_version_id:
                # A successful identical retry is safe, but never overwrite a later confirmation.
                version = version_read(session, self.root, workspace, current) if current else None
                if version and version.markdown_sha256 == body.expected_sha256:
                    verify_version_assets(self.root, version)
                    return version_view(version)
                raise HTTPException(409, '确认版本已变化，请重新预览')
            if current:
                previous = version_read(session, self.root, workspace, current)
                if previous.markdown_sha256 == digest(raw):
                    verify_version_assets(self.root, previous)
                    return version_view(previous)
            q = session.get(Question, (file.question.id, workspace))
            revision = max(q.content['revision'] if q else 0, session.scalar(select(func.max(QuestionVersion.revision)).where(
                QuestionVersion.workspace_id == workspace, QuestionVersion.question_id == file.question.id)) or 0) + 1
            compiled['question']['revision'] = revision
            if q is None:
                q = Question(id=file.question.id, workspace_id=workspace, content=compiled['question'])
                session.add(q)
            else:
                q.content = compiled['question']
            if mapping is None:
                mapping = QuestionFileRecord(workspace_id=workspace, question_id=file.question.id, node_id=node.id,
                                             origin_kind='file', origin_id=node.id, confirmed_version_id=None)
                session.add(mapping)
            session.flush()
            identifier = uuid4().hex
            directory = f'workspaces/{workspace}/question-versions/{identifier}'
            manifest = {key: dict(resource_id=resource.id, sha256=resource.sha256,
                                  mime=resource.mime, size=resource.size, path=file.attachments[key].path)
                        for key, (resource, _) in assets.items()}
            content_hash = json_hash({'content': compiled, 'attachments': manifest})
            # Retained receipt explains orphaned files if the process exits before SQLite commit.
            receipt = dict(id=identifier, workspace_id=workspace, question_id=file.question.id,
                           markdown_sha256=digest(raw), content_sha256=content_hash, content=compiled, attachments=manifest)
            write_new(resource_path(self.root, directory + '/receipt.json'), json.dumps(
                receipt, ensure_ascii=False, allow_nan=False).encode())
            write_new(resource_path(self.root, directory + '/question.md'), raw)
            for key, (_, data) in assets.items():
                write_new(resource_path(self.root, directory + '/' + manifest[key]['path']), data)
            if digest(self.documents.source(session, workspace, node_id)[-1]) != body.expected_sha256:
                raise HTTPException(409, '文件在确认期间改变，快照字节保留但未发布')
            item = QuestionVersion(id=identifier, workspace_id=workspace, question_id=file.question.id, revision=revision,
                                   markdown_sha256=digest(raw), content_sha256=content_hash,
                                   relative_path=directory + '/question.md', content=compiled, attachments=manifest,
                                   created_at=datetime.now(timezone.utc).isoformat())
            if digest(text_bytes(self.root, item.relative_path)) != item.markdown_sha256:
                raise HTTPException(409, '新确认版Markdown落盘校验失败，未发布，失败字节保留')
            verify_version_assets(self.root, item)
            session.add(item)
            session.flush()
            mapping.confirmed_version_id = item.id
            return version_view(item)

    def legacy(self, session, workspace, identifier, kind):
        require_workspace(session, workspace)
        mapping = session.get(QuestionFileRecord, (workspace, identifier))
        if mapping:
            if kind == 'markdown-question' and (mapping.origin_kind, mapping.origin_id) != (kind, identifier):
                raise HTTPException(409, '旧MD与另一题目同ID，不能自动合并')
            return dict(resource_item_id=mapping.node_id, status='mapped')
        provenance = None
        if kind == 'question-json':
            record = session.get(Question, (identifier, workspace))
            if record is None:
                raise HTTPException(404, '旧题目不存在')
            question = record.content
            passage_record = session.get(PassageRecord, (question['passage_id'], workspace)) if question.get('passage_id') else None
            if question.get('passage_id') and passage_record is None:
                raise HTTPException(409, '旧阅读材料缺失，原记录保留，不能伪造内容')
            passage = passage_record.content if passage_record else None
            source_hash = json_hash({'question': question, 'passage': passage})
            title = question['source']['title']
        else:
            record = session.get(MarkdownQuestion, identifier)
            if record is None or record.workspace_id != workspace:
                raise HTTPException(404, '旧Markdown题目不存在')
            if session.get(Question, (identifier, workspace)):
                raise HTTPException(409, '旧MD与旧JSON题目同ID，请先解决冲突，不能自动合并')
            resource = session.get(Resource, record.markdown_resource_id)
            source = session.get(Resource, record.source_resource_id)
            if resource is None or source is None or resource.workspace_id != workspace or source.workspace_id != workspace:
                raise HTTPException(409, '旧MD来源关系缺失或跨空间，不能转换')
            source_hash = digest(read_resource(self.root, resource))
            job = session.get(ImportJob, record.import_job_id)
            provenance = {key: value for key, value in record.content.items() if key not in {'blocks', 'shared_materials'}}
            provenance.update(original_markdown_resource_id=resource.id, original_markdown_sha256=resource.sha256,
                              original_filename=source.original_name, original_sha256=source.sha256,
                              parser_version=job.parser_version if job else None,
                              shared_materials=[{key: value for key, value in material.items() if key != 'blocks'}
                                                for material in record.content.get('shared_materials', [])])
            title, passage = record.title, None
            question = dict(schema_version=1, id=identifier, revision=1, subject='未分类', kind='subjective',
                            stem=all_blocks(record.content), options=[], answer=None,
                            explanation=[dict(type='text', text='未提供解析')], knowledge_points=[],
                            source=dict(kind='imported', title=title, original_resource_id=record.source_resource_id,
                                        verification='unverified'))
        FileQuestion.model_validate(question)
        descriptors = {}
        extensions = {'image/png': '.png', 'image/jpeg': '.jpg', 'text/plain': '.txt', 'application/json': '.json',
                      'application/pdf': '.pdf', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document': '.docx'}
        total = 0
        for key in attachment_ids([question, passage]):
            resource = session.get(Resource, key)
            if resource is None or resource.workspace_id != workspace:
                raise HTTPException(422, '旧题目附件缺失或跨空间，不能转换')
            total += resource.size
            if resource.size > 16 * 1024 * 1024 or total > ASSET_LIMIT:
                raise HTTPException(413, '题目附件超过单个16MiB/合计64MiB预算')
            descriptors[key] = dict(path='assets/' + key + extensions[resource.mime],
                                    sha256=resource.sha256, mime=resource.mime)
        validate_attachments(session, workspace, [question, passage], self.root)
        file = QuestionFile(title=title.replace('\r', ' ').replace('\n', ' '), question=question, passage=passage, attachments=descriptors,
                            legacy_origin={'kind': kind, 'id': identifier}, legacy_provenance=provenance)
        markdown = serialize_file(file)
        return dict(status='preview', markdown=markdown, source_sha256=source_hash, preview_sha256=digest(markdown.encode()),
                    question=file.question.model_dump(mode='json'), passage=passage,
                    warning='仅创建新的编辑文件；不覆盖旧JSON/MD，不推断答案；发布确认版仍需另行确认')

    def create_legacy(self, workspace, identifier, kind, body):
        with self.documents.lock, write_transaction(self.engine) as session:
            value = self.legacy(session, workspace, identifier, kind)
            if value['status'] == 'mapped':
                return describe_node(session, self.root, node_in(session, workspace, value['resource_item_id']))
            if (body.expected_source_sha256 != value['source_sha256'] or
                    body.expected_preview_sha256 != value['preview_sha256']):
                raise HTTPException(409, '旧内容/转换预览已变化，原件保留')
            file = parse_file(value['markdown'])
            _, assets = self.assets(session, workspace, file)
            display_name = '题目-' + re.sub(r'[\x00-\x1f<>:"/\\|?*]', '_', file.title).rstrip(' .')[:150]
            folder = insert_node(session, workspace, None, display_name, 'folder')
            asset_folder = insert_node(session, workspace, folder.id, 'assets', 'folder') if assets else None
            directory = f'workspaces/{workspace}/question-files/{uuid4().hex}'
            raw = value['markdown'].encode()
            relative = directory + '/question.md'
            write_new(resource_path(self.root, relative), raw)
            for key, (resource, data) in assets.items():
                name = Path(file.attachments[key].path).name
                write_new(resource_path(self.root, directory + '/' + file.attachments[key].path), data)
                insert_node(session, workspace, asset_folder.id, name, 'resource', resource_id=resource.id)
            resource = session.scalar(select(Resource).where(Resource.workspace_id == workspace, Resource.sha256 == digest(raw)))
            if resource is None:
                resource = Resource(id=uuid4().hex, workspace_id=workspace, original_name=display_name + '.md',
                                    relative_path=relative, sha256=digest(raw), size=len(raw), mime='text/markdown')
                session.add(resource)
                session.flush()
            node = insert_node(session, workspace, folder.id, display_name + '.md', 'resource', resource_id=resource.id)
            work_path = directory + '/current.md'
            write_new(resource_path(self.root, work_path), raw)
            session.add(DocumentWorkfile(node_id=node.id, workspace_id=workspace, relative_path=work_path, indexed_sha256=digest(raw)))
            session.add(QuestionFileRecord(workspace_id=workspace, question_id=identifier, node_id=node.id,
                                          origin_kind=kind, origin_id=identifier, confirmed_version_id=None))
            return describe_node(session, self.root, node)

    def router(self):
        router = APIRouter(prefix='/api/workspaces/{workspace_id}')

        @router.get('/nodes/{node_id}/question-file')
        def inspect(workspace_id: str, node_id: str):
            return self.inspect(workspace_id, node_id)

        @router.post('/nodes/{node_id}/question-file/confirm')
        def confirm(workspace_id: str, node_id: str, body: ConfirmFile):
            return self.confirm(workspace_id, node_id, body)

        @router.get('/question-versions/{version_id}')
        def version(workspace_id: str, version_id: str):
            with Session(self.engine) as session:
                return version_view(version_read(session, self.root, workspace_id, version_id))

        @router.get('/question-versions/{version_id}/assets/{resource_id}')
        def asset(workspace_id: str, version_id: str, resource_id: str):
            with Session(self.engine) as session:
                item = version_read(session, self.root, workspace_id, version_id)
                entry = next((v for v in item.attachments.values() if v['resource_id'] == resource_id), None)
                if entry is None or entry['mime'] not in {'image/png', 'image/jpeg'}:
                    raise HTTPException(404, '确认版图片不存在')
                data = snapshot_asset(self.root, item, entry)
                image_size(data)
                return dict(image_base64=base64.b64encode(data).decode())

        @router.get('/questions/{question_id}/file-preview')
        def question_preview(workspace_id: str, question_id: str):
            with Session(self.engine) as session:
                return self.legacy(session, workspace_id, question_id, 'question-json')

        @router.post('/questions/{question_id}/file')
        def question_file(workspace_id: str, question_id: str, body: ConvertFile):
            return self.create_legacy(workspace_id, question_id, 'question-json', body)

        @router.get('/question-markdown/{question_id}/file-preview')
        def markdown_preview(workspace_id: str, question_id: str):
            with Session(self.engine) as session:
                return self.legacy(session, workspace_id, question_id, 'markdown-question')

        @router.post('/question-markdown/{question_id}/file')
        def markdown_file(workspace_id: str, question_id: str, body: ConvertFile):
            return self.create_legacy(workspace_id, question_id, 'markdown-question', body)

        return router

    def export(self, session, workspace, write):
        results, metadata_size = [], 0
        for mapping in session.scalars(select(QuestionFileRecord).where(
                QuestionFileRecord.workspace_id == workspace).order_by(QuestionFileRecord.question_id)):
            node, _, _, _, raw = self.documents.source(session, workspace, mapping.node_id)
            base = f'question-files/{mapping.node_id}'
            write(base + '/question.md', raw)
            entry = dict(question_id=mapping.question_id, resource_item_id=mapping.node_id,
                         current_sha256=digest(raw), confirmed_version_id=mapping.confirmed_version_id,
                         path=base + '/question.md', versions=[])
            try:
                file = parse_file(raw.decode('utf-8-sig'))
                _, assets = self.assets(session, workspace, file, node)
            except (ValueError, UnicodeError):
                entry['status'] = 'invalid_current_file_retained'
            else:
                entry['status'] = 'current_file'
                for key, (_, data) in assets.items():
                    write(base + '/' + file.attachments[key].path, data)
            for item in session.scalars(select(QuestionVersion).where(
                    QuestionVersion.workspace_id == workspace, QuestionVersion.question_id == mapping.question_id
                    ).order_by(QuestionVersion.revision)):
                item = version_read(session, self.root, workspace, item.id)
                version_base = base + '/versions/' + item.id
                write(version_base + '/question.md', text_bytes(self.root, item.relative_path))
                for asset in item.attachments.values():
                    data = snapshot_asset(self.root, item, asset)
                    write(version_base + '/' + asset['path'], data)
                value = dict(version_view(item), attachments=item.attachments, path=version_base + '/question.md')
                metadata_size += len(json.dumps(value, ensure_ascii=False).encode())
                if metadata_size > 32 * 1024 * 1024:
                    raise HTTPException(413, '题目文件确认版元数据超过32MiB导出预算')
                entry['versions'].append(value)
            metadata_size += len(json.dumps({k: v for k, v in entry.items() if k != 'versions'}).encode())
            if metadata_size > 32 * 1024 * 1024:
                raise HTTPException(413, '题目文件元数据超过导出预算')
            results.append(entry)
        return results
