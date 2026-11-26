import hashlib
from io import BytesIO

from docx import Document
from docx.oxml import OxmlElement
from study_workbench.word_outline import outline
from test_document_files import PREFIX, add, client


def original(document):
    stream = BytesIO()
    document.save(stream)
    return stream.getvalue()


def test_outline_pages_keep_blank_paragraphs_and_whole_tables(tmp_path):
    document = Document()
    for n in range(49):
        document.add_paragraph('开头' * 100 if n == 0 else '')
    cell = document.add_table(rows=1, cols=1).cell(0, 0)
    cell.text = '9. 表格内的题号'
    cell.add_table(rows=1, cols=1).cell(0, 0).text = '嵌套'
    document.add_paragraph('末\t尾\n续行')
    raw = original(document)
    sha = hashlib.sha256(raw).hexdigest()
    with client(tmp_path) as c:
        node, identifier, path = add(c, tmp_path, '试题.docx', raw)
        url = f'{PREFIX}/nodes/{node}/document-word-outline'
        params = {'expected_sha256': sha}
        result = c.get(url, params=params).json()
        assert result['available'] and result['source_sha256'] == sha and result['resource_id'] == identifier
        assert result['total_positions'] == 51 and result['next_position'] == 51
        assert len(result['positions']) == 50 and len(result['positions'][0]['excerpt']) == 120
        assert result['positions'][1] == {'position': 2, 'kind': 'paragraph', 'excerpt': ''}
        assert result['positions'][-1]['kind'] == 'table' and '9. 表格' in result['positions'][-1]['excerpt']
        page = c.get(url, params={**params, 'first_position': 51}).json()
        assert page['positions'] == [{'position': 51, 'kind': 'paragraph', 'excerpt': '末 尾 续行'}]
        assert page['next_position'] is None
        assert c.get(url, params={**params, 'first_position': 52}).json()['reason'] == 'position_out_of_range'
        assert c.get(url, params={'expected_sha256': '0' * 64}).status_code == 409
        assert c.get(url.replace('/default/', '/foreign/'), params=params).status_code == 404
        assert path.read_bytes() == raw
        path.write_bytes(raw + b'changed')
        assert c.get(url, params=params).status_code == 409


def test_empty_and_unpositionable_blocks():
    document = Document()
    assert outline(original(document), 1) == {
        'available': True, 'total_positions': 0, 'positions': [], 'next_position': None,
    }
    document.add_paragraph('已有正文')
    document.element.body.insert(0, OxmlElement('w:sdt'))
    assert outline(original(document), 1) == {'available': False, 'reason': 'unsupported_body_structure'}
