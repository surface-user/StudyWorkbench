import copy
import hashlib
import json
import sqlite3
import warnings
from contextlib import closing
from pathlib import Path

import pytest
from alembic import command, op
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy.exc import SAWarning
from study_workbench import backup_store, library_integrity, media_sources, recovery_storage
from study_workbench.db import database
from study_workbench.media_probe_runtime import SNAPSHOT
from study_workbench.migrate import migrate
from test_explorer import PREFIX, client
from test_library_integrity import snapshot

JOB = 'a' * 32


def selection():
    return dict(schema_version=1, kind='local_pair', recipe_version=media_sources.RECIPE,
                component_snapshot_sha256=SNAPSHOT, tracks=[
                    dict(media_id='video', sha256='1' * 64, size=10, mime='video/mp4', role='video', stream_index=0),
                    dict(media_id='audio', sha256='2' * 64, size=10, mime='audio/mp4', role='audio', stream_index=0)])


def metadata(role):
    stream = dict(index=0, role=role, codec='h264' if role == 'video' else 'aac', duration_ms=200)
    stream.update(dict(width=16, height=16) if role == 'video' else dict(sample_rate=48000, channels=1))
    return dict(container='mp4', duration_ms=200, streams=[stream])


def receipt(source, state='pending'):
    directory = f'workspaces/default/downloads/{JOB}/1/1'
    tracks = [dict(ordinal=i, state=state, relative_path=f"{directory}/input{i}{'.mp4' if i == 0 else '.m4a'}",
                   metadata=metadata(role) if state == 'probed' else None) for i, role in enumerate(['video', 'audio'])]
    return dict(schema_version=1, source_snapshot_sha256=media_sources.source_digest(source), tracks=tracks, output=None)


@pytest.mark.parametrize('fault', ['extra', 'url', 'cookie', 'version_bool', 'version_float', 'version_future',
                                  'component', 'recipe', 'mime', 'role_order', 'index_bool', 'index_large',
                                  'sha', 'size_bool', 'size_zero', 'size_total', 'same_stream', 'third_track',
                                  'id_empty', 'id_large'])
def test_source_snapshot_is_a_strict_bounded_selection(fault):
    data = selection()
    if fault in {'extra', 'url', 'cookie'}:
        data[fault] = 'not an arbitrary network or CLI object'
    elif fault.startswith('version_'):
        data['schema_version'] = {'bool': True, 'float': 1.0, 'future': 2}[fault[8:]]
    elif fault == 'component':
        data['component_snapshot_sha256'] = '0' * 64
    elif fault == 'recipe':
        data['recipe_version'] = 'arbitrary-ffmpeg'
    elif fault == 'mime':
        data['tracks'][0]['mime'] = 'video/webm'
    elif fault == 'role_order':
        data['tracks'].reverse()
    elif fault == 'index_bool':
        data['tracks'][0]['stream_index'] = False
    elif fault == 'index_large':
        data['tracks'][0]['stream_index'] = 2
    elif fault == 'sha':
        data['tracks'][0]['sha256'] = 'A' * 64
    elif fault == 'size_bool':
        data['tracks'][0]['size'] = True
    elif fault == 'size_zero':
        data['tracks'][0]['size'] = 0
    elif fault == 'size_total':
        data['tracks'][0]['size'] = media_sources.INPUT_LIMIT
    elif fault == 'same_stream':
        data['tracks'][1]['media_id'] = 'video'
    elif fault == 'third_track':
        data['tracks'].append(copy.deepcopy(data['tracks'][1]))
    elif fault == 'id_empty':
        data['tracks'][0]['media_id'] = ''
    elif fault == 'id_large':
        data['tracks'][0]['media_id'] = 'a' * 101
    with pytest.raises(ValueError):
        media_sources.source_snapshot(data)


@pytest.mark.parametrize('raw', [
    '{"schema_version":1,"schema_version":1}', '{"schema_version":NaN}',
    '{"extra":"' + 'x' * 16384 + '"}', '[' * 14 + '0' + ']' * 14,
    '{"schema_version":true}', '[]', '"text"', '{} trailing',
])
def test_raw_json_duplicate_nonfinite_byte_depth_and_version_limits(raw):
    with pytest.raises(ValueError):
        media_sources.source_snapshot(raw)


def test_snapshot_digest_excludes_itself_and_is_independent_of_json_key_order():
    data = selection()
    source = media_sources.source_snapshot(data)
    expected = hashlib.sha256(json.dumps(data, ensure_ascii=False, sort_keys=True,
                                        separators=(',', ':'), allow_nan=False).encode()).hexdigest()
    assert media_sources.source_digest(source) == expected
    assert media_sources.source_digest(media_sources.source_snapshot(json.dumps(data, sort_keys=True))) == expected
    assert 'source_snapshot_sha256' not in source.model_dump()
    data['tracks'][0]['stream_index'] = 1
    assert media_sources.source_digest(media_sources.source_snapshot(data)) != expected


