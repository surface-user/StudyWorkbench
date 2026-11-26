"""Read bounded excerpts at stable positions in a managed Word document."""
from io import BytesIO
from xml.etree import ElementTree
from zipfile import ZipFile

from .office_inputs import validate_office

WORD = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'


def outline(data, first_position):
    if type(first_position) is not int or not 1 <= first_position <= 200000:
        raise ValueError('正文起点超限')
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
        return {'available': False, 'reason': 'unsupported_body_structure'}
    if first_position > max(1, len(blocks)):
        return {'available': False, 'reason': 'position_out_of_range', 'total_positions': len(blocks)}
    positions = []
    for index, block in enumerate(blocks[first_position - 1:first_position + 49], first_position):
        is_table = block.tag == WORD + 'tbl'
        paragraphs = block.iterfind(f'{WORD}tr/{WORD}tc/{WORD}p') if is_table else (block,)
        # Only direct runs contribute text. Field instructions and deleted revisions stay out of excerpts.
        excerpt = ' '.join(''.join(t.text or '' for t in p.iterfind(f'{WORD}r/{WORD}t')) for p in paragraphs)
        positions.append({'position': index, 'kind': 'table' if is_table else 'paragraph', 'excerpt': excerpt[:120]})
    following = first_position + len(positions)
    return {'available': True, 'total_positions': len(blocks), 'positions': positions,
            'next_position': following if following <= len(blocks) else None}
