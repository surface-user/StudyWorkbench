"""Self-authored numbered Word/PDF questions; no licensed exam or personal content."""
import base64
import io
from pathlib import Path

PNG = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+j4WQAAAAASUVORK5CYII=')


def docx_sample():
    from docx import Document
    from docx.oxml import parse_xml
    from docx.shared import Inches

    doc = Document()
    doc.add_paragraph('Self-authored practice material / 自编拆题样本')
    doc.add_paragraph('1. 计算平方，保留下列公式、图片和表格。')
    doc.add_paragraph()._p.append(parse_xml(
        '<m:oMath xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math">'
        '<m:sSup><m:e><m:r><m:t>x</m:t></m:r></m:e><m:sup><m:r><m:t>2</m:t></m:r></m:sup>'
        '</m:sSup></m:oMath>'))
    doc.add_picture(io.BytesIO(PNG), width=Inches(0.2))
    table = doc.add_table(rows=2, cols=2)
    for cell, value in zip([*table.rows[0].cells, *table.rows[1].cells], ['x', 'x^2', '2', '4'], strict=True):
        cell.text = value
    doc.add_paragraph('2. 说明为什么需要保留原文。没有标准答案。')
    doc.add_paragraph('这是第二题的补充条件，不属于第一题。')
    out = io.BytesIO()
    doc.save(out)
    return out.getvalue()


def pdf_sample():
    objects = [b'<< /Type /Catalog /Pages 2 0 R >>', b'<< /Type /Pages /Kids [3 0 R 4 0 R] /Count 2 >>']
    for stream in (6, 7):
        objects.append(f'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 5 0 R >> >> /Contents {stream} 0 R >>'.encode())
    objects.append(b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>')
    for content in (b'BT /F1 16 Tf 50 740 Td (1. Find the square of x.) Tj 0 -30 Td (This question continues on the next page.) Tj ET',
                    b'BT /F1 16 Tf 50 740 Td (Continuation of question one: keep this condition.) Tj 0 -120 Td (2. Explain the meaning of the diagram.) Tj 0 -30 Td (No reference answer is supplied.) Tj ET'):
        objects.append(f'<< /Length {len(content)} >>\nstream\n'.encode() + content + b'\nendstream')
    data, offsets = bytearray(b'%PDF-1.4\n'), [0]
    for index, value in enumerate(objects, 1):
        offsets.append(len(data))
        data.extend(f'{index} 0 obj\n'.encode() + value + b'\nendobj\n')
    start = len(data)
    data.extend(f'xref\n0 {len(offsets)}\n0000000000 65535 f \n'.encode())
    for offset in offsets[1:]:
        data.extend(f'{offset:010d} 00000 n \n'.encode())
    data.extend(f'trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{start}\n%%EOF'.encode())
    return bytes(data)


if __name__ == '__main__':
    target = Path(__file__).resolve().parents[1] / 'contracts/samples'
    for suffix, build in [('docx', docx_sample), ('pdf', pdf_sample)]:
        (target / f'numbered-questions.{suffix}').write_bytes(build())
    print('Created self-authored numbered-questions.docx/pdf')
