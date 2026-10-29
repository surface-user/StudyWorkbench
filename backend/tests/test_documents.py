import io
import subprocess
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
