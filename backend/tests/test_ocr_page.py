import hashlib
import json
import os
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from study_workbench import ocr_page
from test_document_files import add
from test_explorer import PREFIX, client

HEADER = b'level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext\n'
PAGE = b'1\t1\t0\t0\t0\t0\t0\t0\t100\t50\t-1\t\n'
WORD = b'5\t1\t1\t1\t1\t1\t10\t5\t50\t20\t45.5\tFirst\n'
PDF = b'%PDF-self-authored OCR fixture'
BODY = {'expected_sha256': hashlib.sha256(PDF).hexdigest(), 'page': 1,
        'language': 'eng', 'request_id': '1' * 32}


def test_words_positions_confidence_line_breaks_blank_and_budget():
    result = ocr_page.preview_words(HEADER + PAGE + WORD + WORD.replace(b'1\t1\t10', b'2\t2\t10'), 100, 50, 'eng')
    assert result['text'] == 'First\nFirst' and result['warnings'] == ['low_confidence']
    assert result['regions'][0] == {'text': 'First', 'box': [.1, .1, .6, .5], 'confidence': 45.5}
    assert ocr_page.preview_words(HEADER + PAGE, 100, 50, 'eng')['warnings'] == ['no_text']
    long = ocr_page.preview_words(HEADER + PAGE + WORD * 4005, 100, 50, 'eng')
    assert 'truncated' in long['warnings'] and len(long['text']) <= 20000


@pytest.mark.parametrize('raw', [b'', HEADER + WORD, HEADER + PAGE + PAGE, HEADER + PAGE + WORD.replace(b'45.5', b'nan'),
                                  HEADER + PAGE + WORD.replace(b'50\t20', b'95\t20'), HEADER + PAGE + WORD + b'bad\n'])
def test_reject_malformed_regions(raw):
    with pytest.raises(ValueError):
        ocr_page.preview_words(raw, 100, 50, 'eng')


def test_no_worker_for_wrong_scope_hash_or_untrusted_options(tmp_path, monkeypatch):
    monkeypatch.setattr(ocr_page, 'recognize', lambda *args: pytest.fail('unvalidated input reached worker'))
    with client(tmp_path) as c:
        node, _, _ = add(c, tmp_path, 'sample.pdf', PDF)
        url = f'{PREFIX}/nodes/{node}/document-ocr'
        for options, expected in [({'expected_sha256': '0' * 64}, 409), ({'page': 0}, 422),
                                  ({'language': '../eng'}, 422), ({'program': 'bad'}, 422),
                                  ({'request_id': 'bad'}, 422)]:
            assert c.post(url, json={**BODY, **options}).status_code == expected
        assert c.post(url.replace('/default/', '/other/'), json=BODY).status_code == 404


@pytest.mark.parametrize('action', ['cancel', 'replace'])
def test_discard_result_after_cancel_or_source_replacement(tmp_path, monkeypatch, action):
    started, finish = Event(), Event()

    def controlled(data, page, language, cancelled):
        assert data == PDF and page == 1 and language == 'eng'
        started.set()
        assert finish.wait(8)
        return {'text': 'unpublished'}

    monkeypatch.setattr(ocr_page, 'recognize', controlled)
    with client(tmp_path) as c, ThreadPoolExecutor(1) as pool:
        node, _, source = add(c, tmp_path, 'sample.pdf', PDF)
        url = f'{PREFIX}/nodes/{node}/document-ocr'
        stop = url + '/' + BODY['request_id'] + '/cancel'
        running = pool.submit(c.post, url, json=BODY)
        try:
            assert started.wait(6)
            assert c.post(url, json=BODY).status_code == 409
            assert c.post(stop.replace('/default/', '/other/')).status_code == 404
            if action == 'cancel':
                assert c.post(stop).json() == {'cancelled': True}
            else:
                source.write_bytes(b'%PDF-changed')
        finally:
            finish.set()
        result = running.result(timeout=6)
        assert result.status_code == 409 and 'unpublished' not in result.text
        assert c.post(stop).status_code == 404


@pytest.mark.skipif(os.name != 'nt', reason='Native Windows process job')
def test_absent_runtime_fails_closed_and_worker_cancellation(tmp_path, monkeypatch):
    monkeypatch.setenv('STUDY_OCR_RUNTIME', str(tmp_path / 'missing'))
    with client(tmp_path) as c:
        node, _, _ = add(c, tmp_path, 'sample.pdf', PDF)
        url = f'{PREFIX}/nodes/{node}/document-ocr'
        r = c.post(url, json=BODY)
        assert r.status_code == 503 and '组件' in json.dumps(r.json(), ensure_ascii=False)
    cancel = Event()
    cancel.set()
    with pytest.raises(HTTPException) as caught:
        ocr_page.recognize(PDF, 1, 'eng', cancel)
    assert caught.value.status_code == 409


@pytest.mark.skipif(os.name != 'nt', reason='Native Windows process job')
def test_deadline_discards_worker_and_releases_handles(monkeypatch):
    clock = iter([0, 26])
    monkeypatch.setattr(ocr_page, 'time', SimpleNamespace(monotonic=lambda: next(clock)))
    with pytest.raises(HTTPException) as caught:
        ocr_page.recognize(PDF, 1, 'eng', Event())
    assert caught.value.status_code == 408

@pytest.mark.skipif(os.name != 'nt', reason='Windows kill-on-close job and wait handles')
def test_abrupt_owner_exit_reaps_the_worker_and_its_child(tmp_path):
    import _winapi
    import subprocess
    import sys
    import time
    from pathlib import Path

    worker = tmp_path / 'worker.py'
    worker.write_text("""import json, os, subprocess, sys, time
from pathlib import Path
child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(45)'])
Path('pending').write_text(json.dumps([os.getpid(), child.pid]))
Path('pending').rename('ready')
time.sleep(45)
""", encoding='utf-8')
    owner = tmp_path / 'owner.py'
    owner.write_text("""import os, sys, tempfile
from study_workbench.office_runtime import WindowsProcessJob
job = WindowsProcessJob()
with tempfile.TemporaryFile() as source, tempfile.TemporaryFile() as output, open(os.devnull, 'wb') as errors:
    job.start([sys.executable, 'worker.py'], os.getcwd(), dict(os.environ), streams=(source, output, errors))
    sys.stdin.buffer.read(1)
    os._exit(0)
""", encoding='utf-8')
    env = {**os.environ, 'PYTHONPATH': str(Path(__file__).resolve().parents[1])}
    with subprocess.Popen([sys.executable, str(owner)], env=env, cwd=tmp_path, stdin=subprocess.PIPE) as process:
        handles = []
        try:
            ready = tmp_path / 'ready'
            deadline = time.monotonic() + 15
            while not ready.exists() and process.poll() is None and time.monotonic() < deadline:
                time.sleep(.05)
            assert ready.is_file()
            for pid in json.loads(ready.read_text()):
                handles.append(_winapi.OpenProcess(0x100000, False, pid))
            assert len(handles) == 2 and all(_winapi.WaitForSingleObject(h, 0) == 258 for h in handles)
            process.communicate(b'x', timeout=10)
            assert process.returncode == 0
            assert all(_winapi.WaitForSingleObject(h, 5000) == 0 for h in handles)
        finally:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=5)
            for handle in handles:
                _winapi.CloseHandle(handle)
