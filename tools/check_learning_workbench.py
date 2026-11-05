"""Source/frozen black-box learning flow with newly generated data only. Never prints session credentials."""
import argparse
import hashlib
import json
import os
import re
import secrets
import sqlite3
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from contextlib import closing
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import pypdfium2 as pdfium


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--exe', type=Path)
    parser.add_argument('--test-root', type=Path, required=True)
    parser.add_argument('--media-fixture', type=Path)
    parser.add_argument('--download-url')
    parser.add_argument('--expected-download-sha1')
    args = parser.parse_args()
    if bool(args.download_url) != bool(args.expected_download_sha1):
        parser.error('Public download verification requires both URL and independently sourced SHA1')
    if args.download_url and (urllib.parse.urlsplit(args.download_url).query
                             or not re.fullmatch('[a-f0-9]{40}', args.expected_download_sha1)):
        parser.error('Use only a public non-secret fixture URL and a SHA1 digest')
    root = args.test_root.resolve()
    root.mkdir()  # No fixture/profile reuse and no cleanup of a previous failed run.
    repository = Path(__file__).resolve().parent.parent
    command = [str(args.exe.resolve())] if args.exe else [sys.executable, '-m', 'study_workbench']
    env = {**os.environ, 'PYTHONUTF8': '1', 'PYTHONIOENCODING': 'utf-8'}
    if args.exe:
        env['PATH'] = str(Path(os.environ['SystemRoot']) / 'System32')
        env.pop('PYTHONPATH', None)
        env.pop('PYTHONHOME', None)
    source, target = root / 'data', root / 'restored'
    config, package = root / 'profile/settings.json', root / 'library.zip'
    materials = root / 'materials'
    materials.mkdir()
    (materials / '提纲.md').write_text('# 自编课程\n慢启动与拥塞控制\n', encoding='utf-8')
    (materials / '术语.txt').write_text('术语\n慢启动\n拥塞窗口\n', encoding='utf-8')
    json_text = '{"自编数据":"<script>只读字面</script>","公式":"=1+1"}\n'
    (materials / '数据.json').write_bytes(json_text.encode('utf-8'))
    main_ns = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
    rel_ns = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
    package_ns = 'http://schemas.openxmlformats.org/package/2006/relationships'
    with ZipFile(materials / '数值.xlsx', 'w', compression=ZIP_DEFLATED) as archive:
        archive.writestr('[Content_Types].xml', '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/></Types>')
        archive.writestr('_rels/.rels', f'<Relationships xmlns="{package_ns}"><Relationship Id="book" Type="{rel_ns}/officeDocument" Target="xl/workbook.xml"/></Relationships>')
        archive.writestr('xl/workbook.xml', f'<workbook xmlns="{main_ns}" xmlns:r="{rel_ns}"><sheets><sheet name="缓存数据" sheetId="1" r:id="one"/><sheet name="稀疏数据" sheetId="2" r:id="two"/></sheets></workbook>')
        archive.writestr('xl/_rels/workbook.xml.rels', f'<Relationships xmlns="{package_ns}"><Relationship Id="one" Type="{rel_ns}/worksheet" Target="worksheets/one.xml"/><Relationship Id="two" Type="{rel_ns}/worksheet" Target="worksheets/two.xml"/></Relationships>')
        archive.writestr('xl/worksheets/one.xml', f'<worksheet xmlns="{main_ns}"><sheetData><row r="1"><c r="A1"><f>1+1</f><v>2</v></c><c r="B1"><f>1+1</f></c></row></sheetData></worksheet>')
        archive.writestr('xl/worksheets/two.xml', f'<worksheet xmlns="{main_ns}"><sheetData><row r="1048576"><c r="XFD1048576" t="inlineStr"><is><t>稀疏原文_x000D__xD83D__xDE00_</t></is></c></row></sheetData></worksheet>')
    pdf = pdfium.PdfDocument.new()
    for _ in range(2):
        pdf.new_page(400, 600)
    pdf.save(materials / '教材.pdf')
    pdf.close()
    source_hashes = {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in materials.iterdir()}
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    process = None
    downloaded_relative = None
    prefix = '/api/workspaces/default'

    def launch(data):
        nonlocal process
        process = subprocess.Popen(command + ['--data-dir', str(data), '--config', str(config)],
                                   cwd=root if args.exe else repository / 'backend', env=env,
                                   stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   text=True, encoding='utf-8',
                                   creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        token = secrets.token_urlsafe(32)
        process.stdin.write(json.dumps({'token': token}) + '\n')
        process.stdin.flush()
        line = process.stdout.readline()
        if not line:
            raise RuntimeError(process.stderr.read(8192))
        hello = json.loads(line)
        base = f"http://127.0.0.1:{hello['port']}"
        def request(method, path, body=None, *, raw=None, expected=200):
            headers = {'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json'}
            if raw is not None:
                headers['Content-Type'] = 'application/octet-stream'
            payload = raw if raw is not None else json.dumps(body, ensure_ascii=False).encode() if body is not None else None
            req = urllib.request.Request(base + path, data=payload, method=method, headers=headers)
            try:
                with opener.open(req, timeout=60) as response:
                    assert response.status == expected
                    data = response.read()
                    return json.loads(data) if 'json' in response.headers.get_content_type() else data
            except urllib.error.HTTPError as error:
                if error.code == expected:
                    return None
                raise AssertionError(f'{method} {path.split("?")[0]} failed ({error.code})') from None
        for _ in range(100):
            try:
                request('GET', '/api/health')
                return request
            except urllib.error.URLError:
                time.sleep(.1)
        raise RuntimeError('Frozen backend did not become ready')

    def stop():
        nonlocal process
        if process is None:
            return
        process.stdin.close()
        process.wait(timeout=20)
        if process.returncode:
            raise RuntimeError('Backend shutdown failed')
        process = None

    def offline(arguments):
        run = subprocess.run(command + arguments, cwd=root if args.exe else repository / 'backend',
                             env=env, capture_output=True, text=True, encoding='utf-8', timeout=180,
                             creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        if run.returncode:
            raise RuntimeError('Offline worker failed: ' + run.stderr[-1000:])
        return json.loads(run.stdout.splitlines()[-1])

    def rows_hash(path):
        with closing(sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)) as connection:
            checksum = hashlib.sha256()
            for line in connection.iterdump():
                checksum.update(line.encode('utf-8') + b'\n')
            return checksum.hexdigest()

    try:
        api = launch(source)
        job = api('POST', prefix + '/resource-add-jobs', {'source_path': str(materials)})
        for _ in range(200):
            job = api('GET', prefix + '/resource-add-jobs/' + job['id'])
            if job['status'] not in {'queued', 'running'}:
                break
            time.sleep(.05)
        assert job['status'] == 'completed', job['status']
        roots = api('GET', prefix + '/nodes')
        folder = next(node for node in roots if node['kind'] == 'folder')
        nodes = api('GET', prefix + '/nodes?parent_id=' + folder['resource_item_id'])
        by_name = {node['name']: node for node in nodes}
        sheet_node = by_name['数值.xlsx']['resource_item_id']
        json_node = by_name['数据.json']['resource_item_id']
        sheet_info = api('GET', f'{prefix}/nodes/{sheet_node}/document')
        assert sheet_info['type'] == 'spreadsheet' and sheet_info['cell_count'] == 3
        assert sheet_info['sheets'][0]['cells'][0]['value'] == '2'
        assert sheet_info['sheets'][0]['cells'][1]['cache_missing']
        assert sheet_info['sheets'][1]['cells'][0]['address'] == 'XFD1048576'
        assert sheet_info['sheets'][1]['cells'][0]['value'] == '稀疏原文\r😀'
        assert api('GET', f'{prefix}/nodes/{json_node}/document')['text'] == json_text
        assert api('GET', prefix + '/media-downloads') == []
        invalid_target = root / 'worker-rejected.webm'
        rejected = subprocess.run(command + ['--download-media'],
            input=json.dumps(dict(url='http://fixture.invalid/?secret=fixture', path=str(invalid_target), suffix='.webm', offset=0)).encode() + b'\n',
            cwd=root if args.exe else repository / 'backend', env=env, capture_output=True, timeout=20,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        assert rejected.returncode == 0 and 'error' in json.loads(rejected.stdout)
        assert b'secret' not in rejected.stdout and not invalid_target.exists()
        api('POST', f'{prefix}/nodes/{sheet_node}/working-copy', {'expected_sha256': sheet_info['sha256']}, expected=422)
        pdf_node, text_node = by_name['教材.pdf']['resource_item_id'], by_name['术语.txt']['resource_item_id']
        note = api('POST', prefix + '/markdown-notes', {'name': '拥塞控制笔记.md', 'request_id': 'learning-flow-note-request'})
        note_id = note['resource_item_id']
        pdf_info = api('GET', f'{prefix}/nodes/{pdf_node}/document')
        assert pdf_info['page_count'] == 2
        point = api('POST', f'{prefix}/nodes/{pdf_node}/learning-anchor',
                    {'kind': 'pdf_page', 'page': 2, 'expected_sha256': pdf_info['sha256']})
        bookmark = api('POST', prefix + '/learning-marks', {'request_id': 'learning-flow-mark-request',
            'anchor': point, 'title': '慢启动疑问', 'note': '回顾教材第二页', 'targets': [{'kind': 'file_note', 'id': note_id}]})
        text_info = api('GET', f'{prefix}/nodes/{text_node}/document')
        text_anchor = api('POST', f'{prefix}/nodes/{text_node}/learning-anchor',
                          {'kind': 'text_line', 'line': 2, 'expected_sha256': text_info['sha256']})
        api('POST', prefix + '/learning-marks', {'request_id': 'learning-flow-text-request', 'anchor': text_anchor, 'title': '术语行'})
        uri = f"studyworkbench://v1/workspaces/default/marks/{bookmark['id']}"
        text = '# 拥塞控制\n慢启动课程笔记\n[返回教材](' + uri + ')\n'
        note_info = api('GET', f'{prefix}/nodes/{note_id}/document')
        saved = api('PUT', f'{prefix}/nodes/{note_id}/document', {'expected_sha256': note_info['sha256'], 'text': text})
        resolved = api('POST', prefix + '/internal-links/resolve', {'uri': uri})
        assert resolved['status'] == 'valid' and resolved['anchor']['page'] == 2
        result = api('GET', prefix + '/learning-search?q=' + urllib.parse.quote('慢启动'))
        assert not result['truncated'] and {'file_note', 'mark'} <= {item['kind'] for item in result['items']}
        api('PATCH', f'{prefix}/nodes/{pdf_node}', {'name': '教材-改名.pdf', 'parent_id': None})
        assert api('POST', prefix + '/internal-links/resolve', {'uri': uri})['resource']['name'] == '教材-改名.pdf'
        other = api('POST', '/api/workspaces', {'name': '归档课程'})
        api('POST', f"/api/workspaces/{other['id']}/markdown-notes", {'name': '归档笔记.md', 'request_id': 'learning-flow-archived-note'})
        api('POST', f"/api/workspaces/{other['id']}/internal-links/resolve", {'uri': uri}, expected=404)
        api('DELETE', f"/api/workspaces/{other['id']}", {'confirm_name': '归档课程'})
        layout = api('GET', prefix + '/layout')
        layout['version'] = 2
        layout['tabs'].append(dict(id='f' * 32, kind='resource', resource_item_id=note_id, view_kind='document',
            resource_name='拥塞控制笔记.md', draft=text + '尚未保存的页面草稿', draft_base_sha256=saved['sha256'],
            document_state=dict(version=1, page=1, scroll=0, zoom=1, mode='edit', representation='original')))
        layout['active_tab_id'] = 'f' * 32
        api('PUT', prefix + '/layout', layout)
        if args.media_fixture:
            media = api('POST', prefix + '/media/import?filename=' + urllib.parse.quote(args.media_fixture.name), raw=args.media_fixture.read_bytes())
            assert media['status'] == 'ready'
        if args.download_url:
            downloaded = api('POST', prefix + '/media-downloads', {'url': args.download_url,
                'name': 'CC0验证.webm', 'request_id': 'public-media-download-check', 'rights_confirmed': True})
            deadline = time.monotonic() + 240
            while downloaded['status'] in {'queued', 'running'} and time.monotonic() < deadline:
                time.sleep(.1)
                downloaded = api('GET', prefix + '/media-downloads/' + downloaded['id'])
            assert downloaded['status'] == 'ready', {'download_status': downloaded['status'], 'error': downloaded['error']}
            with closing(sqlite3.connect(source / 'study.db')) as connection:
                downloaded_relative, sha256 = connection.execute('SELECT relative_path,sha256 FROM media_entries WHERE id=?',
                    (downloaded['result']['media_id'],)).fetchone()
            raw_download = (source / downloaded_relative).read_bytes()
            assert hashlib.sha1(raw_download).hexdigest() == args.expected_download_sha1
            assert hashlib.sha256(raw_download).hexdigest() == sha256
        attempt = api('POST', prefix + '/attempts', {'question_id': 'demo-integral', 'response': {'selected': ['a']}})
        grant = api('POST', prefix + '/agent-grants', {'attempt_ids': [attempt['id']], 'purpose': 'analyze_attempts', 'confirm': True})
        context = api('POST', f"{prefix}/agent-grants/{grant['id']}/read-analysis-context")
        assert context['scope'] == 'summary' and not context['question_versions']
        candidate = api('POST', prefix + '/analysis-drafts', {'grant_id': grant['id'], 'context_sha256': context['context_sha256'],
            'request_id': 'frozen-external-candidate-0001', 'title': '自编审核候选', 'body': '外部候选```<script>字面文本', 'source_label': '自编测试'})
        adoption = {'expected_revision': candidate['revision'], 'expected_payload_sha256': candidate['payload_sha256'],
            'request_id': 'frozen-review-adoption-0001', 'name': '自编分析候选.md', 'confirm': True}
        reviewed = api('POST', f"{prefix}/analysis-drafts/{candidate['id']}/adopt", adoption)
        assert reviewed['status'] == 'adopted' and reviewed['result']['verification'] == 'unverified'
        review_node = reviewed['result']['resource_item_id']
        review_text = api('GET', f'{prefix}/nodes/{review_node}/document')['text']
        assert '本应用未调用模型' in review_text and '````' in review_text
        stopped = api('POST', prefix + '/analysis-drafts', {'grant_id': grant['id'], 'context_sha256': context['context_sha256'],
            'request_id': 'frozen-failed-candidate-0002', 'title': '自编失败审核', 'body': '仅测试失效目标与拒绝，不执行内容'})
        stopped_path = f"{prefix}/analysis-drafts/{stopped['id']}"
        failed_request = dict(adoption, expected_revision=stopped['revision'], expected_payload_sha256=stopped['payload_sha256'], parent_id='f' * 32)
        api('POST', stopped_path + '/adopt', failed_request, expected=404)
        failed = api('GET', stopped_path)
        assert failed['status'] == 'failed' and failed['adoption'] == failed_request and not failed['result']
        rejected = api('POST', stopped_path + '/reject', {'expected_revision': failed['revision'],
            'expected_payload_sha256': failed['payload_sha256'], 'reason': '自编失效目标，保留收据并停止重试'})
        assert rejected['status'] == 'rejected' and rejected['adoption'] == failed_request
        api('POST', stopped_path + '/adopt', failed_request, expected=409)
        stop()
        api = launch(source)
        assert api('GET', f"{prefix}/analysis-drafts/{candidate['id']}") == reviewed
        assert api('POST', f"{prefix}/analysis-drafts/{candidate['id']}/adopt", adoption) == reviewed
        assert api('GET', f'{prefix}/nodes/{note_id}/document')['text'] == text
        assert api('GET', prefix + '/layout')['tabs'][-1]['draft'].endswith('尚未保存的页面草稿')
        assert api('POST', prefix + '/internal-links/resolve', {'uri': uri})['status'] == 'valid'
        stop()
        before = rows_hash(source / 'study.db')
        backup = offline(['--data-dir', str(source), '--backup-to', str(package), '--confirm-all-workspaces', '--config', str(config)])['result']
        assert backup['source_retained'] and backup['data_activated'] is False
        inspection = offline(['--inspect-backup', str(package)])
        assert inspection['database_semantics_checked'] is False and inspection['data_activated'] is False
        restored = offline(['--data-dir', str(target), '--restore-backup', str(package), '--config', str(config)])['result']
        assert restored['database_semantics_checked'] and restored['data_activated']
        assert rows_hash(target / 'study.db') == before == rows_hash(source / 'study.db')
        api = launch(target)
        assert api('GET', f'{prefix}/nodes/{sheet_node}/document')['sheets'] == sheet_info['sheets']
        assert api('GET', f'{prefix}/nodes/{json_node}/document')['text'] == json_text
        assert api('GET', f'{prefix}/nodes/{note_id}/document')['text'] == text
        assert api('POST', prefix + '/internal-links/resolve', {'uri': uri})['anchor']['page'] == 2
        assert api('GET', f"{prefix}/analysis-drafts/{candidate['id']}") == reviewed
        assert api('GET', f'{prefix}/nodes/{review_node}/document')['text'] == review_text
        assert api('GET', stopped_path) == rejected
        assert api('GET', prefix + '/learning-search?q=' + urllib.parse.quote('慢启动'))['total'] >= 2
        assert len(api('GET', '/api/workbench')['archived_workspaces']) == 1
        if downloaded_relative:
            assert hashlib.sha1((target / downloaded_relative).read_bytes()).hexdigest() == args.expected_download_sha1
        stop()
        assert source_hashes == {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in materials.iterdir()}
        result = dict(source_frozen=bool(args.exe), import_notes_marks_links_search=True, restart=True,
                      backup_restore=True, rows_sha256=before, source_files_unchanged=True, readonly_json_xlsx=True,
                      media_import=bool(args.media_fixture), media_playback_window_verified=False,
                      user_acceptance=False, phase_acceptance=False)
        result['public_download_and_restore_verified'] = bool(downloaded_relative)
        result['download_worker_rejection_verified'] = True
        result['manual_analysis_review_restart_and_restore_verified'] = True
        result['failed_analysis_rejection_preserves_receipt'] = True
        (root / 'result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        print(json.dumps(result, ensure_ascii=False))
    finally:
        if process is not None and process.poll() is None:
            process.stdin.close()
            try:
                process.wait(timeout=20)
            except subprocess.TimeoutExpired:
                process.kill()  # Only this test's own retained fixture process.
                process.wait(timeout=10)


if __name__ == '__main__':
    main()
