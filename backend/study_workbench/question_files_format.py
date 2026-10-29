"""Readable, bounded QuestionFile v1; old QuestionDocument v1 remains strict."""
import html
import json
import re
from typing import Annotated
from urllib.parse import quote

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, field_validator, model_validator

from .question_protocol import (
    ChoiceAnswer,
    FillAnswer,
    Passage,
    QuestionDocument,
    ResourceId,
    ShortText,
    WrittenAnswer,
)

LIMIT = 1024 * 1024
LABEL = '~~~study-workbench-question-v1\n'
END_BLOCK = '\n<!-- swq:endblock -->\n\n'


class FileQuestion(QuestionDocument):
    answer: ChoiceAnswer | FillAnswer | WrittenAnswer | None
    knowledge_points: Annotated[list[ShortText], Field(max_length=100)]
    blank_ids: list[ResourceId] = Field(default_factory=list, max_length=30)

    @model_validator(mode='after')
    def answer_matches_kind(self):
        if self.answer is not None:
            super().answer_matches_kind()
        else:
            kind = self.response_kind if self.kind == 'reading_question' else self.kind
            if (self.kind == 'reading_question' and (self.passage_id is None or self.response_kind is None)
                    or self.kind != 'reading_question' and self.response_kind is not None
                    or self.parent_question_id == self.id):
                raise ValueError('题型/阅读材料/父题关系无效')
            ids = [option.id for option in self.options]
            if kind in {'single_choice', 'multiple_choice'}:
                if len(ids) < 2 or len(ids) != len(set(ids)):
                    raise ValueError('无答案选择题也必须有至少两个独立选项')
            elif self.options:
                raise ValueError('非选择题不能带选项')
            if kind == 'fill_blank' and not self.blank_ids:
                raise ValueError('无答案填空题必须声明空格ID')
        kind = self.response_kind if self.kind == 'reading_question' else self.kind
        expected = [b.id for b in self.answer.blanks] if isinstance(self.answer, FillAnswer) else self.blank_ids
        if (len(self.blank_ids) != len(set(self.blank_ids)) or
                kind != 'fill_blank' and self.blank_ids or self.blank_ids and self.blank_ids != expected):
            raise ValueError('空格ID重复或与题型/答案不一致')
        return self


class FileAttachment(BaseModel):
    model_config = ConfigDict(extra='forbid')
    path: str = Field(min_length=1, max_length=240)
    sha256: str = Field(pattern=r'^[a-f0-9]{64}$')
    mime: str = Field(max_length=200)

    @field_validator('path')
    @classmethod
    def portable(cls, value):
        if not re.fullmatch(r'assets/[A-Za-z0-9][A-Za-z0-9._-]{0,150}', value) or '..' in value:
            raise ValueError('附件须为assets目录内的单个相对文件，不接受网络或磁盘路径')
        return value


class QuestionFile(BaseModel):
    model_config = ConfigDict(extra='allow')
    title: ShortText
    question: FileQuestion
    attachments: dict[ResourceId, FileAttachment] = Field(default_factory=dict, max_length=200)
    passage: Passage | None = None

    @model_validator(mode='after')
    def relations(self):
        if set(self.model_extra) & {'format_version', 'option_ids'}:
            raise ValueError('扩展字段不能覆盖格式控制字段')
        if '\n' in self.title or '\r' in self.title:
            raise ValueError('标题只允许一行')
        if (self.question.passage_id is None) != (self.passage is None):
            raise ValueError('阅读题必须携带共享材料快照')
        if self.passage and self.passage.id != self.question.passage_id:
            raise ValueError('阅读材料ID不一致')
        if len(json.dumps(self.model_extra, ensure_ascii=False).encode()) > 65536:
            raise ValueError('扩展元数据超过64KiB，原文件保留')
        paths = [a.path.casefold() for a in self.attachments.values()]
        if len(paths) != len(set(paths)):
            raise ValueError('附件相对名称在Windows下冲突')
        return self


def safe_json(value, *, pretty=False):
    return json.dumps(value, ensure_ascii=False, indent=2 if pretty else None, allow_nan=False).replace(
        '<', r'\u003c').replace('>', r'\u003e').replace('&', r'\u0026')


