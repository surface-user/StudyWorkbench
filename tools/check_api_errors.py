"""Check additive API errors through real source/frozen HTTP with fresh generated data."""
import argparse
import json
import os
import queue
import re
import secrets
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--exe', type=Path)
    parser.add_argument('--test-root', type=Path, required=True)
    args = parser.parse_args()
    root = args.test_root.resolve()
    root.mkdir()  # Refuse reuse; never modify an existing profile or previous failure.
    media = root / 'fixture.mp4'
    media.write_bytes(bytes(range(256)) * 8)
    command = [str(args.exe.resolve())] if args.exe else [sys.executable, '-m', 'study_workbench']
    environment = {**os.environ, 'PYTHONUTF8': '1', 'PYTHONIOENCODING': 'utf-8'}
    if args.exe:
        environment['PATH'] = str(Path(os.environ['SystemRoot']) / 'System32')
        environment.pop('PYTHONPATH', None)
        environment.pop('PYTHONHOME', None)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    identifiers = set()
    private = 'private-fixture-https://example.invalid/?secret=not-echoed'
    checks = 0
    node = None
    for restart in (False, True):
        token = secrets.token_urlsafe(32)
        process = subprocess.Popen(command + ['--data-dir', str(root / 'data'), '--media', str(media)],
            cwd=root if args.exe else Path(__file__).resolve().parents[1] / 'backend', env=environment,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8',
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        try:
            process.stdin.write(json.dumps({'token': token}) + '\n')
            process.stdin.flush()
            hello = queue.Queue()
            threading.Thread(target=lambda: hello.put(process.stdout.readline()), daemon=True).start()
            port = json.loads(hello.get(timeout=30))['port']

            def request(path, body=None, *, expected=200, headers=None, method=None, raw=False):
                nonlocal checks
                auth = {'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json'}
                if headers is not None:
                    auth.update(headers)
                data = json.dumps(body).encode() if isinstance(body, dict) else body
                req = urllib.request.Request(f'http://127.0.0.1:{port}{path}', data=data, method=method, headers=auth)
                try:
                    response = opener.open(req, timeout=30)
                except urllib.error.HTTPError as error:
                    response = error
                with response:
                    payload = response.read()
                    assert response.status == expected, f'Unexpected HTTP status {response.status}; expected {expected}'
                    checks += 1
                    return payload if raw else json.loads(payload), response.headers

            for _ in range(50):
                try:
                    value, _ = request('/api/health')
                    assert value['status'] == 'ok' and 'error' not in value
                    break
                except urllib.error.URLError:
                    time.sleep(.1)
            else:
                raise AssertionError('Backend did not become ready')

            def error(path, status, code, body=None, **options):
                value, headers = request(path, body, expected=status, **options)
                identifier = value['error']['request_id']
                assert re.fullmatch('[0-9a-f]{32}', identifier) and identifier not in identifiers
                identifiers.add(identifier)
                assert headers['X-Request-ID'] == identifier
                assert value['error']['code'] == code
                rendered = json.dumps(value)
                assert private not in rendered and token not in rendered
                return value

            error('/api/health', 401, 'unauthorized', headers={'Authorization': '', 'X-Request-ID': private})
            error('/api/health', 403, 'forbidden', headers={'Origin': private})
            error('/api/health', 400, 'bad_request', headers={'Host': 'evil.example'})
            error('/api/health', 405, 'method_not_allowed', method='POST')
            error('/api/missing', 404, 'not_found')
            validation = error('/api/workspaces', 422, 'validation_failed', {'name': 5, private: private})
            assert isinstance(validation['detail'], list) and validation['detail']
            error('/api/workspaces', 413, 'payload_too_large', (b'x' * 4096 for _ in range(17)))
            prefix = '/api/workspaces/default'
            body = {'name': 'kept.md', 'request_id': 'api-error-fixture-note'}
            note, _ = request(prefix + '/markdown-notes', body)
            assert node is None or note['resource_item_id'] == node
            node = note['resource_item_id']
            again, _ = request(prefix + '/markdown-notes', body)
            assert again == note
            error(prefix + '/markdown-notes', 409, 'conflict', {**body, 'name': 'changed.md'})
            error('/api/workspaces/missing/nodes/' + node, 404, 'not_found')
            document, _ = request(prefix + '/nodes/' + node + '/document')
            assert 'kept' in document['text']
            player, _ = request('/api/player', raw=True)
            capability = player.decode().split('?cap=', 1)[1].split("'", 1)[0]
            chunk, headers = request('/media/demo?cap=' + capability, expected=206,
                headers={'Range': 'bytes=10-29'}, raw=True)
            assert chunk == media.read_bytes()[10:30] and headers['Content-Range'] == 'bytes 10-29/2048'
            assert 'X-Request-ID' not in headers
            _, headers = request('/media/demo?cap=' + capability, expected=416,
                headers={'Range': 'bytes=9999-'}, raw=True)
            assert 'X-Request-ID' not in headers
            value, headers = request('/media/demo', expected=403)
            assert value == {'detail': 'Invalid media capability'} and 'X-Request-ID' not in headers
        finally:
            process.stdin.close()
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
                raise AssertionError('Backend did not stop after EOF') from None
            assert process.returncode == 0, 'Backend exited unexpectedly'
            assert not process.stderr.read().strip(), 'Backend emitted unexpected stderr'
    print(json.dumps(dict(checks=checks, unique_error_ids=len(identifiers), restarted=True,
                         receipts_preserved=True, media_range_preserved=True, frozen=bool(args.exe))))


if __name__ == '__main__':
    main()
