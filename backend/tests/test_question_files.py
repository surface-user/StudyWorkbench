import base64
import hashlib
import io
import json
import sqlite3
from copy import deepcopy
from pathlib import Path
from zipfile import ZipFile

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from study_workbench.db import Attempt, QuestionVersion, Resource, database
from study_workbench.question_files_format import QuestionFile, parse_file, serialize_file
from test_document_files import add
from test_explorer import PREFIX, TOKEN, assert_preserved, client, snapshot
from test_imports import confirm, upload
from test_question_protocol import question

KINDS = ['single_choice', 'multiple_choice', 'fill_blank', 'calculation', 'proof', 'subjective', 'reading_question']


def file_for(kind='single_choice', *, missing=False):
    q = question(kind)
    if missing:
        q['answer'] = None
        if kind == 'fill_blank':
            q['blank_ids'] = ['blank-1']
    passage = dict(id='passage-1', content=[dict(type='text', text='阅读材料')], source=q['source']) if kind == 'reading_question' else None
    return QuestionFile(title='中文文件', question=q, passage=passage, future_metadata={'keep': ['未知字段', 1]})


@pytest.mark.parametrize('kind', KINDS)
@pytest.mark.parametrize('missing', [False, True])
def test_file_roundtrip_all_kinds_and_missing_answers(kind, missing):
    file = file_for(kind, missing=missing)
    file.question.stem[0].text += '\r\n<literal>&amp;\n<!-- swq:endsection -->\n'
    rendered = serialize_file(file)
    assert '## 题干' in rendered and '## 答案' in rendered
    assert parse_file(rendered) == file
    changed = rendered.replace('计算定积分', '编辑过的题干') if '计算定积分' in rendered else rendered.replace('&amp;amp;', '正文已改')
    assert parse_file(changed).question.stem != file.question.stem


def test_all_blocks_relative_attachments_and_visible_projection_guard():
    file = file_for()
    raw = file.model_dump(mode='json')
    raw['attachments'] = {key: {'path': f'assets/{key}.png', 'sha256': 'a' * 64, 'mime': 'image/png'}
                          for key in ['picture', 'chart', 'data']}
    raw['question']['stem'] += [
        {'type': 'image', 'attachment_id': 'picture', 'alt': '中文图', 'caption': '说明'},
        {'type': 'chart', 'attachment_id': 'chart', 'alt': '图表', 'data_attachment_id': 'data'},
        {'type': 'attachment', 'attachment_id': 'data', 'label': '数据'},
        {'type': 'table', 'headers': [[{'type': 'text', 'text': '变量'}]],
         'rows': [[[{'type': 'latex', 'tex': 'x=1', 'display': False}, {'type': 'text', 'text': 'A|B\n第二行'}]]]},
    ]
    file = QuestionFile.model_validate(raw)
    markdown = serialize_file(file)
    assert parse_file(markdown) == file
    with pytest.raises(ValueError, match='不一致'):
        parse_file(markdown.replace('![中文图]', '![只改投影]'))
    for path in ['../outside.png', 'https://example.com/x', 'assets/../x', 'assets/x%2epng']:
        bad = deepcopy(raw)
        bad['attachments']['picture']['path'] = path
        with pytest.raises(ValueError):
            serialize_file(bad)
    with pytest.raises(ValueError):
        parse_file(markdown.replace('"format_version": 1', '"format_version": true'))
    with pytest.raises(ValueError):
        parse_file(markdown.replace('"format_version": 1', '"format_version": 1, "format_version": 1'))
    with pytest.raises(ValueError):
        parse_file(markdown + '不可丢弃的尾部')


def preview(c, node):
    response = c.get(f'{PREFIX}/nodes/{node}/question-file')
    assert response.status_code == 200, response.text
    return response.json()


def publish(c, node, value):
    return c.post(f'{PREFIX}/nodes/{node}/question-file/confirm', json={
        'expected_sha256': value['sha256'], 'expected_version_id': value['confirmed_version_id'], 'confirm': True})


