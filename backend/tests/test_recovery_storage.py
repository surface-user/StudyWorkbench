import json
import os
import sqlite3
import subprocess
import sys
from contextlib import contextmanager
from pathlib import Path

import pytest
from study_workbench import recovery_storage as scan
from study_workbench.data_root import DataLock
from test_backup_store import library
from test_document_files import working
from test_document_recovery import interrupted
from test_explorer import PREFIX, client, make_0006
from test_library_integrity import snapshot


def totals(root):
    return {p.relative_to(root).as_posix(): p.stat().st_size for p in root.rglob('*')
            if p.is_file() and len(p.relative_to(root).parts) >= 4
            and p.relative_to(root).parts[0] == 'workspaces'
            and p.relative_to(root).parts[2] in scan.KINDS}


def test_all_spaces_tombstones_question_files_and_unknown_bytes_are_metadata_only(tmp_path, monkeypatch):
    node, _ = library(tmp_path)
    with sqlite3.connect(tmp_path / 'study.db') as db:
        question_node = db.execute('SELECT node_id FROM question_files LIMIT 1').fetchone()[0]
    with client(tmp_path) as c:
        working(c, question_node)
        assert c.delete(f'{PREFIX}/nodes/{node}').status_code == 200
    extra = tmp_path / f'workspaces/default/working/{node}/old-generation/retained.bin'
    extra.parent.mkdir()
    extra.write_bytes(b'\xff\x00retained without text decoding')
    expected = totals(tmp_path)
    before = snapshot(tmp_path)
    real_open = Path.open

    def guarded(path, *args, **kwargs):
        assert path.name == '.study.lock', 'Capacity inventory opened business contents'
        return real_open(path, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(Path, 'open', guarded)
        result = scan.report_recovery_storage(tmp_path)
    assert result['complete'], result
    assert result['file_count'] == len(expected)
    assert result['logical_bytes'] == sum(expected.values())
    assert sum(g['logical_bytes'] for g in result['categories'].values()) == result['logical_bytes']
    assert result['categories']['current_workfile']['file_count'] >= 3  # Includes archived and QuestionFile.
    assert result['categories']['unreferenced_working_file'] == dict(file_count=1, logical_bytes=extra.stat().st_size)
    assert result['categories']['before_recovery']['file_count'] == 1
    assert result['missing_committed_pending'] == 1
    assert result['content_integrity_checked'] is False and result['library_health_checked'] is False
    assert result['data_modified'] is False and result['deletion_authorized'] is False
    assert result['snapshot_atomic'] is False and result['bytes_kind'] == 'observed_logical_lengths'
    assert str(tmp_path) not in json.dumps(result) and '原件正文' not in json.dumps(result, ensure_ascii=False)
    assert snapshot(tmp_path) == before


@pytest.mark.parametrize('status', ['prepared', 'interrupted', 'conflict', 'committed'])
@pytest.mark.parametrize('missing_pending', [False, True])
def test_receipt_states_and_missing_pending_are_not_deletion_advice(tmp_path, monkeypatch, status, missing_pending):
    with client(tmp_path) as c:
        _, _, identifier, paths, _, original = interrupted(c, tmp_path, monkeypatch)
    with sqlite3.connect(tmp_path / 'study.db') as db:
        db.execute('UPDATE document_saves SET status=? WHERE id=?', (status, identifier))
    if missing_pending:
        paths['pending_path'].rename(tmp_path / 'retained-pending.bin')
    before = snapshot(tmp_path)
    result = scan.report_recovery_storage(tmp_path)
    assert result['records_by_status'][status] == 1
    assert result['complete'] is (not missing_pending or status == 'committed'), result
    assert result['categories']['before_recovery'] == dict(file_count=1, logical_bytes=3)
    assert result['categories']['current_workfile'] == dict(file_count=1, logical_bytes=3)
    assert result['categories']['pending_recovery'] == dict(file_count=int(not missing_pending),
                                                         logical_bytes=0 if missing_pending else 7)
    assert result['missing_committed_pending'] == int(missing_pending and status == 'committed')
    assert snapshot(tmp_path) == before and original.read_bytes() == b'old'


@pytest.mark.parametrize('fault', ['work_path', 'work_owner', 'save_path', 'save_id', 'status'])
def test_corrupt_references_fail_closed_and_never_follow_arbitrary_paths(tmp_path, monkeypatch, fault):
    with client(tmp_path) as c:
        _, _, identifier, _, _, _ = interrupted(c, tmp_path, monkeypatch)
    with sqlite3.connect(tmp_path / 'study.db') as db:
        if fault == 'work_path':
            db.execute("UPDATE document_workfiles SET relative_path='../../outside/current.md'")
        elif fault == 'work_owner':
            db.execute("UPDATE document_workfiles SET workspace_id='foreign'")
        elif fault == 'save_path':
            db.execute("UPDATE document_saves SET backup_path='../../outside/private.md'")
        elif fault == 'save_id':
            db.execute("UPDATE document_saves SET id='invalid'")
        else:
            db.execute("UPDATE document_saves SET status='unexpected'")
    before = snapshot(tmp_path)
    result = scan.report_recovery_storage(tmp_path)
    assert not result['complete'] and result['issues'], result
    assert all('outside' not in item['relative_path'] for item in result['largest_files'])
    assert result['deletion_authorized'] is False and snapshot(tmp_path) == before


@pytest.mark.parametrize('limit', ['ENTRY_LIMIT', 'ROW_LIMIT', 'SECONDS', 'ISSUE_LIMIT'])
def test_budget_exhaustion_is_explicit_and_leaves_every_byte(tmp_path, monkeypatch, limit):
    library(tmp_path)
    if limit == 'ISSUE_LIMIT':
        with sqlite3.connect(tmp_path / 'study.db') as db:
            db.execute("UPDATE document_workfiles SET relative_path='../../outside/' || node_id")
    before = snapshot(tmp_path)
    monkeypatch.setattr(scan, limit, 0)
    result = scan.report_recovery_storage(tmp_path)
    assert result['complete'] is False and 'limit_reason' in result, result
    assert snapshot(tmp_path) == before


def test_large_sparse_files_and_top_list_are_logical_lengths_not_reclaimable_space(tmp_path):
    library(tmp_path)
    folder = tmp_path / 'workspaces/default/working/unregistered'
    folder.mkdir()
    for i in range(25):
        (folder / f'file-{i:02}.bin').write_bytes(b'x' * i)
    large = folder / 'large.bin'
    with large.open('wb') as stream:
        stream.truncate(1024 * 1024 * 1024)
    result = scan.report_recovery_storage(tmp_path)
    assert result['complete'], result
    assert result['categories']['unreferenced_working_file'] == dict(file_count=26, logical_bytes=1024**3 + sum(range(25)))
    assert len(result['largest_files']) == 20 and result['largest_files_truncated'] is True
    assert result['largest_files'][0]['relative_path'].endswith('large.bin')
    assert result['largest_files'] == sorted(result['largest_files'], key=lambda item: (-item['logical_bytes'], item['relative_path']))
    assert 'reclaimable_bytes' not in result and large.stat().st_size == 1024**3


def test_hardlinks_are_counted_per_relative_path_without_claiming_disk_allocation(tmp_path):
    library(tmp_path)
    folder = tmp_path / 'workspaces/default/working/extra'
    folder.mkdir()
    first, second = folder / 'one.bin', folder / 'two.bin'
    first.write_bytes(b'logical')
    os.link(first, second)
    before = snapshot(tmp_path)
    result = scan.report_recovery_storage(tmp_path)
    assert result['complete'] and result['categories']['unreferenced_working_file'] == dict(file_count=2, logical_bytes=14)
    assert result['bytes_kind'] == 'observed_logical_lengths' and snapshot(tmp_path) == before


def test_missing_required_file_is_reported_without_repair(tmp_path):
    library(tmp_path)
    with sqlite3.connect(tmp_path / 'study.db') as db:
        relative = db.execute('SELECT relative_path FROM document_workfiles LIMIT 1').fetchone()[0]
    target = tmp_path / relative
    target.rename(tmp_path / 'retained-current.bin')
    before = snapshot(tmp_path)
    result = scan.report_recovery_storage(tmp_path)
    assert not result['complete'] and any(i['code'] == 'missing_required_reference' for i in result['issues'])
    assert snapshot(tmp_path) == before and not target.exists()


def test_metadata_change_during_scan_is_not_presented_as_complete(tmp_path, monkeypatch):
    library(tmp_path)
    target = tmp_path / 'workspaces/default/working/changing.bin'
    target.write_bytes(b'original external bytes')
    before = snapshot(tmp_path)
    real_scan = scan.os.scandir

    class Changed:
        def __init__(self, entry):
            self.path, self.name, self.entry = entry.path, entry.name, entry

        def stat(self, **kwargs):
            info = self.entry.stat(**kwargs)
            target.write_bytes(b'external changed bytes remain')
            return info

    @contextmanager
    def changing(path):
        with real_scan(path) as entries:
            yield (Changed(e) if Path(e.path) == target else e for e in entries)

    with monkeypatch.context() as patch:
        patch.setattr(scan.os, 'scandir', changing)
        result = scan.report_recovery_storage(tmp_path)
    assert not result['complete'] and any(i['code'] == 'file_changed_during_scan' for i in result['issues'])
    before[target.relative_to(tmp_path).as_posix()] = b'external changed bytes remain'
    assert snapshot(tmp_path) == before


def test_unreadable_scan_and_database_are_incomplete(tmp_path, monkeypatch):
    library(tmp_path)
    before = snapshot(tmp_path)
    with monkeypatch.context() as patch:
        patch.setattr(scan.os, 'scandir', lambda *args: (_ for _ in ()).throw(PermissionError('injected')))
        result = scan.report_recovery_storage(tmp_path)
    assert not result['complete'] and any(i['code'] == 'scan_unreadable' for i in result['issues'])
    assert snapshot(tmp_path) == before
    (tmp_path / 'study.db').write_bytes(b'corrupt SQLite fixture')
    before = snapshot(tmp_path)
    result = scan.report_recovery_storage(tmp_path)
    assert not result['complete'] and snapshot(tmp_path) == before


def test_active_lock_missing_library_and_old_schema_do_not_create_or_migrate(tmp_path):
    absent = tmp_path / 'absent'
    with pytest.raises(ValueError):
        scan.report_recovery_storage(absent)
    assert not absent.exists()
    library(tmp_path / 'active')
    with DataLock(tmp_path / 'active'), pytest.raises(RuntimeError):
        scan.report_recovery_storage(tmp_path / 'active')
    old = tmp_path / 'old'
    make_0006(old)
    before = snapshot(old)
    result = scan.report_recovery_storage(old)
    assert not result['complete'] and result['issues'] == [dict(code='unsupported_schema')]
    assert snapshot(old) == before


def test_windows_junction_is_not_expanded_or_counted(tmp_path):
    if os.name != 'nt':
        pytest.skip('Windows junction boundary')
    library(tmp_path)
    working = tmp_path / 'workspaces/default/working'
    retained = working.with_name('retained-working')
    expected = {p.relative_to(working).as_posix(): p.read_bytes() for p in working.rglob('*') if p.is_file()}
    working.rename(retained)
    link = subprocess.run(['cmd', '/c', 'mklink', '/J', str(working), str(retained)], capture_output=True, timeout=15)
    assert link.returncode == 0, link.stderr.decode(errors='replace')
    result = scan.report_recovery_storage(tmp_path)
    assert not result['complete'] and any(i['code'] == 'reparse_point' for i in result['issues'])
    assert not any(item['relative_path'].startswith('workspaces/default/working/') for item in result['largest_files'])
    assert {p.relative_to(retained).as_posix(): p.read_bytes() for p in retained.rglob('*') if p.is_file()} == expected


def test_cli_requires_explicit_scope_and_rejects_other_operations(tmp_path):
    library(tmp_path)
    command = [sys.executable, '-m', 'study_workbench', '--data-dir', str(tmp_path), '--report-recovery-storage']
    env = {**os.environ, 'PYTHONPATH': str(Path(__file__).parents[1]), 'PYTHONUTF8': '1'}
    before = snapshot(tmp_path)
    for flags in [[], ['--confirm-all-workspaces', '--config', str(tmp_path / 'config.json')],
                  ['--confirm-all-workspaces', '--media', str(tmp_path / 'video.mp4')],
                  ['--confirm-all-workspaces', '--parent-pipe'], ['--check-library'],
                  ['--backup-to', str(tmp_path / 'new.zip')], ['--move-data', str(tmp_path / 'moved')]]:
        run = subprocess.run(command + flags, env=env, capture_output=True, timeout=40)
        assert run.returncode != 0 and snapshot(tmp_path) == before
    run = subprocess.run(command + ['--confirm-all-workspaces'], env=env, capture_output=True, timeout=40)
    assert run.returncode == 0, run.stderr.decode(errors='replace')
    report = json.loads(run.stdout)['result']
    assert report['complete'] and report['deletion_authorized'] is False
    assert snapshot(tmp_path) == before and not (tmp_path / 'new.zip').exists()
