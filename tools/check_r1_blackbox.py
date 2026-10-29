"""R1 black-box regression: real server, public HTTP only, fresh generated profile."""
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
    proc = subprocess.Popen([sys.executable, '-m', 'study_workbench', '--data-dir', str(root / 'data')], cwd=Path(__file__).resolve().parents[1] / 'backend', env={**os.environ, 'PYTHONUTF8': '1'}, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8')
    token = secrets.token_urlsafe(32)
    proc.stdin.write(json.dumps({'token': token}) + '\n')
    proc.stdin.flush()
    port = json.loads(proc.stdout.readline())['port']
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    checks = 0

    def call(path, body=None, method=None, expected=200, headers=None):
        nonlocal checks
        req = urllib.request.Request(f'http://127.0.0.1:{port}' + path, data=json.dumps(body).encode() if body is not None else None, method=method, headers=headers if headers is not None else {'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json'})
        try:
            with opener.open(req, timeout=30) as response:
                code, value = response.status, json.load(response)
        except urllib.error.HTTPError as error:
            code, value = error.code, json.load(error)
        assert code == expected, (path, body, code, value, expected)
        checks += 1
        return value

    prefix = '/api/workspaces/default'
    try:
        for _ in range(100):
            try:
                call('/api/health')
                break
            except urllib.error.URLError:
                time.sleep(.05)
        call(prefix + '/nodes', expected=401, headers={})
        call(prefix + '/nodes', expected=403, headers={'Authorization': 'Bearer ' + token, 'Origin': 'https://example.com'})
        def folder(name, parent=None, expected=200):
            return call(prefix + '/nodes', {'kind': 'folder', 'name': name, 'parent_id': parent}, expected=expected)
        first = folder('é')
        assert folder('e\u0301')['name'] != 'e\u0301'
        a = first['resource_item_id']
        child = folder('中文', a)['resource_item_id']
        call(prefix + '/nodes/' + a, {'name': '环', 'parent_id': child}, 'PATCH', 409)
        call(prefix + '/nodes/' + a, {'name': '自身', 'parent_id': a}, 'PATCH', 409)
        for name in ['', '.', '..', 'CON', 'nul.txt', 'COM1', 'LPT9', 'a/b', 'a\\b', 'x:', 'x.', 'x ', 'x\n', '\x00']:
            folder(name, expected=422)
        for url in ['file:///C:/test', 'http://example.com', 'https://localhost', 'https://127.0.0.1', 'https://[::1]', 'https://a:b@example.com']:
            call(prefix + '/nodes', {'kind': 'link', 'name': 'bad', 'url': url}, expected=422)
        link = call(prefix + '/nodes', {'kind': 'link', 'name': 'web', 'url': 'https://example.com/path'})
        folder('bad parent', link['resource_item_id'], 422)
        foreign = call('/api/workspaces', {'name': '隔离'})['id']
        call(f'/api/workspaces/{foreign}/nodes/' + a, expected=404)
        call(f'/api/workspaces/{foreign}/nodes', {'kind': 'folder', 'name': '跨空间', 'parent_id': a}, expected=404)
        for query in ['limit=0', 'limit=201', 'offset=-1']:
            call(prefix + '/nodes?' + query, expected=422)
        for i in range(12):
            folder('分页' + str(i))
        pages = [call(prefix + f'/nodes?limit=5&offset={offset}') for offset in (0, 5, 10, 15)]
        ids = [n['resource_item_id'] for page in pages for n in page]
        assert len(ids) == len(set(ids))
        source = root / '来源'
        source.mkdir()
        (source / 'empty').mkdir()
        (source / 'a.md').write_text('相同字节', encoding='utf-8')
        (source / 'b.md').write_bytes((source / 'a.md').read_bytes())
        (source / 'zero.bin').write_bytes(b'')
        before = {p.name: p.read_bytes() for p in source.iterdir() if p.is_file()}
        job = call(prefix + '/resource-add-jobs', {'source_path': str(source)})
        for _ in range(200):
            job = call(prefix + '/resource-add-jobs/' + job['id'])
            if job['status'] not in {'queued', 'running'}:
                break
            time.sleep(.02)
        assert job['status'] == 'completed', job
        assert len(job['results']) == 5, job
        copied_ids = [r['resource_item_id'] for r in job['results']]
        assert len(set(copied_ids)) == 5
        assert before == {p.name: p.read_bytes() for p in source.iterdir() if p.is_file()}
        for bad_source in [str(root / 'data'), str(root), 'relative.md', r'\\server\share\x', str(root / 'missing')]:
            call(prefix + '/resource-add-jobs', {'source_path': bad_source}, expected=422)
        print(json.dumps({'stage': 'R1', 'public_http_checks': checks, 'source_preserved': True, 'independent_cases': 'NFC, cycle/self-cycle, names, URL, auth/origin, scope, pagination, empty file/folder, duplicate identity, rejected paths'}))
    finally:
        proc.stdin.close()
        try:
            proc.wait(timeout=15)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
        assert proc.returncode == 0, proc.stderr.read()


if __name__ == '__main__':
    main()
