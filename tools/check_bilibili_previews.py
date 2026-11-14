"""Explicit metadata-only Bilibili probe for a declared CC-BY Blender movie mirror."""
import argparse
import json
import os
import queue
import secrets
import sqlite3
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

FIXTURE = 'https://www.bilibili.com/video/BV1gi4y1V7Xx/'
LICENSE = 'https://peach.blender.org/about/'


def no_private_fields(value):
    if isinstance(value, dict):
        assert not {'url', 'source_url', 'fragments', 'http_headers', 'cookies'} & value.keys()
        for child in value.values():
            no_private_fields(child)
    elif isinstance(value, list):
        for child in value:
            no_private_fields(child)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--exe', type=Path)
    parser.add_argument('--test-root', type=Path, required=True)
    parser.add_argument('--allow-public-fixture', action='store_true')
    args = parser.parse_args()
    if not args.allow_public_fixture:
        parser.error('Public metadata requests require --allow-public-fixture')
    root = args.test_root.resolve()
    root.mkdir()
    command = [str(args.exe.resolve())] if args.exe else [sys.executable, '-m', 'study_workbench']
    environment = {**os.environ, 'PYTHONUTF8': '1', 'PYTHONIOENCODING': 'utf-8'}
    if args.exe:
        environment['PATH'] = str(Path(os.environ['SystemRoot']) / 'System32')
        environment.pop('PYTHONPATH', None)
        environment.pop('PYTHONHOME', None)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    identifier = None
    observations = []
    for restart in (False, True):
        token = secrets.token_urlsafe(32)
        process = subprocess.Popen(command + ['--data-dir', str(root / 'data')],
            cwd=root if args.exe else Path(__file__).resolve().parents[1] / 'backend', env=environment,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8',
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        try:
            process.stdin.write(json.dumps({'token': token}) + '\n')
            process.stdin.flush()
            hello = queue.Queue()
            threading.Thread(target=lambda: hello.put(process.stdout.readline()), daemon=True).start()
            port = json.loads(hello.get(timeout=30))['port']

            def request(path, body=None, expected=200):
                data = None if body is None else json.dumps(body).encode('utf-8')
                req = urllib.request.Request(f'http://127.0.0.1:{port}{path}', data=data,
                    headers={'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json'})
                try:
                    response = opener.open(req, timeout=10)
                except urllib.error.HTTPError as error:
                    response = error
                with response:
                    raw = response.read(128 * 1024 + 1)
                    assert len(raw) <= 128 * 1024 and response.status == expected, 'Unexpected local API response'
                    return json.loads(raw)

            for _ in range(50):
                try:
                    assert request('/api/health')['status'] == 'ok'
                    break
                except urllib.error.URLError:
                    time.sleep(.1)
            else:
                raise AssertionError('Backend did not become ready')
            prefix = '/api/workspaces/default/media-site-previews'
            if restart:
                request(prefix + '/' + identifier, expected=404)
                observations.append({'restart_invalidates_candidate': True})
            else:
                body = {'url': FIXTURE, 'rights_confirmed': True, 'request_id': 'public-blender-metadata-fixture-001'}
                value = request(prefix, body)
                identifier = value['id']
                deadline = time.monotonic() + 60
                while value['status'] == 'running' and time.monotonic() < deadline:
                    time.sleep(.2)
                    value = request(prefix + '/' + identifier)
                no_private_fields(value)
                if value['status'] != 'ready':
                    diagnostic = value.get('error_diagnostic')
                    if diagnostic is not None:
                        assert (isinstance(diagnostic, dict) and set(diagnostic) == {'stage', 'http_status'}
                                and type(diagnostic['stage']) is str and diagnostic['stage'] in {'shortlink', 'page', 'nav', 'playurl'}
                                and type(diagnostic['http_status']) is int and 100 <= diagnostic['http_status'] <= 599)
                    print(json.dumps({'frozen': bool(args.exe), 'error_diagnostic': diagnostic}), flush=True)
                    (root / 'failed-preview.json').write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
                    raise AssertionError('Public metadata preview did not complete; sanitized result retained')
                result = value['result']
                no_private_fields(value)
                assert result['video_id'] == 'BV1gi4y1V7Xx'
                assert 'Big Buck Bunny' in result['title'] or '大雄兔' in result['title']
                assert 550 <= result['duration_seconds'] <= 700
                assert 0 < len(result['formats']) <= 64
                assert all(not item['download_supported'] for item in result['formats'])
                assert request(prefix, body)['id'] == identifier
                other = request('/api/workspaces', {'name': 'Preview isolation fixture'})['id']
                request(f'/api/workspaces/{other}/media-site-previews/{identifier}', expected=404)
                assert request(prefix + '/' + identifier + '/cancel', {})['status'] == 'cancelled'
                observations.append({'metadata_ready': True, 'video_id': result['video_id'],
                                     'extractor_version': result['extractor_version'],
                                     'duration_seconds': result['duration_seconds'],
                                     'format_count': len(result['formats']), 'no_private_fields': True,
                                     'same_request_reused': True, 'cross_workspace_refused': True,
                                     'candidate_cancelled': True})
        finally:
            process.stdin.close()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
                raise AssertionError('Backend did not stop after EOF') from None
            assert process.returncode == 0, 'Backend exited unexpectedly'
            assert not process.stderr.read().strip(), 'Backend emitted unexpected stderr'
    with sqlite3.connect(root / 'data/study.db') as connection:
        assert connection.execute('SELECT COUNT(*) FROM media_download_jobs').fetchone() == (0,)
        assert connection.execute('SELECT COUNT(*) FROM media_entries').fetchone() == (0,)
    summary = {'frozen': bool(args.exe), 'fixture': FIXTURE, 'original_work': 'Big Buck Bunny',
               'author': 'Blender Foundation', 'declared_license': 'CC-BY-3.0', 'original_license_url': LICENSE,
               'scope': 'public page/API metadata only; no movie or track requested',
               'media_byte_correspondence_verified': False, 'observations': observations,
               'download_records': 0, 'media_records': 0}
    (root / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == '__main__':
    main()
