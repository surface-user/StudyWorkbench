"""Opt-in public download evidence; fixed fixtures, real queue/TLS, fresh test data only."""
import argparse
import hashlib
import json
import os
import queue
import secrets
import sqlite3
import subprocess
import sys
import threading
import time
import urllib.request
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))

from study_workbench import media_download_http as transport  # noqa: E402

FLOWER = ('https://raw.githubusercontent.com/mdn/interactive-examples/'
          '9991b045e1561681d3ffc66215b92f68531ec97b/live-examples/media/cc0-videos/flower.webm')
GREEN = 'https://wpt.live/media/2x2-green.mp4'
RELATIVE = 'https://wpt.live/common/redirect.py?location=/media/2x2-green.mp4'
CROSS_HOST = 'https://wpt.live/common/redirect.py?location=' + quote(FLOWER, safe='')
FIXTURES = {
    FLOWER: (554058, '5b8edf7d8384c057dfb13627073288cebfb54d74'),
    GREEN: (3503, '157361c2ddc97fc1179006ab1dfa9639fe14950f'),
}
BODY_BUDGET = 5 * 1024 * 1024
PREFIX = '/api/workspaces/default/media-downloads'


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def verify_fixture(data, url):
    size, blob = FIXTURES[url]
    require(len(data) == size, 'Public fixture length changed')
    require(hashlib.sha1(b'blob ' + str(size).encode() + b'\0' + data).hexdigest() == blob,
            'Public fixture no longer matches its pinned Git object')
    return hashlib.sha256(data).hexdigest()


def install_transport(test_root):
    """Observe the original pinned TLS connection; impose a smaller test body budget."""
    original = transport.PinnedHTTPS
    budget_file = test_root / 'body-bytes.json'
    log = test_root / 'network.jsonl'

    class Connection(original):
        def request(self, method, url, body=None, headers=None, **kwargs):
            self.observed = {'host': self.host, 'address': self.address, 'method': method,
                             'range': (headers or {}).get('Range'), 'if_range': (headers or {}).get('If-Range')}
            return super().request(method, url, body=body, headers=headers or {}, **kwargs)

        def getresponse(self):
            response = super().getresponse()
            fields = response.getheaders()
            selected = {k.lower(): v for k, v in fields
                        if k.lower() in {'etag', 'content-length', 'content-range', 'location'}}
            require(sum(len(k) + len(v) for k, v in fields) <= 32768, 'Public headers exceed budget')
            length = selected.get('content-length')
            if length is not None:
                require(length.isdigit() and int(length) <= FIXTURES[FLOWER][0], 'Fixture response too large')
            with log.open('a', encoding='utf-8') as out:
                out.write(json.dumps({**self.observed, 'status': response.status, **selected}) + '\n')
            read = response.read

            def bounded_read(amount=None):
                used = json.loads(budget_file.read_text(encoding='utf-8'))
                require(used < BODY_BUDGET, 'Public response body budget exhausted')
                data = read(min(amount if amount is not None else transport.CHUNK, BODY_BUDGET - used))
                budget_file.write_text(json.dumps(used + len(data)), encoding='utf-8')
                return data

            response.read = bounded_read
            return response

    transport.PinnedHTTPS = Connection


def instrument_worker(test_root, hold):
    from study_workbench import media_download_worker
    original = media_download_worker.transfer

    def transfer(url, path, suffix, **options):
        expected = FIXTURES[GREEN if url == RELATIVE else FLOWER][0]
        require(url in {FLOWER, RELATIVE, CROSS_HOST}, 'Only the pinned public fixtures are allowed')
        progress, checkpoint = options['progress'], options['checkpoint']

        def observed(value):
            require(value['total'] == expected and value['received'] <= expected, 'Public fixture size changed')
            stop = hold and not options['offset'] and value['received'] == transport.CHUNK
            if stop:
                # The production worker rate-limits progress; make this real first block observable.
                time.sleep(.21)
            progress(value)
            if stop:
                deadline = time.monotonic() + 30
                while time.monotonic() < deadline:
                    checkpoint()
                    time.sleep(.02)
                raise RuntimeError('Test did not request pause at the first real block')

        return original(url, path, suffix, **{**options, 'progress': observed})

    install_transport(test_root)
    media_download_worker.transfer = transfer
    media_download_worker.worker()


