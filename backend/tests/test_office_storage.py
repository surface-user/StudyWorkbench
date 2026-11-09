import hashlib
import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

import pytest
from study_workbench import recovery_storage as scan
from study_workbench.data_root import DataLock
from test_document_files import add
from test_explorer import PREFIX, client, make_0006
from test_library_integrity import snapshot
from test_office_previews import package


def office_library(root, statuses=None, *, archived=False, missing_pdf=False):
    jobs = []
    with client(root) as c:
        other = c.post('/api/workspaces', json={'name': 'Archived Office'}).json()['id'] if archived else None
        for status in sorted(statuses or scan.OFFICE_STATUSES):
            raw = package(value=f'<document>{status}</document>')
            node, resource, original = add(c, root, status + '.docx', raw)
            jobs.append(dict(id=uuid4().hex, status=status, node=node, resource=resource, original=original,
                             workspace='default', sha=hashlib.sha256(raw).hexdigest()))
        if archived:
            assert c.delete(f"{PREFIX}/nodes/{jobs[0]['node']}").status_code == 200
            assert c.request('DELETE', f'/api/workspaces/{other}', json={'confirm_name': 'Archived Office'}).status_code == 200
    # Insert offline so queued/running fixtures are not reconciled by normal startup.
    with sqlite3.connect(root / 'study.db') as db:
        for i, job in enumerate(jobs):
            if archived and i == 0:
                job['workspace'] = other
                relative = f"workspaces/{other}/originals/{job['resource']}.bin"
                target = root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                job['original'].rename(target)
                job['original'] = target
                db.execute('UPDATE resources SET workspace_id=?,relative_path=? WHERE id=?', (other, relative, job['resource']))
                db.execute('UPDATE workspace_nodes SET workspace_id=? WHERE id=?', (other, job['node']))
            job['directory'] = root / f"workspaces/{job['workspace']}/previews/{job['id']}"
            pdf = f"workspaces/{job['workspace']}/previews/{job['id']}/output/source.pdf"
            db.execute('INSERT INTO document_previews '
                       '(id,workspace_id,node_id,source_resource_id,source_sha256,runtime_fingerprint,converter_version, '
                       'options_hash,status,cancel_requested,relative_pdf,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',
                       (job['id'], job['workspace'], job['node'], job['resource'], job['sha'], 'a' * 64, 'fixture',
                        'b' * 64, job['status'], False, pdf, '2026-11-10T00:00:00+08:00'))
            for name, data in {'source.docx': b'retained source copy', 'profile/user/settings.bin': b'private profile',
                               'tmp/partial.bin': b'failed bytes', 'output/source.pdf': b'not parsed as PDF'}.items():
                if missing_pdf and name == 'output/source.pdf':
                    continue
                target = job['directory'] / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
    return jobs


