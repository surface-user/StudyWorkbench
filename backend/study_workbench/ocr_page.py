"""Read one selected PDF page with the pinned offline Windows component."""

import base64
import csv
import ctypes
import io
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from fastapi import HTTPException

from . import ocr_component
from .document_view_worker import render
from .office_runtime import WindowsProcessJob

MAX_TSV = 1024 * 1024
MAX_RESULT = 2 * MAX_TSV
HEADER = 'level page_num block_num par_num line_num word_num left top width height conf text'.split()


def preview_words(raw, width, height, language):
    if len(raw) > MAX_TSV:
        raise ValueError('OCR output exceeds budget')
    rows = csv.DictReader(io.StringIO(raw.decode('utf-8')), delimiter='\t', quoting=csv.QUOTE_NONE)
    if rows.fieldnames != HEADER:
        raise ValueError('Unexpected OCR header')
    parts, regions, warnings = [], [], []
    last_line, length = None, 0
    page_seen = False
    for row in rows:
        if None in row or None in row.values() or row['page_num'] != '1':
            raise ValueError('Invalid OCR row')
        if row['level'] == '1':
            if page_seen or (int(row['width']), int(row['height'])) != (width, height):
                raise ValueError('Unexpected OCR dimensions')
            page_seen = True
        if row['level'] != '5':
            continue
        text = row['text'].strip()
        x, y, w, h = (int(row[k]) for k in ('left', 'top', 'width', 'height'))
        confidence = float(row['conf'])
        if not (page_seen and text and 0 <= x < x + w <= width and 0 <= y < y + h <= height
                and 0 <= confidence <= 100):
            raise ValueError('Invalid OCR word')
        line = tuple(row[k] for k in ('block_num', 'par_num', 'line_num'))
        separator = ''
        if regions:
            if line != last_line:
                separator = '\n'
            elif language == 'eng' or (parts[-1][-1].isascii() and text[0].isascii()):
                separator = ' '
        length += len(separator) + len(text)
        if length > 20000 or len(regions) >= 4000:
            warnings.append('truncated')
            break
        parts.append(separator + text)
        regions.append({'text': text, 'confidence': confidence, 'box': [x / width, y / height,
                                                                           (x + w) / width, (y + h) / height]})
        last_line = line
    if not page_seen:
        raise ValueError('Missing OCR page')
    if not regions and 'truncated' not in warnings:
        warnings.append('no_text')
    if any(word['confidence'] < 60 for word in regions):
        warnings.append('low_confidence')
    return {'text': ''.join(parts), 'regions': regions, 'warnings': warnings}


def component_directory():
    override = os.environ.get('STUDY_OCR_RUNTIME')
    root = (Path(override) if override else
            (Path(sys.executable).parent.parent / 'converters/ocr' if getattr(sys, 'frozen', False)
             else Path(__file__).resolve().parents[2] / '.local/release-tools/ocr'))
    if os.name != 'nt' or not root.is_absolute() or str(root).startswith(('\\\\', '//')):
        raise ValueError('OCR requires a local Windows component')
    ocr_component.verify(root)
    return root


def worker(page, language):
    from PIL import Image

    try:
        root = component_directory()
    except (ValueError, OSError):
        print('{"error":"component"}', flush=True)
        return
    try:
        if language not in {'eng', 'chi_sim'} or not 1 <= page <= 2000:
            raise ValueError('Unsupported page or language')
        data = sys.stdin.buffer.read(8 * 1024 * 1024 + 1)
        if not data.startswith(b'%PDF-') or len(data) > 8 * 1024 * 1024:
            raise ValueError('Invalid PDF input')
        rendered = render(data, 'pdf-page', page)
        with Image.open(io.BytesIO(base64.b64decode(rendered['image_base64'], validate=True))) as picture:
            width, height = picture.size
            if not (0 < width <= 2048 and 0 < height <= 2048):
                raise ValueError('Invalid bitmap')
            command = [str(root / 'bin/tesseract.exe'), 'stdin', 'stdout', '--tessdata-dir', str(root / 'tessdata'),
                       '-l', language, '--oem', '1', '--psm', '6', '-c', 'tessedit_create_tsv=1']
            if getattr(sys, 'frozen', False) and not ctypes.windll.kernel32.SetDllDirectoryW(None):
                raise OSError('Could not isolate DLL lookup')
            with tempfile.TemporaryFile() as pgm:
                with picture.convert('L') as grayscale:
                    grayscale.save(pgm, 'PPM')
                pgm.seek(0)
                environment = {key: os.environ[key] for key in ('SystemRoot', 'TMP', 'TEMP') if key in os.environ}
                with subprocess.Popen(command, stdin=pgm, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                      creationflags=subprocess.CREATE_NO_WINDOW, env=environment) as process:
                    raw = process.stdout.read(MAX_TSV + 1)
                    if len(raw) > MAX_TSV:
                        process.kill()
                        raise ValueError('OCR output exceeds budget')
                    if process.wait():
                        raise ValueError('OCR failed')
        result = {**preview_words(raw, width, height, language), 'page': page, 'page_count': rendered['page_count'],
                  'language': language, 'source': 'ocr', 'confirmed': False, 'engine_version': '5.5.4',
                  'model_version': 'tessdata_fast-4.1.0',
                  'model_sha256': ocr_component.FILES[f'tessdata/{language}.traineddata'][1]}
        sys.stdout.buffer.write(json.dumps(result, ensure_ascii=False, allow_nan=False).encode('utf-8'))
    except Exception:
        print('{"error":"document"}', flush=True)


def recognize(data, page, language, cancelled):
    if os.name != 'nt':
        raise HTTPException(503, '当前离线 OCR 组件仅支持 Windows x64')
    deadline = time.monotonic() + 25
    with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryFile() as source, \
            tempfile.TemporaryFile() as output, open(os.devnull, 'wb') as errors:
        source.write(data)
        source.seek(0)
        env = {'SystemRoot': os.environ['SystemRoot'], 'TEMP': directory, 'TMP': directory,
               'PYTHONUTF8': '1', 'PYTHONIOENCODING': 'utf-8'}
        if 'STUDY_OCR_RUNTIME' in os.environ:
            env['STUDY_OCR_RUNTIME'] = os.environ['STUDY_OCR_RUNTIME']
        command = [sys.executable]
        if not getattr(sys, 'frozen', False):
            env['PYTHONPATH'] = str(Path(__file__).resolve().parents[1])
            command.extend(['-m', 'study_workbench'])
        command.extend(['--ocr-page', str(page), language])
        job, process = WindowsProcessJob(), None
        try:
            process = job.start(command, directory, env, streams=(source, output, errors))
            while True:
                if cancelled.is_set():
                    raise HTTPException(409, '扫描页识别已取消')
                if time.monotonic() >= deadline:
                    raise HTTPException(408, '扫描页识别超过 25 秒')
                if process.poll() is not None:
                    break
                cancelled.wait(.05)
            output.seek(0)
            raw = output.read(MAX_RESULT + 1)
            if process.returncode or len(raw) > MAX_RESULT:
                raise ValueError('OCR worker failed')
            result = json.loads(raw)
            if result.get('error') == 'component':
                raise HTTPException(503, '离线 OCR 组件缺失或校验失败')
            if 'error' in result or result.get('page') != page or result.get('language') != language:
                raise ValueError('Invalid OCR result')
            return result
        except (OSError, ValueError) as error:
            raise HTTPException(422, '扫描页识别失败，请检查页码、文档或资源限额') from error
        finally:
            job.close()
            if process is not None:
                try:
                    process.wait(timeout=5)
                finally:
                    process.close()
