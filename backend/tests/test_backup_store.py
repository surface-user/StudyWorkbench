import base64
import hashlib
import json
import os
import re
import sqlite3
import subprocess
import zipfile
from pathlib import Path

import pytest
from study_workbench import backup_store as store
from study_workbench import office_runtime
from study_workbench.backup_archive import inspect_archive
from study_workbench.data_root import DataLock, write_settings
from study_workbench.question_files_format import FileAttachment, serialize_file
from study_workbench.question_protocol import ImageBlock
from test_document_files import add, working
from test_explorer import PREFIX, client, make_0006
from test_learning_marks import anchor, capture, mark, mp4
from test_office_previews import FakeRuntime, wait
from test_office_previews import package as office_package
from test_question_files import file_for


def library(root):
    with client(root) as c:
        node, resource, original = add(c, root, '笔记.md', '原件正文'.encode())
        working(c, node)
        point = anchor(c, node)
        assert c.put(f'{PREFIX}/nodes/{node}/document', json={'expected_sha256': point['content_sha256'], 'text': '当前笔记正文'}).status_code == 200
        saved = mark(c, anchor(c, node), targets=[{'kind': 'file_note', 'id': node}]).json()
        assert c.patch(f"{PREFIX}/learning-marks/{saved['id']}", json={'expected_revision': 1, 'note': '修改后的备注'}).status_code == 200
        question = file_for()
        question.question.id = 'backup-snapshot-question'
        qnode, _, _ = add(c, root, '题目.md', serialize_file(question).encode())
        qhash = c.get(f'{PREFIX}/nodes/{qnode}/document').json()['sha256']
        confirmed = c.post(f'{PREFIX}/nodes/{qnode}/question-file/confirm', json={
            'expected_sha256': qhash, 'expected_version_id': None, 'confirm': True})
        assert confirmed.status_code == 200, confirmed.text
        attempt = c.post(PREFIX + '/attempts', json={'question_id': 'demo-proof', 'response': {'text': '保留的旧作答'}})
        assert attempt.status_code == 200
        other = c.post('/api/workspaces', json={'name': '归档课程'}).json()['id']
        assert c.post(f'/api/workspaces/{other}/markdown-notes', json={'name': '归档笔记.md', 'request_id': 'archived-note-request'}).status_code == 200
        assert c.request('DELETE', f'/api/workspaces/{other}', json={'confirm_name': '归档课程'}).status_code == 200
    unknown = root / 'unknown' / '失败字节.pending'
    unknown.parent.mkdir()
    unknown.write_bytes(b'failed-bytes-do-not-delete')
    for relative in ['workspaces/default/web/tab1/cache.bin', 'workspaces/default/resource/tab2/cache.bin',
                     'workspaces/default/player/tab3/cache.bin', 'workspaces/default/link-web/cache.bin',
                     'web-profile/cache.bin', 'player-profile/cache.bin']:
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b'fake-runtime-capability')
    return node, original


def preserved_files(root):
    return {name: path.read_bytes() for name, path in store.inventory(root)[0] if name != 'study.db'}


