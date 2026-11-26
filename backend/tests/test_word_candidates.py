import hashlib
from io import BytesIO
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZIP_STORED, ZipFile

import pytest
from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from study_workbench.documents import extract
from test_document_files import PREFIX, add, client
from test_word_outline import original


def numbered():
    doc = Document()
    for text in ('OUTSIDE-FIRST', '选取第二题', '选取第三题'):
        doc.add_paragraph(text, style='List Number')
    doc.add_paragraph('OUTSIDE-LAST')
    return doc


def test_managed_range_keeps_original_numbers_and_checks_binding(tmp_path):
    raw = original(numbered())
    whole = extract(raw, '.docx')
    with client(tmp_path) as c:
        node, identifier, saved = add(c, tmp_path, '自动编号.docx', raw)
        endpoint = f'{PREFIX}/nodes/{node}/document-word-candidates'
        body = {'expected_sha256': hashlib.sha256(raw).hexdigest(), 'first_position': 2, 'last_position': 3}
        response = c.post(endpoint, json=body)
        assert response.status_code == 200, response.text
        result = response.json()
        assert result['resource_id'] == identifier and result['source_sha256'] == body['expected_sha256']
        assert result['parser_version'] == 'docx-body-candidates-v1' and result['total_positions'] == 4
        assert result['block_positions'] == [2, 3] and result['first_position'] == 2 and result['last_position'] == 3
        candidates = result['question_drafts']
        assert [d['title'] for d in candidates] == ['2. 选取第二题', '3. 选取第三题']
        assert [d['title'] for d in candidates] == [d['title'] for d in whole['question_drafts'][1:]]
        assert [d['source_positions'] for d in candidates] == [[2], [3]]
        assert all(d['source_pages'] == d['regions'] == [] for d in candidates)
        assert 'OUTSIDE' not in str(result)
        assert any('起点' in w for w in result['warnings']) and any('末尾' in w for w in result['warnings'])
        assert c.post(endpoint, json={**body, 'last_position': 1}).status_code == 422
        assert c.post(endpoint, json={**body, 'last_position': 22}).status_code == 422
        assert c.post(endpoint, json={**body, 'last_position': 6}).json()['reason'] == 'position_out_of_range'
        assert c.post(endpoint, json={**body, 'first_position': True}).status_code == 422
        assert c.post(endpoint.replace('/default/', '/foreign/'), json=body).status_code == 404
        assert c.post(endpoint, json={**body, 'expected_sha256': '0'*64}).status_code == 409
        assert saved.read_bytes() == raw
        saved.write_bytes(raw + b'changed')
        assert c.post(endpoint, json=body).status_code == 409


def test_rich_table_positions_and_incomplete_material(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).parents[2] / 'tools'))
    from numbered_cell_sample import numbered_cell_docx
    raw = numbered_cell_docx()
    rich = extract(raw, '.docx', word_range=(1, 5))
    table = extract(raw, '.docx', word_range=(5, 5))
    assert set(table['block_positions']) == {5} and not table['question_drafts']
    assert any('Label inside a table cell' in b.get('text', '') for b in table['blocks'])
    assert any('y+7' in b.get('tex', '').replace(' ', '') for b in table['blocks'])
    assert len(table['assets']) == 1 and len(rich['assets']) == 2
    assert len(rich['question_drafts']) == 1 and 5 in rich['question_drafts'][0]['source_positions']
    doc = Document()
    for s in ('阅读下列材料，回答第1–2题：', '材料正文', '1. 题一', '2. 题二'):
        doc.add_paragraph(s)
    raw = original(doc)
    intact = extract(raw, '.docx', word_range=(1, 4))
    assert all(d['shared_materials'][0]['source_positions'] == [1, 2] for d in intact['question_drafts'])
    selected = extract(raw, '.docx', word_range=(3, 4))
    assert len(selected['question_drafts']) == 2 and all('shared_materials' not in d for d in selected['question_drafts'])
    assert '材料正文' not in str(selected['blocks'])


def test_unsupported_restart_preserves_text_without_inventing_numbers_and_tables_are_atomic():
    doc = numbered()
    p = doc.paragraphs[1]
    num = p._p.get_or_add_pPr().get_or_add_numPr()
    num.get_or_add_numId().val = 999
    raw = original(doc)
    result = extract(raw, '.docx', word_range=(2, 3))
    assert result['available'] and not result['question_drafts']
    assert '选取第二题' in str(result['blocks']) and any('无法可靠恢复' in w for w in result['warnings'])
    doc = Document()
    doc.add_paragraph('')
    table = doc.add_table(rows=1, cols=1)
    table.cell(0, 0).text = '表' * 20001
    raw = original(doc)
    assert extract(raw, '.docx', word_range=(1, 1))['reason'] == 'no_extractable_content'
    with pytest.raises(ValueError, match='第 2 个正文位置的表格'):
        extract(raw, '.docx', word_range=(2, 2))
    doc = Document()
    cell = doc.add_table(rows=1, cols=1).cell(0, 0)
    span = OxmlElement('w:gridSpan')
    span.set(qn('w:val'), '257')
    cell._tc.get_or_add_tcPr().append(span)
    with pytest.raises(ValueError, match='跨列超限'):
        extract(original(doc), '.docx', word_range=(1, 1))


