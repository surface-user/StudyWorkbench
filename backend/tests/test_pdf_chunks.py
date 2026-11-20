import hashlib
import io
import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor

import pypdfium2 as pdfium
import pytest
from study_workbench import backup_store, imports, pdf_chunks
from test_imports import SCOPE, client, upload

API = SCOPE + '/pdf-chunk-jobs'


def pdf(pages=21):
    output = io.BytesIO()
    with pdfium.PdfDocument.new() as doc:
        for _ in range(pages):
            doc.new_page(50, 50).close()
        doc.save(output)
    return output.getvalue()


def request_job(c, raw, last=21):
    resource = upload(c, raw, '测试.pdf').json()
    return dict(resource_id=resource['resource_id'], expected_sha256=hashlib.sha256(raw).hexdigest(),
                first_page=1, last_page=last)


def test_chunk_job_commits_once_resumes_and_reopens(tmp_path):
    raw = pdf()
    with client(tmp_path) as c:
        body = request_job(c, raw)
        created = c.post(API, json=body)
        assert created.status_code == 200, created.text
        job = created.json()
        url = API + '/' + job['id']
        assert c.post(API, json=body).json()['id'] == job['id']
        assert c.get(url.replace('/default/', '/other/')).status_code == 404
        assert c.post(url + '/advance', json={'first_page': 2}).status_code == 409
        step = c.post(url + '/advance', json={'first_page': 1})
        assert step.status_code == 200, step.text
        assert step.json()['completed_pages'] == 20 and step.json()['status'] == 'ready'
        assert c.post(url + '/advance', json={'first_page': 1}).json() == step.json()
        assert c.get(url + '/chunks/1').json()['last_page'] == 20
        assert c.post(url + '/cancel').json()['status'] == 'cancelled'
        assert c.post(url + '/advance', json={'first_page': 21}).status_code == 409
    with client(tmp_path) as c:
        assert c.get(url).json()['completed_pages'] == 20
        assert [j['id'] for j in c.get(API).json()] == [job['id']]
        assert c.get(API, params={'offset': 1}).json() == []
        assert c.post(url + '/resume').json()['status'] == 'ready'
        done = c.post(url + '/advance', json={'first_page': 21}).json()
        assert done['status'] == 'parsed' and done['completed_pages'] == 21
        assert c.post(url + '/advance', json={'first_page': 21}).json() == done
        assert c.get(url + '/chunks/21').json()['fragments'][0]['source_pages'] == [21]
        assert c.get(f"{SCOPE}/resources/{body['resource_id']}").content == raw


def test_chunk_job_stale_worker_cannot_overwrite_cancel_or_recovery(tmp_path, monkeypatch):
    entered, proceed = threading.Event(), threading.Event()
    original = pdf_chunks.parse_pages

    def pause(data, first, last, version):
        entered.set()
        assert proceed.wait(20)
        return original(data, first, last, version)

    monkeypatch.setattr(pdf_chunks, 'parse_pages', pause)
    with client(tmp_path) as c:
        body = request_job(c, pdf(1), 1)
        job = c.post(API, json=body).json()
        url = API + '/' + job['id']
        with ThreadPoolExecutor(1) as pool:
            result = pool.submit(c.post, url + '/advance', json={'first_page': 1})
            try:
                assert entered.wait(10)
                assert c.post(url + '/advance', json={'first_page': 1}).status_code == 409
                assert c.post(url + '/cancel').json()['status'] == 'cancelled'
                assert c.post(url + '/resume').json()['status'] == 'ready'
            finally:
                proceed.set()
            assert result.result().status_code == 409
        assert c.get(url).json()['completed_pages'] == 0
        assert c.get(url + '/chunks/1').status_code == 404
    with sqlite3.connect(tmp_path / 'study.db') as db:
        db.execute("UPDATE pdf_chunk_jobs SET status='running'")
    with client(tmp_path) as c:
        assert c.get(url).json()['status'] == 'interrupted'
        assert c.post(url + '/resume').json()['status'] == 'ready'


def test_chunk_job_rejects_scope_source_hash_and_budget(tmp_path, monkeypatch):
    raw = pdf(2)
    with client(tmp_path) as c:
        body = request_job(c, raw, 2)
        assert c.post(API, json={**body, 'expected_sha256': '0'*64}).status_code == 409
        assert c.post(API, json={**body, 'last_page': 3}).status_code == 422
        assert c.post(API, json={**body, 'last_page': 101}).status_code == 422
        assert c.post(API, json={**body, 'first_page': True}).status_code == 422
        url = API + '/' + c.post(API, json=body).json()['id']
        with sqlite3.connect(tmp_path / 'study.db') as db:
            db.execute('UPDATE pdf_chunk_jobs SET asset_bytes=67108864')
        assert c.post(url + '/advance', json={'first_page': 1}).status_code == 422
        assert c.get(url).json()['status'] == 'failed' and c.get(url).json()['completed_pages'] == 0
        with sqlite3.connect(tmp_path / 'study.db') as db:
            db.execute("UPDATE resources SET relative_path='workspaces/default-other/originals/x' WHERE id=?",
                       (body['resource_id'],))
        monkeypatch.setattr(imports, 'resource_path', lambda *_: pytest.fail('resolved a foreign path'))
        assert c.post(url + '/resume').status_code == 409
        assert c.post(API, json=body).status_code == 409