def test_offline_roundtrip_all_spaces_history_workfiles_snapshots_and_unknown_bytes(tmp_path, monkeypatch):
    source, target, package = tmp_path / 'source', tmp_path / 'restored', tmp_path / 'backup.zip'
    node, original = library(source)
    fake = FakeRuntime()
    monkeypatch.setattr(office_runtime, 'runtime', lambda: fake)
    monkeypatch.setattr(office_runtime, 'capability', lambda: dict(available=True, fingerprint=fake.fingerprint, version=office_runtime.VERSION))
    with client(source) as c:
        doc = c.get(f'{PREFIX}/nodes/{node}/document').json()
        layout = c.get(PREFIX + '/layout').json()
        layout['version'] = 2
        layout['tabs'].append(dict(id='e' * 32, kind='resource', resource_item_id=node, view_kind='document',
                                   resource_name='笔记.md', draft='未保存页面草稿', draft_base_sha256=doc['sha256'],
                                   document_state=dict(version=1, mode='edit', page=1, zoom=1, scroll=0, representation='original')))
        layout['active_tab_id'] = 'e' * 32
        assert c.put(PREFIX + '/layout', json=layout).status_code == 200
        media = c.post(PREFIX + '/media/import?filename=自建元数据.mp4', content=mp4()).json()
        player = c.get(f"{PREFIX}/media/{media['id']}/player").json()['url']
        state_url = player.replace('/player?', '/state?')
        playback = dict(position=3.456, speed=1.25, subtitle='WEBVTT\n\n00:00.000 --> 00:01.000\n自编字幕\n')
        assert c.post(state_url, json=playback).status_code == 200
        folder = c.post(PREFIX + '/nodes', json={'kind': 'folder', 'name': 'assets'}).json()['resource_item_id']
        png = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=')
        _, picture_id, _ = add(c, source, 'figure.png', png, parent=folder)
        with c.app.state.engine.begin() as connection:
            connection.exec_driver_sql("UPDATE resources SET mime='image/png' WHERE id=?", (picture_id,))
        question = file_for()
        question.question.id = 'backup-question-with-asset'
        question.question.stem.append(ImageBlock(type='image', attachment_id='picture', alt='自编图'))
        question.attachments['picture'] = FileAttachment(path='assets/figure.png', sha256=hashlib.sha256(png).hexdigest(), mime='image/png')
        qnode, _, _ = add(c, source, '带图题.md', serialize_file(question).encode())
        qhash = c.get(f'{PREFIX}/nodes/{qnode}/document').json()['sha256']
        published = c.post(f'{PREFIX}/nodes/{qnode}/question-file/confirm', json={
            'expected_sha256': qhash, 'expected_version_id': None, 'confirm': True})
        assert published.status_code == 200, published.text
        version = published.json()['id']
        slides, _, file = add(c, source, '课件.pptx', office_package('ppt/presentation.xml', '<presentation/>'))
        job = c.post(f'{PREFIX}/nodes/{slides}/previews', json={'expected_source_sha256': hashlib.sha256(file.read_bytes()).hexdigest()}).json()
        job = wait(c, slides, job['id'])
        location = capture(c, slides, kind='office_pdf_page', preview_id=job['id'], page=1, expected_sha256=job['pdf_sha256'])
        assert location.status_code == 200
        office_mark = mark(c, location.json(), request='backup-office-page-request').json()['id']
    before, old_db = preserved_files(source), store.database_info(source / 'study.db')
    config = tmp_path / 'profile' / 'settings.json'
    write_settings(config, source)
    created = store.create_backup(source, package)
    assert created['source_retained'] and created['cleanup_pending'] is False
    manifest = inspect_archive(package)
    assert 'workspaces/default/web/tab1' in manifest['excluded']
    assert {'web-profile', 'player-profile'} <= set(manifest['excluded'])
    assert not any(item['path'].endswith('cache.bin') for item in manifest['files'])
    assert manifest['tables']['workspaces']['rows'] == 2
    assert manifest['tables']['attempts']['rows'] == 1
    assert manifest['tables']['learning_mark_revisions']['rows'] == 1
    result = store.restore_backup(package, target, config)
    assert result['data_activated'] and result['database_semantics_checked'] and not result['cleanup_pending']
    assert json.loads(config.read_text(encoding='utf-8'))['data_dir'] == str(target)
    assert store.database_info(target / 'study.db') == old_db
    assert preserved_files(target) == before == preserved_files(source)
    assert store.database_info(source / 'study.db') == old_db
    assert original.read_bytes() == '原件正文'.encode()
    with client(target) as c:
        assert c.get(f'{PREFIX}/nodes/{node}/document').json()['text'] == '当前笔记正文'
        assert c.get(PREFIX + '/attempts').json()[0]['response']['text'] == '保留的旧作答'
        assert len(c.get('/api/workbench').json()['archived_workspaces']) == 1
        assert c.get(PREFIX + '/layout').json()['tabs'][-1]['draft'] == '未保存页面草稿'
        assert c.get(state_url).status_code == 403  # Old session media capabilities do not survive restore/restart.
        fresh_player = c.get(f"{PREFIX}/media/{media['id']}/player").json()['url']
        assert c.get(fresh_player.replace('/player?', '/state?')).json() == playback
        asset = c.get(f'{PREFIX}/question-versions/{version}/assets/{picture_id}')
        assert asset.status_code == 200 and base64.b64decode(asset.json()['image_base64']) == png
        assert c.get(f'{PREFIX}/learning-marks/{office_mark}').json()['location']['status'] == 'valid'