def test_legacy_conversion_confirm_versions_preserve_old_scores_and_retries(tmp_path):
    with client(tmp_path) as c:
        old = c.post(PREFIX + '/attempts', json={'question_id': 'demo-integral', 'response': {'selected': ['a']}}).json()
        original = c.get(PREFIX + '/questions/demo-integral').json()
        proposal = c.get(PREFIX + '/questions/demo-integral/file-preview').json()
        assert c.get(PREFIX + '/questions/demo-integral').json() == original
        response = c.post(PREFIX + '/questions/demo-integral/file', json={
            'expected_source_sha256': proposal['source_sha256'], 'expected_preview_sha256': proposal['preview_sha256'], 'confirm': True})
        assert response.status_code == 200, response.text
        node = response.json()['resource_item_id']
        value = preview(c, node)
        assert value['status'] == 'unconfirmed'
        first = publish(c, node, value)
        assert first.status_code == 200, first.text
        first = first.json()
        body = dict(question_id='demo-integral', question_revision=first['revision'],
                    question_version_id=first['id'], request_id='file_attempt_00001', response={'selected': ['a']})
        saved = c.post(PREFIX + '/attempts', json=body)
        assert saved.status_code == 200 and saved.json()['score'] == 1, saved.text
        doc = c.get(f'{PREFIX}/nodes/{node}/document').json()
        edited = parse_file(doc['text'])
        edited.question.answer.selected = ['b']
        changed = c.put(f'{PREFIX}/nodes/{node}/document', json={
            'expected_sha256': doc['sha256'], 'text': serialize_file(edited)})
        assert changed.status_code == 200, changed.text
        assert preview(c, node)['status'] == 'unconfirmed'
        assert c.get(PREFIX + '/questions/demo-integral').json()['answer']['selected'] == ['a']
        second = publish(c, node, preview(c, node))
        assert second.status_code == 200, second.text
        assert c.post(PREFIX + '/attempts', json=body).json()['id'] == saved.json()['id']
        assert c.post(PREFIX + '/attempts', json=dict(body, request_id='new_stale_0000001')).status_code == 409
        assert publish(c, node, value).status_code == 409
        history = c.get(PREFIX + '/attempts').json()
        assert next(a for a in history if a['id'] == old['id'])['score'] == 1
        assert next(a for a in history if a['id'] == old['id'])['question_version_id'] is None
        with Session(c.app.state.engine) as session:
            assert session.get(Attempt, saved.json()['id']).question_version_id == first['id']
            with pytest.raises(IntegrityError):
                session.execute(text('UPDATE question_versions SET revision=99 WHERE id=:id'), {'id': first['id']})
            session.rollback()
            assert session.get(QuestionVersion, first['id']).content['question']['answer']['selected'] == ['a']


@pytest.mark.parametrize('kind', KINDS)
def test_unanswered_files_are_pending_and_require_confirmed_version(tmp_path, kind):
    file = file_for(kind, missing=True)
    file.question.id = 'missing-' + kind
    raw = serialize_file(file).encode()
    with client(tmp_path) as c:
        node, _, original = add(c, tmp_path, '题目.md', raw)
        assert c.post(PREFIX + '/attempts', json={'question_id': file.question.id, 'response': {'text': '不应提交'}}).status_code == 404
        value = preview(c, node)
        published = publish(c, node, value)
        assert published.status_code == 200, published.text
        published = published.json()
        effective = file.question.response_kind if kind == 'reading_question' else kind
        response = {'selected': ['a']} if effective in {'single_choice', 'multiple_choice'} else {
            'blanks': {'blank-1': '1/3'}} if effective == 'fill_blank' else {'text': '待批改过程'}
        body = dict(question_id=file.question.id, question_version_id=published['id'], response=response)
        result = c.post(PREFIX + '/attempts', json=body)
        assert result.status_code == 200, result.text
        assert result.json()['status'] == 'pending_review' and result.json()['score'] is None
        assert c.post(PREFIX + '/attempts', json={'question_id': file.question.id, 'response': response}).status_code == 409
        assert original.read_bytes() == raw
        duplicate, _, _ = add(c, tmp_path, '重复.md', raw.replace('中文文件'.encode(), '复制文件'.encode()))
        assert c.get(f'{PREFIX}/nodes/{duplicate}/question-file').status_code == 409
        other = c.post('/api/workspaces', json={'name': '其他空间'}).json()['id']
        assert c.get(f"/api/workspaces/{other}/question-versions/{published['id']}").status_code == 404


