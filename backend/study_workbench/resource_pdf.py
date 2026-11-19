"""One selected PDF page, bounded UTF-16 allocation and a disposable byte-only child."""
import ctypes
import hashlib
import json
import os
import queue
import subprocess
import sys
import threading
from pathlib import Path
from time import monotonic

from fastapi import HTTPException

SOURCE_BYTES = 8 * 1024 * 1024
OUTPUT_BYTES = 128 * 1024
TEXT_UNITS = 16384
VERSION = 'pdfium-page-text-v1'


class PdfLimit(ValueError):
    pass


def extract(data, page):
    import pypdfium2 as pdfium

    if type(page) is not int or not 1 <= page <= 2000 or len(data) > SOURCE_BYTES:
        raise PdfLimit()
    with pdfium.PdfDocument(data) as document:
        count = len(document)
        if not 0 < count <= 2000 or page > count:
            raise IndexError()
        current = document[page - 1]
        try:
            textpage = current.get_textpage()
            try:
                left, bottom, right, top = current.get_bbox()
                args = (textpage.raw, left, top, right, bottom)
                units = pdfium.raw.FPDFText_GetBoundedText(*args, None, 0)
                if not 0 <= units <= TEXT_UNITS:
                    raise PdfLimit()
                buffer = (ctypes.c_ushort * units)()
                written = pdfium.raw.FPDFText_GetBoundedText(*args, buffer, units) if units else 0
                if written != units:
                    raise ValueError('Native text length changed')
                text = bytes(buffer).decode('utf-16-le', errors='strict')
                raw = text.encode('utf-8', errors='strict')
                if len(raw) > 64 * 1024:
                    raise PdfLimit()
                return dict(text=text, page=page, page_count=count, extractor_version=VERSION,
                            pypdfium2_version=pdfium.PYPDFIUM_INFO.version, pdfium_version=pdfium.PDFIUM_INFO.version,
                            text_sha256=hashlib.sha256(raw).hexdigest(),
                            text_status='text' if text else 'no_extractable_text')
            finally:
                textpage.close()
        finally:
            current.close()


def worker():
    try:
        options = json.loads(sys.stdin.buffer.readline(4096))
        if set(options) != {'page'}:
            raise ValueError()
        data = sys.stdin.buffer.read(SOURCE_BYTES + 1)
        value = extract(data, options['page'])
    except PdfLimit:
        value = {'error': 'budget'}
    except IndexError:
        value = {'error': 'page'}
    except Exception:
        value = {'error': 'invalid'}
    raw = json.dumps(value, ensure_ascii=False, allow_nan=False).encode('utf-8')
    if len(raw) >= OUTPUT_BYTES:
        raw = b'{"error":"budget"}'
    sys.stdout.buffer.write(raw)
    sys.stdout.buffer.flush()


def page_text(data, page, deadline):
    from .document_files import VIEW_SLOTS

    if not VIEW_SLOTS.acquire(blocking=False):
        raise HTTPException(429, '已有两个文件正在处理，请稍后重试')
    process, threads = None, []
    try:
        if monotonic() >= deadline:
            raise HTTPException(422, '资料正文处理超过20秒；原件保留')
        if len(data) > SOURCE_BYTES:
            raise HTTPException(413, 'PDF授权源超过8MiB；原件保留')
        command = [sys.executable]
        if not getattr(sys, 'frozen', False):
            command += ['-m', 'study_workbench']
        command += ['--read-resource-pdf']
        environment = {key: os.environ[key] for key in ('SYSTEMROOT', 'WINDIR', 'TEMP', 'TMP') if key in os.environ}
        environment.update(PYTHONUTF8='1', PYTHONIOENCODING='utf-8', PYTHONDONTWRITEBYTECODE='1',
                           PYTHONPATH=str(Path(__file__).resolve().parents[1]),
                           PATH=str(Path(os.environ.get('SystemRoot', sys.executable)) / 'System32'))
        if os.name == 'nt' and not getattr(sys, 'frozen', False):
            # Own the actual interpreter, not a venv redirector whose child could outlive a timeout.
            command[0] = sys._base_executable
            environment['__PYVENV_LAUNCHER__'] = sys.executable
        process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                   env=environment, bufsize=0, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        result = queue.Queue(maxsize=1)

        def write():
            try:
                pending = memoryview(json.dumps({'page': page}).encode() + b'\n' + data)
                while pending:
                    if monotonic() >= deadline:
                        break
                    size = process.stdin.write(pending[:65536])
                    if not size:
                        break
                    pending = pending[size:]
            except (OSError, ValueError):
                pass
            finally:
                try:
                    process.stdin.close()
                except OSError:
                    pass

        def read():
            raw = bytearray()
            try:
                while len(raw) < OUTPUT_BYTES:
                    part = process.stdout.read(min(4096, OUTPUT_BYTES - len(raw)))
                    if not part:
                        result.put((False, bytes(raw)))
                        return
                    raw.extend(part)
                try:
                    process.kill()
                except OSError:
                    pass
                result.put((True, b''))
            except (OSError, ValueError):
                result.put((False, b''))

        threads = [threading.Thread(target=operation, daemon=True) for operation in (write, read)]
        for thread in threads:
            thread.start()
        overflow, raw = result.get(timeout=max(.001, deadline - monotonic()))
        if overflow:
            raise HTTPException(413, 'PDF正文子进程输出超限；未返回截断内容')
        process.wait(timeout=max(.001, deadline - monotonic()))
        if monotonic() >= deadline:
            raise HTTPException(422, '资料正文处理超过20秒；原件保留')
        if process.returncode:
            raise ValueError('Worker failed')
        value = json.loads(raw)
        if 'error' in value:
            code = 413 if value['error'] == 'budget' else 409 if value['error'] == 'page' else 422
            raise HTTPException(code, 'PDF正文不可提取、页码无效或超限；原件保留')
        text = value['text']
        if (set(value) != {'text', 'page', 'page_count', 'extractor_version', 'pypdfium2_version',
                          'pdfium_version', 'text_sha256', 'text_status'}
                or not isinstance(text, str) or len(text.encode('utf-8')) > 64 * 1024
                or type(value['page']) is not int or value['page'] != page
                or type(value['page_count']) is not int or not page <= value['page_count'] <= 2000
                or value['text_status'] != ('text' if text else 'no_extractable_text')
                or any(not isinstance(value[k], str) or not 1 <= len(value[k]) <= 128
                       for k in ('pypdfium2_version', 'pdfium_version'))
                or value['extractor_version'] != VERSION
                or hashlib.sha256(text.encode('utf-8')).hexdigest() != value['text_sha256']):
            raise ValueError('Invalid worker result')
        return value
    except (queue.Empty, subprocess.TimeoutExpired):
        raise HTTPException(422, '资料正文处理超过20秒；原件保留') from None
    except (OSError, ValueError, KeyError, TypeError):
        raise HTTPException(422, 'PDF正文处理失败；原件保留') from None
    finally:
        try:
            if process is not None:
                if process.poll() is None:
                    process.kill()
                try:
                    process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    raise HTTPException(422, '资料子进程未能及时结束；未返回正文') from None
                for thread in threads:
                    thread.join(timeout=1)
                process.stdin.close()
                process.stdout.close()
        finally:
            VIEW_SLOTS.release()
