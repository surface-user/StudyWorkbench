import hashlib
import json
import sqlite3
from pathlib import Path

import pytest
from study_workbench import library_integrity as scan
from test_imports import SCOPE, client, upload
from test_library_integrity import snapshot


def extracted(root, *, archived=False):
    with client(root) as c:
        scope = SCOPE
        if archived:
            workspace = c.post('/api/workspaces', json={'name': 'Archived fixtures'}).json()['id']
            scope = f'/api/workspaces/{workspace}'
        raw = (Path(__file__).parents[2] / 'contracts/samples/numbered-questions.docx').read_bytes()
        job = upload(c, raw, 'fixture.docx', scope=scope).json()
        response = c.post(f"{scope}/imports/{job['id']}/question-markdown", json={
            'expected_revision': job['draft_revision'], 'selected': [0], 'confirm': True})
        assert response.status_code == 200, response.text
        item = response.json()[0]
        if archived:
            assert c.request('DELETE', f'/api/workspaces/{workspace}', json={
                'confirm_name': 'Archived fixtures'}).status_code == 200
    with sqlite3.connect(root / 'study.db') as db:
        db.row_factory = sqlite3.Row
        question = dict(db.execute('SELECT * FROM markdown_questions WHERE id=?', (item['id'],)).fetchone())
        md = db.execute('SELECT relative_path FROM resources WHERE id=?', (item['markdown_resource_id'],)).fetchone()[0]
        asset = next((root / md).parent.joinpath('assets').glob('*.png'))
        original = dict(db.execute('SELECT * FROM resources WHERE id=?', (asset.stem,)).fetchone())
    return question, asset, original


def replace_content(root, question, content):
    with sqlite3.connect(root / 'study.db') as db:
        db.execute('UPDATE markdown_questions SET content=? WHERE id=?', (content, question['id']))


@pytest.mark.parametrize('damage', ['missing', 'same_size', 'truncated'])
def test_registered_image_copy_damage_is_reported_without_touching_original_or_any_bytes(tmp_path, damage):
    _, asset, resource = extracted(tmp_path)
    source = tmp_path / resource['relative_path']
    original = source.read_bytes()
    raw = asset.read_bytes()
    assert raw == original
    if damage == 'missing':
        asset.unlink()
    else:
        asset.write_bytes(raw[:-1] if damage == 'truncated' else raw[:-1] + bytes([raw[-1] ^ 1]))
    before = snapshot(tmp_path)
    checked = scan.check_library(tmp_path)
    assert checked['complete'] and not checked['healthy'], checked
    code = {'missing': 'missing_file', 'same_size': 'hash_mismatch', 'truncated': 'size_mismatch'}[damage]
    assert dict(code=code, severity='error', relative_path=asset.relative_to(tmp_path).as_posix()) in checked['issues']
    assert source.read_bytes() == original and snapshot(tmp_path) == before


@pytest.mark.parametrize('reference', ['missing', 'foreign'])
def test_image_reference_must_exist_in_the_question_workspace(tmp_path, reference):
    question, asset, _ = extracted(tmp_path)
    content = json.loads(question['content'])
    image = next(b for b in content['blocks'] if b['type'] == 'image')
    image['attachment_id'] = 'unknown-image'
    if reference == 'foreign':
        with client(tmp_path) as c:
            workspace = c.post('/api/workspaces', json={'name': 'Other fixtures'}).json()['id']
        relative = f'workspaces/{workspace}/originals/foreign.bin'
        path = tmp_path / relative
        path.parent.mkdir(parents=True)
        raw = asset.read_bytes()
        path.write_bytes(raw)
        with sqlite3.connect(tmp_path / 'study.db') as db:
            db.execute('INSERT INTO resources (id,workspace_id,original_name,relative_path,sha256,size,mime) '
                       'VALUES (?,?,?,?,?,?,?)',
                       ('unknown-image', workspace, 'foreign.png', relative, hashlib.sha256(raw).hexdigest(),
                        len(raw), 'image/png'))
    replace_content(tmp_path, question, json.dumps(content))
    before = snapshot(tmp_path)
    checked = scan.check_library(tmp_path)
    assert checked['complete'] and not checked['healthy'], checked
    assert checked['issues'] == [dict(code='invalid_legacy_attachment_reference', severity='error')]
    assert snapshot(tmp_path) == before


