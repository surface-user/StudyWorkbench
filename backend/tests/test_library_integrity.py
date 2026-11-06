import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest
from study_workbench import library_integrity as scan
from study_workbench.data_root import DataLock
from test_backup_store import library
from test_explorer import make_0006


def snapshot(root):
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob('*')
            if p.is_file() and p.name != '.study.lock'}


def test_clean_all_spaces_history_receipts_and_runtime_profiles_are_read_only(tmp_path):
    library(tmp_path)
    before = snapshot(tmp_path)
    result = scan.check_library(tmp_path)
    assert result['complete'] and result['healthy'], result
    assert result['issues'] == [] and result['bytes_hashed'] > 0
    assert result['data_modified'] is False and result['repair_performed'] is False
    assert snapshot(tmp_path) == before


@pytest.mark.parametrize('kind', ['working', 'question-files', 'question-versions', 'previews'])
@pytest.mark.parametrize('empty', [False, True])
def test_unregistered_derived_directory_is_only_a_candidate_never_removed(tmp_path, kind, empty):
    library(tmp_path)
    orphan = tmp_path / 'workspaces/default' / kind / 'unregistered-task'
    orphan.mkdir(parents=True)
    if not empty:
        (orphan / 'receipt.json').write_bytes(b'not trusted as a database receipt')
    (orphan / 'empty').mkdir()
    before = snapshot(tmp_path)
    result = scan.check_library(tmp_path)
    assert result['complete'] and not result['healthy']
    candidates = [v for v in result['issues'] if v['code'] == 'unreferenced_derived_candidate']
    assert candidates == [dict(code='unreferenced_derived_candidate', severity='warning',
                               relative_path=f'workspaces/default/{kind}/unregistered-task')]
    assert snapshot(tmp_path) == before and (orphan / 'empty').is_dir()


def test_interrupted_creation_and_restore_stage_are_recognized_and_left_untouched(tmp_path):
    library(tmp_path)
    with sqlite3.connect(tmp_path / 'study.db') as db:
        db.execute('INSERT INTO markdown_note_creations VALUES (?,?,?,?,?,?,?)',
                   ('interrupted-note', 'default', 'interrupted-request', '{}', 'unused-resource', 'prepared', None))
    work = tmp_path / 'workspaces/default/working/interrupted-note/note/current.md'
    work.parent.mkdir(parents=True)
    work.write_bytes(b'partial creation')
    stage = tmp_path / '.restore-pending-test'
    stage.mkdir()
    (stage / 'partial').write_bytes(b'restore retained bytes')
    before = snapshot(tmp_path)
    result = scan.check_library(tmp_path)
    codes = {v['code'] for v in result['issues']}
    assert result['complete'] and not result['healthy']
    assert codes == {'note_creation_requires_reconciliation', 'retained_operation_directory'}
    assert snapshot(tmp_path) == before


@pytest.mark.parametrize('damage', ['missing', 'changed', 'workfile', 'metadata'])
def test_corrupt_required_bytes_and_workfile_conflicts_never_repair(tmp_path, damage):
    _, original = library(tmp_path)
    with sqlite3.connect(tmp_path / 'study.db') as db:
        if damage == 'workfile':
            target = tmp_path / db.execute('SELECT relative_path FROM document_workfiles LIMIT 1').fetchone()[0]
            target.write_bytes(b'external editor bytes')
        elif damage == 'metadata':
            pass  # Corrupt the standalone test database after closing this connection below.
        elif damage == 'missing':
            original.unlink()
        else:
            original.write_bytes(b'changed original')
    if damage == 'metadata':
        # A corrupt SQLite file is a separate, read-only diagnostic failure.
        (tmp_path / 'study.db').write_bytes(b'invalid sqlite bytes')
    before = snapshot(tmp_path)
    result = scan.check_library(tmp_path)
    code = {'missing': 'missing_file', 'changed': 'hash_mismatch',
            'workfile': 'workfile_index_changed', 'metadata': 'database_unreadable'}[damage]
    assert code in {i['code'] for i in result['issues']}, result
    assert not result['healthy'] and snapshot(tmp_path) == before