def convert(c, identifier, *, markdown=False):
    path = PREFIX + ('/question-markdown/' if markdown else '/questions/') + identifier
    value = c.get(path + '/file-preview')
    assert value.status_code == 200, value.text
    value = value.json()
    result = c.post(path + '/file', json={'expected_source_sha256': value['source_sha256'],
        'expected_preview_sha256': value['preview_sha256'], 'confirm': True})
    assert result.status_code == 200, result.text
    return result.json()['resource_item_id']


def test_confirmed_assets_portable_export_and_scoped_reimport(tmp_path):
    png = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=')
    with client(tmp_path) as c:
        image = upload(c, png, 'figure.png').json()
        q = question()
        q['id'] = 'portable-question'
        q['stem'].append({'type': 'image', 'attachment_id': image['resource_id'], 'alt': '自编图示'})
        imported = upload(c, q).json()
        assert confirm(c, imported).status_code == 200
        node = convert(c, q['id'])
        assert c.get(f'{PREFIX}/nodes/{node}').json()['name'] == '题目-' + q['source']['title'] + '.md'
        version = publish(c, node, preview(c, node)).json()
        asset_endpoint = f"{PREFIX}/question-versions/{version['id']}/assets/{image['resource_id']}"
        assert base64.b64decode(c.get(asset_endpoint).json()['image_base64']) == png
        exported = c.get(PREFIX + '/export')
        assert exported.status_code == 200, exported.text
        portable = tmp_path.parent / (tmp_path.name + '-portable')
        portable.mkdir()
        with ZipFile(io.BytesIO(exported.content)) as archive:
            manifest = json.loads(archive.read('manifest.json'))
            assert manifest['schema_version'] == 2
            entry = next(row for row in manifest['question_files'] if row['question_id'] == q['id'])
            assert entry['versions'][0]['id'] == version['id']
            prefix = str(Path(entry['path']).parent).replace('\\', '/') + '/'
            for name in archive.namelist():
                if name.startswith(prefix) and '/versions/' not in name:
                    relative = name[len(prefix):]
                    assert '..' not in Path(relative).parts and not Path(relative).is_absolute()
                    path = portable / relative
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(archive.read(name))
        other = c.post('/api/workspaces', json={'name': '便携重导'}).json()['id']
        scope = f'/api/workspaces/{other}'
        added = c.post(scope + '/resource-add-jobs', json={'source_path': str(portable)}).json()
        import time
        for _ in range(300):
            added = c.get(scope + '/resource-add-jobs/' + added['id']).json()
            if added['status'] not in {'queued', 'running'}:
                break
            time.sleep(.01)
        assert added['status'] == 'completed', added
        node_other = next(row['resource_item_id'] for row in added['results'] if row.get('name') == 'question.md')
        candidate = c.get(f'{scope}/nodes/{node_other}/question-file')
        assert candidate.status_code == 200, candidate.text
        candidate = candidate.json()
        rebound = candidate['question']['stem'][-1]['attachment_id']
        assert rebound != image['resource_id']
        next_version = c.post(f'{scope}/nodes/{node_other}/question-file/confirm', json={
            'expected_sha256': candidate['sha256'], 'expected_version_id': None, 'confirm': True}).json()
        result = c.post(scope + '/attempts', json={'question_id': q['id'],
            'question_version_id': next_version['id'], 'response': {'selected': ['a']}})
        assert result.status_code == 200 and result.json()['score'] == 1, result.text
        with Session(c.app.state.engine) as session:
            image_record = session.get(Resource, image['resource_id'])
            original_path = tmp_path / image_record.relative_path
        original_path.write_bytes(b'changed original image')
        assert base64.b64decode(c.get(asset_endpoint).json()['image_base64']) == png
        fallback = c.get(f'{PREFIX}/nodes/{node}/question-file').json()
        assert fallback['status'] == 'invalid_current' and fallback['confirmed_version_id'] == version['id']
        assert publish(c, node, {'sha256': version['markdown_sha256'], 'confirmed_version_id': version['id']}).status_code == 409
        assert c.get(PREFIX + '/export').status_code == 409
        with Session(c.app.state.engine) as session:
            session.add(Attempt(workspace_id='default', question_id=q['id'], response={'selected': ['a']},
                status='graded', score=1, created_at='2026-10-26', question_revision=1, request_id=None,
                question_version_id=next_version['id']))
            with pytest.raises(IntegrityError):
                session.flush()
        with Session(c.app.state.engine) as session:
            stored = session.get(QuestionVersion, version['id'])
            entry = next(iter(stored.attachments.values()))
            snapshot_image = tmp_path / Path(stored.relative_path).parent / entry['path']
        snapshot_image.write_bytes(b'corrupt snapshot')
        assert c.get(asset_endpoint).status_code == 409
        attempt = c.post(PREFIX + '/attempts', json={'question_id': q['id'],
            'question_version_id': version['id'], 'response': {'selected': ['a']}})
        assert attempt.status_code == 409
        assert c.get(PREFIX + '/attempts').json() == []


