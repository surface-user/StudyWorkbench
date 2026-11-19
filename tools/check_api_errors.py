"""Check additive API errors through real source/frozen HTTP with fresh generated data."""
import argparse
import hashlib
import json
import os
import queue
import re
import secrets
import sqlite3
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path


def pdf_resources(request, error, root, convert_office):
    """Generated public fixtures; optional real conversion is distinct from a seeded ready receipt."""
    prefix, grants = '/api/workspaces/default', '/api/workspaces/default/agent-grants'
    samples = Path(__file__).resolve().parents[1] / 'contracts/samples'

    def add(suffix):
        value, _ = request(prefix + '/resource-add-jobs', {'source_path': str(samples / ('original-study.' + suffix))})
        deadline = time.monotonic() + 30
        while value['status'] in {'queued', 'running'} and time.monotonic() < deadline:
            time.sleep(.05)
            value, _ = request(prefix + '/resource-add-jobs/' + value['id'])
        assert value['status'] == 'completed'
        identifier = value['results'][0]['resource_item_id']
        node, _ = request(prefix + '/nodes/' + identifier)
        return identifier, node['resource_id']

    pdf_node, pdf_resource = add('pdf')
    office_node, office_resource = add('docx')
    db = root / 'data/study.db'
    with sqlite3.connect(db) as connection:
        pdf_hash, = connection.execute('SELECT sha256 FROM resources WHERE id=?', (pdf_resource,)).fetchone()
        source_hash, = connection.execute('SELECT sha256 FROM resources WHERE id=?', (office_resource,)).fetchone()
    if convert_office:
        ready, _ = request(f'{prefix}/nodes/{office_node}/previews', {'expected_source_sha256': source_hash})
        deadline = time.monotonic() + 600  # Match the existing real Office probe; runtime verification precedes the 90s engine limit.
        while ready['status'] in {'queued', 'running'} and time.monotonic() < deadline:
            time.sleep(.2)
            ready, _ = request(f'{prefix}/nodes/{office_node}/previews/' + ready['id'])
        assert ready['status'] == 'ready', 'Real ordinary Office conversion did not become ready'
    else:
        # CI tests a receipt boundary without claiming that LibreOffice ran there.
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
        from study_workbench.office_previews import OPTIONS_HASH
        identifier = secrets.token_hex(16)
        relative = f'workspaces/default/previews/{identifier}/output/source.pdf'
        target = root / 'data' / relative
        target.parent.mkdir(parents=True)
        raw = (samples / 'original-study.pdf').read_bytes()
        target.write_bytes(raw)
        with sqlite3.connect(db) as connection:
            connection.execute('INSERT INTO document_previews '
                '(id,workspace_id,node_id,source_resource_id,source_sha256,runtime_fingerprint,converter_version,'
                'options_hash,status,cancel_requested,relative_pdf,pdf_sha256,pdf_size,page_count,created_at) '
                'VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)', (identifier, 'default', office_node, office_resource,
                source_hash, 'a' * 64, 'controlled-receipt-not-conversion', OPTIONS_HASH, 'ready', 0, relative,
                hashlib.sha256(raw).hexdigest(), len(raw), 2, '2026-11-19T00:00:00Z'))
        ready = dict(id=identifier, pdf_sha256=hashlib.sha256(raw).hexdigest())

    def snapshot():
        with sqlite3.connect(db) as connection:
            tables = [n for n, in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")]
            rows = {n: connection.execute(f'SELECT * FROM "{n}" ORDER BY rowid').fetchall() for n in tables}
            paths = connection.execute('SELECT relative_path,sha256 FROM resources').fetchall()
            paths += connection.execute("SELECT relative_pdf,pdf_sha256 FROM document_previews WHERE status='ready'").fetchall()
        assert all(hashlib.sha256((root / 'data' / path).read_bytes()).hexdigest() == wanted for path, wanted in paths)
        return rows

    before = snapshot()
    pdf = dict(kind='resource_node', id=pdf_node, mode='text', representation='original_pdf_text',
               expected_sha256=pdf_hash, page=1)
    office = dict(kind='resource_node', id=office_node, mode='text', representation='office_pdf_text',
                  expected_sha256=ready['pdf_sha256'], expected_source_sha256=source_hash, preview_id=ready['id'], page=1)
    issued, _ = request(grants, dict(purpose='read_resources', selections=[pdf, office], confirm=True))
    value, _ = request(grants + '/' + issued['id'] + '/read-resources', {})
    assert len(value['resources']) == 2 and all(r['source_binary_read'] and r['text'] for r in value['resources'])
    assert {r['id']: r['citation']['source_resource_id'] for r in value['resources']} == {
        pdf_node: pdf_resource, office_node: office_resource}
    assert all(r['citation']['text_sha256'] == hashlib.sha256(r['text'].encode()).hexdigest() for r in value['resources'])
    assert {r['citation']['anchor']['kind'] for r in value['resources']} == {'pdf_page', 'office_pdf_page'}
    again, _ = request(grants + '/' + issued['id'] + '/read-resources', {'page': 2})
    assert again == value  # Read parameters cannot change an already authorized page.
    error(grants, 422, 'validation_failed', dict(purpose='read_resources', selections=[{**pdf, 'page': True}], confirm=True))
    error(grants, 409, 'conflict', dict(purpose='read_resources', selections=[{**office, 'expected_source_sha256': '0' * 64}], confirm=True))
    assert snapshot() == before
    return issued['id']


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--exe', type=Path)
    parser.add_argument('--test-root', type=Path, required=True)
    parser.add_argument('--convert-office', action='store_true', help='Require real ordinary Office conversion before page authorization')
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
    surviving_grant = None
    surviving_pdf_grant = None
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
            grants = prefix + '/agent-grants'
            if restart:
                error(grants + '/' + surviving_grant + '/read-resources', 404, 'not_found', {})
                error(grants + '/' + surviving_pdf_grant + '/read-resources', 404, 'not_found', {})
            surviving_pdf_grant = pdf_resources(request, error, root, args.convert_office)
            selection = {'kind': 'resource_node', 'id': node}
            metadata, _ = request(grants, {'purpose': 'read_resources', 'confirm': True, 'selections': [selection]})
            surviving_grant = metadata['id']
            context, _ = request(grants + '/' + surviving_grant + '/read-resources', {})
            assert context['purpose'] == 'read_resources' and 'text' not in context['resources'][0]
            assert context['links_followed'] is context['binary_attachments_read'] is False
            error(grants + '/' + surviving_grant + '/read-attempts', 404, 'not_found', {})
            error(grants + '/' + surviving_grant + '/read-analysis-context', 404, 'not_found', {})
            error(grants, 422, 'validation_failed', {'purpose': 'read_resources', 'confirm': True,
                'selections': [{**selection, 'path': private}]})
            text_grant, _ = request(grants, {'purpose': 'read_resources', 'confirm': True,
                'selections': [{**selection, 'mode': 'text', 'representation': 'original_text',
                    'expected_sha256': context['resources'][0]['metadata']['original_sha256']}]})
            selected, _ = request(grants + '/' + text_grant['id'] + '/read-resources', {})
            assert 'kept' in selected['resources'][0]['text']
            assert selected['resources'][0]['citation']['authority'] == 'original_text'
            error(grants + '/' + text_grant['id'] + '/read-resources', 401, 'unauthorized', {},
                headers={'Authorization': ''})
            error(grants + '/' + text_grant['id'] + '/read-resources', 403, 'forbidden', {},
                headers={'Origin': private})
            value, _ = request(grants + '/' + text_grant['id'], method='DELETE')
            assert value == {'revoked': True}
            error(grants + '/' + text_grant['id'] + '/read-resources', 404, 'not_found', {})
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
                         resource_grants_checked=True, resource_grants_not_restored=True,
                         receipts_preserved=True, media_range_preserved=True, pdf_page_grants_checked=True,
                         office_conversion_executed=args.convert_office, frozen=bool(args.exe))))


if __name__ == '__main__':
    main()