@pytest.mark.parametrize('limit', ['ENTRY_LIMIT', 'ROW_LIMIT', 'BYTE_LIMIT', 'ISSUE_LIMIT', 'SECONDS'])
def test_any_exhausted_budget_is_incomplete_never_healthy(tmp_path, monkeypatch, limit):
    library(tmp_path)
    if limit == 'ISSUE_LIMIT':
        (tmp_path / 'workspaces/default/previews/unregistered').mkdir(parents=True)
    monkeypatch.setattr(scan, limit, 0)
    before = snapshot(tmp_path)
    result = scan.check_library(tmp_path)
    assert result['complete'] is False and result['healthy'] is False, result
    assert 'limit_reason' in result and snapshot(tmp_path) == before


@pytest.mark.parametrize('status', ['failed', 'ready'])
def test_preview_bytes_are_retained_and_ready_metadata_is_required(tmp_path, status):
    library(tmp_path)
    with sqlite3.connect(tmp_path / 'study.db') as db:
        node, resource = db.execute("SELECT id,resource_id FROM workspace_nodes WHERE kind='resource' LIMIT 1").fetchone()
        db.execute('INSERT INTO document_previews '
                   '(id,workspace_id,node_id,source_resource_id,source_sha256,runtime_fingerprint,converter_version,'
                   'options_hash,status,cancel_requested,relative_pdf,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',
                   ('failed-preview', 'default', node, resource, 'a'*64, 'b'*64, 'test', 'c'*64,
                    status, 0, 'workspaces/default/previews/failed-preview/output/source.pdf', '2026-11-06'))
    path = tmp_path / 'workspaces/default/previews/failed-preview/source.docx'
    path.parent.mkdir(parents=True)
    path.write_bytes(b'failed input retained')
    before = snapshot(tmp_path)
    result = scan.check_library(tmp_path)
    if status == 'failed':
        assert result['healthy'] and result['retained_preview_tasks'] == 1, result
    else:
        assert not result['healthy']
        assert any(i['code'] == 'invalid_ready_preview_metadata' for i in result['issues']), result
    assert snapshot(tmp_path) == before


def test_active_lock_and_missing_database_are_refused_without_creating_a_library(tmp_path):
    absent = tmp_path / 'absent'
    with pytest.raises(ValueError):
        scan.check_library(absent)
    assert not absent.exists()
    library(tmp_path / 'data')
    with DataLock(tmp_path / 'data'), pytest.raises(RuntimeError):
        scan.check_library(tmp_path / 'data')


def test_unsafe_database_reference_never_opens_an_external_file(tmp_path, monkeypatch):
    root = tmp_path / 'data'
    library(root)
    outside = tmp_path / 'outside'
    outside.write_bytes(b'never read by scanner')
    with sqlite3.connect(root / 'study.db') as db:
        db.execute("UPDATE resources SET relative_path='../outside'")
    before = snapshot(root)
    original_open = Path.open
    def guarded(path, *args, **kwargs):
        assert path.resolve() != outside.resolve(), 'Scanner followed a database path outside the library'
        return original_open(path, *args, **kwargs)
    monkeypatch.setattr(Path, 'open', guarded)
    result = scan.check_library(root)
    assert any(i['code'] == 'unsafe_reference' for i in result['issues'])
    assert snapshot(root) == before