def test_old_markdown_conversion_preserves_original_and_provenance(tmp_path):
    with client(tmp_path) as c:
        original = (Path(__file__).parents[2] / 'contracts/samples/numbered-questions.docx').read_bytes()
        job = upload(c, original, '旧资料.docx').json()
        records = c.post(f"{PREFIX}/imports/{job['id']}/question-markdown", json={
            'expected_revision': job['draft_revision'], 'selected': [0], 'confirm': True}).json()
        item = records[0]
        before = c.get(f"{PREFIX}/resources/{item['markdown_resource_id']}").content
        node = convert(c, item['id'], markdown=True)
        data = c.get(f'{PREFIX}/nodes/{node}/document').json()
        file = parse_file(data['text'])
        assert file.question.id == item['id'] and file.question.answer is None
        assert file.model_extra['legacy_provenance']['original_sha256'] == hashlib.sha256(original).hexdigest()
        assert publish(c, node, preview(c, node)).status_code == 200
        assert c.get(f"{PREFIX}/resources/{item['markdown_resource_id']}").content == before
        assert c.get(f"{PREFIX}/resources/{job['resource_id']}").content == original
        assert c.get(f"{PREFIX}/question-markdown/{item['id']}").json()['markdown'].encode() == before
        again = c.get(f"{PREFIX}/question-markdown/{item['id']}/file-preview").json()
        assert again['resource_item_id'] == node and again['status'] == 'mapped'