@pytest.mark.parametrize('reference', ['source_resource', 'foreign_workspace'])
def test_question_must_bind_its_same_workspace_fixed_markdown_resource(tmp_path, reference):
    question, _, _ = extracted(tmp_path)
    if reference == 'foreign_workspace':
        with client(tmp_path) as c:
            workspace = c.post('/api/workspaces', json={'name': 'Other fixtures'}).json()['id']
    with sqlite3.connect(tmp_path / 'study.db') as db:
        if reference == 'source_resource':
            db.execute('UPDATE markdown_questions SET markdown_resource_id=source_resource_id WHERE id=?',
                       (question['id'],))
        else:
            db.execute('UPDATE markdown_questions SET workspace_id=? WHERE id=?', (workspace, question['id']))
    before = snapshot(tmp_path)
    checked = scan.check_library(tmp_path)
    assert checked['complete'] and not checked['healthy'], checked
    assert checked['issues'] == [dict(code='invalid_legacy_question_reference', severity='error')]
    assert snapshot(tmp_path) == before


def test_shared_material_images_and_duplicate_references_hash_each_copy_once(tmp_path):
    question, asset, _ = extracted(tmp_path)
    baseline = scan.check_library(tmp_path)
    content = json.loads(question['content'])
    image = next(b for b in content['blocks'] if b['type'] == 'image' and b['attachment_id'] == asset.stem)
    content['blocks'].remove(image)
    content['shared_materials'] = [{'blocks': [image, image]}]
    replace_content(tmp_path, question, json.dumps(content))
    before = snapshot(tmp_path)
    checked = scan.check_library(tmp_path)
    assert checked['complete'] and checked['healthy'], checked
    assert checked['bytes_hashed'] == baseline['bytes_hashed']
    assert snapshot(tmp_path) == before
    raw = asset.read_bytes()
    asset.write_bytes(raw[:-1] + bytes([raw[-1] ^ 1]))
    before = snapshot(tmp_path)
    checked = scan.check_library(tmp_path)
    assert checked['complete'] and not checked['healthy'], checked
    assert [i['code'] for i in checked['issues']] == ['hash_mismatch', 'hash_mismatch']
    assert snapshot(tmp_path) == before


@pytest.mark.parametrize('content', ['{', '[]'])
def test_invalid_legacy_metadata_is_incomplete_and_never_healthy(tmp_path, content):
    question, _, _ = extracted(tmp_path)
    replace_content(tmp_path, question, content)
    before = snapshot(tmp_path)
    checked = scan.check_library(tmp_path)
    assert not checked['complete'] and not checked['healthy'], checked
    assert any(i['code'] == 'scan_unreadable' for i in checked['issues'])
    assert snapshot(tmp_path) == before


def test_unsafe_attachment_identifier_is_rejected_before_open(tmp_path, monkeypatch):
    question, asset, _ = extracted(tmp_path)
    content = json.loads(question['content'])
    for block in content['blocks']:
        if block.get('attachment_id') == asset.stem:
            block['attachment_id'] = '../../unsafe'
    with sqlite3.connect(tmp_path / 'study.db') as db:
        db.execute('UPDATE resources SET id=? WHERE id=?', ('../../unsafe', asset.stem))
    replace_content(tmp_path, question, json.dumps(content))
    before = snapshot(tmp_path)
    original_open = Path.open
    def guarded(path, *args, **kwargs):
        assert '..' not in path.parts, 'Unvalidated derived path was opened'
        return original_open(path, *args, **kwargs)
    with monkeypatch.context() as patch:
        patch.setattr(Path, 'open', guarded)
        checked = scan.check_library(tmp_path)
    assert any(i['code'] == 'unsafe_reference' for i in checked['issues']), checked
    assert not checked['healthy'] and snapshot(tmp_path) == before


@pytest.mark.parametrize('budget', ['bytes', 'rows'])
def test_legacy_rows_and_copied_image_bytes_share_original_scan_budgets(tmp_path, monkeypatch, budget):
    extracted(tmp_path)
    with sqlite3.connect(tmp_path / 'study.db') as db:
        count, size = db.execute('SELECT count(*),sum(size) FROM resources').fetchone()
    monkeypatch.setattr(scan, 'BYTE_LIMIT' if budget == 'bytes' else 'ROW_LIMIT', size if budget == 'bytes' else count)
    before = snapshot(tmp_path)
    checked = scan.check_library(tmp_path)
    assert not checked['complete'] and not checked['healthy'], checked
    assert checked['limit_reason'] == ('byte_limit' if budget == 'bytes' else 'row_limit')
    assert snapshot(tmp_path) == before


def test_registered_images_in_archived_workspaces_are_checked_without_false_orphans(tmp_path):
    _, asset, _ = extracted(tmp_path, archived=True)
    before = snapshot(tmp_path)
    checked = scan.check_library(tmp_path)
    assert checked['complete'] and checked['healthy'], checked
    assert snapshot(tmp_path) == before
    asset.unlink()
    before = snapshot(tmp_path)
    checked = scan.check_library(tmp_path)
    assert not checked['healthy'] and any(i['code'] == 'missing_file' for i in checked['issues']), checked
    assert not any(i['code'] == 'unreferenced_derived_candidate' for i in checked['issues'])
    assert snapshot(tmp_path) == before
