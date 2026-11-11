"""Conservative numbered-question extraction; never invent answers or question kinds."""
import hashlib
import json
import re

NUMBER = r'(?:\d{1,4}|[一二三四五六七八九]?十[一二三四五六七八九]?|[一二三四五六七八九])'
START = re.compile(
    rf'(?mi)^[ \t]*(?:'
    r'(?:(?:阅读下列材料[，,][ \t]*回答第)|(?:Read the following passage and answer questions[ \t]+))'
    r'(?P<first>\d{1,4})[ \t]*[-—–至][ \t]*(?P<last>\d{1,4})(?:题)?[：:][ \t]*\r?$'
    rf'|(?:第[ \t]*(?P<cn>{NUMBER})[ \t]*题[：:、.．]?'
    r'|【(?P<bracket>\d{1,4})】|(?P<plain>\d{1,4})[.．、](?!\d))[ \t]*\S[^\r\n]*)')


def question_number(match):
    value = match['cn'] or match['bracket'] or match['plain']
    if value.isdecimal():
        return int(value)
    digits = '一二三四五六七八九'
    if re.fullmatch(r'[一二三四五六七八九]?十[一二三四五六七八九]?', value):
        tens, units = value.split('十')
        return (digits.index(tens) + 1 if tens else 1) * 10 + (digits.index(units) + 1 if units else 0)
    return digits.index(value) + 1 if len(value) == 1 and value in digits else None


class DraftSplitter:
    """One boundary policy for Word content and PDF regions; grouping remains a candidate."""

    def __init__(self):
        self.drafts = []
        self.current = None
        self.group = None
        self.warnings = []
        self.numbers = set()
        self.material_count = 0

    def warn(self, message):
        if message not in self.warnings:
            self.warnings.append(message)

    def finish_group(self):
        if self.group is None:
            return
        first, last, material, questions = self.group
        if (0 < first <= last and last - first < 200 and material['blocks'] and
                [number for number, _ in questions] == list(range(first, last + 1))):
            for _, draft in questions:
                draft['shared_materials'] = [material]
        else:
            self.warn('共享材料题号范围缺失、重复、乱序或超限，未自动关联；材料仍保留在整篇预览，请手动归组。')
        self.group = None

    def begin(self, match):
        if match['first'] is not None:
            self.finish_group()
            self.material_count += 1
            if self.material_count > 200:
                raise ValueError('文档共享材料超过200组，请分批导入')
            material = {'id': f'auto-material-{self.material_count}', 'blocks': [],
                        'source_pages': [], 'regions': []}
            self.group = (int(match['first']), int(match['last']), material, [])
            self.current = material
            return material
        number = question_number(match)
        if number is None:
            return self.current
        if self.group is not None and not self.group[0] <= number <= self.group[1]:
            self.finish_group()
        if number in self.numbers:
            self.warn('文档包含重复题号，候选按出现顺序分别保留，未按题号覆盖或合并；请核对章节和边界。')
        self.numbers.add(number)
        self.current = {'title': match.group().strip()[:240], 'blocks': [], 'source_pages': [], 'regions': []}
        self.drafts.append(self.current)
        if len(self.drafts) > 200:
            raise ValueError('文档题目超过200道，请分批导入')
        if self.group is not None:
            self.group[3].append((number, self.current))
        return self.current

    def finish(self):
        self.finish_group()
        return self.drafts


def split_blocks(blocks, warnings=None):
    splitter = DraftSplitter()
    for block in blocks:
        if block['type'] != 'text':
            if splitter.current is not None:
                splitter.current['blocks'].append(block)
            continue
        text = block['text']
        starts = list(START.finditer(text))
        if not starts:
            if splitter.current is not None:
                splitter.current['blocks'].append(block)
            continue
        if splitter.current is not None and text[:starts[0].start()].strip():
            splitter.current['blocks'].append({'type': 'text', 'text': text[:starts[0].start()]})
        for index, match in enumerate(starts):
            end = starts[index + 1].start() if index + 1 < len(starts) else len(text)
            current = splitter.begin(match)
            if current is not None:
                current['blocks'].append({'type': 'text', 'text': text[match.start():end].strip()})
    drafts = splitter.finish()
    if warnings is not None:
        warnings.extend(splitter.warnings)
    return drafts


def draft_revision(drafts):
    return hashlib.sha256(json.dumps(drafts, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def all_blocks(draft):
    return [b for material in draft.get('shared_materials', []) for b in material['blocks']] + draft['blocks']


def markdown(draft):
    parts = []
    for block in all_blocks(draft):
        if block['type'] == 'text':
            parts.append(block['text'])
        elif block['type'] == 'latex':
            delimiter = '$$' if block.get('display') else '$'
            parts.append(f"{delimiter}\n{block['tex']}\n{delimiter}")
        elif block['type'] == 'image':
            label = block['alt'].replace(']', r'\]').replace('\n', ' ')
            parts.append(f"![{label}](assets/{block['attachment_id']}.png)")
    return '\n\n'.join(parts) + '\n'