@pytest.mark.parametrize('fault', ['version_bool', 'extra', 'ordinal', 'unknown_state', 'metadata_before_probe',
                                  'probe_missing_metadata', 'path', 'source_hash', 'selected_role',
                                  'output_before_probes', 'duplicate_stream', 'output_role', 'ready_without_receipt'])
def test_attempts_reject_ambiguous_metadata_path_identity_and_lifecycle(fault):
    data = selection()
    if fault == 'selected_role':
        data['tracks'][0]['stream_index'] = 1
    source = media_sources.source_snapshot(data)
    raw = receipt(source)
    if fault == 'version_bool':
        raw['schema_version'] = True
    elif fault == 'extra':
        raw['args'] = ['arbitrary']
    elif fault == 'ordinal':
        raw['tracks'][0]['ordinal'] = 1
    elif fault == 'unknown_state':
        raw['tracks'][0]['state'] = 'trusted'
    elif fault == 'metadata_before_probe':
        raw['tracks'][0]['metadata'] = metadata('video')
    elif fault == 'probe_missing_metadata':
        raw['tracks'][0]['state'] = 'probed'
    elif fault == 'path':
        raw['tracks'][0]['relative_path'] = 'workspaces/other/private'
    elif fault == 'source_hash':
        raw['source_snapshot_sha256'] = 'f' * 64
    elif fault == 'selected_role':
        raw = receipt(source, 'probed')
    elif fault in {'output_before_probes', 'output_role'}:
        if fault == 'output_role':
            raw = receipt(source, 'probed')
        raw['output'] = dict(state='prepared', pending_path='wrong', final_path='wrong', size=1,
                             sha256='f' * 64, metadata=metadata('video'))
    elif fault == 'duplicate_stream':
        raw = receipt(source, 'probed')
        raw['tracks'][0]['metadata']['streams'] *= 2
    with pytest.raises(ValueError):
        record = media_sources.attempt_record(raw)
        media_sources.attempt_context('default', JOB, 1, 1, source, record, ready=fault == 'ready_without_receipt')


def config():
    value = Config()
    value.set_main_option('script_location', str(Path(__file__).resolve().parents[1] / 'migrations'))
    return value


def legacy_library(root):
    root.mkdir()
    path = root / 'study.db'
    engine = database(path)
    with engine.begin() as connection:
        connection.exec_driver_sql('BEGIN')
        value = config()
        value.attributes['connection'] = connection
        command.upgrade(value, '0017')
    with sqlite3.connect(path) as db:
        for ordinal, status in enumerate(['queued', 'running', 'paused', 'interrupted', 'failed', 'ready']):
            db.execute('INSERT INTO media_download_jobs VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)', (
                f'{ordinal:032x}', 'default', None, f'legacy-request-{ordinal}', 'https://example.invalid/v?private=kept',
                f'{ordinal}.mp4', status, 0, ordinal + 1, f'workspaces/default/downloads/{ordinal:032x}/{ordinal+1}.mp4',
                '{"received":3,"opaque":"old progress"}', '{"legacy":"old result"}', 'old error', '2000-01-01'))
    (root / 'retained.partial').write_bytes(b'original failed attempt')
    return engine, path


