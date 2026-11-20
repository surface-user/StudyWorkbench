import hashlib
import io
import json
import re
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from zipfile import ZipFile

import pytest
from study_workbench import backup_store, library_integrity, markdown_questions
from study_workbench.question_splitting import draft_revision, split_blocks
from test_imports import SCOPE, client, upload
from test_library_integrity import snapshot

SAMPLES = Path(__file__).parents[2] / 'contracts/samples'


@pytest.mark.parametrize('suffix', ['docx', 'pdf'])
def test_real_document_becomes_independent_portable_markdown_questions(tmp_path, suffix):
    raw = (SAMPLES / f'numbered-questions.{suffix}').read_bytes()
    with client(tmp_path) as c:
        job = upload(c, raw, f'自编拆题.{suffix}').json()
        assert job['status'] == 'preview', job
        drafts = job['preview']['question_drafts']
        assert len(drafts) == 2
        assert c.get(f'{SCOPE}/question-markdown').json() == []
        assert c.get(f'{SCOPE}/notes').json() == []
        assert len(c.get(f'{SCOPE}/questions').json()) == 2  # Existing demos were not replaced.
        if suffix == 'docx':
            assert any(b['type'] == 'latex' for b in drafts[0]['blocks'])
            assert any(b['type'] == 'image' for b in drafts[0]['blocks'])
            table = [line for line in job['question_markdown'][0].splitlines() if line.startswith('|')]
            assert len(table) == 3
            assert [cell.strip() for cell in table[0].split('|')[1:-1]] == ['x', 'x^2']
            assert [cell.strip() for cell in table[2].split('|')[1:-1]] == ['2', '4']
            assert '补充条件' not in job['question_markdown'][0]
        else:
            assert drafts[0]['source_pages'] == [1, 2]
            assert drafts[1]['source_pages'] == [2]
            assert 'Continuation of question one' in job['question_markdown'][0]
            assert '2. Explain' not in job['question_markdown'][0]
            assert drafts[0]['regions'][1]['box'][3] < 1
        body = {'expected_revision': job['draft_revision'], 'selected': [0, 1], 'confirm': True}
        saved = c.post(f"{SCOPE}/imports/{job['id']}/question-markdown", json=body)
        assert saved.status_code == 200, saved.text
        items = saved.json()
        assert len({item['id'] for item in items}) == 2
        assert c.post(f"{SCOPE}/imports/{job['id']}/question-markdown", json=body).json() == items
        assert len(c.get(f'{SCOPE}/question-markdown').json()) == 2
        assert c.get(f'{SCOPE}/notes').json() == []
        other = c.post('/api/workspaces', json={'name': '隔离知识库'}).json()['id']
        assert c.get(f'/api/workspaces/{other}/question-markdown').json() == []
        assert c.get(f"/api/workspaces/{other}/question-markdown/{items[0]['id']}").status_code == 404
        assert c.post(f"/api/workspaces/{other}/imports/{job['id']}/question-markdown", json=body).status_code == 404
        exported = c.get(f'{SCOPE}/export')
        assert exported.status_code == 200
        with ZipFile(io.BytesIO(exported.content)) as archive:
            for item in items:
                detail = c.get(f"{SCOPE}/question-markdown/{item['id']}").json()
                md = c.get(f"{SCOPE}/resources/{item['markdown_resource_id']}").content
                path = tmp_path / f"workspaces/default/questions/{item['id']}/question.md"
                assert path.read_bytes() == md == detail['markdown'].encode('utf-8')
                assert 'not_inferred' in detail['markdown'] and 'unverified' in detail['markdown']
                assert hashlib.sha256(raw).hexdigest() in detail['markdown']
                assert archive.read(f"questions/{item['id']}/question.md") == md
                for image_id in re.findall(r'assets/([a-f0-9]{32})\.png', detail['markdown']):
                    image = archive.read(f"questions/{item['id']}/assets/{image_id}.png")
                    assert image.startswith(b'\x89PNG')
                    assert (path.parent / f'assets/{image_id}.png').read_bytes() == image
        assert c.get(f"{SCOPE}/resources/{job['resource_id']}").content == raw
    with client(tmp_path) as c:
        assert len(c.get(f'{SCOPE}/question-markdown').json()) == 2
        assert c.post(f"{SCOPE}/imports/{job['id']}/question-markdown", json=body).json() == items
    before = snapshot(tmp_path)
    checked = library_integrity.check_library(tmp_path)
    assert checked['complete'] and checked['healthy'] and not checked['issues'], checked
    assert snapshot(tmp_path) == before


