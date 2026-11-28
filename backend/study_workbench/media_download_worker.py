"""Disposable download process: no business token, SQL or user-selected destination."""
import json
import shutil
import sys
import threading
import time
from pathlib import Path

from .media_download_http import LIMIT, DownloadError, SiteNetworkBudget, transfer


def fetch_pair(options, check, emit):
    from . import media_probe_runtime as runtime
    from .imports import resource_path
    from .media_inputs import inspect_media_input
    from .media_sources import (
        ReceivedContent,
        SitePairSource,
        attempt_context,
        attempt_record,
        source_snapshot,
    )
    from .site_pair_selection import bound_media_url

    source = source_snapshot(options['snapshot'])
    record = attempt_record(options['record'])
    urls = options['urls']
    if (not isinstance(source, SitePairSource) or not isinstance(urls, list) or len(urls) != 2
            or any(track.state != 'pending' for track in record.tracks)):
        raise DownloadError('站点工作输入无效')
    root = runtime.local_path(Path(options['root']))
    relative = attempt_context(options['workspace'], options['job'], options['attempt'], options['generation'], source, record)
    directory = runtime.local_path(resource_path(root, relative))
    if list(directory.iterdir()) != [directory/'tmp']:
        raise DownloadError('本次轨道目录已有文件，保留旧内容')
    budget = SiteNetworkBudget(**options['site_budget'])
    received = 0
    last = 0
    for selected, frozen, url in zip(source.tracks, record.tracks, urls, strict=True):
        url, host = bound_media_url(selected, url)
        target = resource_path(root, frozen.relative_path)
        def observe(value):
            nonlocal last
            check()
            if shutil.disk_usage(directory).free < budget.bytes_left + LIMIT + 16*1024*1024:
                raise DownloadError('轨道和合成输出空间不足')
            now = time.monotonic()
            if now-last >= .2:
                emit(dict(phase='copying', received=received+value['received'], total=source.input_size,
                          record=record.model_dump(mode='json')))
                last = now
        got = transfer(url, target, target.suffix, site_host=host, expected_size=selected.size_bytes,
                       budget=budget, site_track=True, checkpoint=check, progress=observe)
        actual = ReceivedContent(size=got['size'], sha256=got['sha256'])
        preview = inspect_media_input(root, frozen.relative_path, actual.size, actual.sha256, selected.mime, check)
        if len(preview['streams']) != 1 or preview['streams'][0]['role'] != selected.role:
            raise DownloadError('实际媒体与选定单轨不符')
        frozen.received, frozen.state = actual, 'copied'
        received += actual.size
        emit(dict(phase='copying', received=received, total=source.input_size, record=record.model_dump(mode='json')))
    return record.model_dump(mode='json')


def worker():
    cancelled = threading.Event()
    def parent():
        sys.stdin.read()
        cancelled.set()
    try:
        options = json.loads(sys.stdin.buffer.readline(65536))
        threading.Thread(target=parent, daemon=True).start()
        deadline, last = time.monotonic() + 900, 0.0
        budget = None
        if options.get('site_host') is not None or options.get('mode') == 'site_pair':
            budget = SiteNetworkBudget(**options['site_budget'])
            deadline = min(deadline, options['deadline'])
        def check():
            if cancelled.is_set() or time.monotonic() > deadline:
                raise RuntimeError('下载已暂停或超时，已存部分保留')
        if options.get('mode') == 'site_pair':
            result = fetch_pair(options, check, lambda value: print(json.dumps({'progress':value}), flush=True))
            print(json.dumps({'result':result}), flush=True)
            return
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
