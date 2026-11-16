"""Real pipe/loopback R4 checks with a new profile and self-authored fixtures only."""
import argparse
import base64
import io
import json
import os
import secrets
import sqlite3
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from zipfile import ZipFile


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--exe', type=Path)
    parser.add_argument('--test-root', type=Path, required=True)
    args = parser.parse_args()
    repository = Path(__file__).resolve().parents[1]
    root = args.test_root.resolve()
    root.mkdir()
    command = [str(args.exe.resolve())] if args.exe else [sys.executable, '-m', 'study_workbench']
    environment = dict(os.environ, PYTHONUTF8='1', PYTHONIOENCODING='utf-8')
    if args.exe:
        environment['PATH'] = str(Path(os.environ['SystemRoot']) / 'System32')
        environment.pop('PYTHONPATH', None)
        environment.pop('PYTHONHOME', None)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    process = None

    def launch():
        nonlocal process
        token = secrets.token_urlsafe(32)
        process = subprocess.Popen(command + ['--data-dir', str(root / 'data')],
                                   cwd=root if args.exe else repository / 'backend', env=environment,
                                   stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   text=True, encoding='utf-8', creationflags=subprocess.CREATE_NO_WINDOW)
        process.stdin.write(json.dumps({'token': token}) + '\n')
        process.stdin.flush()
        hello = process.stdout.readline()
        assert hello, process.stderr.read()
        port = json.loads(hello)['port']
        def request(path, body=None, method=None, *, binary=False):
            req = urllib.request.Request(f'http://127.0.0.1:{port}{path}', method=method,
                data=body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False).encode() if body is not None else None,
                headers={'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'})
            with opener.open(req, timeout=60) as response:
                return response.read() if binary else json.load(response)
        return request

    def stop():
        process.stdin.close()
        assert process.wait(15) == 0
        assert not process.stderr.read().strip(), 'Unexpected backend stderr'

    scope = '/api/workspaces/default'
    def inspect(node):
        return request(scope + '/nodes/' + node + '/question-file')
    def confirm(node, value):
        return request(scope + '/nodes/' + node + '/question-file/confirm',
            {'expected_sha256': value['sha256'], 'expected_version_id': value['confirmed_version_id'], 'confirm': True})

    try:
        request = launch()
        original = request(scope + '/questions/demo-integral')
        old = request(scope + '/attempts', {'question_id': 'demo-integral', 'response': {'selected': ['a']}})
        proposal = request(scope + '/questions/demo-integral/file-preview')
        assert request(scope + '/questions/demo-integral') == original
        node = request(scope + '/questions/demo-integral/file', {
            'expected_source_sha256': proposal['source_sha256'], 'expected_preview_sha256': proposal['preview_sha256'], 'confirm': True})
        node_id = node['resource_item_id']
        candidate = inspect(node_id)
        assert candidate['status'] == 'unconfirmed'
        first = confirm(node_id, candidate)
        assert confirm(node_id, candidate)['id'] == first['id']
        body = dict(question_id='demo-integral', question_version_id=first['id'],
                    question_revision=first['revision'], request_id='r4_pipe_request_0001', response={'selected': ['a']})
        saved = request(scope + '/attempts', body)
        assert saved['score'] == 1
        document = request(scope + '/nodes/' + node_id + '/document')
        before = '"selected": [\n    "a"\n  ]'
        assert document['text'].count(before) == 1
        changed = document['text'].replace(before, '"selected": [\n    "b"\n  ]')
        request(scope + '/nodes/' + node_id + '/document',
                {'expected_sha256': document['sha256'], 'text': changed}, 'PUT')
        assert request(scope + '/questions/demo-integral')['answer']['selected'] == ['a']
        second = confirm(node_id, inspect(node_id))
        assert second['revision'] == first['revision'] + 1
        assert request(scope + '/attempts', body)['id'] == saved['id']
        try:
            request(scope + '/attempts', dict(body, request_id='stale_r4_request_0002'))
            raise AssertionError('Stale version accepted')
        except urllib.error.HTTPError as error:
            assert error.code == 409
        request(scope + '/nodes/' + node_id, {'name': '改名后的题目.md', 'parent_id': None}, 'PATCH')
        assert inspect(node_id)['confirmed_version_id'] == second['id']
        added = request(scope + '/resource-add-jobs', {'source_path': str(repository / 'contracts/samples/question-files-v1')})
        for _ in range(300):
            added = request(scope + '/resource-add-jobs/' + added['id'])
            if added['status'] not in {'queued', 'running'}:
                break
            time.sleep(.05)
        assert added['status'] == 'completed', added
        nodes = {r['name']: r['resource_item_id'] for r in added['results'] if r.get('resource_item_id')}
        image_version = confirm(nodes['有答案.md'], inspect(nodes['有答案.md']))
        image_id = image_version['question']['stem'][-1]['attachment_id']
        png = request(scope + f"/question-versions/{image_version['id']}/assets/{image_id}")
        assert base64.b64decode(png['image_base64']) == (repository / 'contracts/samples/question-files-v1/assets/figure-sample.png').read_bytes()
        pending_version = confirm(nodes['待批改.md'], inspect(nodes['待批改.md']))
        pending = request(scope + '/attempts', {'question_id': pending_version['question_id'],
            'question_version_id': pending_version['id'], 'response': {'text': '无标准答案的自编过程'}})
        assert pending['status'] == 'pending_review' and pending['score'] is None
        draft = json.dumps(dict(question_id=pending_version['question_id'], version_id=pending_version['id'],
                                text='跨重启作答草稿', selected=[], blanks={}, request_id=None), ensure_ascii=False)
        layout = request(scope + '/layout', {'version': 2, 'tabs': [{
            'id': 'question-file', 'kind': 'resource', 'resource_item_id': nodes['待批改.md'],
            'view_kind': 'document', 'document_state': {'version': 1, 'mode': 'question'}, 'question_draft': draft,
        }], 'closed_tabs': [], 'active_tab_id': 'question-file'}, 'PUT')
        with ZipFile(io.BytesIO(request(scope + '/export', binary=True))) as archive:
            manifest = json.loads(archive.read('manifest.json'))
            assert manifest['schema_version'] == 2 and len(manifest['question_files']) == 3
            assert 'unknown_field_preserved' in archive.read(f"question-files/{nodes['有答案.md']}/question.md").decode()
        job = request(scope + '/imports?filename=review-note.txt', '自编关联笔记'.encode())
        request(scope + '/imports/' + job['id'] + '/confirm', {})
        note = request(scope + '/notes')[0]
        record_path = scope + f"/attempts/{saved['id']}"
        event_body = dict(request_id='r5_loopback_event_0001', kind='reviewed', note='真实进程关联/修订',
                          note_id=note['id'], knowledge_points=['新标签'])
        event = request(record_path + '/events', event_body)
        assert request(record_path + '/events', event_body) == event
        assert request(record_path + '/notes/' + note['id'])['content'] == note['content']
        record = request(record_path + '/record?limit=1')
        assert record['effective_knowledge_points'] == ['新标签'] and record['reviewed_count'] == 1
        assert record['question_version_id'] == first['id']
        stop()
        request = launch()
        assert request(record_path + '/record')['effective_knowledge_points'] == ['新标签']
        assert request(record_path + '/events', event_body) == event
        assert request(scope + '/layout') == layout
        assert request(scope + '/attempts', body)['id'] == saved['id']
        assert request(scope + '/question-versions/' + first['id'])['question']['answer']['selected'] == ['a']
        history = request(scope + '/attempt-history')
        assert len(history) == 3
        assert next(row for row in history if row['id'] == old['id'])['question_version_id'] is None
        assert next(row for row in history if row['id'] == saved['id'])['question_version_id'] == first['id']
        stop()
        with sqlite3.connect(root / 'data/study.db') as db:
            assert db.execute('SELECT version_num FROM alembic_version').fetchone() == ('0012',)
            assert db.execute('PRAGMA integrity_check').fetchone() == ('ok',)
            assert db.execute('PRAGMA foreign_key_check').fetchall() == []
        print(json.dumps(dict(frozen=bool(args.exe), legacy_source_retained=True, immutable_versions=4,
            attempts=3, old_version_unknown=True, old_scores_retained=True, stale_refused=True,
            idempotent_retry_after_publish_restart=True, null_answer_pending=True,
            portable_export=True, snapshot_image=True, draft_restart=True, learning_events_restart=True,
            linked_note=True, corrected_labels=True, revision='0012')))
    finally:
        if process and process.poll() is None:
            process.kill()
            process.wait(10)


if __name__ == '__main__':
    main()