def test_recovery_preview_matches_only_complete_unregistered_files(tmp_path, monkeypatch):
    with client(tmp_path) as c:
        job = upload(c, (SAMPLES / 'numbered-questions.docx').read_bytes(), '恢复题目.docx').json()
        base = f"{SCOPE}/imports/{job['id']}/question-markdown"
        with monkeypatch.context() as patch:
            def interrupted(*args, **kwargs):
                raise OSError('fixture after all question bytes are written')
            patch.setattr(markdown_questions.Resource, '__init__', interrupted)
            assert c.post(base, json={'expected_revision': job['draft_revision'],
                                      'selected': [0], 'confirm': True}).status_code == 500
        directory, = (tmp_path / 'workspaces/default/questions').iterdir()
        url = base + '/recovery-preview'
        body = dict(directory_id=directory.name, ordinal=0, expected_revision=job['draft_revision'])
        before = snapshot(tmp_path)
        response = c.post(url, json=body)
        assert response.status_code == 200, response.text
        value = response.json()
        assert value['status'] == 'matched' and value['source_resource_id'] == job['resource_id']
        assert value['markdown_sha256'] == hashlib.sha256((directory / 'question.md').read_bytes()).hexdigest()
        assert value['attachment_count'] == len(list((directory / 'assets').iterdir())) > 0
        assert c.post(url, json=body).json() == value
        assert c.post(url, json={**body, 'ordinal': 1}).status_code == 409
        assert c.post(url, json={**body, 'ordinal': True}).status_code == 422
        assert c.post(url, json={**body, 'expected_revision': '0'*64}).status_code == 409
        assert c.get(f'{SCOPE}/question-markdown').json() == []
        assert snapshot(tmp_path) == before
        other = c.post('/api/workspaces', json={'name': '其他空间'}).json()['id']
        assert c.post(url.replace('/default/', f'/{other}/'), json=body).status_code == 404

        extra = directory / 'unregistered.txt'
        extra.write_text('keep', encoding='utf8')
        assert c.post(url, json=body).status_code == 409 and extra.read_bytes() == b'keep'
        extra.unlink()
        image = next((directory / 'assets').iterdir())
        original = image.read_bytes()
        image.write_bytes(bytes([original[0] ^ 1]) + original[1:])
        assert c.post(url, json=body).status_code == 409
        image.write_bytes(original)
        with monkeypatch.context() as limits:
            def oversized(row, workspace):
                if row.id == value['attachments'][0]['id']:
                    row.size = 64 * 1024 * 1024 + 1
            limits.setattr(markdown_questions, 'check_recovery_resource', oversized)
            assert c.post(url, json=body).status_code == 413
        assert c.post(url, json=body).json() == value
        with sqlite3.connect(tmp_path / 'study.db') as db:
            preview = json.loads(db.execute('SELECT preview FROM import_jobs WHERE id=?', (job['id'],)).fetchone()[0])
            drafts = preview['question_drafts']
            drafts.append(drafts[0])
            db.execute('UPDATE import_jobs SET preview=? WHERE id=?', (json.dumps(preview), job['id']))
        ambiguous = c.post(url, json={**body, 'expected_revision': draft_revision(drafts)})
        assert ambiguous.status_code == 409 and '同批多个候选' in ambiguous.text