def test_parsed_job_survives_backup_and_foreign_association_is_rejected(tmp_path):
    root = tmp_path / 'source'
    with client(root) as c:
        body = request_job(c, pdf(1), 1)
        url = API + '/' + c.post(API, json=body).json()['id']
        assert c.post(url + '/advance', json={'first_page': 1}).json()['status'] == 'parsed'
        result = c.get(url + '/chunks/1').json()
    package, target = tmp_path / 'valid.zip', tmp_path / 'restored'
    backup_store.create_backup(root, package)
    backup_store.restore_backup(package, target, tmp_path / 'settings.json')
    with client(target) as c:
        assert c.get(url).json()['status'] == 'parsed' and c.get(url + '/chunks/1').json() == result
    with sqlite3.connect(root / 'study.db') as db:
        db.execute("UPDATE pdf_chunk_jobs SET source_sha256=?", ('0' * 64,))
    with pytest.raises(ValueError, match='原件'):
        backup_store.create_backup(root, tmp_path / 'invalid.zip')


def test_cross_chunk_material_preview_confirmation_and_whole_import_stay_separate(tmp_path):
    from test_complex_question_splitting import grouped_sample

    output = io.BytesIO()
    with pdfium.PdfDocument.new() as doc, pdfium.PdfDocument(grouped_sample('pdf')) as two_pages:
        for _ in range(19):
            doc.new_page(50, 50).close()
        doc.import_pages(two_pages)
        doc.save(output)
    raw = output.getvalue()
    with client(tmp_path) as c:
        original = upload(c, raw, '考题.pdf').json()
        assert original['status'] == 'failed'
        job = c.post(API, json=dict(resource_id=original['resource_id'], expected_sha256=original['sha256'],
                                    first_page=1, last_page=21)).json()
        url = API + '/' + job['id']
        assert c.post(url + '/advance', json={'first_page': 1}).json()['next_page'] == 21
        assert c.post(url + '/preview').status_code == 409
    with client(tmp_path) as c:
        assert c.post(url + '/advance', json={'first_page': 21}).json()['status'] == 'parsed'
        result = c.post(url + '/preview')
        assert result.status_code == 200, result.text
        batch = result.json()
        drafts = batch['preview']['question_drafts']
        assert len(drafts) == 2 and len(batch['preview']['blocks']) == 21
        shared = drafts[0]['shared_materials'][0]
        assert shared == drafts[1]['shared_materials'][0] and shared['source_pages'] == [20, 21]
        assert all(d['source_pages'] == [21] for d in drafts)
        assert 'Shared material continues here.' in batch['question_markdown'][0]
        assert c.post(url + '/preview').json()['draft_revision'] == batch['draft_revision']
        assert c.get(SCOPE + '/question-markdown').json() == []
        assert c.post(f"{SCOPE}/imports/{job['id']}/retry").status_code == 409
        assert c.post(f"{SCOPE}/imports/{job['id']}/confirm").status_code == 409
        selection = dict(expected_revision=batch['draft_revision'], selected=[1], confirm=True)
        confirm = f"{SCOPE}/imports/{job['id']}/question-markdown"
        created = c.post(confirm, json=selection)
        assert created.status_code == 200, created.text
        assert created.json() == c.post(confirm, json=selection).json()
        assert c.post(confirm, json={**selection, 'selected': [0]}).status_code == 409
        assert c.post(url + '/preview').json()['status'] == 'confirmed'
        assert upload(c, raw, '同一原件.pdf').json()['id'] == original['id']
        assert c.get(f"{SCOPE}/resources/{original['resource_id']}").content == raw


def test_editing_selected_second_page_crops_the_original_page(tmp_path):
    from test_complex_question_splitting import grouped_sample
    from test_draft_editing import edit

    with client(tmp_path) as c:
        body = request_job(c, grouped_sample('pdf'), 2)
        body['first_page'] = 2
        url = API + '/' + c.post(API, json=body).json()['id']
        assert c.post(url + '/advance', json={'first_page': 2}).status_code == 200
        batch = c.post(url + '/preview').json()
        assert batch['preview']['warnings'] and len(batch['preview']['blocks']) == 1
        box = batch['preview']['question_drafts'][0]['regions'][0]['box']
        updated = edit(c, batch, 'split_region', position=0, cut=(box[1] + box[3])/2, title='第二段')
        assert updated.status_code == 200, updated.text
        assert all(d['source_pages'] == [2] for d in updated.json()['preview']['question_drafts'])
        assert c.post(url + '/preview').json()['draft_revision'] == updated.json()['draft_revision']


