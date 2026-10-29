"""Independent R4 public HTTP regression; no application imports or database access."""
import json
import os
import secrets
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path


def main():
    root = Path(sys.argv[1]).resolve()
    root.mkdir()
    repo = Path(__file__).resolve().parents[1]
    proc = subprocess.Popen([sys.executable, '-m', 'study_workbench', '--data-dir', str(root / 'data')], cwd=repo / 'backend', env={**os.environ, 'PYTHONUTF8': '1'}, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8')
    token = secrets.token_urlsafe(32)
    proc.stdin.write(json.dumps({'token': token}) + '\n')
    proc.stdin.flush()
    port = json.loads(proc.stdout.readline())['port']
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    checks = 0

    def call(path, body=None, method=None, expected=200):
        nonlocal checks
        req = urllib.request.Request(f'http://127.0.0.1:{port}' + path, data=json.dumps(body).encode() if body is not None else None, method=method, headers={'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json'})
        try:
            with opener.open(req, timeout=30) as response:
                code, value = response.status, json.load(response)
        except urllib.error.HTTPError as error:
            code, value = error.code, json.load(error)
        assert code == expected, (path, code, value, expected)
        checks += 1
        return value

    s = '/api/workspaces/default'
    try:
        for _ in range(100):
            try:
                call('/api/health')
                break
            except urllib.error.URLError:
                time.sleep(.05)
        original = call(s + '/questions/demo-integral')
        proposal = call(s + '/questions/demo-integral/file-preview')
        conversion = dict(expected_source_sha256=proposal['source_sha256'], expected_preview_sha256=proposal['preview_sha256'], confirm=True)
        call(s + '/questions/demo-integral/file', dict(conversion, confirm=False), expected=422)
        assert call(s + '/questions/demo-integral') == original
        node = call(s + '/questions/demo-integral/file', conversion)['resource_item_id']
        p = s + '/nodes/' + node
        inspected = call(p + '/question-file')
        confirmation = dict(expected_sha256=inspected['sha256'], expected_version_id=None, confirm=True)
        call(p + '/question-file/confirm', dict(confirmation, confirm='true'), expected=422)
        call(p + '/question-file/confirm', dict(confirmation, unexpected=1), expected=422)
        call(p + '/question-file/confirm', dict(confirmation, expected_sha256='0' * 64), expected=409)
        first = call(p + '/question-file/confirm', confirmation)
        assert call(p + '/question-file/confirm', confirmation)['id'] == first['id']
        body = dict(question_id='demo-integral', question_version_id=first['id'], request_id='r4_blackbox_attempt_0001', response={'selected': ['a']})
        saved = call(s + '/attempts', body)
        assert saved['score'] == 1
        document = call(p + '/document')
        marker = '"selected": [\n    "a"\n  ]'
        assert document['text'].count(marker) == 1
        changed = document['text'].replace(marker, '"selected": [\n    "b"\n  ]')
        call(p + '/document', dict(expected_sha256=document['sha256'], text=changed), 'PUT')
        assert call(s + '/questions/demo-integral')['answer']['selected'] == ['a']
        call(p + '/question-file/confirm', dict(confirmation, expected_version_id=first['id']), expected=409)
        current = call(p + '/question-file')
        second = call(p + '/question-file/confirm', dict(expected_sha256=current['sha256'], expected_version_id=first['id'], confirm=True))
        assert second['revision'] == first['revision'] + 1
        assert call(s + '/attempts', body) == saved
        call(s + '/attempts', dict(body, request_id='r4_blackbox_stale_0002'), expected=409)
        call(s + '/attempts', dict(body, response={'selected': ['b']}), expected=409)
        assert call(s + '/question-versions/' + first['id'])['question']['answer']['selected'] == ['a']
        assert call(s + '/questions/demo-integral')['answer']['selected'] == ['b']
        other = call('/api/workspaces', {'name': 'R4隔离'})['id']
        call('/api/workspaces/' + other + '/question-versions/' + first['id'], expected=404)
        # Hand-edit a documented sample as user-authored files, never import the parser.
        source = root / 'source'
        source.mkdir()
        raw = (repo / 'contracts/samples/question-files-v1/待批改.md').read_text(encoding='utf-8')
        good = raw.replace('sample-unanswered-file', 'blackbox-unanswered')
        (source / 'pending.md').write_text(good, encoding='utf-8')
        (source / 'future.md').write_text(raw.replace('"format_version": 1', '"format_version": 99'), encoding='utf-8')
        job = call(s + '/resource-add-jobs', {'source_path': str(source)})
        for _ in range(200):
            job = call(s + '/resource-add-jobs/' + job['id'])
            if job['status'] not in {'queued', 'running'}:
                break
            time.sleep(.05)
        assert job['status'] == 'completed'
        nodes = {r['name']: r['resource_item_id'] for r in job['results'] if r.get('resource_item_id')}
        call(s + '/nodes/' + nodes['future.md'] + '/question-file', expected=422)
        pending_path = s + '/nodes/' + nodes['pending.md']
        candidate = call(pending_path + '/question-file')
        version = call(pending_path + '/question-file/confirm', dict(expected_sha256=candidate['sha256'], expected_version_id=None, confirm=True))
        pending = call(s + '/attempts', dict(question_id='blackbox-unanswered', question_version_id=version['id'], response={'text': '自编回答'}))
        assert pending['status'] == 'pending_review' and pending['score'] is None
        assert (source / 'pending.md').read_text(encoding='utf-8') == good
        assert next(a for a in call(s + '/attempt-history') if a['id'] == saved['id'])['score'] == 1
        print(json.dumps(dict(stage='R4', http_assertions=checks, immutable_old_score=True, null_answer_pending=True)))
    finally:
        proc.stdin.close()
        try:
            assert proc.wait(timeout=15) == 0
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.wait(10)


if __name__ == '__main__':
    main()
