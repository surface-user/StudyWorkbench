"""Independent R5 public HTTP regression; no application imports or database access."""
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
        req = urllib.request.Request(f'http://127.0.0.1:{port}' + path, data=body if isinstance(body, bytes) else json.dumps(body).encode() if body is not None else None, method=method, headers={'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json'})
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
        old = call(s + '/attempts', dict(question_id='demo-integral', response={'selected': ['a']}))
        ep = s + '/attempts/' + str(old['id'])
        record = call(ep + '/record')
        assert record['version_status'] == 'unknown' and record['knowledge_points'] is None
        before = call(s + '/attempts')
        stats = call(s + '/statistics')
        def note(scope, title):
            job = call(scope + '/imports?filename=' + title + '.txt', b'Generated review note')
            call(scope + '/imports/' + job['id'] + '/confirm', {})
            return call(scope + '/notes')[0]
        local = note(s, 'local')
        other_id = call('/api/workspaces', {'name': 'R5 isolated'})['id']
        other = '/api/workspaces/' + other_id
        foreign = note(other, 'foreign')
        body = dict(request_id='r5_independent_event_0001', kind='reviewed', note='Review without grading', note_id=local['id'], knowledge_points=['Alpha', 'Beta'])
        first = call(ep + '/events', body)
        assert call(ep + '/events', body) == first
        call(ep + '/events', dict(body, note='Changed'), expected=409)
        call(ep + '/events', dict(body, request_id='r5_foreign_event_0001', note_id=foreign['id']), expected=404)
        call(ep + '/notes/' + foreign['id'], expected=404)
        call(other + '/attempts/' + str(old['id']) + '/record', expected=404)
        call(other + '/attempts/' + str(old['id']) + '/events', body, expected=404)
        assert call(ep + '/notes/' + local['id'])['content'] == local['content']
        call(ep + '/events', dict(body, request_id='r5_empty_event_000001', knowledge_points=[]))
        latest = call(ep + '/events', dict(body, request_id='r5_null_event_0000001', kind='annotation', knowledge_points=None))
        current = call(ep + '/record?limit=1')
        assert current['events'] == [latest] and current['effective_knowledge_points'] == []
        assert current['reviewed_count'] == 2 and current['knowledge_points'] is None
        early = call(ep + '/record?before_id=' + str(latest['id']) + '&limit=1')
        assert early['effective_knowledge_points'] == [] and early['reviewed_count'] == 2
        for invalid in [['A', 'A'], [' '], ['x' * 501]]:
            call(ep + '/events', dict(body, knowledge_points=invalid), expected=422)
        call(ep + '/events', dict(body, command='delete'), expected=422)
        call(ep + '/events/' + str(first['id']), {}, 'DELETE', expected=404)
        assert call(s + '/attempts') == before and call(s + '/statistics') == stats
        proposal = call(s + '/questions/demo-integral/file-preview')
        node = call(s + '/questions/demo-integral/file', dict(expected_source_sha256=proposal['source_sha256'], expected_preview_sha256=proposal['preview_sha256'], confirm=True))['resource_item_id']
        np = s + '/nodes/' + node
        candidate = call(np + '/question-file')
        version = call(np + '/question-file/confirm', dict(expected_sha256=candidate['sha256'], expected_version_id=None, confirm=True))
        new = call(s + '/attempts', dict(question_id='demo-integral', question_version_id=version['id'], response={'selected': ['a']}))
        known = call(s + '/attempts/' + str(new['id']) + '/record')
        assert known['version_status'] == 'known' and known['knowledge_points'] == version['question']['knowledge_points']
        call(np, {'name': 'renamed.md', 'parent_id': None}, 'PATCH')
        assert call(s + '/attempts/' + str(new['id']) + '/record')['resource_item_id'] == node
        doc = call(np + '/document')
        marker = '\"selected\": [\n    \"a\"\n  ]'
        assert marker in doc['text']
        call(np + '/document', dict(expected_sha256=doc['sha256'], text=doc['text'].replace(marker, '\"selected\": [\n    \"b\"\n  ]')), 'PUT')
        changed = call(np + '/question-file')
        call(np + '/question-file/confirm', dict(expected_sha256=changed['sha256'], expected_version_id=version['id'], confirm=True))
        assert call(s + '/attempts/' + str(new['id']) + '/record')['question_version_id'] == version['id']
        assert next(x for x in call(s + '/attempts') if x['id'] == new['id'])['score'] == 1
        assert call(ep + '/record')['version_status'] == 'unknown'
        proc.stdin.close()
        assert proc.wait(timeout=15) == 0
        proc = subprocess.Popen([sys.executable, '-m', 'study_workbench', '--data-dir', str(root / 'data')], cwd=repo / 'backend', env={**os.environ, 'PYTHONUTF8': '1'}, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8')
        proc.stdin.write(json.dumps({'token': token}) + '\n')
        proc.stdin.flush()
        port = json.loads(proc.stdout.readline())['port']
        for _ in range(100):
            try:
                call('/api/health')
                break
            except urllib.error.URLError:
                time.sleep(.05)
        restored = call(ep + '/record?limit=1')
        assert restored['effective_knowledge_points'] == [] and restored['reviewed_count'] == 2
        assert restored['version_status'] == 'unknown'
        assert call(ep + '/events', body) == first
        assert call(ep + '/notes/' + local['id'])['content'] == local['content']
        print(json.dumps(dict(stage='R5', http_assertions=checks, old_score_unchanged=True, whole_stream_projection=True)))
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