def test_recovery_writes_new_question_once_and_restores_its_receipt(tmp_path, monkeypatch):
    root = tmp_path / 'library'
    with client(root) as c:
        job = upload(c, (SAMPLES / 'numbered-questions.docx').read_bytes(), '恢复题目.docx').json()
        base = f"{SCOPE}/imports/{job['id']}/question-markdown"
        first = dict(expected_revision=job['draft_revision'], selected=[0], confirm=True)

        def interrupted(*args, **kwargs):
            raise OSError('test interruption before registration')

        with monkeypatch.context() as patch:
            patch.setattr(markdown_questions.Resource, '__init__', interrupted)
            assert c.post(base, json=first).status_code == 500
        folder = root / 'workspaces/default/questions'
        source, = folder.iterdir()
        before = snapshot(source)
        selection = dict(directory_id=source.name, ordinal=0, expected_revision=job['draft_revision'])
        match = c.post(base + '/recovery-preview', json=selection).json()
        assert match['confirmation'] == dict(selected=[0], finalizes_batch=True)
        request = dict(**selection, request_id='recovery-test-001', candidate_sha256=match['candidate_sha256'],
                       confirm_single_question=True)
        url = base + '/recover'
        for false_value in (False, 1):
            assert c.post(url, json={**request, 'confirm_single_question': false_value}).status_code == 422
        assert c.post(url, json={**request, 'candidate_sha256': '0'*64}).status_code == 409
        assert c.post(url.replace('/default/', '/missing/'), json=request).status_code == 404
        md = source / 'question.md'
        md.write_bytes(before['question.md'] + b'changed')
        assert c.post(url, json=request).status_code == 409
        md.write_bytes(before['question.md'])
        with monkeypatch.context() as patch:
            patch.setattr(markdown_questions.Resource, '__init__', interrupted)
            assert c.post(url, json=request).status_code == 500
        assert c.get(f'{SCOPE}/question-markdown').json() == []
        failed, = set(folder.iterdir()) - {source}
        assert snapshot(failed) == before
    with client(root) as c, ThreadPoolExecutor(2) as pool:
        calls = [pool.submit(c.post, url, json=request) for _ in range(2)]
        responses = [call.result(timeout=30) for call in calls]
        assert [r.status_code for r in responses] == [200, 200]
        receipt = responses[0].json()
        target = receipt['target']
        assert receipt == responses[1].json() and receipt['request'] == request
        assert receipt['markdown_sha256'] == hashlib.sha256(before['question.md']).hexdigest()
        assert (target['source_resource_id'], receipt['import_job_id']) == (job['resource_id'], job['id'])
        assert source.name != target['id'] and set(folder.iterdir()) == {source, failed, folder / target['id']}
        assert all(snapshot(path) == before for path in folder.iterdir())
        assert c.post(base, json=first).json() == [target]
        assert c.post(base, json={**first, 'selected': [1]}).status_code == 409
        assert c.post(url, json={**request, 'request_id': 'changed-request-01'}).status_code == 409
        assert c.post(url, json={**request, 'ordinal': 1}).status_code == 409
    archive, restored = tmp_path / 'backup.zip', tmp_path / 'restored'
    backup_store.create_backup(root, archive)
    backup_store.restore_backup(archive, restored, tmp_path / 'settings.json')
    with client(restored) as c:
        assert c.post(url, json=request).json() == receipt
        assert c.get(f'{SCOPE}/question-markdown').json() == [target]
        assert c.get(f"{SCOPE}/resources/{target['markdown_resource_id']}").content == before['question.md']
    assert snapshot(restored / 'workspaces/default/questions') == snapshot(folder)


