import hashlib
import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event

import pytest
from study_workbench import backup_store, word_jobs
from test_document_files import PREFIX, add, client
from test_draft_editing import edit
from test_word_candidates import numbered, original

API = PREFIX + '/word-range-jobs'


def managed(c, root, raw=None, first=2, last=3):
    data = original(numbered()) if raw is None else raw
    node, resource, path = add(c, root, '原题.docx', data)
    body = dict(node_id=node, expected_sha256=hashlib.sha256(data).hexdigest(), first_position=first, last_position=last)
    response = c.post(API, json=body)
    assert response.status_code == 200, response.text
    return API + '/' + response.json()['id'], body, path, resource


def test_explicit_selection_confirm_receipt_and_replay(tmp_path):
    raw = original(numbered())
    with client(tmp_path) as c:
        url, body, path, resource = managed(c, tmp_path, raw)
        job = c.get(url).json()
        assert job['status'] == 'ready' and job['completed_positions'] == 0
        assert c.post(API, json=body).json() == job
        assert c.get(url.replace('/default/', '/foreign/')).status_code == 404
        assert c.get(API).json() == [job]
        assert c.post(API, json={**body, 'last_position': 22}).status_code == 422
        assert c.get(url + '/preview').status_code == 409
        cancelled = c.post(url + '/cancel').json()
        assert cancelled['status'] == 'cancelled' and c.post(url + '/cancel').json() == cancelled
        assert c.post(url + '/advance').status_code == 409
        assert c.post(url + '/resume').json()['status'] == 'ready'
        ready = c.post(url + '/advance').json()
        assert ready['status'] == 'preview' and ready['completed_positions'] == 2
        assert c.post(url + '/advance').json() == ready
        items = c.get(url + '/preview').json()
        assert [d['title'] for d in items['preview']['question_drafts']] == ['2. 选取第二题', '3. 选取第三题']
        batch = PREFIX + '/imports/' + job['id']
        assert c.post(batch + '/retry').status_code == 409
        assert c.post(batch + '/confirm').status_code == 409
        assert c.get(PREFIX + '/question-markdown').json() == []
        confirm = {'selected': [1], 'expected_revision': items['draft_revision'], 'confirm': True}
        assert c.post(batch + '/question-markdown', json={**confirm, 'confirm': False}).status_code == 422
        path.write_bytes(raw + b'x')
        assert c.get(url + '/preview').status_code == 409
        assert c.post(batch + '/question-markdown', json=confirm).status_code == 409
        path.write_bytes(raw)
        selected = c.post(batch + '/question-markdown', json=confirm)
        assert selected.status_code == 200, selected.text
        selected = selected.json()
        assert len(selected) == 1 and selected[0]['source_resource_id'] == resource
        text = c.get(PREFIX + '/resources/' + selected[0]['markdown_resource_id']).content.decode()
        provenance = json.loads(text.split('```json\n')[1].split('\n```')[0])
        assert provenance['selected_body_range'] == [2, 3] and provenance['source_positions'] == [3]
        assert provenance['pages'] == [] and '选取第二题' not in text
        path.write_bytes(raw + b'changed after confirmation')
        assert c.post(batch + '/question-markdown', json=confirm).json() == selected
        assert c.post(batch + '/question-markdown', json={**confirm, 'selected': [0]}).status_code == 409
        path.write_bytes(raw)
        for command in ('advance','cancel','resume'):
            assert c.post(url + '/' + command).json()['status'] == 'confirmed'
        assert len(c.get(PREFIX + '/question-markdown').json()) == 1 and path.read_bytes() == raw


def test_late_result_after_cancel_and_new_generation_cannot_write(tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).parents[2] / 'tools'))
    from numbered_cell_sample import numbered_cell_docx
    with client(tmp_path) as c:
        url, _, original_path, _ = managed(c, tmp_path, numbered_cell_docx(), 1, 5)
        real = word_jobs.parse_word_range
        entered, release = Event(), Event()
        stale_assets = set()
        def pause_first(data, first, last):
            result = real(data, first, last)
            if not entered.is_set():
                stale_assets.update(asset['id'] for asset in result['assets'])
                entered.set()
                assert release.wait(60)
            return result
        monkeypatch.setattr(word_jobs, 'parse_word_range', pause_first)
        with ThreadPoolExecutor(1) as executor:
            old = executor.submit(c.post, url + '/advance')
            try:
                assert entered.wait(35)
                assert c.post(url + '/resume').status_code == 409
                assert c.post(url + '/cancel').json()['status'] == 'cancelled'
                assert c.get(url + '/preview').status_code == 409
                assert c.post(url + '/resume').json()['status'] == 'ready'
                valid = c.post(url + '/advance')
                assert valid.status_code == 200 and valid.json()['status'] == 'preview'
            finally:
                release.set()
            assert old.result(timeout=15).status_code == 409
        assert c.get(url).json() == valid.json() and c.get(url + '/preview').json()['preview']['question_drafts']
        with sqlite3.connect(tmp_path / 'study.db') as conn:
            assert not any(conn.execute('SELECT 1 FROM resources WHERE id=?',(i,)).fetchone() for i in stale_assets)
        assert stale_assets and all(not (original_path.parent / (i + '.bin')).exists() for i in stale_assets)


