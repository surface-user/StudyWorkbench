"""R3 black-box regression: real server, public HTTP only, fresh generated profile."""
import json
import os
import secrets
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


def main():
    root = Path(sys.argv[1]).resolve()
    root.mkdir()
    proc = subprocess.Popen([sys.executable, '-m', 'study_workbench', '--data-dir', str(root / 'data')], cwd=Path(__file__).resolve().parents[1] / 'backend', env={**os.environ, 'PYTHONUTF8': '1', 'STUDY_OFFICE_RUNTIME': str(root / 'missing-office')}, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8')
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
        import base64
        import hashlib
        import io

        import pypdfium2 as pdfium
        source = root / 'source'
        source.mkdir()
        (source / 'note.md').write_text('# 原件\n![图](image.png)', encoding='utf-8')
        (source / 'image.png').write_bytes(base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+j4ioAAAAASUVORK5CYII='))
        (source / 'bad.pdf').write_bytes(b'not pdf')
        (source / 'old.doc').write_bytes(b'unsupported')
        data = io.BytesIO()
        pdf = pdfium.PdfDocument.new()
        for page in range(21):
            pdf.new_page(100, 100)
        pdf.save(data)
        pdf.close()
        (source / 'long.pdf').write_bytes(data.getvalue())
        sample = Path(__file__).resolve().parents[1] / 'contracts/samples/original-study.docx'
        (source / 'sample.docx').write_bytes(sample.read_bytes())
        hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in source.iterdir()}
        job = call(prefix + '/resource-add-jobs', {'source_path': str(source)})
        for _ in range(1000):
            job = call(prefix + '/resource-add-jobs/' + job['id'])
            if job['status'] not in {'running', 'queued'}:
                break
            time.sleep(.02)
        assert job['status'] == 'completed', job
        top = next(n for n in call(prefix + '/nodes') if n['name'] == 'source')
        nodes = {n['name']: n for n in call(prefix + '/nodes?parent_id=' + top['resource_item_id'])}
        def endpoint(name):
            return prefix + '/nodes/' + nodes[name]['resource_item_id']
        md = endpoint('note.md')
        info = call(md + '/document')
        assert not info['working_copy'] and info['type'] == 'markdown'
        call(md + '/document', {'expected_sha256': info['sha256'], 'text': 'no copy'}, 'PUT', 409)
        call(md + '/working-copy', {'expected_sha256': '0' * 64}, expected=409)
        call(md + '/working-copy', {'expected_sha256': info['sha256']})
        saved = call(md + '/document', {'expected_sha256': info['sha256'], 'text': '# 新版本'}, 'PUT')
        call(md + '/document', {'expected_sha256': info['sha256'], 'text': 'stale overwrite'}, 'PUT', 409)
        assert call(md + '/document')['text'] == '# 新版本'
        call(md + '/document', {'expected_sha256': saved['sha256'], 'text': '超' * 400000}, 'PUT', 413)
        assert call(md + '/document')['sha256'] == saved['sha256']
        image = call(md + '/relative-image?path=image.png')
        assert base64.b64decode(image['image_base64']).startswith(b'\x89PNG')
        for path in ['../image.png', '../../image.png', 'https://example.com/a', 'file:///C:/secret', 'C:\\secret', '//host/a']:
            call(md + '/relative-image?path=' + urllib.parse.quote(path, safe=''), expected=404 if path == '../image.png' else 422)
        (source / 'unregistered.png').write_bytes((source / 'image.png').read_bytes())
        call(md + '/relative-image?path=unregistered.png', expected=404)
        (source / 'unregistered.png').unlink()
        assert call(endpoint('image.png') + '/document')['type'] == 'image'
        assert call(endpoint('long.pdf') + '/document')['page_count'] == 21
        assert base64.b64decode(call(endpoint('long.pdf') + '/document-page?page=21')['image_base64']).startswith(b'\x89PNG')
        call(endpoint('long.pdf') + '/document-page?page=22', expected=422)
        call(endpoint('long.pdf') + '/document-page?page=0', expected=422)
        call(endpoint('bad.pdf') + '/document', expected=422)
        assert call(endpoint('old.doc') + '/document')['type'] == 'unsupported'
        word = call(endpoint('sample.docx') + '/document')
        assert word['type'] == 'word' and not word['preview_capability']['available']
        call(endpoint('sample.docx') + '/previews', {'expected_source_sha256': word['source_sha256']}, expected=409)
        other = call('/api/workspaces', {'name': 'other'})['id']
        call(md.replace('/default/', '/' + other + '/') + '/document', expected=404)
        assert hashes == {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in source.iterdir()}
        print(json.dumps({'stage': 'R3', 'http_assertions': checks, 'source_unchanged': True, 'cases': 'MD explicit copy, stale save, UTF8 budget, relative image isolation, 21 page PDF, bad PDF, legacy doc, absent Office, cross workspace'}))
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