@pytest.mark.parametrize('stage', ['assets_only', 'markdown_written'])
def test_interrupted_question_persistence_is_detected_without_registering_or_changing_bytes(tmp_path, monkeypatch, stage):
    with client(tmp_path) as c:
        job = upload(c, (SAMPLES / 'numbered-questions.docx').read_bytes(), '题目.docx').json()
        original_path = markdown_questions.resource_path

        def fail(*args, **kwargs):
            raise OSError('injected question persistence failure')

        def interrupted_path(root, relative):
            if relative.endswith('/question.md'):
                fail()
            return original_path(root, relative)

        with monkeypatch.context() as patch:
            if stage == 'assets_only':
                patch.setattr(markdown_questions, 'resource_path', interrupted_path)
            else:
                patch.setattr(markdown_questions.Resource, '__init__', fail)
            response = c.post(f"{SCOPE}/imports/{job['id']}/question-markdown", json={
                'expected_revision': job['draft_revision'], 'selected': [0], 'confirm': True})
            assert response.status_code == 500 and response.json()['error']['code'] == 'internal_error'
            assert response.json()['detail'] == '请求未完成，请稍后重试'
            assert 'injected question persistence failure' not in response.text
        assert c.get(f'{SCOPE}/question-markdown').json() == []
    orphan, = (tmp_path / 'workspaces/default/questions').iterdir()
    assert list((orphan / 'assets').glob('*.png'))
    assert (orphan / 'question.md').exists() is (stage == 'markdown_written')
    before = snapshot(tmp_path)
    checked = library_integrity.check_library(tmp_path)
    assert checked['complete'] and not checked['healthy'], checked
    assert checked['issues'] == [dict(code='unreferenced_derived_candidate', severity='warning',
                                      relative_path=orphan.relative_to(tmp_path).as_posix())]
    assert snapshot(tmp_path) == before
    with client(tmp_path) as c:
        response = c.post(f"{SCOPE}/imports/{job['id']}/question-markdown/recovery-preview", json={
            'directory_id': orphan.name, 'ordinal': 0, 'expected_revision': job['draft_revision']})
        assert response.status_code == (200 if stage == 'markdown_written' else 409)
        assert c.get(f'{SCOPE}/question-markdown').json() == []


def test_split_confirmation_validates_selection_revision_and_auth(tmp_path):
    with client(tmp_path) as c:
        raw = (SAMPLES / 'numbered-questions.docx').read_bytes()
        job = upload(c, raw, '题目.docx').json()
        url = f"{SCOPE}/imports/{job['id']}/question-markdown"
        body = {'expected_revision': job['draft_revision'], 'selected': [0], 'confirm': True}
        for selected in ([], [0, 0], [-1], [2], [True], ['0']):
            assert c.post(url, json={**body, 'selected': selected}).status_code == 422
        assert c.post(url, json={**body, 'confirm': False}).status_code == 422
        assert c.post(url, json={**body, 'expected_revision': '0' * 64}).status_code == 409
        assert c.post(url, json=body, headers={'Origin': 'https://example.com'}).status_code == 403
        assert c.post(url, json=body, headers={'Authorization': 'bad'}).status_code == 401
        assert c.get(f'{SCOPE}/question-markdown').json() == []
        assert c.post(url, json=body).status_code == 200
        assert c.post(url, json={**body, 'selected': [1]}).status_code == 409
        with sqlite3.connect(tmp_path / 'study.db') as db:
            assert db.execute('SELECT count(*) FROM markdown_questions').fetchone() == (1,)
            assert db.execute('PRAGMA foreign_key_check').fetchall() == []


def test_splitter_avoids_decimal_and_subquestion_markers_and_keeps_attachments():
    blocks = [{'type': 'text', 'text': '卷头\n1. 主问题\n(1) 小问\n1.25 是小数'},
              {'type': 'image', 'attachment_id': 'image', 'alt': '图'},
              {'type': 'text', 'text': '第2题：另一题\n条件'}]
    drafts = split_blocks(blocks)
    assert len(drafts) == 2
    assert len(drafts[0]['blocks']) == 2
    assert '1.25' in drafts[0]['blocks'][0]['text']
    assert split_blocks([{'type': 'text', 'text': '无可靠题号的资料'}]) == []


def test_word_automatic_numbering_creates_two_candidates(tmp_path):
    from docx import Document

    document = Document()
    document.add_paragraph('First question', style='List Number')
    document.add_paragraph('Second question', style='List Number')
    data = io.BytesIO()
    document.save(data)
    with client(tmp_path) as c:
        job = upload(c, data.getvalue(), '自动编号.docx').json()
        assert job['status'] == 'preview', job
        assert len(job['preview']['question_drafts']) == 2
        assert 'First question' in job['question_markdown'][0]
        assert 'Second question' not in job['question_markdown'][0]