def test_real_reparse_directory_is_reported_without_following_it(tmp_path):
    root, external = tmp_path / 'data', tmp_path / 'external'
    library(root)
    external.mkdir()
    (external / 'keep').write_bytes(b'external')
    link = root / 'unexpected-link'
    if os.name == 'nt':
        result = subprocess.run(['cmd', '/c', 'mklink', '/J', str(link), str(external)],
                                capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
        assert result.returncode == 0
    else:
        link.symlink_to(external, target_is_directory=True)
    result = scan.check_library(root)
    assert any(i['code'] == 'reparse_point' for i in result['issues'])
    with pytest.raises(ValueError):
        scan.check_library(link)
    assert (external / 'keep').read_bytes() == b'external'
    (root / '.study.lock').rename(root / 'original-lock')
    link.rename(root / '.study.lock')
    with pytest.raises(ValueError, match='重解析点'):
        scan.check_library(root)
    assert not (external / '.study.lock').exists()


def test_cli_requires_all_scope_confirmation_and_reports_without_app_startup(tmp_path):
    library(tmp_path)
    command = [sys.executable, '-m', 'study_workbench', '--data-dir', str(tmp_path), '--check-library']
    env = {**os.environ, 'PYTHONPATH': str(Path(__file__).resolve().parents[1]), 'PYTHONIOENCODING': 'utf-8'}
    before = snapshot(tmp_path)
    rejected = subprocess.run(command, env=env, capture_output=True, timeout=40)
    assert rejected.returncode != 0
    config = tmp_path.parent / 'never-written-settings.json'
    rejected = subprocess.run(command + ['--confirm-all-workspaces', '--config', str(config)],
                              env=env, capture_output=True, timeout=40)
    assert rejected.returncode != 0 and not config.exists()
    result = subprocess.run(command + ['--confirm-all-workspaces'], env=env, capture_output=True, timeout=40)
    assert result.returncode == 0, result.stderr.decode(errors='replace')
    assert json.loads(result.stdout)['result']['healthy']
    assert snapshot(tmp_path) == before


def test_cross_workspace_physical_reference_is_rejected_before_read(tmp_path, monkeypatch):
    library(tmp_path)
    target = tmp_path / 'workspaces/foreign/originals/unrelated.bin'
    target.parent.mkdir(parents=True)
    target.write_bytes(b'not part of the default workspace')
    with sqlite3.connect(tmp_path / 'study.db') as db:
        db.execute("UPDATE resources SET relative_path=? WHERE workspace_id='default'",
                   (target.relative_to(tmp_path).as_posix(),))
    before = snapshot(tmp_path)
    original_open = Path.open
    def guarded(path, *args, **kwargs):
        assert path.resolve() != target.resolve(), 'Cross-workspace reference was followed'
        return original_open(path, *args, **kwargs)
    with monkeypatch.context() as patch:
        patch.setattr(Path, 'open', guarded)
        result = scan.check_library(tmp_path)
    assert any(i['code'] == 'cross_workspace_reference' for i in result['issues'])
    assert snapshot(tmp_path) == before


def test_prepared_save_without_pending_bytes_is_a_reconciliation_warning_not_a_missing_file(tmp_path):
    library(tmp_path)
    with sqlite3.connect(tmp_path / 'study.db') as db:
        db.execute("UPDATE document_saves SET status='prepared'")
    before = snapshot(tmp_path)
    result = scan.check_library(tmp_path)
    assert any(i['code'] == 'save_requires_reconciliation' for i in result['issues'])
    assert not any(i['code'] == 'missing_file' for i in result['issues'])
    assert snapshot(tmp_path) == before


def test_unregistered_work_generation_under_a_registered_node_is_not_hidden(tmp_path):
    library(tmp_path)
    with sqlite3.connect(tmp_path / 'study.db') as db:
        relative = db.execute('SELECT relative_path FROM document_workfiles LIMIT 1').fetchone()[0]
    parent = tmp_path.joinpath(*relative.split('/')[:4])
    orphan = parent / 'unregistered-generation'
    orphan.mkdir()
    before = snapshot(tmp_path)
    result = scan.check_library(tmp_path)
    assert any(i.get('relative_path') == orphan.relative_to(tmp_path).as_posix() and
               i['code'] == 'unreferenced_derived_candidate' for i in result['issues']), result
    assert snapshot(tmp_path) == before and orphan.is_dir()


def test_old_schema_is_reported_without_automatic_migration(tmp_path):
    root = tmp_path / 'old-library'
    make_0006(root)
    before = snapshot(root)
    result = scan.check_library(root)
    assert not result['complete'] and not result['healthy']
    assert result['issues'] == [dict(code='unsupported_schema', severity='error')]
    assert snapshot(root) == before


def test_excessively_nested_snapshot_metadata_is_incomplete_and_never_repaired(tmp_path):
    library(tmp_path)
    with sqlite3.connect(tmp_path / 'study.db') as db:
        db.row_factory = sqlite3.Row
        row = dict(db.execute('SELECT * FROM question_versions LIMIT 1').fetchone())
        row.update(id='corrupt-metadata-fixture', revision=row['revision'] + 1,
                   attachments='[' * 2000 + '0' + ']' * 2000)
        columns = ','.join(row)
        db.execute(f"INSERT INTO question_versions ({columns}) VALUES ({','.join('?' for _ in row)})", list(row.values()))
    before = snapshot(tmp_path)
    result = scan.check_library(tmp_path)
    assert not result['complete'] and not result['healthy']
    assert any(i['code'] == 'scan_unreadable' for i in result['issues']), result
    assert snapshot(tmp_path) == before