def load_json(value):
    try:
        result = json.loads(value, object_pairs_hook=unique_pairs,
                            parse_constant=lambda _: (_ for _ in ()).throw(ValueError('JSON不能含非有限数')))
        def bounded(node, depth=0):
            if depth > 32:
                raise ValueError('元数据嵌套过深')
            if isinstance(node, dict):
                for child in node.values():
                    bounded(child, depth + 1)
            elif isinstance(node, list):
                for child in node:
                    bounded(child, depth + 1)
        bounded(result)
        return result
    except (RecursionError, UnicodeError, json.JSONDecodeError) as error:
        raise ValueError('题目元数据JSON损坏，原文件保留') from error


def unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('题目元数据不能有重复键')
        result[key] = value
    return result


def projection(block, assets):
    kind = block['type']
    if kind == 'text':
        return html.escape(block['text'], quote=False).replace('\r', '&#13;')
    if kind == 'latex':
        tex = html.escape(block['tex'], quote=False).replace('\r', '&#13;')
        return '$$\n' + tex + '\n$$' if block.get('display') else '$' + tex + '$'
    if kind in {'image', 'chart', 'attachment'}:
        asset = assets.get(block['attachment_id'])
        if asset is None:
            raise ValueError('块引用的附件没有相对文件描述')
        label = html.escape(block.get('alt', block.get('label', '')), quote=False).replace(
            '\\', '\\\\').replace('[', r'\[').replace(']', r'\]').replace('\n', ' ')
        image = '!' if kind in {'image', 'chart'} else ''
        result = f"{image}[{label}]({quote(asset['path'], safe='/._-')})"
        if block.get('caption'):
            result += '\n\n' + html.escape(block['caption'], quote=False)
        return result.replace('\r', '&#13;')
    if kind == 'table':
        def cell(items):
            return ' '.join(projection(item, assets).replace('\n', '<br>').replace('|', r'\|') for item in items)
        lines = ['| ' + ' | '.join(cell(value) for value in block['headers']) + ' |',
                 '| ' + ' | '.join('---' for _ in block['headers']) + ' |']
        lines += ['| ' + ' | '.join(cell(value) for value in row) + ' |' for row in block['rows']]
        return '\n'.join(lines)
    raise ValueError('不支持的内容块；保留原文件，不静默丢弃')


def section(name, heading, blocks, assets):
    result = f'## {heading}\n<!-- swq:section {name} -->\n'
    for block in blocks:
        meta = {key: value for key, value in block.items() if key not in
                ({'text'} if block['type'] == 'text' else {'tex'} if block['type'] == 'latex' else set())}
        result += '<!-- swq:block ' + safe_json(meta) + ' -->\n' + projection(block, assets) + END_BLOCK
    return result + '<!-- swq:endsection -->\n\n'


def serialize_file(file):
    file = QuestionFile.model_validate(file)
    value = file.model_dump(mode='json')
    q = value.pop('question')
    title = value.pop('title')
    passage = value.pop('passage')
    meta = {**value, 'format_version': 1, 'question': {
        key: val for key, val in q.items() if key not in {'stem', 'options', 'explanation', 'answer'}},
        'option_ids': [o['id'] for o in q['options']],
        'passage': {key: val for key, val in passage.items() if key != 'content'} if passage else None}
    assets = meta['attachments']
    header = safe_json(meta, pretty=True)
    if len(header.encode()) > 65536:
        raise ValueError('题目头元数据超过64KiB')
    result = '# ' + html.escape(title, quote=False) + '\n\n' + LABEL + header + '\n~~~\n\n'
    result += section('passage', '共享材料', passage['content'] if passage else [], assets)
    result += section('stem', '题干', q['stem'], assets)
    for option in q['options']:
        result += section('option:' + option['id'], '选项 ' + option['id'], option['content'], assets)
    answer = q['answer']
    reference = answer.get('reference', []) if answer else []
    answer_meta = {k: v for k, v in answer.items() if k != 'reference'} if answer is not None else None
    result += '## 答案（null表示无标准答案、待人工批改）\n~~~study-workbench-answer\n' + safe_json(
        answer_meta, pretty=True) + '\n~~~\n\n'
    result += section('reference', '参考作答', reference, assets)
    result += section('explanation', '解析', q['explanation'], assets)
    if len(result.encode('utf-8')) > LIMIT:
        raise ValueError('QuestionFile最多1MiB UTF-8，原文件保留')
    return result


