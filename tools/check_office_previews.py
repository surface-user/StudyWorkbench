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

from alembic.config import Config
from alembic.script import ScriptDirectory


def check_complex_pdf(pdf_path, suffix):
    """Finite layout assertions, not pixel equivalence with Microsoft Office."""
    import pypdfium2
    from PIL import ImageChops
    markers = (['FMT PORTRAIT ONE', 'FMT PORTRAIT TWO', 'FMT LANDSCAPE THREE']
               if suffix == '.docx' else ['FMT CHART ONE', 'FMT COLUMNS TWO', 'FMT FORMULA THREE'])
    pages = []
    with pypdfium2.PdfDocument(pdf_path) as pdf:
        assert len(pdf) == 3, f'{suffix}: expected three authored pages, got {len(pdf)}'
        for number, page in enumerate(pdf):
            width, height = page.get_size()
            textpage = page.get_textpage()
            text = textpage.get_text_range()
            assert markers[number] in text, (suffix, number, text)
            for index in range(textpage.count_chars()):
                if not textpage.get_text_range(index, 1).strip():
                    continue
                left, bottom, right, top = textpage.get_charbox(index)
                assert -2 <= left <= right <= width + 2 and -2 <= bottom <= top <= height + 2, (number, index)
            bitmap = page.render(scale=1)
            raster = bitmap.to_pil().convert('RGB')
            assert ImageChops.difference(raster, raster.copy().point(lambda _: 255)).getbbox(), number
            if suffix == '.docx':
                assert 'FMT HEADER' in text and 'FMT FOOTER' in text
                assert (width > height) == (number == 2), (number, width, height)
                if number == 0:
                    assert 'FONT AVAILABLE' in text and 'FONT FALLBACK' in text and re.search(r'x\s*2', text)
                elif number == 1:
                    assert all(f'R{i:02}' in text for i in range(1, 21)) and 'TABLE END' in text
                else:
                    assert 'MERGED HEADING' in text and 'LEFT' in text and 'RIGHT' in text
            elif number == 0:
                assert text.count('数学') >= 2 and text.count('英语') >= 2
            elif number == 1:
                def position(label):
                    found = textpage.search(label).get_next()
                    assert found is not None
                    return textpage.get_charbox(found[0])[0]
                assert position('LEFT COLUMN') < width / 2 < position('RIGHT COLUMN')
                assert 'FONT FALLBACK' in text
            else:
                assert all(label in text for label in ['公式', 'x', 'y', 'z', 'H', 'O'])
            pages.append(dict(page=number + 1, width=width, height=height, text_inside_page=True, nonblank=True))
            bitmap.close()
            textpage.close()
            page.close()
    return pages


def check_complex_workbook(value):
    from datetime import date
    from decimal import Decimal
    assert value['renderer_version'] == 'xlsx-values-v1'
    first, second = value['sheets']
    assert [first['name'], second['name']] == ['复杂成绩', '日期与隐藏'] and second['state'] == 'hidden'
    cells, extra = [{cell['address']: cell for cell in sheet['cells']} for sheet in (first, second)]
    assert cells['A1']['value'] == 'MERGED TITLE' and cells['A2']['value'] == '数学'
    assert cells['C2']['value'] == 'TRUE' and cells['C3']['value'] == 'FALSE'
    assert cells['B4']['formula'] and not cells['B4']['cache_missing'] and Decimal(cells['B4']['value']) == 175
    assert cells['B5']['value'] == '#DIV/0!' and cells['B5']['formula']
    assert cells['B6']['cache_missing'] and cells['B6']['value'] == '公式无缓存值'
    assert Decimal(extra['A1']['value']) == (date(2026, 11, 12) - date(1899, 12, 30)).days
    assert extra['B1']['value'] == '<script>字面数据</script>'
    assert extra['C1']['value'] == '=WEBSERVICE("https://example.invalid")' and not extra['C1']['formula']


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--exe', type=Path)
    parser.add_argument('--test-root', type=Path, required=True)
    parser.add_argument('--runtime', type=Path)
    parser.add_argument('--docx', type=Path, required=True)
    parser.add_argument('--pptx', type=Path, required=True)
    parser.add_argument('--complex-xlsx', type=Path, help='Enable FMT-01 page/layout and inert workbook matrix')
    args = parser.parse_args()
    root = args.test_root.resolve()
    root.mkdir()
    fixtures = [args.docx.resolve(strict=True), args.pptx.resolve(strict=True)]
    if args.complex_xlsx:
        fixtures.append(args.complex_xlsx.resolve(strict=True))
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
            if fixture.suffix == '.xlsx':
                check_complex_workbook(doc)
                assert doc['sha256'] == checksum and hashlib.sha256(fixture.read_bytes()).hexdigest() == checksum
                results.append(dict(format='.xlsx', sheets=len(doc['sheets']), cells=doc['cell_count'],
                                    values_only=True, source_preserved=True))
                print(json.dumps(results[-1]), flush=True)
                continue
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
            layout = check_complex_pdf(root / 'data' / relative, fixture.suffix) if args.complex_xlsx else None
            if fixture.suffix == '.docx':
                assert re.search(r'x\s*2', text), 'OMML formula disappeared from derived PDF'
            else:
                assert text.count('数学') >= 2 and text.count('英语') >= 2, 'Chart labels disappeared from derived PDF'
            for number in range(1, value['page_count'] + 1) if args.complex_xlsx else {1, value['page_count']}:
                page = request(endpoint + '/previews/' + value['id'] + '/page?page=' + str(number))
                png = base64.b64decode(page['image_base64'])
                assert png.startswith(b'\x89PNG')
                (root / f'{fixture.suffix[1:]}-page{number}.png').write_bytes(png)
            assert request(endpoint + '/previews', body)['id'] == value['id']
            assert hashlib.sha256(fixture.read_bytes()).hexdigest() == checksum
            jobs.append((endpoint, value['id'], body))
            results.append(dict(format=fixture.suffix, pages=value['page_count'], pdf_bytes=value['pdf_size'],
                                source_preserved=True, cancelled_retry=True, cache_reused=True,
                                math_or_chart_checked=True, layout=layout))
            print(json.dumps(results[-1]), flush=True)
        stop()
        request = launch()
        for endpoint, identifier, body in jobs:
            assert request(endpoint + '/document')['preview']['id'] == identifier
            assert request(endpoint + '/previews', body)['id'] == identifier
        if args.complex_xlsx:
            check_complex_workbook(request(prefix + '/nodes/' + node + '/document'))
        stop()
        with sqlite3.connect(root / 'data/study.db') as db:
            migrations = Config()
            migrations.set_main_option('script_location', str(Path(__file__).resolve().parents[1] / 'backend/migrations'))
            assert db.execute('SELECT version_num FROM alembic_version').fetchone() == (ScriptDirectory.from_config(migrations).get_current_head(),)
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
