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

    def capacity(*, office=False, download=False, expected=0):
        before = snapshot()
        flag = '--report-download-storage' if download else '--report-office-storage' if office else '--report-recovery-storage'
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
        fixture = Path(__file__).resolve().parents[1] / 'contracts/samples/numbered-questions.docx'
        req = urllib.request.Request(f'http://127.0.0.1:{port}/api/workspaces/default/imports?filename=fixture.docx',
            data=fixture.read_bytes(), headers={'Authorization': 'Bearer ' + token,
                                               'Content-Type': 'application/octet-stream'})
        with opener.open(req, timeout=30) as response:
            imported = json.load(response)
        assert imported['status'] == 'preview'
        extracted = request_json('POST', f"/api/workspaces/default/imports/{imported['id']}/question-markdown",
                                 dict(expected_revision=imported['draft_revision'], selected=[0], confirm=True))[0]
        assert re.fullmatch('[a-f0-9]{32}', extracted['id'])
        blocked = subprocess.run(command + ['--check-library', '--confirm-all-workspaces'], env=env, cwd=root,
                                 capture_output=True, timeout=30, creationflags=subprocess.CREATE_NO_WINDOW)
        assert blocked.returncode != 0, 'Diagnostics bypassed the active application lock'
        blocked = subprocess.run(command + ['--report-recovery-storage', '--confirm-all-workspaces'], env=env, cwd=root,
                                 capture_output=True, timeout=30, creationflags=subprocess.CREATE_NO_WINDOW)
        assert blocked.returncode != 0, 'Capacity report bypassed the active application lock'
        blocked = subprocess.run(command + ['--report-office-storage', '--confirm-all-workspaces'], env=env, cwd=root,
                                 capture_output=True, timeout=30, creationflags=subprocess.CREATE_NO_WINDOW)
        assert blocked.returncode != 0, 'Office report bypassed the active application lock'
        blocked = subprocess.run(command + ['--report-download-storage', '--confirm-all-workspaces'], env=env, cwd=root,
                                 capture_output=True, timeout=30, creationflags=subprocess.CREATE_NO_WINDOW)
        assert blocked.returncode != 0, 'Download report bypassed the active application lock'
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
        question_partial = data / 'workspaces/default/questions/interrupted-assets'
        (question_partial / 'assets').mkdir(parents=True)
        (question_partial / 'assets/keep.png').write_bytes(b'retained incomplete question asset')
        question_empty = question_partial.with_name('interrupted-empty')
        question_empty.mkdir()
        questions = inspect(1)
        assert sorted((item['code'], item.get('relative_path')) for item in questions['issues']) == sorted(
            [(item['code'], item.get('relative_path')) for item in changed['issues']] +
            [('unreferenced_derived_candidate', path.relative_to(data).as_posix())
             for path in (question_partial, question_empty)])
        assert question_empty.is_dir()
        image_copy = next((data / 'workspaces/default/questions' / extracted['id'] / 'assets').glob('*.png'))
        with sqlite3.connect(data / 'study.db') as db:
            original_relative = db.execute('SELECT relative_path FROM resources WHERE id=?', (image_copy.stem,)).fetchone()[0]
        image_original = data / original_relative
        raw = image_copy.read_bytes()
        assert image_original.read_bytes() == raw
        image_copy.write_bytes(raw[:-1] + bytes([raw[-1] ^ 1]))
        damaged_image = inspect(1)
        assert dict(code='hash_mismatch', severity='error',
                    relative_path=image_copy.relative_to(data).as_posix()) in damaged_image['issues']
        image_copy.rename(root / 'retained-corrupt-legacy-image.png')
        missing_image = inspect(1)
        assert dict(code='missing_file', severity='error',
                    relative_path=image_copy.relative_to(data).as_posix()) in missing_image['issues']
        assert image_original.read_bytes() == raw
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
        assert capacity(download=True)['file_count'] == 0
        # Local synthetic records only; this probe never initiates a download.
        download_id, second_download = '1' * 32, '2' * 32
        old_relative = f'workspaces/default/downloads/{download_id}/1.webm'
        current_relative = f'workspaces/default/downloads/{download_id}/2.webm'
        second_relative = f'workspaces/default/downloads/{second_download}/1.webm'
        download_files = {old_relative: b'media authority retained from lower attempt',
                          current_relative: b'current failed attempt', second_relative: b'completed duplicate-like bytes'}
        for relative, content in download_files.items():
            path = data / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        with sqlite3.connect(data / 'study.db') as db:
            for identifier, attempt, relative, status in [(download_id, 2, current_relative, 'failed'),
                                                         (second_download, 1, second_relative, 'ready')]:
                db.execute('INSERT INTO media_download_jobs '
                           '(id,workspace_id,request_id,source_url,name,status,cancel_requested,attempt,relative_path, '
                           'progress,result,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',
                           (identifier, 'default', 'download-storage-probe-' + identifier,
                            'https://media.example.com/no-request?signature=private-probe', 'private-download.webm',
                            status, False, attempt, relative, '{}', '{}', '2026-11-10T00:00:00+08:00'))
            for identifier, status, checksum in [('3' * 32, 'ready', hashlib.sha256(download_files[old_relative]).hexdigest()),
                                                  ('4' * 32, 'failed', '0' * 64)]:
                db.execute('INSERT INTO media_entries (id,workspace_id,title,relative_path,mime,size,sha256,status,playback) '
                           'VALUES (?,?,?,?,?,?,?,?,?)', (identifier, 'default', 'private media title', old_relative,
                           'video/webm', len(download_files[old_relative]), checksum, status, '{}'))
        downloads = capacity(download=True)
        assert downloads['scope'] == 'download_attempt_files' and not downloads['attempt_history_checked']
        assert downloads['media_reference_rows'] == 2 and downloads['media_referenced_paths'] == 1
        assert downloads['categories']['media_referenced_file'] == dict(file_count=1, logical_bytes=len(download_files[old_relative]))
        assert downloads['categories']['current_attempt_file']['file_count'] == 2
        authority = next(i for i in downloads['largest_files'] if i['relative_path'] == old_relative)
        assert authority['media_reference_count'] == 2 and authority['attempt_relation'] == 'lower_numbered'
        assert authority['current_job_status'] == 'failed'
        assert 'private-probe' not in json.dumps(downloads) and 'example.com' not in json.dumps(downloads)
        (data / current_relative).rename(root / 'retained-current-attempt.bin')
        assert capacity(download=True)['missing_optional_download_files'] == 1
        (data / old_relative).rename(root / 'retained-media-authority.bin')
        missing_media = capacity(download=True, expected=1)
        assert any(i == dict(code='missing_required_reference', relative_path=old_relative) for i in missing_media['issues'])
        summary = dict(frozen=True, active_lock_refused=True, healthy_case_verified=True, orphan_detected=True,
                       extracted_question_orphans_detected=True, extracted_question_bytes_preserved=True,
                       legacy_image_damage_detected=True, legacy_image_missing_detected=True,
                       legacy_image_original_preserved=True,
                       external_edit_detected=True, business_bytes_preserved=True, repair_performed=False,
                       recovery_preview_readonly=True, recovery_save_conflict_guard=True, recovery_explicit_save=True,
                       missing_source_copy=True, copy_creation_idempotent=True, original_missing_not_repaired=True,
                       merge_preview_readonly=True, merge_stale_save_refused=True, merge_conflict_has_no_candidate=True,
                       capacity_report_metadata_readonly=True, capacity_unregistered_bytes_accounted=True,
                       capacity_deletion_authorized=False, office_inventory_metadata_readonly=True,
                       office_failed_profile_bytes_accounted=True, office_missing_ready_refused=True,
                       office_deletion_authorized=False, download_inventory_readonly=True,
                       download_media_priority=True, download_alias_bytes_once=True,
                       download_missing_ready_media_refused=True, download_deletion_authorized=False)
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