def test_all_states_archived_tombstones_profiles_and_unknown_files_are_metadata_only(tmp_path, monkeypatch):
    jobs = office_library(tmp_path, archived=True)
    extra = tmp_path / 'workspaces/default/previews/unregistered/retained.bin'
    extra.parent.mkdir(parents=True)
    extra.write_bytes(b'unknown evidence')
    failed = next(job for job in jobs if job['status'] == 'failed')['directory']
    os.link(failed / 'tmp/partial.bin', failed / 'tmp/linked.bin')
    for name in ['downloads/task/old.mp4', 'working/old/draft.md', 'question-versions/version/current.md', 'originals/extra.bin']:
        excluded = tmp_path / 'workspaces/default' / name
        excluded.parent.mkdir(parents=True, exist_ok=True)
        excluded.write_bytes(b'excluded authority bytes')
    expected = {p.relative_to(tmp_path).as_posix(): p.stat().st_size for p in tmp_path.rglob('*')
                if p.is_file() and len(p.relative_to(tmp_path).parts) >= 4
                and p.relative_to(tmp_path).parts[0] == 'workspaces' and p.relative_to(tmp_path).parts[2] == 'previews'}
    before = snapshot(tmp_path)
    real_open = Path.open

    def guarded(path, *args, **kwargs):
        assert path.name == '.study.lock', 'Office inventory opened business contents'
        return real_open(path, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(Path, 'open', guarded)
        result = scan.report_office_storage(tmp_path)
    assert result['complete'], result
    assert result['scope'] == 'office_preview_task_files' and result['schema_version'] == 1
    assert result['file_count'] == len(expected) and result['logical_bytes'] == sum(expected.values())
    assert sum(g['logical_bytes'] for g in result['categories'].values()) == result['logical_bytes']
    for job in jobs:
        expected_sizes = [p.stat().st_size for p in job['directory'].rglob('*') if p.is_file()]
        assert result['categories'][job['status'] + '_preview_file'] == dict(file_count=len(expected_sizes), logical_bytes=sum(expected_sizes))
    assert result['categories']['unregistered_preview_file'] == dict(file_count=1, logical_bytes=extra.stat().st_size)
    assert result['records_by_status'] == {s: 1 for s in scan.OFFICE_STATUSES}
    assert len(result['largest_files']) == 20 and result['largest_files_truncated']
    assert result['largest_files'] == sorted(result['largest_files'], key=lambda item: (-item['logical_bytes'], item['relative_path']))
    assert all('preview_status' in item and 'save_status' not in item for item in result['largest_files'])
    assert result['missing_nonready_pdf'] == 0 and 'missing_committed_pending' not in result
    for flag in ['data_modified', 'deletion_authorized', 'content_integrity_checked', 'library_health_checked', 'snapshot_atomic']:
        assert result[flag] is False
    assert result['bytes_kind'] == 'observed_logical_lengths' and 'reclaimable_bytes' not in result
    assert str(tmp_path) not in json.dumps(result) and 'private profile' not in json.dumps(result)
    assert snapshot(tmp_path) == before


@pytest.mark.parametrize('status', sorted(scan.OFFICE_STATUSES))
def test_missing_pdf_only_ready_is_required_and_states_are_not_reconciled(tmp_path, status):
    office_library(tmp_path, [status], missing_pdf=True)
    before = snapshot(tmp_path)
    result = scan.report_office_storage(tmp_path)
    assert result['complete'] is (status != 'ready'), result
    assert result['missing_nonready_pdf'] == int(status != 'ready')
    assert result['records_by_status'][status] == 1
    assert result['categories'][status + '_preview_file']['file_count'] == 3
    if status == 'ready':
        assert any(i['code'] == 'missing_required_reference' for i in result['issues'])
    assert snapshot(tmp_path) == before


@pytest.mark.parametrize('fault', ['path', 'id', 'status', 'workspace', 'node_kind', 'node_source', 'resource_space', 'missing_space'])
def test_invalid_task_metadata_cannot_attribute_or_expand_arbitrary_paths(tmp_path, fault):
    office_library(tmp_path, ['failed'])
    with sqlite3.connect(tmp_path / 'study.db') as db:
        sql = {'path': "UPDATE document_previews SET relative_pdf='../../outside/private.pdf'",
               'id': "UPDATE document_previews SET id='bad-id'",
               'status': "UPDATE document_previews SET status='unknown'",
               'workspace': "UPDATE document_previews SET workspace_id='foreign'",
               'node_kind': "UPDATE workspace_nodes SET kind='folder',resource_id=NULL WHERE id IN (SELECT node_id FROM document_previews)",
               'node_source': "UPDATE workspace_nodes SET resource_id='foreign' WHERE id IN (SELECT node_id FROM document_previews)",
               'resource_space': "UPDATE resources SET workspace_id='foreign' WHERE id IN (SELECT source_resource_id FROM document_previews)",
               'missing_space': "DELETE FROM workspaces WHERE id='default'"}[fault]
        db.execute(sql)
    before = snapshot(tmp_path)
    result = scan.report_office_storage(tmp_path)
    assert not result['complete'] and result['issues'], result
    assert result['categories']['failed_preview_file']['file_count'] == 0
    assert result['categories']['unregistered_preview_file']['file_count'] == 4
    assert all('outside' not in item['relative_path'] for item in result['largest_files'])
    assert snapshot(tmp_path) == before


@pytest.mark.parametrize('limit', ['ENTRY_LIMIT', 'ROW_LIMIT', 'SECONDS', 'ISSUE_LIMIT'])
def test_office_budget_is_incomplete_and_read_only(tmp_path, monkeypatch, limit):
    office_library(tmp_path, ['failed'])
    if limit == 'ISSUE_LIMIT':
        with sqlite3.connect(tmp_path / 'study.db') as db:
            db.execute("UPDATE document_previews SET status='invalid'")
    before = snapshot(tmp_path)
    monkeypatch.setattr(scan, limit, 0)
    result = scan.report_office_storage(tmp_path)
    assert not result['complete'] and 'limit_reason' in result, result
    assert snapshot(tmp_path) == before


def test_office_lock_missing_old_and_corrupt_library_are_not_migrated(tmp_path):
    absent = tmp_path / 'absent'
    with pytest.raises(ValueError):
        scan.report_office_storage(absent)
    assert not absent.exists()
    active = tmp_path / 'active'
    office_library(active, ['failed'])
    with DataLock(active), pytest.raises(RuntimeError):
        scan.report_office_storage(active)
    old = tmp_path / 'old'
    make_0006(old)
    before = snapshot(old)
    result = scan.report_office_storage(old)
    assert not result['complete'] and result['issues'] == [dict(code='unsupported_schema')]
    assert snapshot(old) == before
    (active / 'study.db').write_bytes(b'corrupt fixture')
    before = snapshot(active)
    assert not scan.report_office_storage(active)['complete'] and snapshot(active) == before


def test_office_junction_is_not_followed_and_target_bytes_survive(tmp_path):
    if os.name != 'nt':
        pytest.skip('Windows junction boundary')
    office_library(tmp_path, ['failed'])
    previews = tmp_path / 'workspaces/default/previews'
    retained = previews.with_name('retained-previews')
    expected = {p.relative_to(previews).as_posix(): p.read_bytes() for p in previews.rglob('*') if p.is_file()}
    previews.rename(retained)
    run = subprocess.run(['cmd', '/c', 'mklink', '/J', str(previews), str(retained)], capture_output=True, timeout=15)
    assert run.returncode == 0, run.stderr.decode(errors='replace')
    result = scan.report_office_storage(tmp_path)
    assert not result['complete'] and any(i['code'] == 'reparse_point' for i in result['issues'])
    assert result['file_count'] == 0
    assert {p.relative_to(retained).as_posix(): p.read_bytes() for p in retained.rglob('*') if p.is_file()} == expected


def test_office_cli_is_explicit_mutually_exclusive_and_read_only(tmp_path):
    office_library(tmp_path, ['interrupted'])
    command = [sys.executable, '-m', 'study_workbench', '--data-dir', str(tmp_path), '--report-office-storage']
    env = {**os.environ, 'PYTHONPATH': str(Path(__file__).parents[1]), 'PYTHONUTF8': '1'}
    before = snapshot(tmp_path)
    for flags in [[], ['--confirm-all-workspaces', '--config', str(tmp_path / 'config.json')],
                  ['--confirm-all-workspaces', '--media', str(tmp_path / 'movie.mp4')],
                  ['--confirm-all-workspaces', '--parent-pipe'], ['--confirm-all-workspaces', '--check-library'],
                  ['--confirm-all-workspaces', '--report-recovery-storage'],
                  ['--confirm-all-workspaces', '--backup-to', str(tmp_path / 'new.zip')],
                  ['--confirm-all-workspaces', '--restore-backup', str(tmp_path / 'no.zip')],
                  ['--confirm-all-workspaces', '--move-data', str(tmp_path / 'moved')]]:
        run = subprocess.run(command + flags, env=env, capture_output=True, timeout=40)
        assert run.returncode != 0 and snapshot(tmp_path) == before
    run = subprocess.run(command + ['--confirm-all-workspaces'], env=env, capture_output=True, timeout=40)
    assert run.returncode == 0, run.stderr.decode(errors='replace')
    result = json.loads(run.stdout)['result']
    assert result['complete'] and result['scope'] == 'office_preview_task_files' and not result['deletion_authorized']
    assert snapshot(tmp_path) == before and not (tmp_path / 'new.zip').exists()
