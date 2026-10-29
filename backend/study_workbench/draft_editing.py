"""User corrections to unconfirmed question boundaries; source documents remain immutable."""
import base64
import copy
import io
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

from .db import ImportJob, MarkdownQuestion, Resource, write_transaction
from .imports import describe, image_size, persist_assets, read_resource, validate_attachments
from .question_protocol import Content
from .question_splitting import all_blocks, draft_revision
from .workspaces import require_workspace


class DraftEdit(BaseModel):
    model_config = ConfigDict(extra='forbid')
    expected_revision: str = Field(pattern=r'^[a-f0-9]{64}$')
    action: Literal['merge_next', 'split_block', 'split_region', 'share', 'rename']
    index: int = Field(ge=0, strict=True)
    position: int = Field(default=0, ge=0, strict=True)
    text_offset: int = Field(default=0, ge=0, strict=True)
    cut: float | None = Field(default=None, ge=0, le=1, allow_inf_nan=False)
    title: str = Field(default='拆分出的题目', min_length=1, max_length=240, pattern=r'\S')
    targets: list[int] = Field(default_factory=list, max_length=200)
    source_blocks: list[int] = Field(default_factory=list, max_length=200)


def cropped_draft(session, root, workspace_id, preview, original, regions):
    from PIL import Image

    pages = [b for b in preview['blocks'] if b['type'] == 'image']
    result = {**copy.deepcopy(original), 'blocks': [], 'regions': regions,
              'source_pages': sorted({r['page'] for r in regions}), 'text_status': 'manual_crop_image_only'}
    assets = []
    total = 0
    for region in regions:
        number = region['page']
        if not 1 <= number <= len(pages):
            raise HTTPException(422, '找不到原页图，请重新解析原件')
        resource = session.get(Resource, pages[number - 1]['attachment_id'])
        if resource is None or resource.workspace_id != workspace_id:
            raise HTTPException(422, '页图不属于当前工作空间')
        data = read_resource(root, resource)
        image_size(data)
        with Image.open(io.BytesIO(data)) as picture:
            left, top, right, bottom = region['box']
            box = (int(left * picture.width), int(top * picture.height),
                   min(picture.width, int(right * picture.width + .999)),
                   min(picture.height, int(bottom * picture.height + .999)))
            if box[2] <= box[0] or box[3] <= box[1]:
                raise HTTPException(422, '裁切区域过小')
            with picture.crop(box) as crop:
                out = io.BytesIO()
                crop.save(out, format='PNG')
        raw = out.getvalue()
        total += len(raw)
        if len(raw) > 8 * 1024 * 1024 or total > 64 * 1024 * 1024:
            raise HTTPException(413, '裁切图片超过预算，请缩小区域')
        identifier = uuid4().hex
        assets.append({'id': identifier, 'name': f'人工裁切-第{number}页.png', 'data': base64.b64encode(raw).decode()})
        result['blocks'].append({'type': 'image', 'attachment_id': identifier, 'alt': f'第{number}页人工裁切'})
    return result, assets


