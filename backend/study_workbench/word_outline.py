"""Read bounded excerpts at stable positions in a managed Word document."""
import hashlib
import json
from io import BytesIO
from itertools import islice
from xml.etree import ElementTree
from zipfile import ZipFile

from .office_inputs import validate_office

WORD = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
WORD_JOB_PREFIX = 'docx-range-job-'
WORD_JOB_VERSION = WORD_JOB_PREFIX + 'v1'
WORD_BATCH_VERSION = WORD_JOB_PREFIX + 'v2'
WORD_JOB_VERSIONS = (WORD_JOB_VERSION, WORD_BATCH_VERSION)


def word_job_id(workspace, resource, state, version=WORD_JOB_VERSION):
    key = [version, workspace, state['node_id'], resource, state['source_sha256'],
           state['first_position'], state['last_position']]
    return hashlib.sha256(json.dumps(key, separators=(',', ':')).encode()).hexdigest()


def excerpt_characters(paragraphs):
    for index, paragraph in enumerate(paragraphs):
        if index:
            yield ' '
        for run in paragraph.iterfind(WORD + 'r'):
            for part in run:
                if part.tag == WORD + 't':
                    yield from part.text or ''
                elif part.tag in {WORD + 'tab', WORD + 'br', WORD + 'cr'}:
                    yield ' '


def body_blocks(data):
    with ZipFile(BytesIO(data)) as archive:
        members = archive.infolist()
        if len(members) > 2000 or sum(m.file_size for m in members) > 64 * 1024 * 1024:
            raise ValueError('Word 解压大小或文件数超限')
        validate_office(data, '.docx')
        document = ElementTree.fromstring(archive.read('word/document.xml'))
    bodies = document.findall(WORD + 'body')
    if document.tag != WORD + 'document' or len(bodies) != 1:
        raise ValueError('Word 正文结构无效')
    blocks = list(bodies[0])
    if blocks and blocks[-1].tag == WORD + 'sectPr':
        blocks.pop()
    if any(block.tag not in {WORD + 'p', WORD + 'tbl'} for block in blocks):
        return None
    return blocks


def outline(data, first_position):
    if type(first_position) is not int or not 1 <= first_position <= 200000:
        raise ValueError('正文起点超限')
    blocks = body_blocks(data)
    if blocks is None:
        return {'available': False, 'reason': 'unsupported_body_structure'}
    if first_position > max(1, len(blocks)):
        return {'available': False, 'reason': 'position_out_of_range', 'total_positions': len(blocks)}
    positions = []
    for index, block in enumerate(blocks[first_position - 1:first_position + 49], first_position):
        is_table = block.tag == WORD + 'tbl'
        paragraphs = block.iterfind(f'{WORD}tr/{WORD}tc/{WORD}p') if is_table else (block,)
        # Only direct runs contribute text. Field instructions and deleted revisions stay out of excerpts.
        excerpt = ''.join(islice(excerpt_characters(paragraphs), 120))
        positions.append({'position': index, 'kind': 'table' if is_table else 'paragraph', 'excerpt': excerpt})
    following = first_position + len(positions)
    return {'available': True, 'total_positions': len(blocks), 'positions': positions,
            'next_position': following if following <= len(blocks) else None}
