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

    def pause(data, first, last):
        entered.set()
        assert proceed.wait(20)
        return original(data, first, last)

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
        monkeypatch.setattr(imports, 'read_resource', lambda *_: pytest.fail('resolved a foreign path'))
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