def test_whole_package_preflight_before_selection():
    raw = original(numbered())
    out = BytesIO()
    with ZipFile(BytesIO(raw)) as read, ZipFile(out, 'w', ZIP_DEFLATED) as changed:
        for entry in read.infolist():
            data = read.read(entry)
            if entry.filename == 'word/_rels/document.xml.rels':
                data = data.replace(b'</Relationships>', b'<Relationship Id="extra" Type="hyperlink" '
                                    b'TargetMode="External" Target="https://example.invalid"/></Relationships>')
            changed.writestr(entry, data)
    with pytest.raises(ValueError, match='外部关系'):
        extract(out.getvalue(), '.docx', word_range=(2, 2))


def test_numbered_table_cell_preserves_original_counter_without_starting_a_question():
    doc = Document()
    doc.add_paragraph('第一题', style='List Number')
    cell = doc.add_table(rows=1, cols=1).cell(0, 0).paragraphs[0]
    cell.style = 'List Number'
    cell.add_run('单元格')
    doc.add_paragraph('原题三', style='List Number')
    raw = original(doc)
    selected = extract(raw, '.docx', word_range=(2, 3))
    assert selected['table_positions'] == [2] and selected['block_positions'] == [2, 3]
    assert any('2. 单元格' in b.get('text', '') for b in selected['blocks'])
    assert [d['title'] for d in selected['question_drafts']] == ['3. 原题三']
    all_positions = extract(raw, '.docx', word_range=(1, 3))
    assert all_positions['question_drafts'][0]['source_positions'] == [1, 2]
    assert len(all_positions['question_drafts']) == 2


@pytest.mark.parametrize('complex_numbering', ['restart', 'nested'])
def test_complex_numbering_returns_selected_text_for_manual_verification(complex_numbering):
    doc = numbered()
    part = doc.part.numbering_part.element
    num = part.add_num(7)
    number = num.numId
    if complex_numbering == 'restart':
        num.add_lvlOverride(0).add_startOverride(43)
    for p in doc.paragraphs[:3]:
        props = p._p.get_or_add_pPr().get_or_add_numPr()
        props.get_or_add_numId().val = number
        props.get_or_add_ilvl().val = 1 if complex_numbering == 'nested' else 0
    selected = extract(original(doc), '.docx', word_range=(2, 3))
    assert selected['available'] and selected['question_drafts'] == []
    assert [b['text'] for b in selected['blocks']] == ['选取第二题', '选取第三题']
    assert any('无法可靠恢复' in w for w in selected['warnings'])


def test_above_legacy_upload_limit_and_candidate_budget(tmp_path):
    raw = original(numbered())
    buffer = BytesIO(raw)
    with ZipFile(buffer, 'a') as archive:
        archive.writestr('custom/fixture-padding.dat', bytes(8 * 1024 * 1024), compress_type=ZIP_STORED)
    raw = buffer.getvalue()
    with client(tmp_path) as c:
        node, _, saved = add(c, tmp_path, '大文档.docx', raw)
        url = f'{PREFIX}/nodes/{node}/document-word-candidates'
        result = c.post(url, json={'expected_sha256': hashlib.sha256(raw).hexdigest(),
                                   'first_position': 2, 'last_position': 2}).json()
        assert [d['title'] for d in result['question_drafts']] == ['2. 选取第二题']
        assert saved.read_bytes() == raw
    doc = Document()
    doc.add_paragraph('\n'.join(f'{i}. 独立题' for i in range(1, 202)))
    with pytest.raises(ValueError, match='200'):
        extract(original(doc), '.docx', word_range=(1, 1))


def test_unresolved_prefix_counter_cannot_restart_a_selected_question():
    doc = numbered()
    props = doc.paragraphs[0]._p.get_or_add_pPr().get_or_add_numPr()
    props.get_or_add_ilvl().val = 0
    result = extract(original(doc), '.docx', word_range=(2, 3))
    assert result['question_drafts'] == [] and result['block_positions'] == [2, 3]
    assert [b['text'] for b in result['blocks']] == ['选取第二题', '选取第三题']
