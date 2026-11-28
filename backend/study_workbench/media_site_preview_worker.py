"""Disposable metadata worker with no token, database or media destination."""
import json
import re
import sys
from threading import Event, Thread

from .bilibili_preview import OUTPUT_LIMIT, DownloadError, PreviewHTTPError, extract


def worker():
    cancelled = Event()
    try:
        line = sys.stdin.buffer.readline(32768)
        options = json.loads(line)
        if not isinstance(options, dict) or set(options) not in ({'url'}, {'url','selected_refs'}):
            raise DownloadError('预览输入字段无效')

        refs = options.get('selected_refs', [])
        if (not isinstance(refs, list) or 'selected_refs' in options and (len(refs) != 2 or
                any(not isinstance(ref, str) or not re.fullmatch(role+'-[a-f0-9]{64}', ref)
                    for role, ref in zip(('video','audio'), refs)))):
            raise DownloadError('选择引用无效')

        def parent():
            sys.stdin.read()
            cancelled.set()

        Thread(target=parent, daemon=True).start()

        def check():
            if cancelled.is_set():
                raise DownloadError('预览已取消')

        packet = json.dumps({'result': extract(options['url'], checkpoint=check, selected_refs=refs)}, ensure_ascii=False).encode('utf-8')
        if len(packet) + 1 > OUTPUT_LIMIT:
            raise DownloadError('预览结果超过128KiB')
        sys.stdout.buffer.write(packet + b'\n')
        sys.stdout.buffer.flush()
    except DownloadError as error:
        packet = {'error': str(error)}
        if isinstance(error, PreviewHTTPError):
            packet['error_diagnostic'] = error.diagnostic
        print(json.dumps(packet, ensure_ascii=False), flush=True)
    except Exception:
        print(json.dumps({'error': '预览未完成：输入、站点或工作进程异常'}, ensure_ascii=False), flush=True)
