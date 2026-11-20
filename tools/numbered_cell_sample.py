"""Self-authored rich cell that looks like a question outside its table."""
import io
from pathlib import Path

from docx import Document
from docx.oxml import parse_xml
from docx.shared import Inches
from make_question_samples import PNG


def numbered_cell_docx():
    path = Path(__file__).resolve().parents[1] / 'contracts/samples/numbered-questions.docx'
    doc = Document(path)
    cell = doc.tables[0].cell(1, 1)
    cell.text = '0017'
    cell.add_paragraph('9. Label inside a table cell')
    cell.add_paragraph().add_run().add_picture(io.BytesIO(PNG), width=Inches(0.25))
    cell.add_paragraph()._p.append(parse_xml(
        '<m:oMath xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math">'
        '<m:r><m:t>y+7</m:t></m:r></m:oMath>'))
    doc.add_paragraph('3. Question after the table and the second question.')
    stream = io.BytesIO()
    doc.save(stream)
    return stream.getvalue()


def check_numbered_cell(result):
    drafts = result['question_drafts']
    assert len(drafts) == 3 and [d['title'].split('.')[0] for d in drafts] == ['1', '2', '3']
    texts = [b['text'] for b in result['blocks'] if b['type'] == 'text']
    containing = [t for t in texts if 'Label inside a table cell' in t]
    assert len(containing) == 1 and containing[0].startswith('|') and '0017' in containing[0]
    first = drafts[0]['blocks']
    assert any('Label inside a table cell' in b.get('text', '') for b in first)
    assert any('y+7' in b.get('tex', '').replace(' ', '') for b in first)
    images = [b['attachment_id'] for b in first if b['type'] == 'image']
    assert len(set(images)) == 2 and set(images) <= {a['id'] for a in result['_assets']}
