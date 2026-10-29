"""Real loopback conversion with self-authored fixture paths and a fresh data root."""
import argparse
import base64
import hashlib
import json
import os
import re
import secrets
import sqlite3
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from zipfile import ZipFile


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--exe', type=Path)
    parser.add_argument('--test-root', type=Path, required=True)
    parser.add_argument('--runtime', type=Path)
    parser.add_argument('--docx', type=Path, required=True)
    parser.add_argument('--pptx', type=Path, required=True)
    args = parser.parse_args()
    root = args.test_root.resolve()
    root.mkdir()
    fixtures = [args.docx.resolve(strict=True), args.pptx.resolve(strict=True)]
    hashes = [hashlib.sha256(path.read_bytes()).hexdigest() for path in fixtures]
    env = dict(os.environ, PYTHONUTF8='1', PYTHONIOENCODING='utf-8')
    env.pop('STUDY_OFFICE_RUNTIME', None)
    if args.runtime:
        env['STUDY_OFFICE_RUNTIME'] = str(args.runtime.resolve())
    if args.exe:
        env['PATH'] = str(Path(os.environ['SystemRoot']) / 'System32')
        env.pop('PYTHONPATH', None)
        env.pop('PYTHONHOME', None)
    command = [str(args.exe.resolve())] if args.exe else [sys.executable, '-m', 'study_workbench']
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    process = None

    def launch():
        nonlocal process
        token = secrets.token_urlsafe(32)
        process = subprocess.Popen(command + ['--data-dir', str(root / 'data')],
                                   cwd=root if args.exe else Path(__file__).resolve().parents[1] / 'backend',
                                   env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, text=True, encoding='utf-8',
                                   creationflags=subprocess.CREATE_NO_WINDOW)
        process.stdin.write(json.dumps({'token': token}) + '\n')
        process.stdin.flush()
        hello = process.stdout.readline()
        assert hello, process.stderr.read()
        port = json.loads(hello)['port']

        def request(path, body=None):
            req = urllib.request.Request(f'http://127.0.0.1:{port}{path}',
                                         data=json.dumps(body).encode() if body is not None else None,
                                         headers={'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'})
            with opener.open(req, timeout=60) as response:
                return json.load(response)
        return request

    def wait(endpoint, states, timeout=600):
        deadline, report = time.monotonic() + timeout, time.monotonic()
        while time.monotonic() < deadline:
            value = request(endpoint)
            if value['status'] not in states:
                return value
            if time.monotonic() > report:
                print(json.dumps(dict(waiting=value['status'])), flush=True)
                report = time.monotonic() + 30
            time.sleep(.2)
        raise AssertionError('Real conversion deadline exceeded')

    def stop():
        process.stdin.close()
        assert process.wait(15) == 0
        assert not process.stderr.read().strip()

    prefix, jobs, results = '/api/workspaces/default', [], []
    try:
        request = launch()
        excessive = root / 'xml-budget.docx'
        with ZipFile(excessive, 'w') as archive:
            archive.writestr('[Content_Types].xml', '<Types/>')
            archive.writestr('_rels/.rels', '<Relationships/>')
            archive.writestr('word/document.xml', '<document>' * 129 + '</document>' * 129)
        added = request(prefix + '/resource-add-jobs', {'source_path': str(excessive)})
        added = wait(prefix + '/resource-add-jobs/' + added['id'], {'queued', 'running'}, 20)
        assert added['status'] == 'completed'
        endpoint = prefix + '/nodes/' + added['results'][0]['resource_item_id']
        rejected = request(endpoint + '/previews', {'expected_source_sha256': hashlib.sha256(excessive.read_bytes()).hexdigest()})
        rejected = wait(endpoint + '/previews/' + rejected['id'], {'queued', 'running'})
        assert rejected['status'] == 'failed' and 'XML节点或嵌套预算' in rejected['error'], rejected
        for fixture, checksum in zip(fixtures, hashes, strict=True):
            added = request(prefix + '/resource-add-jobs', {'source_path': str(fixture)})
            added = wait(prefix + '/resource-add-jobs/' + added['id'], {'queued', 'running'}, 20)
            assert added['status'] == 'completed', added
            node = added['results'][0]['resource_item_id']
            endpoint = prefix + '/nodes/' + node
            doc = request(endpoint + '/document')
            assert doc['source_sha256'] == checksum and doc['preview_capability']['available'], doc
            body = {'expected_source_sha256': checksum}
            cancelled = request(endpoint + '/previews', body)
            request(endpoint + '/previews/' + cancelled['id'] + '/cancel', {})
            assert wait(endpoint + '/previews/' + cancelled['id'], {'queued', 'running'})['status'] == 'cancelled'
            started = request(endpoint + '/previews', body)
            value = wait(endpoint + '/previews/' + started['id'], {'queued', 'running'})
            assert value['status'] == 'ready' and value['page_count'] >= 1, value
            # These deliberately self-authored samples contain OMML x² and a labelled chart.
            import pypdfium2
            with sqlite3.connect(root / 'data/study.db') as db:
                relative = db.execute('SELECT relative_pdf FROM document_previews WHERE id=?', (value['id'],)).fetchone()[0]
            with pypdfium2.PdfDocument(root / 'data' / relative) as pdf:
                text = ''.join(page.get_textpage().get_text_range() for page in pdf)
            if fixture.suffix == '.docx':
                assert re.search(r'x\s*2', text), 'OMML formula disappeared from derived PDF'
            else:
                assert text.count('数学') >= 2 and text.count('英语') >= 2, 'Chart labels disappeared from derived PDF'
            for number in {1, value['page_count']}:
                page = request(endpoint + '/previews/' + value['id'] + '/page?page=' + str(number))
                png = base64.b64decode(page['image_base64'])
                assert png.startswith(b'\x89PNG')
                (root / f'{fixture.suffix[1:]}-page{number}.png').write_bytes(png)
            assert request(endpoint + '/previews', body)['id'] == value['id']
            assert hashlib.sha256(fixture.read_bytes()).hexdigest() == checksum
            jobs.append((endpoint, value['id'], body))
            results.append(dict(format=fixture.suffix, pages=value['page_count'], pdf_bytes=value['pdf_size'],
                                source_preserved=True, cancelled_retry=True, cache_reused=True,
                                math_or_chart_checked=True))
            print(json.dumps(results[-1]), flush=True)
        stop()
        request = launch()
        for endpoint, identifier, body in jobs:
            assert request(endpoint + '/document')['preview']['id'] == identifier
            assert request(endpoint + '/previews', body)['id'] == identifier
        stop()
        with sqlite3.connect(root / 'data/study.db') as db:
            assert db.execute('SELECT version_num FROM alembic_version').fetchone() == ('0011',)
            assert db.execute('PRAGMA integrity_check').fetchone() == ('ok',)
            assert db.execute('PRAGMA foreign_key_check').fetchall() == []
        print(json.dumps(dict(frozen=bool(args.exe), results=results, restart_cache=True,
                              xml_budget_rejected=True)), flush=True)
    finally:
        if process and process.poll() is None:
            process.kill()
            process.wait(10)


if __name__ == '__main__':
    main()