def test_restart_backup_and_source_or_parser_changes(tmp_path):
    root = tmp_path/'data'
    raw = original(numbered())
    with client(root) as c:
        url, _, path, _ = managed(c, root, raw)
        job = c.get(url).json()
    with sqlite3.connect(root/'study.db') as db:
        db.execute("UPDATE import_jobs SET status='running' WHERE id=?", (job['id'],))
    with client(root) as c:
        stopped = c.get(url).json()
        assert stopped['status'] == 'interrupted' and stopped['generation'] > job['generation']
        path.write_bytes(raw + b'x')
        assert c.post(url + '/resume').status_code == 409
        assert c.get(url).json() == stopped
        path.write_bytes(raw)
    package, restored = tmp_path/'valid.zip', tmp_path/'restored'
    backup_store.create_backup(root, package)
    backup_store.restore_backup(package, restored, tmp_path/'settings.json')
    with client(restored) as c:
        assert c.get(url).json() == stopped
        assert c.post(url + '/resume').json()['status'] == 'ready'
        assert c.post(url + '/advance').json()['status'] == 'preview'
        with sqlite3.connect(restored/'study.db') as db:
            db.execute("UPDATE import_jobs SET parser_version='docx-range-job-unknown' WHERE id=?", (job['id'],))
        assert c.post(url + '/resume').status_code == 409
        assert c.get(url + '/preview').status_code == 409
        assert c.post(url + '/advance').status_code == 409
    with sqlite3.connect(root/'study.db') as db:
        db.execute("UPDATE import_jobs SET preview=json_set(preview,'$.word_range.source_sha256',?) WHERE id=?",
                   ('0'*64, job['id']))
    with pytest.raises(ValueError, match='原件'):
        backup_store.create_backup(root, tmp_path/'wrong.zip')


def test_changed_original_before_commit_keeps_checkpoint_and_writes_no_candidates(tmp_path, monkeypatch):
    raw = original(numbered())
    with client(tmp_path) as c:
        url, _, path, _ = managed(c, tmp_path, raw)
        real = word_jobs.parse_word_range
        def replace_after_read(data, first, last):
            value = real(data, first, last)
            path.write_bytes(raw + b'updated')
            return value
        monkeypatch.setattr(word_jobs, 'parse_word_range', replace_after_read)
        assert c.post(url + '/advance').status_code == 409
        job = c.get(url).json()
        assert job['status'] == 'failed' and job['completed_positions'] == 0
        assert c.get(url + '/preview').status_code == 409 and c.post(url + '/resume').status_code == 409
        path.write_bytes(raw)
        assert c.post(url + '/resume').json()['status'] == 'ready'


def test_restoring_rich_preview_checks_attachments(tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).parents[2] / 'tools'))
    from numbered_cell_sample import numbered_cell_docx
    root, restored = tmp_path / 'data', tmp_path / 'restored'
    with client(root) as c:
        url, _, _, _ = managed(c, root, numbered_cell_docx(), 1, 5)
        assert c.post(url + '/advance').json()['status'] == 'preview'
        job = c.get(url + '/preview').json()
        blocks = job['preview']['blocks']
        image_index = next(i for i, block in enumerate(blocks) if block['type'] == 'image')
        assert any(block['type'] == 'latex' for block in blocks)
        image_url = PREFIX + '/resources/' + blocks[image_index]['attachment_id']
        image_bytes = c.get(image_url).content
        assert image_bytes.startswith(b'\x89PNG')
    package = tmp_path / 'rich.zip'
    backup_store.create_backup(root, package)
    backup_store.restore_backup(package, restored, tmp_path / 'settings.json')
    with client(restored) as c:
        assert c.get(url + '/preview').json() == job
        assert c.get(image_url).content == image_bytes
        confirmed = c.post(PREFIX + '/imports/' + job['id'] + '/question-markdown', json={
            'selected': [0], 'expected_revision': job['draft_revision'], 'confirm': True})
        assert confirmed.status_code == 200, confirmed.text
    with sqlite3.connect(root / 'study.db') as db:
        db.execute('UPDATE import_jobs SET preview=json_set(preview,?,?) WHERE id=?',
                   (f'$.blocks[{image_index}].attachment_id', 'missing', job['id']))
    with pytest.raises(ValueError, match='图片'):
        backup_store.create_backup(root, tmp_path / 'broken.zip')


def test_draft_edits_keep_each_original_position_and_whole_import_separate(tmp_path):
    with client(tmp_path) as c:
        url, _, _, resource = managed(c, tmp_path)
        assert c.post(url + '/advance').json()['status'] == 'preview'
        job = c.get(url + '/preview').json()
        merged = edit(c, job, 'merge_next').json()
        item = merged['preview']['question_drafts'][0]
        assert item['block_positions'] == item['source_positions'] == [2, 3]
        split = edit(c, merged, 'split_block', position=1, title='第三题').json()
        assert [d['source_positions'] for d in split['preview']['question_drafts']] == [[2], [3]]
        shared = edit(c, split, 'share', source_blocks=[0], targets=[1]).json()
        assert shared['preview']['question_drafts'][1]['shared_materials'][0]['source_positions'] == [2]
        full = c.post(PREFIX + '/resources/' + resource + '/analyze')
        assert full.status_code == 200 and full.json()['id'] != job['id']
        assert c.get(url + '/preview').json()['draft_revision'] == shared['draft_revision']


def test_rebound_node_cannot_confirm_old_original(tmp_path):
    with client(tmp_path) as c:
        url, body, _, _ = managed(c, tmp_path)
        assert c.post(url + '/advance').json()['status'] == 'preview'
        job = c.get(url + '/preview').json()
        _, replacement, _ = add(c, tmp_path, '另一原件.docx', original(numbered()) + b'different bytes')
        with sqlite3.connect(tmp_path / 'study.db') as db:
            db.execute('UPDATE workspace_nodes SET resource_id=? WHERE id=?', (replacement, body['node_id']))
        assert c.get(url + '/preview').status_code == 409
        confirm = {'selected': [0], 'expected_revision': job['draft_revision'], 'confirm': True}
        assert c.post(PREFIX + '/imports/' + job['id'] + '/question-markdown', json=confirm).status_code == 409
        assert c.get(PREFIX + '/question-markdown').json() == []