def test_locked_source_nonempty_target_and_overlapping_paths_are_refused(tmp_path):
    source = tmp_path / 'source'
    library(source)
    package, config = tmp_path / 'backup.zip', tmp_path / 'profile/settings.json'
    with DataLock(source), pytest.raises(RuntimeError):
        store.create_backup(source, package)
    assert not package.exists()
    with pytest.raises(ValueError):
        store.create_backup(source, source / 'inside.zip')
    store.create_backup(source, package)
    target = tmp_path / 'target'
    target.mkdir()
    important = target / 'keep.txt'
    important.write_bytes(b'user data')
    with pytest.raises(ValueError):
        store.restore_backup(package, target, config)
    assert important.read_bytes() == b'user data'
    with pytest.raises(ValueError):
        store.restore_backup(package, tmp_path / 'empty', tmp_path / 'empty/settings.json')
    assert not config.exists()


@pytest.mark.parametrize('stage', ['packing-chunk', 'publishing-chunk'])
def test_backup_interruption_preserves_source_and_unfinished_bytes(tmp_path, stage):
    source = tmp_path / 'source'
    library(source)
    before = store.database_info(source / 'study.db'), preserved_files(source)
    def stop(actual):
        if actual == stage:
            raise RuntimeError('cancelled')
    with pytest.raises(RuntimeError):
        store.create_backup(source, tmp_path / 'backup.zip', checkpoint=stop)
    assert (store.database_info(source / 'study.db'), preserved_files(source)) == before
    assert list(tmp_path.glob('.backup-pending-*'))


@pytest.mark.parametrize('stage', ['restoring-chunk', 'promoting-chunk', 'before-settings'])
def test_restore_interruption_never_changes_old_config_or_library(tmp_path, stage):
    source = tmp_path / 'source'
    library(source)
    package, target, config = tmp_path / 'backup.zip', tmp_path / 'target', tmp_path / 'profile/settings.json'
    write_settings(config, source)
    store.create_backup(source, package)
    before = config.read_bytes(), store.database_info(source / 'study.db'), preserved_files(source)
    def stop(actual):
        if actual == stage:
            raise RuntimeError('cancelled')
    with pytest.raises(RuntimeError):
        store.restore_backup(package, target, config, checkpoint=stop)
    assert (config.read_bytes(), store.database_info(source / 'study.db'), preserved_files(source)) == before
    assert list(target.glob('.restore-pending-*'))


def test_restore_detects_external_target_write_and_config_failure(tmp_path, monkeypatch):
    source = tmp_path / 'source'
    library(source)
    package, target, config = tmp_path / 'backup.zip', tmp_path / 'target', tmp_path / 'profile/settings.json'
    write_settings(config, source)
    store.create_backup(source, package)
    before = config.read_bytes()
    def inject(stage):
        if stage == 'restore-validated':
            (target / 'keep.txt').write_bytes(b'external file')
    with pytest.raises(ValueError):
        store.restore_backup(package, target, config, checkpoint=inject)
    assert (target / 'keep.txt').read_bytes() == b'external file' and config.read_bytes() == before
    def denied(*_):
        raise PermissionError('read-only settings')
    monkeypatch.setattr(store, 'write_settings', denied)
    with pytest.raises(PermissionError):
        store.restore_backup(package, tmp_path / 'another-target', config)
    assert config.read_bytes() == before


def test_reference_corruption_and_disk_budget_fail_without_success(tmp_path, monkeypatch):
    source = tmp_path / 'source'
    _, original = library(source)
    original.write_bytes(b'corrupt original')
    with pytest.raises(ValueError):
        store.create_backup(source, tmp_path / 'corrupt.zip')
    assert not (tmp_path / 'corrupt.zip').exists()
    original.write_bytes('原件正文'.encode())
    class Full:
        free = 0
    monkeypatch.setattr(store.shutil, 'disk_usage', lambda _: Full())
    with pytest.raises(ValueError, match='空间不足'):
        store.create_backup(source, tmp_path / 'full.zip')
    assert not (tmp_path / 'full.zip').exists()


