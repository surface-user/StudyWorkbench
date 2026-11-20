"""Check additive API errors through real source/frozen HTTP with fresh generated data."""
import argparse
import hashlib
import io
import json
import os
import queue
import re
import secrets
import struct
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path


def media_fixture():
    """Generated container structure only; sample bytes intentionally do not prove codec validity."""
    def box(kind, raw):
        return struct.pack('>I4s', len(raw) + 8, kind) + raw
    ftyp = box(b'ftyp', b'isom\0\0\0\0isom')
    sample = box(b'avc1', b'\0' * 6 + b'\0\1' + b'\0' * 70 + box(b'avcC', b'\1' + b'\0' * 6))
    tables = box(b'stsd', struct.pack('>II', 0, 1) + sample)
    tables += box(b'stts', struct.pack('>IIII', 0, 1, 1, 1))
    tables += box(b'stsc', struct.pack('>IIIII', 0, 1, 1, 1, 1))
    tables += box(b'stsz', struct.pack('>III', 0, 4, 1))
    tables += box(b'stco', struct.pack('>III', 0, 1, len(ftyp) + 8))
    dref = box(b'dref', struct.pack('>II', 0, 1) + box(b'url ', b'\0\0\0\1'))
    info = box(b'vmhd', b'\0\0\0\1' + b'\0' * 8) + box(b'dinf', dref) + box(b'stbl', tables)
    handler = box(b'hdlr', b'\0' * 8 + b'vide' + b'\0' * 12)
    track = box(b'tkhd', b'\0' * 84) + box(b'mdia', box(b'mdhd', b'\0' * 24) + handler + box(b'minf', info))
    return ftyp + box(b'mdat', b'\0' * 4) + box(b'moov', box(b'mvhd', b'\0' * 100) + box(b'trak', track))


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
    environment['STUDY_FFMPEG_RUNTIME'] = str(root / 'missing-optional-media-runtime')
    if args.exe:
        environment['PATH'] = str(Path(os.environ['SystemRoot']) / 'System32')
        environment.pop('PYTHONPATH', None)
        environment.pop('PYTHONHOME', None)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    identifiers = set()
    private = 'private-fixture-https://example.invalid/?secret=not-echoed'
    checks = 0
    node = None
    media_item = None
    surviving_grant = None
    import pypdfium2 as pdfium
    sample = Path(__file__).resolve().parents[1] / 'contracts/samples/numbered-questions.pdf'
    output = io.BytesIO()
    with pdfium.PdfDocument.new() as document, pdfium.PdfDocument(sample) as numbered:
        for _ in range(19):
            document.new_page(50, 50).close()
        document.import_pages(numbered)
        document.save(output)
    pdf_bytes = output.getvalue()
    chunk_url = source_resource = None
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
            if not restart:
                media_item, _ = request(prefix + '/media/import?filename=input.mp4', media_fixture())
            preview_path = prefix + '/media/' + media_item['id'] + '/input-preview'
            expected = {'expected_sha256': media_item['sha256']}
            preview, _ = request(preview_path, expected)
            assert preview['policy_version'] == 'local-mp4-input-v1' and not preview['native_probe_performed']
            assert preview['streams'] == [{'role': 'video', 'declared_codec': 'h264'}]
            assert preview['sha256'] == hashlib.sha256(media_fixture()).hexdigest()
            error(preview_path, 409, 'conflict', {'expected_sha256': '0' * 64})
            error(preview_path, 422, 'validation_failed', {**expected, 'path': private})
            error(preview_path, 401, 'unauthorized', expected, headers={'Authorization': ''})
            error('/api/workspaces/missing/media/' + media_item['id'] + '/input-preview', 404, 'not_found', expected)
            error(prefix + '/media/' + media_item['id'] + '/native-probe', 503, 'unavailable', expected)
            error(prefix + '/media/' + media_item['id'] + '/native-probe', 422, 'validation_failed', {**expected, 'command': private})
            assert request(prefix + '/media')[0] == [media_item]
            assert (root / 'data/workspaces/default/media' / (media_item['id'] + '.mp4')).read_bytes() == media_fixture()
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
            if not restart:
                original, _ = request(prefix + '/imports?filename=chunk.pdf', pdf_bytes,
                                      headers={'Content-Type': 'application/pdf'})
                assert original['status'] == 'failed'
                source_resource = original['resource_id']
                bound, _ = request(prefix + '/pdf-chunk-jobs', {'resource_id': source_resource,
                    'expected_sha256': original['sha256'], 'first_page': 1, 'last_page': 21})
                chunk_url = prefix + '/pdf-chunk-jobs/' + bound['id']
                step, _ = request(chunk_url + '/advance', {'first_page': 1})
                assert step['completed_pages'] == 20
                cancelled, _ = request(chunk_url + '/cancel', {})
                assert cancelled['status'] == 'cancelled'
            else:
                previous, _ = request(chunk_url)
                assert previous['status'] == 'cancelled' and previous['completed_pages'] == 20
                request(chunk_url + '/resume', {})
                final, _ = request(chunk_url + '/advance', {'first_page': 21})
                assert final['status'] == 'parsed'
                batch, _ = request(chunk_url + '/preview', {})
                drafts = batch['preview']['question_drafts']
                assert [d['source_pages'] for d in drafts] == [[20, 21], [21]]
                path = prefix + '/imports/' + batch['id'] + '/question-markdown'
                selection = {'expected_revision': batch['draft_revision'], 'selected': [0], 'confirm': True}
                stored, _ = request(path, selection)
                repeated, _ = request(path, selection)
                assert stored == repeated and stored[0]['source_pages'] == [20, 21]
                original_bytes, _ = request(prefix + '/resources/' + source_resource, raw=True)
                assert original_bytes == pdf_bytes
            grants = prefix + '/agent-grants'
            if restart:
                error(grants + '/' + surviving_grant + '/read-resources', 404, 'not_found', {})
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
                         pdf_chunk_confirmation_checked=True, receipts_preserved=True, media_range_preserved=True,
                         local_media_input_preview=True, native_probe_performed=False, frozen=bool(args.exe))))


if __name__ == '__main__':
    main()