def draft_router(engine, root):
    router = APIRouter(prefix='/api/workspaces/{workspace_id}')

    @router.post('/imports/{job_id}/question-drafts/edit')
    def edit(workspace_id: str, job_id: str, body: DraftEdit):
        from sqlalchemy import select

        with write_transaction(engine) as session:
            require_workspace(session, workspace_id)
            job = session.get(ImportJob, job_id)
            if job is None or job.workspace_id != workspace_id:
                raise HTTPException(404, '导入任务不存在')
            if job.status != 'preview' or session.scalar(select(MarkdownQuestion.id).where(
                    MarkdownQuestion.import_job_id == job.id).limit(1)):
                raise HTTPException(409, '已入库或未就绪的批次不能修改拆题预览')
            preview = copy.deepcopy(job.preview)
            drafts = preview.get('question_drafts', [])
            if draft_revision(drafts) != body.expected_revision:
                raise HTTPException(409, '预览已更新，当前修改未保存，请重新打开最新预览')
            if body.index >= len(drafts):
                raise HTTPException(422, '候选题目不存在')
            current = drafts[body.index]
            assets = []
            if body.action == 'rename':
                current['title'] = body.title.strip()
            elif body.action == 'merge_next':
                if body.index + 1 >= len(drafts):
                    raise HTTPException(422, '当前题目后面没有可合并的题目')
                following = drafts.pop(body.index + 1)
                current['blocks'].extend(following['blocks'])
                current['regions'].extend(following['regions'])
                current['source_pages'] = sorted(set(current['source_pages'] + following['source_pages']))
                shared = {m['id']: m for m in current.get('shared_materials', []) + following.get('shared_materials', [])}
                current['shared_materials'] = list(shared.values())
            elif body.action == 'split_block':
                if current['regions']:
                    raise HTTPException(422, 'PDF请按页内位置裁切，不能用文字段落猜测图像边界')
                blocks = current['blocks']
                if body.position >= len(blocks):
                    raise HTTPException(422, '请选择有效分割位置')
                left, right = blocks[:body.position], blocks[body.position:]
                if body.text_offset:
                    block = right[0]
                    if block['type'] != 'text' or body.text_offset >= len(block['text']):
                        raise HTTPException(422, '文字分割位置无效')
                    left = left + [{**block, 'text': block['text'][:body.text_offset]}]
                    right = [{**block, 'text': block['text'][body.text_offset:]}] + right[1:]
                if not left or not right:
                    raise HTTPException(422, '拆分后两题都必须有内容')
                following = {**copy.deepcopy(current), 'title': body.title.strip(), 'blocks': right}
                current['blocks'] = left
                drafts.insert(body.index + 1, following)
            elif body.action == 'split_region':
                regions = current['regions']
                if body.position >= len(regions) or body.cut is None:
                    raise HTTPException(422, '请选择PDF页内的有效分割位置')
                region = regions[body.position]
                left_edge, top, right_edge, bottom = region['box']
                if not top < body.cut < bottom:
                    raise HTTPException(422, '分割线必须在当前题目区域内部')
                before = regions[:body.position] + [{**region, 'box': [left_edge, top, right_edge, body.cut]}]
                after = [{**region, 'box': [left_edge, body.cut, right_edge, bottom]}] + regions[body.position + 1:]
                left, first_assets = cropped_draft(session, root, workspace_id, preview, current, before)
                right, last_assets = cropped_draft(session, root, workspace_id, preview, current, after)
                right['title'] = body.title.strip()
                drafts[body.index:body.index + 1] = [left, right]
                assets = first_assets + last_assets
            elif body.action == 'share':
                if (not body.targets or not body.source_blocks or
                        any(type(i) is not int or not 0 <= i < len(drafts) for i in body.targets) or
                        any(type(i) is not int or not 0 <= i < len(preview['blocks']) for i in body.source_blocks)):
                    raise HTTPException(422, '请选择原资料内容段和目标题目')
                material = {'id': uuid4().hex, 'blocks': [copy.deepcopy(preview['blocks'][i])
                                                       for i in sorted(set(body.source_blocks))]}
                for i in set(body.targets):
                    drafts[i].setdefault('shared_materials', []).append(material)
            if len(drafts) > 200:
                raise HTTPException(422, '候选超过200题，请分批处理')
            try:
                for draft in drafts:
                    TypeAdapter(Content).validate_python(all_blocks(draft))
            except ValueError as error:
                raise HTTPException(422, '修改后的内容超出协议预算，原预览保留') from error
            preview['_assets'] = assets
            persist_assets(session, root, workspace_id, preview)
            for draft in drafts:
                validate_attachments(session, workspace_id, all_blocks(draft), root)
            job.preview = preview
            return describe(job, session.get(Resource, job.resource_id), preview=True)

    return router