def test_old_schema_restore_preserves_old_rows_and_retains_migration_backup(tmp_path):
    source = tmp_path / 'old'
    make_0006(source)
    media = source / 'media.bin'
    media.write_bytes(b'oldm')
    with sqlite3.connect(source / 'study.db') as connection:
        connection.execute('UPDATE resources SET sha256=?', (hashlib.sha256(b'old').hexdigest(),))
        connection.execute('UPDATE media_entries SET sha256=?', (hashlib.sha256(b'oldm').hexdigest(),))
    package, target = tmp_path / 'old.zip', tmp_path / 'upgraded'
    store.create_backup(source, package)
    assert inspect_archive(package)['schema_revision'] == '0006'
    result = store.restore_backup(package, target, tmp_path / 'settings.json')
    assert result['schema_revision'] == '0016'
    assert list((target / 'backups').glob('study-before-0016-*.db'))
    with sqlite3.connect(target / 'study.db') as connection:
        assert connection.execute('SELECT response FROM attempts WHERE id=12').fetchone()[0] == '{"text":"原作答"}'
        assert connection.execute('SELECT title FROM notes WHERE id=\'n\'').fetchone()[0] == '笔记'
    assert store.database_info(source / 'study.db')[0] == '0006'


def test_manifest_counts_cannot_replace_database_semantics(tmp_path):
    source = tmp_path / 'source'
    library(source)
    original = tmp_path / 'backup.zip'
    store.create_backup(source, original)
    with zipfile.ZipFile(original) as archive:
        files = {item.filename: archive.read(item) for item in archive.infolist()}
    value = json.loads(files['backup-manifest.json'])
    value['tables']['attempts']['rows'] += 1
    files['backup-manifest.json'] = json.dumps(value).encode()
    tampered = tmp_path / 'tampered.zip'
    with zipfile.ZipFile(tampered, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for name, data in files.items():
            archive.writestr(name, data)
    inspect_archive(tampered)
    config = tmp_path / 'settings.json'
    write_settings(config, source)
    before = config.read_bytes()
    with pytest.raises(ValueError, match='行数/行摘要'):
        store.restore_backup(tampered, tmp_path / 'target', config)
    assert config.read_bytes() == before


def test_application_version_and_typed_row_hashes_match_real_sources(tmp_path):
    pubspec = Path(__file__).resolve().parents[2] / 'apps/desktop/pubspec.yaml'
    assert re.search(r'^version:\s*(.+)$', pubspec.read_text(encoding='utf-8'), re.M)[1] == store.APP_VERSION
    path = tmp_path / 'typed.db'
    with sqlite3.connect(path) as connection:
        connection.execute('CREATE TABLE values_test (id INTEGER PRIMARY KEY, text TEXT, data BLOB, score REAL)')
        connection.execute('INSERT INTO values_test VALUES (1,?,?,?)', ('中文\x00原文', b'\x00\xff', .5))
    with store.connect(path) as connection:
        first = store.table_summary(connection)
    with sqlite3.connect(path) as connection:
        connection.execute('UPDATE values_test SET data=?', (b'\x00\xfe',))
    with store.connect(path) as connection:
        assert store.table_summary(connection) != first


def test_real_reparse_roots_and_nested_entries_are_refused_without_touching_target(tmp_path):
    source, external = tmp_path / 'source', tmp_path / 'external'
    library(source)
    external.mkdir()
    keep = external / 'keep.txt'
    keep.write_bytes(b'outside library')
    junction = source / 'unexpected-link'
    if os.name == 'nt':
        result = subprocess.run(['cmd', '/c', 'mklink', '/J', str(junction), str(external)], capture_output=True,
                                creationflags=subprocess.CREATE_NO_WINDOW)
        assert result.returncode == 0
    else:
        junction.symlink_to(external, target_is_directory=True)
    with pytest.raises(ValueError, match='重解析点'):
        store.create_backup(source, tmp_path / 'backup.zip')
    with pytest.raises(ValueError, match='重解析点'):
        store.create_backup(junction, tmp_path / 'linked-root.zip')
    assert keep.read_bytes() == b'outside library'


@pytest.mark.parametrize('name', ['backup.zip:stream', 'CON.zip', 'backup.'])
def test_backup_output_refuses_ads_and_windows_reserved_names(tmp_path, name):
    source = tmp_path / 'source'
    library(source)
    with pytest.raises(ValueError):
        store.create_backup(source, tmp_path / name)
    assert not list(tmp_path.glob('.backup-pending-*'))
