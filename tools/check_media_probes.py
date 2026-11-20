"""Real source/frozen probe and cancellation using exact prior owned synthetic fixtures, never downloads."""
import argparse
import hashlib
import http.client
import json
import os
import queue
import secrets
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

FIXTURES = {'av.mp4': (2177, '2411bd2e6c0ccee4aafa95e560f44ddd08aef4b15125094a9b2e7eb65e6fab25'),
            'audio.m4a': (911, '9bfd9f2c05af35aeb733ba0cd9d7de3eb62437390326607da0ce327a5e245352')}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--exe', type=Path)
    parser.add_argument('--runtime', type=Path, required=True)
    parser.add_argument('--fixtures', type=Path, required=True)
    parser.add_argument('--test-root', type=Path, required=True)
    args = parser.parse_args()
    original = {}
    for name, (size, checksum) in FIXTURES.items():
        data = (args.fixtures / name).read_bytes()
        assert len(data) == size and hashlib.sha256(data).hexdigest() == checksum
        original[name] = data
    root = args.test_root.resolve()
    root.mkdir()  # Refuse existing data, including prior failures.
    token = secrets.token_urlsafe(32)
    environment = {**os.environ, 'PYTHONUTF8': '1', 'PYTHONIOENCODING': 'utf-8',
                   'STUDY_FFMPEG_RUNTIME': str(args.runtime.resolve())}
    if args.exe:
        environment['PATH'] = str(Path(os.environ['SystemRoot']) / 'System32')
        environment.pop('PYTHONPATH', None)
        environment.pop('PYTHONHOME', None)
    command = [str(args.exe.resolve())] if args.exe else [sys.executable, '-m', 'study_workbench']
    process = subprocess.Popen(command + ['--data-dir', str(root / 'data')],
        cwd=root if args.exe else Path(__file__).resolve().parents[1] / 'backend', env=environment,
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8',
        creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    prefix = '/api/workspaces/default/media'
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    pool = ThreadPoolExecutor(max_workers=1)
    checks = 0
    try:
        process.stdin.write(json.dumps({'token': token}) + '\n')
        process.stdin.flush()
        hello = queue.Queue()
        threading.Thread(target=lambda: hello.put(process.stdout.readline()), daemon=True).start()
        port = json.loads(hello.get(timeout=30))['port']
        def request(path, body=None):
            nonlocal checks
            data = json.dumps(body).encode() if isinstance(body, dict) else body
            req = urllib.request.Request(f'http://127.0.0.1:{port}' + path, data=data,
                headers={'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json'})
            try:
                response = opener.open(req, timeout=30)
            except urllib.error.HTTPError as error:
                response = error
            with response:
                status, value = response.status, json.load(response)
            checks += 1
            return status, value
        def upload(name):
            status, item = request(prefix + '/import?filename=' + name, original[name])
            assert status == 200
            return item, prefix + '/' + item['id'] + '/native-probe', {'expected_sha256': item['sha256']}
        def operations():
            parent = root / 'data/workspaces/default/media-probes'
            return set(parent.iterdir()) if parent.exists() else set()
        def started(previous, suffix, size):
            until = time.monotonic() + 15
            while time.monotonic() < until:
                fresh = operations() - previous
                assert len(fresh) <= 1
                if fresh:
                    operation = next(iter(fresh))
                    source = operation / ('source' + suffix)
                    if source.exists() and source.stat().st_size == size:
                        return operation
                time.sleep(.002)
            raise AssertionError('Probe did not freeze its selected source')
        for name in FIXTURES:
            item, route, body = upload(name)
            status, value = request(route, body)
            assert status == 200 and value['native_probe_performed'] is True
            assert value['sha256'] == item['sha256'] and value['size'] == item['size'] and value['duration_ms'] == 200
            assert [s['codec'] for s in value['streams']] == (['h264', 'aac'] if name == 'av.mp4' else ['aac'])
            assert (root / 'data/workspaces/default/media' / (item['id'] + Path(name).suffix)).read_bytes() == original[name]
        # A real native result for a frozen old version must not become a result for a changed original.
        item, route, body = upload('av.mp4')
        previous = operations()
        future = pool.submit(request, route, body)
        operation = started(previous, '.mp4', item['size'])
        changed = root / 'data/workspaces/default/media' / (item['id'] + '.mp4')
        changed.write_bytes(b'x' * item['size'])
        assert future.result(timeout=15)[0] == 409
        receipt = json.loads((operation / 'result.json').read_text('utf-8'))
        assert receipt['native_probe_performed'] is True and changed.read_bytes() == b'x' * item['size']
        # Closing this HTTP connection is the synchronous request's explicit cancellation.
        item, route, body = upload('audio.m4a')
        previous = operations()
        connection = http.client.HTTPConnection('127.0.0.1', port, timeout=15)
        connection.request('POST', route, json.dumps(body), {'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json'})
        operation = started(previous, '.m4a', item['size'])
        connection.close()
        until = time.monotonic() + 5
        cancelled_result = None
        while time.monotonic() < until:
            try:
                cancelled_result = json.loads((operation / 'result.json').read_text('utf-8'))
                break
            except (FileNotFoundError, json.JSONDecodeError):
                time.sleep(.01)
        assert cancelled_result == {'error_code': 'cancelled'}
        # A subsequent real probe proves the cancelled request released its shared view slot.
        assert request(route, body)[0] == 200
        item, route, body = upload('av.mp4')
        previous = operations()
        future = pool.submit(request, route, body)
        operation = started(previous, '.mp4', item['size'])
        process.stdin.close()
        process.wait(timeout=10)
        assert process.returncode == 0 and future.result(timeout=5)[0] == 409
        assert (root / 'data/workspaces/default/media' / (item['id'] + '.mp4')).read_bytes() == original['av.mp4']
        assert not process.stderr.read().strip(), 'Backend emitted unexpected stderr'
        for name, data in original.items():
            assert (args.fixtures / name).read_bytes() == data
        print(json.dumps({'frozen': bool(args.exe), 'checks': checks, 'real_mp4_m4a': True,
                          'stale_native_result_rejected': True, 'http_disconnect_cancelled': True,
                          'parent_eof_cancelled': True, 'source_fixtures_retained': True}))
    finally:
        if not process.stdin.closed:
            process.stdin.close()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
        pool.shutdown(wait=True)


if __name__ == '__main__':
    main()
