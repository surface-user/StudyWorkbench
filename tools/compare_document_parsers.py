"""Run offline candidates on real, self-authored DOCX/PDF files, never personal data.

Run in .local/parser-benchmark; this tool is not a production dependency.
"""
import base64
import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = ROOT / "contracts/samples"
OUT = ROOT / "docs/evidence/m2-followup-20261024"


def make_samples():
    from docx import Document
    from docx.oxml import parse_xml
    from docx.shared import Inches

    SAMPLES.mkdir(exist_ok=True)
    png = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+j4WQAAAAASUVORK5CYII=")
    from io import BytesIO
    doc = Document()
    doc.add_heading("自编导入样本 / Study sample", 0)
    doc.add_paragraph("中文题干：计算平方。This is original test material, not an exam question.")
    paragraph = doc.add_paragraph()
    paragraph._p.append(parse_xml('<m:oMath xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math">'
                                 '<m:sSup><m:e><m:r><m:t>x</m:t></m:r></m:e>'
                                 '<m:sup><m:r><m:t>2</m:t></m:r></m:sup></m:sSup></m:oMath>'))
    table = doc.add_table(rows=2, cols=2)
    for cell, text in zip([*table.rows[0].cells, *table.rows[1].cells], ["变量", "结果", "2", "4"], strict=True):
        cell.text = text
    doc.add_picture(BytesIO(png), width=Inches(0.2))
    doc.add_page_break()
    doc.add_paragraph("第二页：参考答案由人确认。Page two, answer requires human review.")
    doc.save(SAMPLES / "original-study.docx")
    # Two-page PDF with an embedded image and selectable text. No generator dependency.
    objects = [b"<< /Type /Catalog /Pages 2 0 R >>",
               b"<< /Type /Pages /Kids [3 0 R 4 0 R] /Count 2 >>"]
    for stream in (6, 7):
        objects.append(f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 5 0 R >> /XObject << /Im1 8 0 R >> >> /Contents {stream} 0 R >>".encode())
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    for content in (b"BT /F1 16 Tf 50 740 Td (Original study sample: x^2) Tj 0 -30 Td (Variable | Result) Tj 0 -25 Td (2 | 4) Tj ET q 40 0 0 40 50 600 cm /Im1 Do Q",
                    b"BT /F1 16 Tf 50 740 Td (Page two: reference answer needs human review.) Tj ET"):
        objects.append(f"<< /Length {len(content)} >>\nstream\n".encode() + content + b"\nendstream")
    pixel = b"\xff\x00\x00"
    objects.append(b"<< /Type /XObject /Subtype /Image /Width 1 /Height 1 /ColorSpace /DeviceRGB /BitsPerComponent 8 /Length 3 >>\nstream\n" + pixel + b"\nendstream")
    data, offsets = bytearray(b"%PDF-1.4\n"), [0]
    for i, obj in enumerate(objects, 1):
        offsets.append(len(data))
        data.extend(f"{i} 0 obj\n".encode() + obj + b"\nendobj\n")
    start = len(data)
    data.extend(f"xref\n0 {len(offsets)}\n0000000000 65535 f \n".encode())
    for offset in offsets[1:]:
        data.extend(f"{offset:010d} 00000 n \n".encode())
    data.extend(f"trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{start}\n%%EOF".encode())
    (SAMPLES / "original-study.pdf").write_bytes(data)


def compare():
    from docling.backend.msword_backend import MsWordDocumentBackend
    from docling.backend.pypdfium2_backend import PyPdfiumDocumentBackend
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.document import InputDocument
    from markitdown import MarkItDown

    results = []
    for path in sorted(SAMPLES.iterdir()):
        if path.suffix not in {".docx", ".pdf"}:
            continue
        for candidate in ("markitdown", "docling-offline-backend"):
            start = time.monotonic()
            try:
                if candidate == "markitdown":
                    text = MarkItDown(enable_plugins=False).convert_local(str(path)).text_content
                elif path.suffix == ".docx":
                    document = InputDocument(path, format=InputFormat.DOCX, backend=MsWordDocumentBackend)
                    text = document._backend.convert().export_to_markdown()
                    document._backend.unload()
                else:
                    document = InputDocument(path, format=InputFormat.PDF, backend=PyPdfiumDocumentBackend)
                    pages = []
                    for index in range(document._backend.page_count()):
                        page = document._backend.load_page(index)
                        pages.append("\n".join(cell.text for cell in page.get_text_cells()))
                        page.unload()
                    document._backend.unload()
                    text = "\n\n--- page ---\n\n".join(pages)
                output = f"{candidate}-{path.suffix[1:]}.md"
                (OUT / output).write_text(text, encoding="utf-8")
                results.append({"parser": candidate, "sample": path.name, "status": "ok",
                                "seconds": round(time.monotonic() - start, 3), "characters": len(text),
                                "chinese_retained": "中文题干" in text, "math_text": "x" in text and "2" in text,
                                "page_two_text": "Page two" in text, "output": output})
            except Exception as error:
                results.append({"parser": candidate, "sample": path.name, "status": "failed",
                                "error": f"{type(error).__name__}: {error}", "seconds": round(time.monotonic() - start, 3)})
    (OUT / "parser-comparison.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(results, ensure_ascii=False, indent=2))
    if any(result["status"] != "ok" for result in results):
        raise SystemExit(1)


if __name__ == "__main__":
    make_samples()
    compare()