def test_selected_column_layout_preserves_continuation_material_and_exact_crops(tmp_path):
    from pathlib import Path

    from PIL import Image

    raw = (Path(__file__).parents[2] / 'contracts/samples/two-column-questions.pdf').read_bytes()
    with client(tmp_path) as c:
        body = request_job(c, raw, 1)
        one = c.post(API, json=body).json()
        assert c.post(API, json={**body, 'layout': 'automatic'}).status_code == 422
        two = c.post(API, json={**body, 'layout': 'two_columns'}).json()
        assert two['id'] != one['id'] and two['parser_version'] == 'pdf-column-chunks-v1'
        url = API + '/' + two['id']
        advanced = c.post(url + '/advance', json={'first_page': 1})
        assert advanced.json()['status'] == 'parsed', advanced.text
    with client(tmp_path) as c:
        response = c.post(url + '/preview')
        assert response.status_code == 200, response.text
        batch = response.json()
        first, second = batch['preview']['question_drafts']
        shared = first['shared_materials'][0]
        assert shared == second['shared_materials'][0] and shared['source_pages'] == [1]
        assert 'Shared facts from the left column.' in shared['blocks'][1]['text']
        assert 'First question continues here.' in first['blocks'][-1]['text']
        assert 'First question continues here.' not in str(second['blocks'])
        assert [first['title'], second['title']] == ['1. First question', '2. Second question']
        assert first['source_pages'] == second['source_pages'] == [1]
        assert [b['box'][::2] for b in first['regions']] == [[0, .5], [.5, 1]]
        assert second['regions'][0]['box'][::2] == [.5, 1]
        picture = c.get(SCOPE + '/resources/' + first['blocks'][0]['attachment_id'])
        with Image.open(io.BytesIO(picture.content)) as crop:
            # The filled blue figure belongs only to the lower left region.
            assert crop.width == 600 and crop.getpixel((100, 120)) == (51, 102, 204)
        confirm = f"{SCOPE}/imports/{two['id']}/question-markdown"
        choice = dict(expected_revision=batch['draft_revision'], selected=[0], confirm=True)
        created = c.post(confirm, json=choice)
        assert created.status_code == 200 and c.post(confirm, json=choice).json() == created.json()
        assert c.post(confirm, json={**choice, 'selected': [1]}).status_code == 409
        assert c.get(f"{SCOPE}/resources/{body['resource_id']}").content == raw
        assert c.get(API + '/' + one['id']).json()['status'] == 'ready'


@pytest.mark.parametrize('drawing', [b'295 110 8 15', b'35 160 28 50'])
def test_ambiguous_figure_preserves_full_page_and_yields_no_guessed_draft(drawing):
    from pathlib import Path

    from study_workbench.documents import extract

    raw = (Path(__file__).parents[2] / 'contracts/samples/two-column-questions.pdf').read_bytes()
    # Preserve stream lengths and xref offsets with a fixed-size replacement.
    source = b'35 110 28 15 re f 0 g'
    replacement = drawing + b' re f 0 g'
    assert len(replacement) == len(source)
    result = extract(raw.replace(source, replacement), '.pdf', page_range=(1, 1), two_columns=True)
    assert len(result['_assets']) == 1 and result['blocks'][-1]['type'] == 'image'
    assert len(result['fragments']) == 1 and result['fragments'][0]['ambiguous']
    assert not result['fragments'][0]['blocks']


def test_chunk_snapshot_read_budget_disk_failure_and_stale_copy(tmp_path, monkeypatch):
    from fastapi import HTTPException
    from sqlalchemy.orm import Session
    from test_document_files import add

    raw = b'%PDF-' + b'A' * (8 * 1024 * 1024)
    digest = hashlib.sha256(raw).hexdigest()
    with client(tmp_path) as c, Session(c.app.state.engine) as session:
        node, identifier, path = add(c, tmp_path, 'large.pdf', raw)
        assert c.post(f'{SCOPE}/nodes/{node}/document-columns',
                      json={'expected_sha256': digest, 'page': 1}).status_code == 413
        source_args = session, tmp_path, 'default', identifier, digest

        class Sink(io.BytesIO):
            def write(self, data):
                assert len(data) <= 1024 * 1024
                return super().write(data)

        snapshot = Sink()
        imports.check_chunk_pdf(*source_args, output=snapshot)
        assert snapshot.getvalue() == raw

        class Full(Sink):
            def flush(self):
                raise OSError('full')

        with pytest.raises(HTTPException) as full:
            imports.check_chunk_pdf(*source_args, output=Full())
        assert full.value.status_code == 507
        with path.open('r+b') as changed:
            changed.seek(-1, 2)
            changed.write(b'B')
        with pytest.raises(HTTPException) as stale:
            imports.check_chunk_pdf(*source_args)
        assert stale.value.status_code == 409 and snapshot.getvalue() == raw
        monkeypatch.setattr(imports, 'CHUNK_PDF_LIMIT', len(raw) - 1)
        monkeypatch.setattr(imports, 'resource_path', lambda *_: pytest.fail('over-budget source was opened'))
        with pytest.raises(HTTPException) as oversized:
            imports.check_chunk_pdf(*source_args)
        assert oversized.value.status_code == 413