def test_0009_upgrade_rollback_and_old_version_unknown(tmp_path, monkeypatch):
    root = tmp_path / 'old9'
    root.mkdir()
    engine = database(root / 'study.db')
    config = Config()
    config.set_main_option('script_location', str(Path(__file__).parents[1] / 'migrations'))
    q = question()
    with engine.begin() as connection:
        config.attributes['connection'] = connection
        command.upgrade(config, '0009')
        connection.execute(text("INSERT INTO questions VALUES (:id,'default',:q)"), {'id': q['id'], 'q': json.dumps(q)})
        connection.exec_driver_sql("INSERT INTO attempts VALUES (91,'default',?,'{\"selected\":[\"a\"]}','graded',1,'2026-10-24',1,'old_request_000001')", (q['id'],))
    engine.dispose()
    before = snapshot(root / 'study.db')
    upgrading = command.upgrade
    def fail(config, target):
        upgrading(config, target)
        raise RuntimeError('injected 0010 failure')
    monkeypatch.setattr(command, 'upgrade', fail)
    from study_workbench.app import create_app
    with pytest.raises(RuntimeError, match='0010'):
        create_app(root, TOKEN)
    assert snapshot(root / 'study.db') == before
    monkeypatch.setattr(command, 'upgrade', upgrading)
    with client(root) as c:
        after = snapshot(root / 'study.db')
        # Startup also seeds the second self-authored demo only if absent; existing rows stay exact.
        assert after['attempts'] == [(*before['attempts'][0], None)]
        for table, rows in before.items():
            if table != 'questions':
                assert_preserved({table: rows}, after)
        assert before['questions'][0] in after['questions']
        assert c.get(PREFIX + '/attempts').json()[0]['question_version_id'] is None
        with sqlite3.connect(root / 'study.db') as db:
            assert db.execute('PRAGMA integrity_check').fetchone() == ('ok',)
            assert db.execute('PRAGMA foreign_key_check').fetchall() == []
            assert db.execute('SELECT version_num FROM alembic_version').fetchone() == ('0012',)
    backups = list((root / 'backups').glob('study-before-0012-*.db'))
    assert backups and all(snapshot(path) == before for path in backups)


def test_confirmation_refuses_implicit_ack_unknown_commands_and_unresolved_parent(tmp_path):
    file = file_for(missing=True)
    file.question.id = 'confirmation-boundary'
    with client(tmp_path) as c:
        node, _, original = add(c, tmp_path, '边界.md', serialize_file(file).encode())
        value = preview(c, node)
        body = dict(expected_sha256=value['sha256'], expected_version_id=None, confirm=True)
        endpoint = f'{PREFIX}/nodes/{node}/question-file/confirm'
        for acknowledgment in [False, None, 1, 'true']:
            assert c.post(endpoint, json=dict(body, confirm=acknowledgment)).status_code == 422
        assert c.post(endpoint, json=dict(body, command='arbitrary')).status_code == 422
        assert c.post(endpoint, json=body, headers={'Origin': 'https://example.com'}).status_code == 403
        assert c.post(endpoint, json=body, headers={'Authorization': 'bad'}).status_code == 401
        assert c.get(PREFIX + '/questions/' + file.question.id).status_code == 404
        assert original.read_bytes() == serialize_file(file).encode()
        invalid = file_for(missing=True)
        invalid.question.id = 'unresolved-parent'
        invalid.question.parent_question_id = 'does-not-exist'
        bad, _, path = add(c, tmp_path, '父题未找到.md', serialize_file(invalid).encode())
        assert c.get(f'{PREFIX}/nodes/{bad}/question-file').status_code == 422
        assert path.read_bytes() == serialize_file(invalid).encode()


def test_snapshot_write_failure_retains_receipt_without_changing_cached_answer(tmp_path, monkeypatch):
    import study_workbench.question_files as service
    with client(tmp_path) as c:
        original = c.get(PREFIX + '/questions/demo-integral').json()
        node = convert(c, 'demo-integral')
        candidate = preview(c, node)
        writing = service.write_new
        def corrupt(path, data):
            writing(path, data)
            if 'question-versions' in path.parts and path.name == 'question.md':
                path.write_bytes(b'partial')
        monkeypatch.setattr(service, 'write_new', corrupt)
        assert publish(c, node, candidate).status_code == 409
        assert c.get(PREFIX + '/questions/demo-integral').json() == original
        assert preview(c, node)['confirmed_version_id'] is None
        assert list((tmp_path / 'workspaces/default/question-versions').glob('*/receipt.json'))
        with Session(c.app.state.engine) as session:
            assert list(session.query(QuestionVersion)) == []
        monkeypatch.setattr(service, 'write_new', writing)
        assert publish(c, node, preview(c, node)).status_code == 200