def test_single_head_upgrade_keeps_every_legacy_column_no_invented_attempts_and_sql_guards(tmp_path):
    root = tmp_path / 'old'
    engine, path = legacy_library(root)
    with closing(backup_store.connect(path)) as db:
        columns = [row['name'] for row in db.execute('PRAGMA table_info(media_download_jobs)')]
        before = backup_store.table_summary(db)
        before.pop('alembic_version')
    with warnings.catch_warnings():
        warnings.simplefilter('error', SAWarning)
        migrate(engine, path)
    with closing(backup_store.connect(path)) as db:
        assert ScriptDirectory.from_config(config()).get_heads() == ['0018']
        assert db.execute('SELECT version_num FROM alembic_version').fetchall()[0][0] == '0018'
        old_columns = {row[0]: [c['name'] for c in db.execute('PRAGMA table_info("' + row[0] + '")')]
                       for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        old_columns['media_download_jobs'] = columns
        summary = backup_store.table_summary(db, columns={name: old_columns[name] for name in before})
        assert summary == before
        assert [tuple(row) for row in db.execute('SELECT source_kind,source_url,source_snapshot,source_snapshot_sha256,run_generation '
                               'FROM media_download_jobs')] == [
                                   ('direct_https', 'https://example.invalid/v?private=kept', None, None, 0)] * 6
        assert db.execute('SELECT count(*) FROM media_download_attempts').fetchone()[0] == 0
        assert db.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
        assert not db.execute('PRAGMA foreign_key_check').fetchall()
        indexes = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='index'")}
        assert {'ux_nodes_sibling_name', 'ix_download_workspace'} <= indexes
        foreign = list(db.execute('PRAGMA foreign_key_list(media_download_jobs)'))
        assert {r['table'] for r in foreign} == {'workspace_nodes', 'workspaces'}
    with sqlite3.connect(path) as db:
        db.execute('PRAGMA foreign_keys=ON')
        for sql in ["UPDATE media_download_jobs SET source_url='https://changed.invalid'",
                    "UPDATE media_download_jobs SET status='unknown'", 'UPDATE media_download_jobs SET attempt=0',
                    "UPDATE media_download_jobs SET workspace_id='missing'",
                    "UPDATE media_download_jobs SET parent_id='missing'",
                    "UPDATE media_download_jobs SET request_id='same-request'"]:
            with pytest.raises(sqlite3.IntegrityError):
                db.execute(sql)
            db.rollback()
    backup = list((root / 'backups').glob('study-before-0018-*.db'))
    assert len(backup) == 1 and (root / 'retained.partial').read_bytes() == b'original failed attempt'
    with sqlite3.connect(backup[0]) as db:
        assert db.execute('SELECT version_num FROM alembic_version').fetchone() == ('0017',)
    engine.dispose()


def test_migration_failure_rolls_back_table_recreation_and_keeps_original_backup(tmp_path, monkeypatch):
    root = tmp_path / 'old'
    engine, path = legacy_library(root)
    with closing(backup_store.connect(path)) as db:
        before = backup_store.table_summary(db)
        schema = list(db.execute('SELECT name,sql FROM sqlite_master ORDER BY name'))
    real = op.create_table
    def fail(name, *args, **kwargs):
        if name == 'media_download_attempts':
            raise RuntimeError('owned injected migration failure')
        return real(name, *args, **kwargs)
    monkeypatch.setattr(op, 'create_table', fail)
    with pytest.raises(RuntimeError, match='owned injected'):
        migrate(engine, path)
    with closing(backup_store.connect(path)) as db:
        assert backup_store.table_summary(db) == before
        assert list(db.execute('SELECT name,sql FROM sqlite_master ORDER BY name')) == schema
        assert db.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
    assert len(list((root / 'backups').glob('study-before-0018-*.db'))) == 1
    assert (root / 'retained.partial').read_bytes() == b'original failed attempt'
    engine.dispose()


def local_library(root, *, ready=False, prepared=False):
    # Semantic persistence fixture only: these bytes/metadata are not a native mux result.
    with client(root):
        pass
    raw = selection()
    files = [b'owned test video', b'owned test audio']
    with sqlite3.connect(root / 'study.db') as db:
        for ordinal, data in enumerate(files):
            track = raw['tracks'][ordinal]
            track['sha256'], track['size'] = hashlib.sha256(data).hexdigest(), len(data)
            relative = f"workspaces/default/media/{track['media_id']}{'.mp4' if ordinal == 0 else '.m4a'}"
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            db.execute('INSERT INTO media_entries VALUES (?,?,?,?,?,?,?,?,?)',
                       (track['media_id'], 'default', 'private original title', relative, track['mime'],
                        len(data), track['sha256'], 'ready', '{}'))
        source = media_sources.source_snapshot(raw)
        record = receipt(source, 'probed' if ready or prepared else 'copied')
        for track, data in zip(record['tracks'], files, strict=True):
            path = root / track['relative_path']
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        final = f'workspaces/default/downloads/{JOB}/1.mp4'
        result = {}
        if ready or prepared:
            output = b'owned synthetic receipt bytes, no native claim'
            record['output'] = dict(state='committed' if ready else 'prepared',
                                    pending_path=f'workspaces/default/downloads/{JOB}/1/1/output.pending.mp4',
                                    final_path=final, size=len(output), sha256=hashlib.sha256(output).hexdigest(),
                                    metadata=dict(container='mp4', duration_ms=200, streams=[
                                        metadata('video')['streams'][0], {**metadata('audio')['streams'][0], 'index': 1}]))
            (root / final).write_bytes(output)
            if ready:
                result = dict(media_id='result-media', resource_item_id='result-node', deduplicated=False)
                db.execute('INSERT INTO media_entries VALUES (?,?,?,?,?,?,?,?,?)', (
                    'result-media', 'default', 'result.mp4', final, 'video/mp4', len(output),
                    record['output']['sha256'], 'ready', '{}'))
                db.execute('INSERT INTO workspace_nodes '
                           '(id,workspace_id,kind,name,name_key,media_id) VALUES (?,?,?,?,?,?)',
                           ('result-node', 'default', 'media', 'result.mp4', 'result.mp4', 'result-media'))
        db.execute('INSERT INTO media_download_jobs '
                   '(id,workspace_id,parent_id,request_id,source_url,name,status,cancel_requested,attempt,relative_path,'
                   'progress,result,error,created_at,source_kind,source_snapshot,source_snapshot_sha256,run_generation) '
                   'VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)', (
                       JOB, 'default', None, 'owned-local-pair-request', None, 'result.mp4', 'ready' if ready else 'paused',
                       0, 1, final, '{}', json.dumps(result), None, '2000-01-01', 'local_pair', json.dumps(raw),
                       media_sources.source_digest(source), 1))
        db.execute('INSERT INTO media_download_attempts VALUES (?,?,?,?,?,?,?,?,?)', (
            JOB, 1, 'default', 1, media_sources.source_digest(source), 'ready' if ready else 'paused',
            'ready' if ready else 'publishing' if prepared else 'copying', json.dumps(record), '2000-01-01'))
    return source, record


@pytest.mark.parametrize('state', ['copied', 'prepared_move', 'committed'])
def test_complete_backup_restore_retains_originals_attempts_receipts_and_never_replays(tmp_path, state):
    source_root, restored = tmp_path / 'source', tmp_path / 'restored'
    local_library(source_root, ready=state == 'committed', prepared=state == 'prepared_move')
    before = snapshot(source_root)
    package = tmp_path / 'backup.zip'
    saved = backup_store.create_backup(source_root, package)
    result = backup_store.restore_backup(package, restored, tmp_path / 'settings.json')
    assert saved['schema_revision'] == result['schema_revision'] == '0018'
    assert snapshot(source_root) == before
    assert {k: v for k, v in snapshot(restored).items() if k != 'study.db'} == {
        k: v for k, v in before.items() if k != 'study.db'}
    with closing(backup_store.connect(source_root / 'study.db')) as left, closing(backup_store.connect(restored / 'study.db')) as right:
        assert backup_store.table_summary(left) == backup_store.table_summary(right)
    checked = library_integrity.check_library(restored)
    assert checked['complete'] and checked['healthy'], checked
    with client(restored) as c:
        row = c.get(PREFIX + '/media-downloads/' + JOB).json()
        assert row['source_kind'] == 'local_pair' and row['source_host'] == '本地所选媒体' and not row['can_resume']
        assert row['status'] == ('ready' if state == 'committed' else 'paused')
        if state != 'committed':
            assert c.post(PREFIX + '/media-downloads/' + JOB + '/retry', json={'mode': 'resume'}).status_code == 409
        assert row['source_snapshot']['kind'] == 'local_pair' and 'private original title' not in str(row)


@pytest.mark.parametrize('fault', ['source_hash', 'source_extra', 'source_cross_workspace', 'record_path',
                                  'record_hash', 'generation', 'missing_copy', 'changed_copy',
                                  'missing_current', 'ready_result', 'output_hash'])
def test_backup_and_integrity_fail_closed_for_corrupt_source_receipt_or_output(tmp_path, fault):
    root = tmp_path / 'source'
    _, record = local_library(root, ready=True)
    with sqlite3.connect(root / 'study.db') as db:
        if fault.startswith('source_'):
            db.execute('DROP TRIGGER immutable_media_download_source')
            if fault == 'source_hash':
                db.execute("UPDATE media_download_jobs SET source_snapshot_sha256=?", ('f' * 64,))
            elif fault == 'source_extra':
                value = json.loads(db.execute('SELECT source_snapshot FROM media_download_jobs').fetchone()[0])
                value['headers'] = {'private': 'forbidden'}
                db.execute('UPDATE media_download_jobs SET source_snapshot=?', (json.dumps(value),))
            else:
                db.execute("UPDATE media_entries SET workspace_id='foreign' WHERE id='video'")
        elif fault in {'record_path', 'record_hash', 'output_hash'}:
            if fault == 'record_path':
                record['tracks'][0]['relative_path'] = 'workspaces/other/private'
            elif fault == 'record_hash':
                record['source_snapshot_sha256'] = 'f' * 64
            else:
                record['output']['sha256'] = 'f' * 64
            db.execute('UPDATE media_download_attempts SET record=?', (json.dumps(record),))
        elif fault == 'generation':
            db.execute('UPDATE media_download_jobs SET run_generation=0')
        elif fault == 'missing_current':
            db.execute('DELETE FROM media_download_attempts')
        elif fault == 'ready_result':
            db.execute("UPDATE media_download_jobs SET result='{}'")
    if fault == 'missing_copy':
        (root / record['tracks'][0]['relative_path']).unlink()
    elif fault == 'changed_copy':
        (root / record['tracks'][0]['relative_path']).write_bytes(b'changed frozen bytes')
    before = snapshot(root)
    with pytest.raises(ValueError):
        backup_store.create_backup(root, tmp_path / 'backup.zip')
    checked = library_integrity.check_library(root)
    assert not checked['healthy'] and checked['issues'], checked
    assert snapshot(root) == before
    assert not (tmp_path / 'backup.zip').exists()


def test_capacity_counts_owned_execution_files_without_opening_content_or_reading_sensitive_columns(tmp_path, monkeypatch):
    root = tmp_path / 'source'
    _, record = local_library(root)
    older = root / f'workspaces/default/downloads/{JOB}/1/2/unregistered.partial'
    older.parent.mkdir()
    older.write_bytes(b'not an actual attempt')
    before = snapshot(root)
    original_connect, original_open = recovery_storage.connect, Path.open
    denied = {'source_url', 'source_snapshot', 'source_snapshot_sha256', 'progress', 'result', 'record', 'sha256', 'title'}
    def connect(path):
        connection = original_connect(path)
        def authorizer(action, table, column, *_):
            assert not (action == sqlite3.SQLITE_READ and column in denied), (table, column)
            return sqlite3.SQLITE_OK
        connection.set_authorizer(authorizer)
        return connection
    def guarded(path, *args, **kwargs):
        assert path.name == '.study.lock', 'metadata report read business bytes'
        return original_open(path, *args, **kwargs)
    with monkeypatch.context() as patch:
        patch.setattr(recovery_storage, 'connect', connect)
        patch.setattr(Path, 'open', guarded)
        result = recovery_storage.report_download_storage(root)
    assert result['complete'] and result['execution_receipt_rows'] == 1, result
    assert not result['attempt_history_checked'] and not result['content_integrity_checked']
    assert result['categories']['current_attempt_file']['file_count'] == 2
    assert result['categories']['other_download_file']['file_count'] == 1
    assert result['missing_optional_download_files'] == 1
    assert snapshot(root) == before


def test_backend_restart_marks_only_current_running_execution_interrupted_without_replay(tmp_path):
    root = tmp_path / 'source'
    local_library(root)
    with sqlite3.connect(root / 'study.db') as db:
        db.execute("UPDATE media_download_jobs SET status='running'")
        db.execute("UPDATE media_download_attempts SET status='running'")
    before = {k: v for k, v in snapshot(root).items() if k != 'study.db'}
    with client(root) as c:
        result = c.get(PREFIX + '/media-downloads/' + JOB).json()
        assert result['status'] == 'interrupted' and not result['can_resume']
    with sqlite3.connect(root / 'study.db') as db:
        assert db.execute('SELECT status,phase FROM media_download_attempts').fetchone() == ('interrupted', 'copying')
    assert {k: v for k, v in snapshot(root).items() if k != 'study.db'} == before


def test_execution_sql_constraints_keep_workspace_generation_status_and_receipt_bounds(tmp_path):
    root = tmp_path / 'source'
    local_library(root)
    with sqlite3.connect(root / 'study.db') as db:
        db.execute('PRAGMA foreign_keys=ON')
        for sql in ["UPDATE media_download_attempts SET workspace_id='foreign'",
                    'UPDATE media_download_attempts SET generation=0',
                    'UPDATE media_download_attempts SET attempt=0',
                    "UPDATE media_download_attempts SET status='unknown'",
                    "UPDATE media_download_attempts SET status='ready'",
                    "UPDATE media_download_attempts SET phase='ready'",
                    "UPDATE media_download_attempts SET phase='network'",
                    "UPDATE media_download_attempts SET record=zeroblob(8193)",
                    "UPDATE media_download_attempts SET source_snapshot_sha256='unknown'",
                    "UPDATE media_download_jobs SET source_snapshot=source_snapshot"]:
            with pytest.raises(sqlite3.IntegrityError):
                db.execute(sql)
            db.rollback()
        assert db.execute('SELECT status,phase FROM media_download_attempts').fetchone() == ('paused', 'copying')
        assert not db.execute('PRAGMA foreign_key_check').fetchall()