def instrument_backend(test_root, hold):
    from study_workbench import __main__ as backend
    from study_workbench import media_downloads
    original = media_downloads.subprocess.Popen

    def spawn(command, *args, **kwargs):
        if command == [sys.executable, '-m', 'study_workbench', '--download-media']:
            command = [sys.executable, str(Path(__file__).resolve()), '--worker', '--test-root', str(test_root),
                       '--allow-public-fixtures']
            if hold:
                command += ['--hold-first-block']
        return original(command, *args, **kwargs)

    media_downloads.subprocess.Popen = spawn
    sys.argv = [sys.argv[0], '--data-dir', str(test_root / 'data')]
    backend.main()


@contextmanager
def backend_process(test_root, hold=False, exe=None):
    command = [sys.executable, str(Path(__file__).resolve()), '--serve', '--test-root', str(test_root),
               '--allow-public-fixtures']
    if hold:
        command += ['--hold-first-block']
    token = secrets.token_urlsafe(32)
    environment = {**os.environ, 'PYTHONUTF8': '1', 'PYTHONIOENCODING': 'utf-8'}
    if exe:
        require(not hold, 'Frozen backend cannot use source instrumentation')
        command = [str(exe.resolve()), '--data-dir', str(test_root / 'data')]
        environment['PATH'] = str(Path(os.environ['SystemRoot']) / 'System32')
        environment.pop('PYTHONPATH', None)
        environment.pop('PYTHONHOME', None)
    with (test_root / ('pause-stderr.txt' if hold else 'resume-stderr.txt')).open('w', encoding='utf-8') as log:
        process = subprocess.Popen(command, cwd=test_root if exe else ROOT, env=environment, stdin=subprocess.PIPE,
                                   stdout=subprocess.PIPE, stderr=log, text=True, encoding='utf-8',
                                   creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        try:
            process.stdin.write(json.dumps({'token': token}) + '\n')
            process.stdin.flush()
            hello = queue.Queue()
            threading.Thread(target=lambda: hello.put(process.stdout.readline()), daemon=True).start()
            port = json.loads(hello.get(timeout=30))['port']
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

            def request(path, body=None):
                request = urllib.request.Request(f'http://127.0.0.1:{port}{path}',
                    data=json.dumps(body).encode() if body is not None else None,
                    headers={'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json'})
                with opener.open(request, timeout=15) as response:
                    return json.load(response)

            for _ in range(100):
                try:
                    require(request('/api/health')['status'] == 'ok', 'Backend health failed')
                    break
                except urllib.error.URLError:
                    time.sleep(.1)
            else:
                raise RuntimeError('Backend did not become ready')
            yield request, process.pid
        finally:
            process.stdin.close()
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
                raise RuntimeError('Test backend failed to stop') from None
            process.stdout.close()
    require(process.returncode == 0, 'Test backend exited unsuccessfully')


def wait_job(request, identifier, state, *, received=None, expected_size=554058):
    deadline = time.monotonic() + 45
    while time.monotonic() < deadline:
        item = request(PREFIX + '/' + identifier)
        if (item['progress']['received'] > expected_size
                or item['progress']['total'] not in {None, expected_size}):
            if item['status'] != 'ready':
                request(PREFIX + '/' + identifier + '/pause', {})
            raise RuntimeError('Public fixture exceeded expected size; requested stop')
        if item['status'] in {'failed', 'interrupted'}:
            raise RuntimeError('Public download failed: ' + str(item['error']))
        if item['status'] in state and (received is None or item['progress']['received'] == received):
            return item
        time.sleep(.05)
    raise RuntimeError('Public download did not reach the required state')


def saved_job(test_root, identifier):
    with sqlite3.connect(test_root / 'data/study.db') as connection:
        row = connection.execute('SELECT relative_path, progress, attempt FROM media_download_jobs WHERE id=?',
                                 (identifier,)).fetchone()
    require(row is not None, 'Persistent download row missing')
    return test_root / 'data' / row[0], json.loads(row[1]), row[2]


def preflight(test_root):
    install_transport(test_root)
    canonical, host, target = transport.parse_url(FLOWER)
    connection = transport.PinnedHTTPS(host, transport.resolve(host))
    try:
        connection.request('HEAD', target, headers={'Accept-Encoding': 'identity'})
        response = connection.getresponse()
        etag = response.getheader('ETag')
        require(response.status == 200 and transport.strong_etag(etag), 'Fixture has no strong ETag')
        require(response.getheader('Content-Length') == str(FIXTURES[FLOWER][0]), 'Fixture length changed')
    finally:
        connection.close()
    connection = transport.PinnedHTTPS(host, transport.resolve(host))
    try:
        connection.request('GET', target, headers={'Range': 'bytes=0-0', 'If-Range': etag,
                                                  'Accept-Encoding': 'identity'})
        response = connection.getresponse()
        require(response.status == 206 and response.getheader('ETag') == etag, 'Fixture rejected positive Range')
        require(response.getheader('Content-Range') == 'bytes 0-0/554058'
                and response.getheader('Content-Length') == '1', 'Fixture returned an unexpected Range')
        require(len(response.read(2)) == 1, 'Range probe was not exactly one byte')
    finally:
        connection.close()
    require(canonical == FLOWER, 'Pinned URL changed during canonicalization')


def pause_fixture(test_root):
    with backend_process(test_root, hold=True) as (request, before_pid):
        item = request(PREFIX, {'url': FLOWER, 'name': 'flower.webm', 'rights_confirmed': True,
                               'request_id': 'public-range-fixed-flower-01'})
        identifier = item['id']
        wait_job(request, identifier, {'running'}, received=transport.CHUNK)
        request(PREFIX + '/' + identifier + '/pause', {})
        paused = wait_job(request, identifier, {'paused'})
        path, progress, attempt = saved_job(test_root, identifier)
        prefix = path.read_bytes()
        require(len(prefix) == progress['received'] == transport.CHUNK and attempt == 1, 'Invalid real prefix')
        require(hashlib.sha256(prefix).hexdigest() == progress['partial_sha256'] and paused['can_resume'],
                'Persisted prefix cannot be verified')
    return identifier, path, progress, prefix, attempt, before_pid


def frozen_resume(test_root, exe, checksum):
    test_root.mkdir()
    (test_root / 'body-bytes.json').write_text('0', encoding='utf-8')
    identifier, path, progress, prefix, attempt, before_pid = pause_fixture(test_root)
    with backend_process(test_root, exe=exe) as (request, after_pid):
        require(before_pid != after_pid, 'Frozen resume must use a new backend process')
        require(request(PREFIX + '/' + identifier)['status'] == 'paused' and path.read_bytes() == prefix,
                'Frozen restart changed paused state or bytes')
        request(PREFIX + '/' + identifier + '/retry', {'mode': 'resume'})
        ready = wait_job(request, identifier, {'ready'})
        same_path, final, same_attempt = saved_job(test_root, identifier)
        data = path.read_bytes()
        require(same_path == path and same_attempt == attempt and data.startswith(prefix), 'Frozen replaced prefix')
        require(verify_fixture(data, FLOWER) == checksum == final['partial_sha256'], 'Frozen hash differs')
        require(final['etag'] == progress['etag'] and bool(ready['result']['media_id']), 'Frozen version/publication changed')
    source_bytes = json.loads((test_root / 'body-bytes.json').read_text(encoding='utf-8'))
    return {'new_process': True, 'same_attempt': True, 'prefix_bytes': len(prefix), 'sha256': checksum,
            'source_prefix_body_bytes': source_bytes, 'frozen_appended_bytes': len(data) - len(prefix),
            'range_response_inferred_from_product_validator': True,
            'frozen_body_hard_limit': transport.LIMIT, 'expected_file_bytes': FIXTURES[FLOWER][0],
            'exe_sha256': hashlib.sha256(exe.read_bytes()).hexdigest()}


def run(test_root, exe=None):
    test_root.mkdir()  # An existing profile or earlier failure is never reused or removed.
    (test_root / 'body-bytes.json').write_text('0', encoding='utf-8')
    preflight(test_root)
    identifier, path, progress, prefix, attempt, before_pid = pause_fixture(test_root)
    with backend_process(test_root) as (request, after_pid):
        require(before_pid != after_pid, 'Resume must use a new backend process')
        old = request(PREFIX + '/' + identifier)
        require(old['status'] == 'paused' and path.read_bytes() == prefix, 'Restart changed paused bytes/state')
        request(PREFIX + '/' + identifier + '/retry', {'mode': 'resume'})
        ready = wait_job(request, identifier, {'ready'})
        same_path, final, same_attempt = saved_job(test_root, identifier)
        data = path.read_bytes()
        checksum = verify_fixture(data, FLOWER)
        require(same_path == path and same_attempt == attempt and data.startswith(prefix), 'Resume replaced its prefix')
        require(final['partial_sha256'] == checksum and ready['result']['media_id'], 'Publication hash missing')
        for index, (url, source, name) in enumerate(((RELATIVE, GREEN, 'green.mp4'),
                                                   (CROSS_HOST, FLOWER, 'redirect-flower.webm'))):
            item = request(PREFIX, {'url': url, 'name': name, 'rights_confirmed': True,
                                   'request_id': f'public-redirect-fixed-{index:02}'})
            redirected = wait_job(request, item['id'], {'ready'}, expected_size=FIXTURES[source][0])
            target, _, _ = saved_job(test_root, item['id'])
            verify_fixture(target.read_bytes(), source)
            if source == FLOWER:
                require(redirected['result']['media_id'] == ready['result']['media_id'], 'Dedup identity changed')
    independent = test_root / 'independent.webm'
    result = transport.transfer(FLOWER, independent, '.webm')
    require(verify_fixture(independent.read_bytes(), FLOWER) == checksum == result['sha256'], 'Independent hash differs')
    network = [json.loads(line) for line in (test_root / 'network.jsonl').read_text(encoding='utf-8').splitlines()]
    require(any(row['range'] == 'bytes=262144-' and row['if_range'] == progress['etag'] and row['status'] == 206
                and row.get('content-range') == 'bytes 262144-554057/554058' for row in network),
            'No successful real resume Range was observed')
    require(any(row['status'] == 302 and row.get('location') == '/media/2x2-green.mp4' for row in network),
            'Relative redirect not observed')
    require(any(row['status'] == 302 and row.get('location') == FLOWER for row in network), 'Cross-host redirect not observed')
    used = json.loads((test_root / 'body-bytes.json').read_text(encoding='utf-8'))
    frozen = frozen_resume(test_root / 'frozen', exe, checksum) if exe else None
    actual = used + (frozen['source_prefix_body_bytes'] + frozen['frozen_appended_bytes'] if frozen else 0)
    require(actual <= BODY_BUDGET, 'Combined observed bodies exceeded the expected test budget')
    summary = {'real_queue_pause': True, 'new_process_resume': True, 'resume_status': 206,
               'prefix_bytes': len(prefix), 'same_attempt': True, 'relative_redirect': True,
               'cross_host_redirect': True, 'media_identity_reused': True, 'sha256': checksum,
               'source_body_bytes_read': used, 'expected_body_budget': BODY_BUDGET,
               'observed_body_bytes': actual, 'mode': 'source-and-frozen' if frozen else 'instrumented-source',
               'frozen': frozen}
    (test_root / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(summary))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--test-root', type=Path, required=True)
    parser.add_argument('--exe', type=Path, help='Also resume a real saved prefix with an unmodified frozen backend')
    parser.add_argument('--allow-public-fixtures', action='store_true')
    parser.add_argument('--serve', action='store_true', help=argparse.SUPPRESS)
    parser.add_argument('--worker', action='store_true', help=argparse.SUPPRESS)
    parser.add_argument('--hold-first-block', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args()
    test_root = args.test_root.resolve()
    if not args.allow_public_fixtures:
        parser.error('Public network requires --allow-public-fixtures')
    if args.worker:
        instrument_worker(test_root, args.hold_first_block)
    elif args.serve:
        instrument_backend(test_root, args.hold_first_block)
    else:
        run(test_root, args.exe)


if __name__ == '__main__':
    main()
