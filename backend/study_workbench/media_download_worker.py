"""Disposable download process: no business token, SQL or user-selected destination."""
import json
import shutil
import sys
import threading
import time
from pathlib import Path

from .media_download_http import LIMIT, DownloadError, SiteNetworkBudget, transfer


def worker():
    cancelled = threading.Event()
    def parent():
        sys.stdin.read()
        cancelled.set()
    try:
        options = json.loads(sys.stdin.buffer.readline(32768))
        threading.Thread(target=parent, daemon=True).start()
        deadline, last = time.monotonic() + 900, 0.0
        budget = None
        if options.get('site_host') is not None:
            budget = SiteNetworkBudget(**options['site_budget'])
            deadline = min(deadline, options['deadline'])
        def check():
            if cancelled.is_set() or time.monotonic() > deadline:
                raise RuntimeError('下载已暂停或超时，已存部分保留')
        def progress(value):
            nonlocal last
            remaining = (value['total'] if value['total'] is not None else LIMIT) - value['received']
            if shutil.disk_usage(Path(options['path']).parent).free < remaining + 16 * 1024 * 1024:
                raise DownloadError('下载空间不足，已存部分保留')
            now = time.monotonic()
            if now - last >= .2:
                print(json.dumps({'progress': value}), flush=True)
                last = now
        result = transfer(options['url'], Path(options['path']), options['suffix'],
                          offset=options['offset'], etag=options.get('etag'), partial_sha256=options.get('partial_sha256'),
                          site_host=options.get('site_host'), expected_size=options.get('expected_size'), budget=budget,
                          checkpoint=check, progress=progress)
        print(json.dumps({'result': result}), flush=True)
    except (DownloadError, RuntimeError) as error:
        print(json.dumps({'error': str(error)}), flush=True)
    except Exception:
        print(json.dumps({'error': '下载未完成：格式、配置或工作进程异常；已存部分保留'}), flush=True)
