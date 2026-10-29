"""R2 black-box regression: real server, public HTTP only, fresh generated profile."""
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
        import copy
        legacy = {'version': 1, 'tabs': [{'id': 'old', 'kind': 'question', 'draft': '旧草稿\n中文'}], 'closed_tabs': [{'id': 'closed', 'kind': 'web', 'url': 'https://example.org/history'}], 'active_tab_id': 'old'}
        saved = call(prefix + '/layout', legacy, 'PUT')
        assert saved['tabs'][0]['draft'] == legacy['tabs'][0]['draft']
        unknown = {'id': 'unknown', 'kind': 'future', 'state': {'version': 9, 'draft': ['保留', {'x': 1}]}}
        a = call(prefix + '/nodes', {'kind': 'link', 'name': '同名', 'url': 'https://example.com/a'})
        folder = call(prefix + '/nodes', {'kind': 'folder', 'name': '文件夹'})
        b = call(prefix + '/nodes', {'kind': 'link', 'name': '同名', 'parent_id': folder['resource_item_id'], 'url': 'https://example.com/b'})
        def tab(node, identifier):
            return {'id': identifier, 'kind': 'resource', 'resource_item_id': node['resource_item_id'], 'view_kind': 'web', 'resource_name': node['name'], 'url': node['url']}
        layout = dict(legacy, version=2, tabs=legacy['tabs'] + [tab(a, 'a'), tab(b, 'b'), unknown])
        saved = call(prefix + '/layout', layout, 'PUT')
        assert saved['tabs'][-1] == unknown
        assert saved['tabs'][1]['resource_item_id'] != saved['tabs'][2]['resource_item_id']
        for field, value in [('view_kind', 'media'), ('resource_item_id', 'invalid'), ('url', 'http://127.0.0.1'), ('command', 'run')]:
            bad = copy.deepcopy(layout)
            bad['tabs'][1][field] = value
            call(prefix + '/layout', bad, 'PUT', 422)
            assert call(prefix + '/layout') == saved
        bad = copy.deepcopy(layout)
        bad['tabs'].append(dict(bad['tabs'][1], id='duplicate'))
        call(prefix + '/layout', bad, 'PUT', 422)
        foreign = call('/api/workspaces', {'name': '隔离'})['id']
        call(f'/api/workspaces/{foreign}/layout', layout, 'PUT', 422)
        missing = copy.deepcopy(layout)
        missing['tabs'][1]['resource_item_id'] = 'f' * 32
        call(prefix + '/layout', missing, 'PUT')
        call(prefix + '/nodes/' + 'f' * 32, expected=404)
        call(prefix + '/layout', layout, 'PUT')
        call(prefix + '/nodes/' + a['resource_item_id'], {'name': '移动改名', 'parent_id': folder['resource_item_id']}, 'PATCH')
        assert call(prefix + '/layout')['tabs'][1]['resource_item_id'] == a['resource_item_id']
        closed = copy.deepcopy(layout)
        closed['closed_tabs'].append(closed['tabs'].pop(1))
        call(prefix + '/layout', closed, 'PUT')
        assert call(prefix + '/layout')['closed_tabs'][-1]['id'] == 'a'
        print(json.dumps({'stage': 'R2', 'public_http_checks': checks, 'cases': 'v1 drafts, v2 stable identity, same names, unknown payload, invalid saves atomic, scope, missing, move, closed history'}))
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
