"""Conservative numbered-question extraction; never invent answers or question kinds."""
import hashlib
import json
import re

START = re.compile(r"(?m)^[ \t]*(?:第[ \t]*\d{1,4}[ \t]*题[：:、.．]?|\d{1,4}[.．、](?!\d))[ \t]*\S[^\r\n]*")


def split_blocks(blocks):
    drafts = []
    current = None
    for block in blocks:
        if block['type'] != 'text':
            if current is not None:
                current['blocks'].append(block)
            continue
        text = block['text']
        starts = list(START.finditer(text))
        if not starts:
            if current is not None:
                current['blocks'].append(block)
            continue
        if current is not None and text[:starts[0].start()].strip():
            current['blocks'].append({'type': 'text', 'text': text[:starts[0].start()]})
        for index, match in enumerate(starts):
            end = starts[index + 1].start() if index + 1 < len(starts) else len(text)
            current = {'title': match.group().strip()[:240], 'blocks': [
                {'type': 'text', 'text': text[match.start():end].strip()}], 'source_pages': [], 'regions': []}
            drafts.append(current)
            if len(drafts) > 200:
                raise ValueError('文档题目超过200道，请分批导入')
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
