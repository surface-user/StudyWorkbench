"""The durable confirmation contains identity and format, never a signed media address."""
import hashlib
import re
from urllib.parse import urlsplit

from .media_download_http import LIMIT, DownloadError, bilibili_media_host, parse_url


def candidate(result, preview_id, format_id):
    item = next((v for v in result['formats'] if v['format_id'] == format_id), None)
    if (item is None or not item['download_supported'] or item['delivery'] != 'progressive'
            or item['requires_merge'] or item['container'] != 'mp4'):
        raise DownloadError('此格式不能确认单文件下载')
    url, host, _ = parse_url(item['url'])
    page = 'https://www.bilibili.com/video/' + result['video_id']
    receipt = dict(preview_id=preview_id, format_id=format_id, extractor_version=result['extractor_version'],
                   video_id=result['video_id'], cid=result['source_cid'], quality=item['source_format_id'],
                   size=item['size_bytes'], duration=result['duration_seconds'], container='mp4', cdn_host=host,
                   path_sha256=hashlib.sha256(urlsplit(url).path.encode('ascii')).hexdigest())
    if not valid(receipt, page):
        raise DownloadError('站点候选身份或媒体格式无效')
    return receipt, page, url


def valid(value, page):
    keys = {'preview_id', 'format_id', 'extractor_version', 'video_id', 'cid', 'quality',
            'size', 'duration', 'container', 'cdn_host', 'path_sha256'}
    if not isinstance(value, dict) or set(value) != keys:
        return False
    text = {'preview_id': '[a-f0-9]{32}', 'format_id': 'legacy-[0-9]{1,2}',
            'video_id': 'BV[A-Za-z0-9]{10}', 'path_sha256': '[a-f0-9]{64}'}
    return (all(isinstance(value[k], str) and re.fullmatch(pattern, value[k]) for k, pattern in text.items())
            and all(type(value[k]) is int and 0 < value[k] <= limit for k, limit in
                    [('cid', 2**53-1), ('size', LIMIT), ('duration', 7*86400), ('quality', 2**53-1)])
            and value['extractor_version'] == 'bilibili-preview-v3' and value['container'] == 'mp4'
            and page == 'https://www.bilibili.com/video/' + value['video_id']
            and isinstance(value['cdn_host'], str) and bilibili_media_host(value['cdn_host']))
