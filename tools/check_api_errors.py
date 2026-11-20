"""Check additive API errors through real source/frozen HTTP with fresh generated data."""
import argparse
import hashlib
import io
import json
import os
import queue
import random
import re
import secrets
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path


def add_source(request, prefix, source):
    job, _ = request(prefix + '/resource-add-jobs', {'source_path': str(source), 'parent_id': None})
    for _ in range(100):
        job, _ = request(prefix + '/resource-add-jobs/' + job['id'])
        if job['status'] not in {'queued', 'running'}:
            break
        time.sleep(.1)
    return job['results'][0]['resource_item_id']


def large_question_pdf(path):
    import pypdfium2 as pdfium
    from PIL import Image

    image_pdf = io.BytesIO()
    pixels = random.Random(23).randbytes(1900 * 1500 * 3)
    with Image.frombytes('RGB', (1900, 1500), pixels) as picture:
        picture.save(image_pdf, 'PDF', quality=98, subsampling=0)
    sample = Path(__file__).resolve().parents[1] / 'contracts/samples/two-column-questions.pdf'
    with pdfium.PdfDocument(image_pdf.getvalue()) as document, pdfium.PdfDocument(sample) as questions:
        document.import_pages(questions)
        document.save(path)
    assert 8 * 1024 * 1024 < path.stat().st_size < 128 * 1024 * 1024


def check_column_questions(request, prefix, managed=None):
    if managed is None:
        raw = (Path(__file__).resolve().parents[1] / 'contracts/samples/two-column-questions.pdf').read_bytes()
        source, _ = request(prefix + '/imports?filename=columns.pdf', raw, headers={'Content-Type': 'application/pdf'})
        page = 1
    else:
        large_question_pdf(managed)
        node = add_source(request, prefix, managed)
        source, _ = request(prefix + '/nodes/' + node)
        raw = managed.read_bytes()
        assert hashlib.sha256(raw).hexdigest() == source['sha256']
        page = 2
    options = {'resource_id': source['resource_id'], 'expected_sha256': source['sha256'],
               'first_page': page, 'last_page': page}
    classic, _ = request(prefix + '/pdf-chunk-jobs', options)
    job, _ = request(prefix + '/pdf-chunk-jobs', {**options, 'layout': 'two_columns'})
    assert job['id'] != classic['id'] and job['parser_version'] == 'pdf-column-chunks-v1'
    url = prefix + '/pdf-chunk-jobs/' + job['id']
    if managed is not None:
        assert request(url + '/cancel', {})[0]['status'] == 'cancelled'
        assert request(url + '/resume', {})[0]['status'] == 'ready'
    parsed, _ = request(url + '/advance', {'first_page': page})
    assert parsed['status'] == 'parsed'
    batch, _ = request(url + '/preview', {})
    first, second = batch['preview']['question_drafts']
    assert first['shared_materials'] == second['shared_materials'] and first['source_pages'] == [page]
    assert [r['box'][::2] for r in first['regions']] == [[0, .5], [.5, 1]]
    assert 'First question continues here.' in batch['question_markdown'][0]
    assert 'First question continues here.' not in batch['question_markdown'][1]
    choice = {'expected_revision': batch['draft_revision'], 'selected': [0], 'confirm': True}
    confirm = prefix + '/imports/' + job['id'] + '/question-markdown'
    saved, _ = request(confirm, choice)
    assert request(confirm, choice)[0] == saved
    assert request(prefix + '/resources/' + source['resource_id'], raw=True)[0] == raw


def check_scan(request, prefix, root):
    from PIL import Image, ImageDraw, ImageFont

    cases = [('eng', 'Study page 123', 'arial.ttf'), ('chi_sim', '中文学习', 'msyh.ttc'), ('eng', '', 'arial.ttf')]
    pages = []
    for _, line, font in cases:
        picture = Image.new('RGB', (390, 84), 'white')
        face = ImageFont.truetype(str(Path(os.environ['SystemRoot']) / 'Fonts' / font), 48)
        ImageDraw.Draw(picture).text((10, 3), line, font=face, fill='black')
        pages.append(picture)
    source = root / 'scan.pdf'
    pages[0].save(source, 'PDF', save_all=True, append_images=pages[1:], resolution=144)
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    node = add_source(request, prefix, source)
    url = prefix + '/nodes/' + node + '/document-ocr'
    options = {'expected_sha256': digest, 'request_id': '7' * 32}
    resource = None
    for page, (language, expected_text, _) in enumerate(cases, 1):
        value, _ = request(url, {**options, 'page': page, 'language': language})
        assert value['text'] == expected_text and not value['confirmed'] and value['source'] == 'ocr'
        assert (value['page'], value['page_count'], value['language'], value['source_sha256']) == (page, 3, language, digest)
        assert value['engine_version'] == '5.5.4' and value['model_version'] == 'tessdata_fast-4.1.0'
        assert re.fullmatch('[a-f0-9]{64}', value['model_sha256'])
        assert bool(value['regions']) == bool(expected_text) and ('no_text' in value['warnings']) == (not expected_text)
        for word in value['regions']:
            x, y, right, bottom = word['box']
            assert 0 <= x < right <= 1 and 0 <= y < bottom <= 1 and 0 <= word['confidence'] <= 100
        resource = value['resource_id']
    cancel = url + '/' + options['request_id'] + '/cancel'
    with ThreadPoolExecutor(max_workers=1) as pool:
        running = pool.submit(request, url, {**options, 'page': 1, 'language': 'eng'}, expected=409)
        for _ in range(100):
            status, _ = request(cancel, {}, expected=(200, 404))
            if status.get('cancelled'):
                break
            time.sleep(.02)
        assert status.get('cancelled') and running.result(timeout=30)[0]['error']['code'] == 'conflict'
    preserved, _ = request(prefix + '/resources/' + resource, raw=True)
    assert preserved == source.read_bytes()
    return cancel


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--exe', type=Path)
    parser.add_argument('--ocr-component', type=Path)
    parser.add_argument('--test-root', type=Path, required=True)
    args = parser.parse_args()
    root = args.test_root.resolve()
    root.mkdir()  # Refuse reuse; never modify an existing profile or previous failure.
    media = root / 'fixture.mp4'
    media.write_bytes(bytes(range(256)) * 8)
    command = [str(args.exe.resolve())] if args.exe else [sys.executable, '-m', 'study_workbench']
    environment = {**os.environ, 'PYTHONUTF8': '1', 'PYTHONIOENCODING': 'utf-8'}
    if args.ocr_component:
        environment['STUDY_OCR_RUNTIME'] = str(args.ocr_component.resolve(strict=True))
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
    previous_scan = None
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
                    allowed = expected if isinstance(expected, tuple) else (expected,)
                    assert response.status in allowed, f'Unexpected HTTP status {response.status}; expected {expected}'
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
            if args.ocr_component:
                if restart:
                    request(previous_scan, {}, expected=404)
                else:
                    previous_scan = check_scan(request, prefix, root)
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
                check_column_questions(request, prefix)
                check_column_questions(request, prefix, root / 'larger.pdf')
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
                         scan_checked=bool(previous_scan), two_column_confirmation_checked=True, large_managed_pdf_checked=True, frozen=bool(args.exe))))


if __name__ == '__main__':
    main()
