import hashlib
from pathlib import Path

from test_imports import SCOPE, client, upload

SAMPLES = Path(__file__).parents[2] / 'contracts/samples'


def edit(c, job, action, **values):
    return c.post(f"{SCOPE}/imports/{job['id']}/question-drafts/edit", json={
        'expected_revision': job['draft_revision'], 'action': action, 'index': 0, **values})


def test_word_merge_split_shared_material_and_immutable_original(tmp_path):
    raw = (SAMPLES / 'numbered-questions.docx').read_bytes()
    with client(tmp_path) as c:
        job = upload(c, raw, '题目.docx').json()
        first_count = len(job['preview']['question_drafts'][0]['blocks'])
        merged = edit(c, job, 'merge_next')
        assert merged.status_code == 200, merged.text
        merged = merged.json()
        assert len(merged['preview']['question_drafts']) == 1
        assert edit(c, job, 'merge_next').status_code == 409
        separated = edit(c, merged, 'split_block', position=first_count, title='恢复第二题')
        assert separated.status_code == 200, separated.text
        separated = separated.json()
        assert len(separated['preview']['question_drafts']) == 2
        assert '没有标准答案' not in separated['question_markdown'][0]
        shared = edit(c, separated, 'share', source_blocks=[0], targets=[0, 1]).json()
        drafts = shared['preview']['question_drafts']
        assert drafts[0]['shared_materials'][0]['id'] == drafts[1]['shared_materials'][0]['id']
        assert 'Self-authored practice' in shared['question_markdown'][0]
        assert 'Self-authored practice' in shared['question_markdown'][1]
        result = c.post(f"{SCOPE}/imports/{job['id']}/question-markdown", json={
            'expected_revision': shared['draft_revision'], 'selected': [0, 1], 'confirm': True})
        assert result.status_code == 200
        assert edit(c, shared, 'rename', title='不能覆盖').status_code == 409
        assert hashlib.sha256(c.get(f"{SCOPE}/resources/{job['resource_id']}").content).digest() == hashlib.sha256(raw).digest()
    with client(tmp_path) as c:
        assert len(c.get(f'{SCOPE}/question-markdown').json()) == 2


def test_pdf_manual_split_matches_regions_and_keeps_source(tmp_path):
    raw = (SAMPLES / 'numbered-questions.pdf').read_bytes()
    with client(tmp_path) as c:
        job = upload(c, raw, '跨页.pdf').json()
        assert edit(c, job, 'split_block', position=1).status_code == 422
        box = job['preview']['question_drafts'][0]['regions'][0]['box']
        cut = (box[1] + box[3]) / 2
        result = edit(c, job, 'split_region', position=0, cut=cut, title='新分割题目')
        assert result.status_code == 200, result.text
        updated = result.json()
        first, second, _ = updated['preview']['question_drafts']
        assert first['regions'][-1]['box'][3] == second['regions'][0]['box'][1] == cut
        assert first['text_status'] == second['text_status'] == 'manual_crop_image_only'
        assert all(b['type'] == 'image' for b in first['blocks'] + second['blocks'])
        assert second['source_pages'] == [1, 2]
        for block in first['blocks'] + second['blocks']:
            assert c.get(f"{SCOPE}/resources/{block['attachment_id']}").content.startswith(b'\x89PNG')
        assert c.get(f"{SCOPE}/resources/{job['resource_id']}").content == raw
        assert c.get(f'{SCOPE}/question-markdown').json() == []
        assert edit(c, updated, 'split_region', cut=1).status_code == 422


def test_corrections_reject_cross_workspace_and_invalid_boundaries(tmp_path):
    with client(tmp_path) as c:
        job = upload(c, (SAMPLES / 'numbered-questions.docx').read_bytes(), '题.docx').json()
        assert edit(c, job, 'split_block', position=0).status_code == 422
        assert edit(c, job, 'share', source_blocks=[9999], targets=[0]).status_code == 422
        assert edit(c, job, 'share', source_blocks=[0], targets=[9999]).status_code == 422
        other = c.post('/api/workspaces', json={'name': '隔离'}).json()['id']
        assert c.post(f"/api/workspaces/{other}/imports/{job['id']}/question-drafts/edit", json={
            'expected_revision': job['draft_revision'], 'action': 'merge_next', 'index': 0}).status_code == 404