def _parse_file(text):
    if not isinstance(text, str) or len(text.encode('utf-8')) > LIMIT or '\x00' in text:
        raise ValueError('QuestionFile须为非二进制UTF-8，最多1MiB')
    text = text.removeprefix('\ufeff').replace('\r\n', '\n')
    if not text.startswith('# ') or '\n\n' not in text:
        raise ValueError('不是受支持的题目文件；普通Markdown可继续阅读')
    title, rest = text[2:].split('\n\n', 1)
    if not rest.startswith(LABEL) or '\n~~~\n\n' not in rest:
        raise ValueError('题目格式/版本不支持，原文件保留')
    header, rest = rest[len(LABEL):].split('\n~~~\n\n', 1)
    if len(header.encode()) > 65536:
        raise ValueError('题目头元数据超过64KiB')
    meta = load_json(header)
    if not isinstance(meta, dict) or type(meta.get('format_version')) is not int or meta.pop('format_version') != 1:
        raise ValueError('题目格式版本无效')
    if 'title' in meta:
        raise ValueError('标题必须来自Markdown标题行')
    q = meta.pop('question')
    if not isinstance(q, dict) or set(q) & {'stem', 'options', 'answer', 'explanation'}:
        raise ValueError('正文/选项/答案/解析必须来自Markdown正文')
    assets = meta.get('attachments', {})
    # Validate attachment names before using them in a readable projection.
    assets = {key: value.model_dump() for key, value in TypeAdapter(
        dict[ResourceId, FileAttachment]).validate_python(assets).items()}

    def read_section(name, heading):
        nonlocal rest
        prefix = f'## {heading}\n<!-- swq:section {name} -->\n'
        if not rest.startswith(prefix):
            raise ValueError('题目分段/顺序损坏，原文件保留')
        content, rest = rest[len(prefix):].split('<!-- swq:endsection -->\n\n', 1)
        blocks = []
        while content:
            if not content.startswith('<!-- swq:block '):
                raise ValueError('内容块标记损坏，原文件保留')
            record, body = content[len('<!-- swq:block '):].split(' -->\n', 1)
            shown, content = body.split(END_BLOCK, 1)
            block = load_json(record)
            if not isinstance(block, dict):
                raise ValueError('内容块类型记录无效')
            if block.get('type') == 'text':
                if set(block) != {'type'}:
                    raise ValueError('文本正文不能藏在类型记录内')
                block['text'] = html.unescape(shown)
            elif block.get('type') == 'latex':
                if not set(block) <= {'type', 'display'}:
                    raise ValueError('公式字段无效')
                start, end = ('$$\n', '\n$$') if block.get('display') else ('$', '$')
                if not shown.startswith(start) or not shown.endswith(end):
                    raise ValueError('公式分隔符损坏')
                block['tex'] = html.unescape(shown[len(start):-len(end)])
            elif shown != projection(block, assets):
                raise ValueError('结构块的可读内容与类型记录不一致，请同时核对结构记录；不会忽略正文修改')
            blocks.append(block)
            if len(blocks) > 200:
                raise ValueError('单个题目分段最多200块')
        return blocks

    try:
        passage_content = read_section('passage', '共享材料')
        q['stem'] = read_section('stem', '题干')
        ids = meta.pop('option_ids')
        if not isinstance(ids, list) or len(ids) > 30 or len(ids) != len(set(ids)):
            raise ValueError('选项ID重复或无效')
        q['options'] = [{'id': identifier, 'content': read_section('option:' + identifier, '选项 ' + identifier)} for identifier in ids]
        prefix = '## 答案（null表示无标准答案、待人工批改）\n~~~study-workbench-answer\n'
        if not rest.startswith(prefix):
            raise ValueError('答案段损坏')
        answer, rest = rest[len(prefix):].split('\n~~~\n\n', 1)
        q['answer'] = load_json(answer)
        if isinstance(q['answer'], dict) and 'reference' in q['answer']:
            raise ValueError('参考作答必须来自正文分段')
        reference = read_section('reference', '参考作答')
        if q['answer'] is not None and 'rubric' in q['answer']:
            q['answer']['reference'] = reference
        elif reference:
            raise ValueError('此答案类型不能带参考作答块')
        q['explanation'] = read_section('explanation', '解析')
        if rest:
            raise ValueError('题目末尾有未识别内容，不会静默丢弃')
        passage = meta.pop('passage')
        if passage is not None:
            passage['content'] = passage_content
        elif passage_content:
            raise ValueError('未声明共享材料ID')
        return QuestionFile.model_validate(dict(meta, title=html.unescape(title), question=q, passage=passage))
    except (KeyError, TypeError, RecursionError) as error:
        raise ValueError('题目格式/字段损坏，原文件保留') from error


def parse_file(text):
    try:
        return _parse_file(text)
    except (KeyError, TypeError, RecursionError) as error:
        raise ValueError('题目格式/字段损坏，原文件保留') from error
