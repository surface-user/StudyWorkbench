import io
import json
import subprocess
import sys
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import pytest
from study_workbench.documents import extract
from test_imports import SCOPE, client, confirm, upload

SAMPLES = Path(__file__).parents[2] / 'contracts/samples'


@pytest.mark.parametrize('suffix', ['docx', 'pdf'])
def test_real_offline_document_worker_retains_images_and_original(tmp_path, suffix):
    raw = (SAMPLES / f'original-study.{suffix}').read_bytes()
    with client(tmp_path) as c:
        job = upload(c, raw, f'自编样本.{suffix}').json()
        assert job['status'] == 'preview', job
        assert job['preview']['warnings']
        assert job['preview']['question_drafts'] == []  # Unnumbered samples stay material, never fabricated questions.
        blocks = job['preview']['blocks']
        assert any(b['type'] == 'image' for b in blocks)
        if suffix == 'docx':
            assert any(b['type'] == 'latex' and 'x' in b['tex'] for b in blocks)
            assert any('中文题干' in b.get('text', '') for b in blocks)
        else:
            assert len([b for b in blocks if b['type'] == 'image']) == 2
            assert any(b.get('text') == '第 2 页' for b in blocks)
        for block in blocks:
            if block['type'] == 'image':
                image = c.get(f"{SCOPE}/resources/{block['attachment_id']}")
                assert image.status_code == 200 and image.content.startswith(b'\x89PNG')
                # A resource extracted from another original may later be imported itself.
                image_job = upload(c, image.content, '复用图片.png').json()
                assert image_job['status'] == 'preview'
        assert c.get(f'{SCOPE}/notes').json() == []
        assert confirm(c, job).status_code == 200
        assert len(c.get(f'{SCOPE}/notes').json()) == 1
        assert c.get(f"{SCOPE}/resources/{job['resource_id']}").content == raw
        assert c.post(f"{SCOPE}/imports/{job['id']}/retry").status_code == 409


def test_docx_archive_limits_external_entities_and_macros_reject():
    for filename, data in [('word/document.xml', b'<!DOCTYPE evil>'), ('word/vbaProject.bin', b'macro'),
                           ('word/media/test.svg', b'<svg/>'), ('word/charts/chart.xml', b'<chart/>')]:
        output = io.BytesIO()
        with ZipFile(output, 'w', ZIP_DEFLATED) as archive:
            archive.writestr(filename, data)
        with pytest.raises(ValueError):
            extract(output.getvalue(), '.docx')


def test_worker_timeout_preserves_original_and_failed_job(tmp_path, monkeypatch):
    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired('controlled-document-worker', 25)
    monkeypatch.setattr(subprocess, 'run', timeout)
    with client(tmp_path) as c:
        raw = (SAMPLES / 'original-study.docx').read_bytes()
        job = upload(c, raw, 'timeout.docx').json()
        assert job['status'] == 'failed' and '25 秒' in job['error']
        assert confirm(c, job).status_code == 409
        assert c.get(f"{SCOPE}/resources/{job['resource_id']}").content == raw


def test_pdf_page_worker_preserves_continuation_and_absolute_coordinates():
    import pypdfium2 as pdfium
    from test_complex_question_splitting import grouped_sample

    output = io.BytesIO()
    with pdfium.PdfDocument.new() as combined, pdfium.PdfDocument(grouped_sample('pdf')) as sample:
        for _ in range(19):
            combined.new_page(200, 300).close()
        combined.import_pages(sample)
        combined.new_page(200, 300).close()
        combined.save(output)
    data = output.getvalue()
    with pytest.raises(ValueError, match='20 页'):
        extract(data, '.pdf')
    result = subprocess.run([sys.executable, '-m', 'study_workbench', '--parse-pdf-pages', '21', '21'],
                            input=data, capture_output=True, check=True, timeout=25, cwd=Path(__file__).parents[1])
    chunk = json.loads(result.stdout)
    assert (chunk['first_page'], chunk['last_page'], chunk['page_count']) == (21, 21, 22)
    assert len(chunk['warnings']) == 2
    fragments = chunk['fragments']
    assert [f['marker'] for f in fragments] == [None, '1. First question.', '2. Second question.']
    assert 'Shared material continues here.' in fragments[0]['blocks'][1]['text']
    assert all(f['source_pages'] == [21] and f['regions'][0]['page'] == 21 for f in fragments)
    assert all(0 <= f['regions'][0]['box'][1] < f['regions'][0]['box'][3] <= 1 for f in fragments)
    assert len(chunk['_assets']) == 4
    material = extract(data, '.pdf', page_range=(20, 20))['fragments'][-1]
    assert material['marker'].startswith('Read the following passage')
    assert material['source_pages'] == [20]
    blank = extract(data, '.pdf', page_range=(22, 22))
    assert len(blank['_assets']) == 1
    assert blank['fragments'][0]['blocks'][0] == blank['blocks'][-1]


@pytest.mark.parametrize('pages', [(0, 1), (2, 1), (1, 3), (True, 1), (1, 1.0)])
def test_pdf_page_worker_rejects_invalid_ranges(pages):
    with pytest.raises(ValueError, match='页区间'):
        extract((SAMPLES / 'original-study.pdf').read_bytes(), '.pdf', page_range=pages)


def test_pdf_page_worker_rejects_more_than_twenty_selected_pages():
    import pypdfium2 as pdfium

    data = io.BytesIO()
    with pdfium.PdfDocument.new() as doc:
        for _ in range(21):
            doc.new_page(20, 30).close()
        doc.save(data)
    with pytest.raises(ValueError, match='页区间'):
        extract(data.getvalue(), '.pdf', page_range=(1, 21))


def test_pdf_chunk_unlocated_marker_cannot_extend_a_previous_question(monkeypatch):
    import pypdfium2 as pdfium
    from test_complex_question_splitting import grouped_sample

    monkeypatch.setattr(pdfium.PdfTextSearcher, 'get_next', lambda self: None)
    chunk = extract(grouped_sample('pdf'), '.pdf', page_range=(2, 2))
    assert len(chunk['fragments']) == 1
    fragment = chunk['fragments'][0]
    assert fragment['ambiguous'] and fragment['marker'] is None
    assert fragment['regions'] == [{'page': 2, 'box': [0, 0, 1, 1]}]


@pytest.mark.parametrize(('first', 'size', 'error'), [
    ('-1', 4, '页码'), ('1', 8 * 1024 * 1024 + 1, '8 MiB'),
])
def test_pdf_chunk_worker_rejects_invalid_input_before_parsing(first, size, error):
    result = subprocess.run([sys.executable, '-m', 'study_workbench', '--parse-pdf-pages', first, '1'],
                            input=bytes(size), capture_output=True, check=True, timeout=25, cwd=Path(__file__).parents[1])
    assert error in json.loads(result.stdout)['error']
