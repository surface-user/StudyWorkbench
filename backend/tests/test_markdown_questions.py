import hashlib
import io
import re
import sqlite3
from pathlib import Path
from zipfile import ZipFile

import pytest
from study_workbench import library_integrity, markdown_questions
from study_workbench.question_splitting import split_blocks
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
            with pytest.raises(OSError, match='injected question persistence failure'):
                c.post(f"{SCOPE}/imports/{job['id']}/question-markdown", json={
                    'expected_revision': job['draft_revision'], 'selected': [0], 'confirm': True})
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
