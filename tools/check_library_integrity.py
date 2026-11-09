"""Black-box frozen diagnostics: create fresh fixtures through HTTP, preserve all business bytes."""
import argparse
import hashlib
import json
import os
import queue
import re
import secrets
import sqlite3
import subprocess
import threading
import urllib.error
import urllib.request
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--exe', type=Path, required=True)
    parser.add_argument('--test-root', type=Path, required=True)
    args = parser.parse_args()
    root = args.test_root.resolve()
    root.mkdir()  # Never reuse or erase a previous fixture or personal library.
    data = root / 'data'
    command = [str(args.exe.resolve()), '--data-dir', str(data)]
    env = {**os.environ, 'PATH': str(Path(os.environ['SystemRoot']) / 'System32')}
    for key in ['PYTHONPATH', 'PYTHONHOME']:
        env.pop(key, None)
    token = secrets.token_urlsafe(32)
    process = subprocess.Popen(command, env=env, cwd=root, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, text=True, encoding='utf-8',
                               creationflags=subprocess.CREATE_NO_WINDOW)

    def inspect(expected):
        before = snapshot()
        run = subprocess.run(command + ['--check-library', '--confirm-all-workspaces'], env=env, cwd=root,
                             capture_output=True, text=True, encoding='utf-8', timeout=60,
                             creationflags=subprocess.CREATE_NO_WINDOW)
        assert run.returncode == expected, run.stderr[-1000:]
        result = json.loads(run.stdout)['result']
        assert result['complete'] and not result['data_modified'] and not result['repair_performed']
        assert snapshot() == before, 'Offline diagnostics changed business data'
        return result

    def snapshot():
        return {p.relative_to(data).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in data.rglob('*') if p.is_file() and p.name != '.study.lock'}

    def capacity(*, office=False, expected=0):
        before = snapshot()
        flag = '--report-office-storage' if office else '--report-recovery-storage'
        run = subprocess.run(command + [flag, '--confirm-all-workspaces'], env=env, cwd=root,
                             capture_output=True, text=True, encoding='utf-8', timeout=60,
                             creationflags=subprocess.CREATE_NO_WINDOW)
        assert run.returncode == expected, run.stderr[-1000:] + run.stdout[-2000:]
        report = json.loads(run.stdout)['result']
        assert report['complete'] is (expected == 0) and not report['data_modified'] and not report['deletion_authorized']
        assert not report['content_integrity_checked'] and not report['library_health_checked']
        assert report['bytes_kind'] == 'observed_logical_lengths' and not report['snapshot_atomic']
        assert snapshot() == before, 'Capacity report changed business data'
        return report

    try:
        process.stdin.write(json.dumps({'token': token}) + '\n')
        process.stdin.flush()
        hello = queue.Queue()
        threading.Thread(target=lambda: hello.put(process.stdout.readline()), daemon=True).start()
        port = json.loads(hello.get(timeout=30))['port']
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        request = urllib.request.Request(f'http://127.0.0.1:{port}/api/workspaces/default/markdown-notes',
            data=json.dumps({'name': '巡检样本.md', 'request_id': 'integrity-blackbox-note-0001'}).encode(),
            headers={'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json'})
        with opener.open(request, timeout=30) as response:
            node = json.load(response)['resource_item_id']
        assert re.fullmatch('[a-f0-9]{32}', node)

        def request_json(method, path, body=None, expected=200):
            api_path = path if path.startswith('/api/') else f'/api/workspaces/default/nodes/{node}' + path
            req = urllib.request.Request(f'http://127.0.0.1:{port}' + api_path,
                data=None if body is None else json.dumps(body).encode(), method=method,
                headers={'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json'})
            try:
                with opener.open(req, timeout=30) as response:
                    assert response.status == expected
                    return json.load(response)
            except urllib.error.HTTPError as error:
                assert error.code == expected, str(error.code)
                return json.load(error)

        initial = request_json('GET', '/document')
        saved = request_json('PUT', '/document', {'expected_sha256': initial['sha256'], 'text': 'new workfile'})
        rows = request_json('GET', '/document-saves?limit=1')
        receipt = rows[0]['id']
        before = {p: b for p, b in snapshot().items() if p.endswith('.md')}
        recovered = request_json('GET', f'/document-saves/{receipt}?version=before')
        assert recovered['text'] == initial['text'] and recovered['current_sha256'] == saved['sha256']
        request_json('GET', f'/document-saves/{receipt}?version=pending', expected=409)
        assert {p: b for p, b in snapshot().items() if p.endswith('.md')} == before
        current = data / 'workspaces/default/working' / node / 'note/current.md'
        current.write_bytes(b'external after recovery preview')
        request_json('PUT', '/document', {'expected_sha256': recovered['current_sha256'], 'text': recovered['text']}, expected=409)
        assert current.read_bytes() == b'external after recovery preview'
        recovered = request_json('GET', f'/document-saves/{receipt}?version=before')
        request_json('PUT', '/document', {'expected_sha256': recovered['current_sha256'], 'text': recovered['text']})
        assert current.read_text(encoding='utf-8') == initial['text']
        assert request_json('GET', '/document-saves/' + receipt + '?version=before')['text'] == initial['text']
        # A merge preview must retain the same bytes/receipts and cannot authorize a later stale save.
        merge_body = dict(base='before', save_id=receipt, expected_base_sha256=initial['sha256'],
                          expected_current_sha256=initial['sha256'], text=initial['text'])
        before = snapshot()
        candidate = request_json('POST', '/document-merge-preview', merge_body)
        assert not candidate['conflicted'] and candidate['text'] == initial['text']
        assert snapshot() == before
        current.write_bytes(b'external after merge preview')
        request_json('PUT', '/document', {'expected_sha256': candidate['current_sha256'],
                                        'text': candidate['text']}, expected=409)
        assert current.read_bytes() == b'external after merge preview'
        request_json('POST', '/document-merge-preview', merge_body, expected=409)
        merge_body.update(expected_current_sha256=hashlib.sha256(current.read_bytes()).hexdigest(),
                          text='different local text')
        before = snapshot()
        candidate = request_json('POST', '/document-merge-preview', merge_body)
        assert candidate['conflicted'] and candidate['text'] is None
        assert snapshot() == before
        request_json('PUT', '/document', {'expected_sha256': merge_body['expected_current_sha256'],
                                        'text': initial['text']})
        retained = current.with_name('missing-current.retained')
        current.rename(retained)  # Deliberately missing fixture; the product never repairs this path.
        request_json('GET', '/document', expected=409)
        recovered = request_json('GET', f'/document-saves/{receipt}?version=before')
        assert recovered['current_sha256'] is None
        copy_request = {'name': '恢复副本.md', 'request_id': 'integrity-recovery-copy-0001'}
        copied = request_json('POST', '/api/workspaces/default/markdown-notes', copy_request)
        copy_id = copied['resource_item_id']
        assert copy_id != node
        copy_path = f'/api/workspaces/default/nodes/{copy_id}/document'
        initial_copy = request_json('GET', copy_path)
        assert initial_copy['sha256'] == copied['sha256']
        request_json('PUT', copy_path, {'expected_sha256': copied['sha256'], 'text': recovered['text']})
        saved_copy = request_json('GET', copy_path)
        assert saved_copy['sha256'] == recovered['sha256'] and saved_copy['text'] == recovered['text']
        duplicate = request_json('POST', '/api/workspaces/default/markdown-notes', copy_request)
        assert duplicate['resource_item_id'] == copy_id
        edited = request_json('PUT', copy_path, {'expected_sha256': saved_copy['sha256'], 'text': 'keep changed copy'})
        request_json('POST', '/api/workspaces/default/markdown-notes', copy_request)
        request_json('PUT', copy_path, {'expected_sha256': copied['sha256'], 'text': recovered['text']}, expected=409)
        assert request_json('GET', copy_path)['sha256'] == edited['sha256']
        assert not current.exists() and retained.read_text(encoding='utf-8') == initial['text']
        assert request_json('GET', f'/document-saves/{receipt}?version=before')['text'] == initial['text']
        retained.rename(current)  # Reset only this deliberate missing-file fixture for the healthy CLI case below.
        blocked = subprocess.run(command + ['--check-library', '--confirm-all-workspaces'], env=env, cwd=root,
                                 capture_output=True, timeout=30, creationflags=subprocess.CREATE_NO_WINDOW)
        assert blocked.returncode != 0, 'Diagnostics bypassed the active application lock'
        blocked = subprocess.run(command + ['--report-recovery-storage', '--confirm-all-workspaces'], env=env, cwd=root,
                                 capture_output=True, timeout=30, creationflags=subprocess.CREATE_NO_WINDOW)
        assert blocked.returncode != 0, 'Capacity report bypassed the active application lock'
        blocked = subprocess.run(command + ['--report-office-storage', '--confirm-all-workspaces'], env=env, cwd=root,
                                 capture_output=True, timeout=30, creationflags=subprocess.CREATE_NO_WINDOW)
        assert blocked.returncode != 0, 'Office report bypassed the active application lock'
        process.stdin.close()
        assert process.wait(timeout=20) == 0
        assert not process.stderr.read().strip()
        healthy = inspect(0)
        assert healthy['healthy'] and not healthy['issues']
        sizes = capacity()
        assert sizes['categories']['current_workfile']['file_count'] == 2
        assert sizes['categories']['before_recovery']['file_count'] >= 1
        orphan = data / 'workspaces/default/working' / node / 'orphan-generation'
        orphan.mkdir()
        (orphan / 'keep').write_bytes(b'self-authored retained orphan')
        found = inspect(1)
        assert not found['healthy']
        assert found['issues'] == [dict(code='unreferenced_derived_candidate', severity='warning',
                                       relative_path=orphan.relative_to(data).as_posix())]
        extra = capacity()
        assert (extra['categories']['unreferenced_working_file']['logical_bytes']
                - sizes['categories']['unreferenced_working_file']['logical_bytes']) == len(b'self-authored retained orphan')
        current = data / 'workspaces/default/working' / node / 'note/current.md'
        current.write_bytes(b'external workfile edit must survive diagnostics')
        changed = inspect(1)
        assert {item['code'] for item in changed['issues']} == {
            'unreferenced_derived_candidate', 'workfile_index_changed'}
        assert capacity(office=True)['file_count'] == 0
        # Synthetic offline metadata exercises the CLI without requiring an Office runtime.
        resource_id, office_node, preview_id = 'd' * 32, 'e' * 32, 'f' * 32
        source_relative = f'workspaces/default/originals/{resource_id}.bin'
        source = data / source_relative
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_bytes(b'self-authored retained Office source')
        pdf_relative = f'workspaces/default/previews/{preview_id}/output/source.pdf'
        with sqlite3.connect(data / 'study.db') as db:
            db.execute('INSERT INTO resources (id,workspace_id,original_name,relative_path,mime,size,sha256) VALUES (?,?,?,?,?,?,?)',
                       (resource_id, 'default', 'fixture.docx', source_relative, 'application/octet-stream',
                        source.stat().st_size, hashlib.sha256(source.read_bytes()).hexdigest()))
            db.execute('INSERT INTO workspace_nodes (id,workspace_id,kind,name,name_key,resource_id) VALUES (?,?,?,?,?,?)',
                       (office_node, 'default', 'resource', 'fixture.docx', 'fixture.docx', resource_id))
            db.execute('INSERT INTO document_previews '
                       '(id,workspace_id,node_id,source_resource_id,source_sha256,runtime_fingerprint,converter_version, '
                       'options_hash,status,cancel_requested,relative_pdf,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',
                       (preview_id, 'default', office_node, resource_id, hashlib.sha256(source.read_bytes()).hexdigest(),
                        'a' * 64, 'fixture', 'b' * 64, 'failed', False, pdf_relative, '2026-11-10T00:00:00+08:00'))
        directory = (data / pdf_relative).parent.parent
        generated = {'source.docx': b'retained source', 'profile/user/failed.bin': b'failed profile evidence',
                     'tmp/partial.bin': b'partial output'}
        for name, content in generated.items():
            target = directory / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
        orphan_office = data / 'workspaces/default/previews/unregistered/keep'
        orphan_office.parent.mkdir(parents=True)
        orphan_office.write_bytes(b'unknown Office evidence')
        office = capacity(office=True)
        assert office['scope'] == 'office_preview_task_files' and office['missing_nonready_pdf'] == 1
        assert office['records_by_status']['failed'] == 1
        assert office['categories']['failed_preview_file'] == dict(file_count=3, logical_bytes=sum(map(len, generated.values())))
        assert office['categories']['unregistered_preview_file'] == dict(file_count=1, logical_bytes=orphan_office.stat().st_size)
        with sqlite3.connect(data / 'study.db') as db:
            db.execute("UPDATE document_previews SET status='ready' WHERE id=?", (preview_id,))
        missing_ready = capacity(office=True, expected=1)
        assert any(i['code'] == 'missing_required_reference' for i in missing_ready['issues'])
        summary = dict(frozen=True, active_lock_refused=True, healthy_case_verified=True, orphan_detected=True,
                       external_edit_detected=True, business_bytes_preserved=True, repair_performed=False,
                       recovery_preview_readonly=True, recovery_save_conflict_guard=True, recovery_explicit_save=True,
                       missing_source_copy=True, copy_creation_idempotent=True, original_missing_not_repaired=True,
                       merge_preview_readonly=True, merge_stale_save_refused=True, merge_conflict_has_no_candidate=True,
                       capacity_report_metadata_readonly=True, capacity_unregistered_bytes_accounted=True,
                       capacity_deletion_authorized=False, office_inventory_metadata_readonly=True,
                       office_failed_profile_bytes_accounted=True, office_missing_ready_refused=True,
                       office_deletion_authorized=False)
        (root / 'result.json').write_text(json.dumps(summary, indent=2) + '\n', encoding='utf-8')
        print(json.dumps(summary))
    finally:
        if process.poll() is None:
            process.stdin.close()
            try:
                process.wait(timeout=20)
            except subprocess.TimeoutExpired:
                process.kill()  # Only this script's retained fixture process.
                process.wait(timeout=10)


if __name__ == '__main__':
    main()
