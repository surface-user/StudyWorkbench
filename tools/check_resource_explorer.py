"""Exercise source/frozen R1 over the real loopback pipe using newly generated data only."""
import argparse
import base64
import hashlib
import json
import os
import secrets
import sqlite3
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--exe', type=Path)
    parser.add_argument('--test-root', type=Path, required=True)
    parser.add_argument('--documents', action='store_true')
    parser.add_argument('--without-office', action='store_true')
    args = parser.parse_args()
    root = args.test_root.resolve()
    root.mkdir()  # Refuse to reuse an existing profile or fixture directory.
    source = root / '中文来源'
    (source / '章节').mkdir(parents=True)
    (source / '无答案.md').write_text('# 资料原文', encoding='utf-8')
    (source / '章节' / '副本.md').write_bytes((source / '无答案.md').read_bytes())
    (source / '讲义.pptx').write_bytes(b'opaque-preserved-no-parser')
    hashes = {str(p.relative_to(source)): hashlib.sha256(p.read_bytes()).hexdigest() for p in source.rglob('*') if p.is_file()}
    command = [str(args.exe.resolve())] if args.exe else [sys.executable, '-m', 'study_workbench']
    environment = {**os.environ, 'PYTHONUTF8': '1', 'PYTHONIOENCODING': 'utf-8'}
    if args.without_office:
        environment['STUDY_OFFICE_RUNTIME'] = str(root / 'missing-optional-office')
    if args.exe:
        environment['PATH'] = str(Path(os.environ['SystemRoot']) / 'System32')
        environment.pop('PYTHONPATH', None)
        environment.pop('PYTHONHOME', None)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    processes = []

    def launch():
        token = secrets.token_urlsafe(32)
        process = subprocess.Popen(command + ['--data-dir', str(root / 'data')],
                                   cwd=root if args.exe else Path(__file__).resolve().parents[1] / 'backend',
                                   env=environment, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, text=True, encoding='utf-8')
        processes.append(process)
        process.stdin.write(json.dumps({'token': token}) + '\n')
        process.stdin.flush()
        hello = process.stdout.readline()
        if not hello:
            raise RuntimeError(process.stderr.read())
        port = json.loads(hello)['port']

        def request(path, body=None, method=None):
            req = urllib.request.Request(f'http://127.0.0.1:{port}{path}', method=method,
                                         data=json.dumps(body).encode() if body is not None else None,
                                         headers={'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'})
            with opener.open(req, timeout=60) as response:
                return json.load(response)
        for _ in range(50):
            try:
                request('/api/health')
                return process, request
            except urllib.error.URLError:
                time.sleep(.1)
        raise RuntimeError('Backend not ready')

    def stop(process):
        process.stdin.close()
        process.wait(timeout=10)
        assert process.returncode == 0
        assert not process.stderr.read().strip(), 'Backend emitted unexpected stderr'

    prefix = '/api/workspaces/default'
    try:
        process, request = launch()
        assert request('/api/workbench')['workspaces'][0]['name'] == '我的学习空间'
        assert request(prefix + '/layout')['tabs'] == []
        inspected = request(prefix + '/resource-inspections', {'source_paths': [str(source / '无答案.md')]})
        assert inspected[0]['type'] == 'Markdown 笔记' and inspected[0]['error'] is None
        assert request(prefix + '/nodes') == [] and request(prefix + '/resource-add-jobs') == []
        layout = {'version': 1, 'tabs': [{'id': 'legacy', 'kind': 'question', 'draft': '升级仍保留的草稿'}],
                  'closed_tabs': [], 'active_tab_id': 'legacy'}
        layout = request(prefix + '/layout', layout, 'PUT')
        attempt = request(prefix + '/attempts', {'question_id': 'demo-integral', 'response': {'selected': ['a']}})
        job = request(prefix + '/resource-add-jobs', {'source_path': str(source)})
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            job = request(prefix + '/resource-add-jobs/' + job['id'])
            if job['status'] not in {'running', 'queued'}:
                break
            time.sleep(.02)
        assert job['status'] == 'completed', job
        assert len(job['results']) == 5
        assert sum(row['status'] == 'duplicate' for row in job['results']) == 1
        top = request(prefix + '/nodes')[0]
        children = request(prefix + '/nodes?parent_id=' + top['resource_item_id'])
        node = next(row for row in children if row['name'] == '无答案.md')
        analyzed = request(prefix + '/resources/' + node['resource_id'] + '/analyze', {}, 'POST')
        assert analyzed['resource_id'] == node['resource_id'] and analyzed['status'] == 'preview'
        assert request(prefix + '/notes') == []
        assert request(prefix + '/nodes?search=' + urllib.parse.quote('无答案'))[0]['resource_item_id'] == node['resource_item_id']
        renamed = request(prefix + '/nodes/' + node['resource_item_id'], {'name': '已改名.md', 'parent_id': None}, 'PATCH')
        assert renamed['resource_item_id'] == node['resource_item_id']
        assert request(prefix + '/nodes/' + node['resource_item_id'])['status'] == 'ready'
        if args.documents:
            endpoint = prefix + '/nodes/' + node['resource_item_id']
            document = request(endpoint + '/document')
            assert document['type'] == 'markdown' and not document['working_copy']
            request(endpoint + '/working-copy', {'expected_sha256': document['sha256']})
            saved = request(endpoint + '/document', {'expected_sha256': document['sha256'], 'text': '# 保存的工作副本'}, 'PUT')
            assert request(endpoint + '/document')['text'] == '# 保存的工作副本'
            for suffix in ['pdf', 'docx']:
                fixture = Path(__file__).resolve().parents[1] / 'contracts/samples' / ('original-study.' + suffix)
                added = request(prefix + '/resource-add-jobs', {'source_path': str(fixture)})
                deadline = time.monotonic() + 20
                while time.monotonic() < deadline:
                    added = request(prefix + '/resource-add-jobs/' + added['id'])
                    if added['status'] not in {'running', 'queued'}:
                        break
                    time.sleep(.02)
                assert added['status'] == 'completed'
                added_id = added['results'][0]['resource_item_id']
                value = request(prefix + '/nodes/' + added_id + '/document')
                assert value['type'] == ('pdf' if suffix == 'pdf' else 'word')
                if suffix == 'pdf':
                    assert value['page_count'] == 2
                    value = request(prefix + '/nodes/' + added_id + '/document-page?page=2')
                    assert base64.b64decode(value['image_base64']).startswith(b'\x89PNG')
                else:
                    assert any('中文题干' in b.get('text', '') for b in value['blocks'])
                    if args.without_office:
                        assert not value['preview_capability']['available']
            layout['version'] = 2
            layout['tabs'].append({'id': 'resource-md', 'kind': 'resource', 'resource_item_id': node['resource_item_id'],
                                   'view_kind': 'document', 'draft': '未写入的文件草稿', 'draft_base_sha256': saved['sha256'],
                                   'document_state': {'version': 1, 'mode': 'edit', 'page': 1, 'zoom': 1, 'scroll': 12}})
            layout = request(prefix + '/layout', layout, 'PUT')
        stop(process)
        process, request = launch()
        assert request(prefix + '/layout') == layout
        assert request(prefix + '/attempts')[0]['id'] == attempt['id']
        assert request(prefix + '/resource-add-jobs/' + job['id'])['results'] == job['results']
        assert request(prefix + '/nodes/' + node['resource_item_id'])['name'] == '已改名.md'
        if args.documents:
            assert request(endpoint + '/document')['text'] == '# 保存的工作副本'
            with sqlite3.connect(root / 'data/study.db') as db:
                relative = db.execute('SELECT relative_path FROM document_workfiles WHERE node_id=?', (node['resource_item_id'],)).fetchone()[0]
            (root / 'data' / relative).write_text('外部修改', encoding='utf-8')
            try:
                request(endpoint + '/document', {'expected_sha256': saved['sha256'], 'text': '不能覆盖'}, 'PUT')
                raise AssertionError('Expected conflict')
            except urllib.error.HTTPError as error:
                assert error.code == 409
            assert request(endpoint + '/document')['text'] == '外部修改'
        removed_id = node['resource_item_id']
        assert request(prefix + '/nodes/' + removed_id, method='DELETE')['removed_ids'] == [removed_id]
        assert all(row['resource_item_id'] != removed_id for row in request(prefix + '/nodes'))
        assert request(prefix + '/layout') == layout
        stop(process)
        process, request = launch()
        assert all(row['resource_item_id'] != removed_id for row in request(prefix + '/nodes'))
        assert request(prefix + '/nodes/' + removed_id)['status'] == 'removed'
        assert request(prefix + '/layout') == layout
        assert request(prefix + '/attempts')[0]['id'] == attempt['id']
        stop(process)
        with sqlite3.connect(root / 'data/study.db') as db:
            assert db.execute('SELECT version_num FROM alembic_version').fetchone() == ('0012',)
            assert db.execute('PRAGMA integrity_check').fetchone() == ('ok',)
            assert db.execute('PRAGMA foreign_key_check').fetchall() == []
        assert hashes == {str(p.relative_to(source)): hashlib.sha256(p.read_bytes()).hexdigest() for p in source.rglob('*') if p.is_file()}
        print(json.dumps(dict(frozen=bool(args.exe), nodes=5, duplicate_blob=1, layout_preserved=True, documents=args.documents,
                              attempts_preserved=True, source_preserved=True, restart=True, revision='0012',
                              removal_preserved_after_restart=True,
                              without_office=args.without_office)))
    finally:
        for process in processes:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=10)


if __name__ == '__main__':
    main()
