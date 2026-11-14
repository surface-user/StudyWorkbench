"""Bounded ordinary Bilibili preview; WBI follows pinned yt-dlp's Unlicense source."""
import hashlib
import http.client
import json
import math
import re
import time
from fractions import Fraction
from urllib.parse import parse_qs, urlencode, urljoin, urlsplit

from .media_download_http import DownloadError, PinnedHTTPS, parse_url, resolve

VERSION = 'bilibili-preview-v1'
RESPONSE_LIMIT = 2 * 1024 * 1024
TOTAL_LIMIT = 8 * 1024 * 1024
OUTPUT_LIMIT = 128 * 1024
NAV = 'https://api.bilibili.com/x/web-interface/nav'
VIEW = 'https://api.bilibili.com/x/web-interface/wbi/view/detail'
PLAY = 'https://api.bilibili.com/x/player/wbi/playurl'
USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) StudyWorkbench/1.0'
HTTP_STAGES = {'/x/web-interface/nav': 'nav', '/x/web-interface/wbi/view/detail': 'view',
               '/x/player/wbi/playurl': 'playurl'}
# yt-dlp f264a6cbd1f630894da0f368df00f8aae50140e0, extractor/bilibili.py:134-167.
MIXIN = (46, 47, 18, 2, 53, 8, 23, 32, 15, 50, 10, 31, 58, 3, 45, 35, 27, 43, 5, 49,
         33, 9, 42, 19, 29, 28, 14, 39, 12, 38, 41, 13, 37, 48, 7, 16, 24, 55, 40,
         61, 26, 17, 0, 1, 60, 51, 30, 4, 22, 25, 54, 21, 56, 59, 6, 63, 57, 62, 11,
         36, 20, 34, 44, 52)


def safe_http_diagnostic(value):
    if (not isinstance(value, dict) or set(value) != {'stage', 'http_status'}
            or type(value['stage']) is not str or value['stage'] not in {'shortlink', 'nav', 'view', 'playurl'}
            or type(value['http_status']) is not int or not 100 <= value['http_status'] <= 599):
        return None
    return dict(stage=value['stage'], http_status=value['http_status'])


class PreviewHTTPError(DownloadError):
    def __init__(self, stage, http_status):
        self.diagnostic = safe_http_diagnostic({'stage': stage, 'http_status': http_status})
        if self.diagnostic is None:
            raise ValueError('Invalid fixed HTTP diagnostic')
        super().__init__('该视频暂不可预览，可能需要权限或访问限制')


def page_url(value, *, short=True):
    canonical, host, _ = parse_url(value)
    parts = urlsplit(canonical)
    if parse_qs(parts.query).get('p', ['1']) != ['1']:
        raise DownloadError('暂不支持多P视频，请选择普通单视频')
    if short and host == 'b23.tv' and re.fullmatch(r'/[A-Za-z0-9]{1,32}/?', parts.path):
        return 'https://b23.tv/' + parts.path.strip('/')
    if host in {'www.bilibili.com', 'bilibili.com'} and re.fullmatch(
            r'/video/(BV[A-Za-z0-9]{10}|av[1-9][0-9]{0,17})/?', parts.path):
        return 'https://www.bilibili.com' + parts.path.rstrip('/')
    raise DownloadError('仅支持B站普通BV或av单视频链接及b23.tv短链')


class Client:
    def __init__(self, checkpoint):
        self.checkpoint, self.requests, self.received = checkpoint, 0, 0

    def fetch(self, url, *, short=False):
        current = page_url(url) if short else url
        expected_path = urlsplit(url).path
        for redirects in range(4):
            self.checkpoint()
            current, host, target = parse_url(current)
            if short:
                canonical = page_url(current)
                if host != 'b23.tv':
                    return b'', canonical
            elif host != 'api.bilibili.com' or urlsplit(current).path != expected_path or expected_path not in {
                    '/x/web-interface/nav', '/x/web-interface/wbi/view/detail', '/x/player/wbi/playurl'}:
                raise DownloadError('预览接口重定向到了不支持的位置')
            self.requests += 1
            if self.requests > 10:
                raise DownloadError('预览请求次数超过10次')
            address = resolve(host)
            self.checkpoint()
            connection = PinnedHTTPS(host, address)
            try:
                connection.request('GET', target, headers={
                    'Accept-Encoding': 'identity', 'User-Agent': USER_AGENT,
                    'Connection': 'close', 'Referer': 'https://www.bilibili.com/',
                    'Origin': 'https://www.bilibili.com'})
                response = connection.getresponse()
                fields = response.getheaders()
                if sum(len(k) + len(v) for k, v in fields) > 32768:
                    raise DownloadError('预览响应头超过32KiB')
                values = {}
                for key, value in fields:
                    key = key.lower()
                    if key in values and key in {'content-length', 'content-range', 'content-encoding', 'transfer-encoding', 'content-type', 'location'}:
                        raise DownloadError('预览响应头重复或存在歧义')
                    values[key] = value.strip()
                if response.status in {301, 302, 303, 307, 308}:
                    if redirects == 3 or not values.get('location'):
                        raise DownloadError('预览重定向缺失或超过3跳')
                    current = urljoin(current, values['location'])
                    continue
                if response.status != 200:
                    raise PreviewHTTPError('shortlink' if short else HTTP_STAGES[expected_path], response.status)
                if short:
                    raise DownloadError('短链未返回受支持的普通视频重定向，未执行脚本')
                if 'content-range' in values:
                    raise DownloadError('未请求的预览范围响应')
                length = values.get('content-length')
                encoding = values.get('content-encoding', 'identity').lower()
                chunked = values.get('transfer-encoding', '').lower()
                if (encoding != 'identity' or chunked not in {'', 'chunked'} or chunked and length is not None
                        or length is not None and (not re.fullmatch('[0-9]{1,10}', length) or int(length) > RESPONSE_LIMIT)):
                    raise DownloadError('预览响应编码、长度或2MiB预算不符合要求')
                mime = values.get('content-type', '').split(';', 1)[0].strip().lower()
                if mime != 'application/json':
                    raise DownloadError('站点未返回预期的页面或JSON，未执行挑战内容')
                data = bytearray()
                while True:
                    self.checkpoint()
                    block = response.read(32768)
                    if not block:
                        break
                    self.received += len(block)
                    data.extend(block)
                    if len(data) > RESPONSE_LIMIT or self.received > TOTAL_LIMIT:
                        raise DownloadError('预览实际字节超过单响应2MiB或累计8MiB')
                if length is not None and len(data) != int(length):
                    raise DownloadError('预览实际长度与响应声明不符')
                return bytes(data), current
            finally:
                connection.close()
        raise DownloadError('预览重定向超过3跳')


def object_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate source field')
        result[key] = value
    return result


def reject_constant(_):
    raise ValueError('Non-finite JSON constant')


def source_json(raw):
    text = raw.decode('utf-8')
    decoder = json.JSONDecoder(object_pairs_hook=object_pairs, parse_constant=reject_constant)
    value = decoder.decode(text)
    pending, count = [(value, 0)], 0
    while pending:
        item, depth = pending.pop()
        count += 1
        if depth > 64 or count > 50000 or isinstance(item, float) and not math.isfinite(item):
            raise DownloadError('预览JSON节点、嵌套或数值超过预算')
        if isinstance(item, dict):
            pending.extend((child, depth + 1) for child in item.values())
        elif isinstance(item, list):
            pending.extend((child, depth + 1) for child in item)
    if not isinstance(value, dict):
        raise DownloadError('站点数据格式已变化')
    return value


def number(value, *, maximum=2**53 - 1, optional=False):
    if optional and value is None:
        return None
    if type(value) is not int or not 0 <= value <= maximum:
        raise DownloadError('站点数值字段无效或超限')
    return value


def plain(value, limit, *, optional=False):
    if optional and value is None:
        return None
    if not isinstance(value, str) or not 0 < len(value) <= limit or any(ord(c) < 32 and c not in '\t\r\n' for c in value):
        raise DownloadError('站点文本字段无效或超限')
    return value


def restricted(value, names):
    return any(value.get(name) not in (None, False, 0, '') for name in names)


def sign(params, key):
    params = {**params, 'wts': round(time.time())}
    params = {name: ''.join(c for c in str(value) if c not in "!'()*") for name, value in sorted(params.items())}
    params['w_rid'] = hashlib.md5((urlencode(params) + key).encode(), usedforsecurity=False).hexdigest()
    return urlencode(params)


def formats(play):
    result = []
    dash = play.get('dash') or {}
    if not isinstance(dash, dict):
        raise DownloadError('站点DASH格式字段已变化')
    for kind in ('video', 'audio'):
        tracks = dash.get(kind) or []
        if kind == 'audio':
            dolby, flac = dash.get('dolby') or {}, dash.get('flac') or {}
            if not isinstance(dolby, dict) or not isinstance(flac, dict):
                raise DownloadError('站点音轨格式字段已变化')
            extra = dolby.get('audio') or []
            if not isinstance(tracks, list) or not isinstance(extra, list):
                raise DownloadError('站点音轨格式字段已变化')
            tracks = tracks + extra + ([flac['audio']] if flac.get('audio') else [])
        if not isinstance(tracks, list) or len(result) + len(tracks) > 64:
            raise DownloadError('预览格式超过64项或字段已变化')
        for item in tracks:
            if not isinstance(item, dict) or restricted(item, ('drm_tech_type', 'drm_type', 'is_drm', 'license_url')):
                raise DownloadError('不支持加密或受限格式')
            uri = item.get('baseUrl') or item.get('base_url') or item.get('url')
            try:
                uri = parse_url(uri)[0]
            except DownloadError:
                uri = None
            mime = item.get('mimeType') or item.get('mime_type')
            container = {'video/mp4': 'mp4', 'audio/mp4': 'm4a', 'video/webm': 'webm',
                         'audio/webm': 'webm', 'audio/flac': 'flac'}.get(mime)
            fps = item.get('frameRate') or item.get('frame_rate')
            fps = float(Fraction(plain(fps, 32))) if isinstance(fps, str) else fps
            if fps is not None and (type(fps) not in (int, float) or not math.isfinite(fps) or not 0 < fps <= 1000):
                raise DownloadError('站点帧率字段无效')
            result.append(dict(format_id=f'{kind}-{len(result)}', delivery='dash_' + kind,
                               source_format_id=number(item.get('id'), optional=True),
                               container=container, codecs=plain(item.get('codecs'), 128, optional=True),
                               width=number(item.get('width'), maximum=32768, optional=True),
                               height=number(item.get('height'), maximum=32768, optional=True), fps=fps,
                               size_bytes=number(item.get('size'), optional=True), requires_merge=True,
                               download_supported=False, url=uri, fragments=None,
                               limitation='暂不支持分轨下载' if uri else '来源不是受支持的HTTPS媒体链接'))
    fragments = play.get('durl') or []
    if not isinstance(fragments, list) or len(fragments) > 64:
        raise DownloadError('预览分段超过64项或字段已变化')
    if fragments:
        urls, sizes = [], []
        for item in fragments:
            if not isinstance(item, dict):
                raise DownloadError('站点分段格式已变化')
            try:
                urls.append(parse_url(item.get('url'))[0])
            except DownloadError:
                urls.append(None)
            sizes.append(number(item.get('size'), optional=True))
        segmented = len(fragments) > 1
        result.append(dict(format_id=f'legacy-{len(result)}', delivery='segments' if segmented else 'progressive',
                           source_format_id=number(play.get('quality'), optional=True),
                           container=None, codecs=None, width=None, height=None, fps=None,
                           size_bytes=sum(sizes) if all(x is not None for x in sizes) else None,
                           requires_merge=segmented, download_supported=False,
                           url=urls[0] if not segmented else None, fragments=urls if segmented else None,
                           limitation='暂不支持分段下载' if segmented else '此格式尚未接入下载'))
    if not 0 < len(result) <= 64:
        raise DownloadError('未取得可预览格式，或格式超过64项')
    return result


def extract(url, *, checkpoint=lambda: None):
    deadline = time.monotonic() + 45

    def check():
        checkpoint()
        if time.monotonic() > deadline:
            raise DownloadError('预览超过45秒')

    try:
        client = Client(check)
        canonical = page_url(url)
        if urlsplit(canonical).hostname == 'b23.tv':
            _, canonical = client.fetch(canonical, short=True)
        nav, _ = client.fetch(NAV)
        session = source_json(nav)
        if type(session.get('code')) is not int or session['code'] not in {0, -101}:
            raise DownloadError('站点暂不允许预览，请稍后重试；未尝试其他访问方式')
        images = session['data']['wbi_img']
        keys = ''.join(urlsplit(images[name]).path.rsplit('/', 1)[-1].split('.')[0] for name in ('img_url', 'sub_url'))
        if not re.fullmatch('[0-9a-f]{64}', keys):
            raise DownloadError('站点WBI字段已变化')
        key = ''.join(keys[index] for index in MIXIN)[:32]
        expected = urlsplit(canonical).path.rsplit('/', 1)[-1]
        query = {'platform': 'web', 'bvid' if expected.startswith('BV') else 'aid':
                 expected if expected.startswith('BV') else expected[2:]}
        raw, _ = client.fetch(VIEW + '?' + sign(query, key))
        view = source_json(raw)
        if type(view.get('code')) is not int or view['code'] != 0 or not isinstance(view.get('data'), dict):
            raise DownloadError('站点明确限制访问或视频不存在，未尝试其他访问方式')
        video = view.get('data', {}).get('View')
        if not isinstance(video, dict) or not isinstance(video.get('rights'), dict):
            raise DownloadError('仅支持普通单视频，站点数据缺失或已变化')
        identifier = plain(video.get('bvid'), 12)
        aid, cid = number(video.get('aid')), number(video.get('cid'))
        if not re.fullmatch('BV[A-Za-z0-9]{10}', identifier) or expected not in {identifier, f'av{aid}'} or not aid or not cid:
            raise DownloadError('页面视频身份与请求不符')
        pages = video.get('pages')
        if not isinstance(pages, list) or len(pages) != 1:
            raise DownloadError('暂不支持多P或缺少明确分页的视频')
        if not isinstance(pages[0], dict) or number(pages[0].get('cid')) != cid:
            raise DownloadError('页面与分P视频身份不一致')
        if restricted(video, ('is_upower_exclusive', 'is_chargeable_season', 'redirect_url')) or restricted(
                video['rights'], ('pay', 'ugc_pay', 'arc_pay', 'is_stein_gate')):
            raise DownloadError('暂不支持付费、专属、互动或跳转到其他类型的视频')
        title = plain(video.get('title'), 512)
        duration = number(video.get('duration'), maximum=7 * 86400)
        raw, _ = client.fetch(PLAY + '?' + sign({'bvid': identifier, 'cid': cid, 'fnval': 4048}, key))
        response = source_json(raw)
        if type(response.get('code')) is not int or response['code'] != 0 or not isinstance(response.get('data'), dict):
            raise DownloadError('该视频未返回可用格式，可能需要权限或访问挑战')
        play = response['data']
        if 'cid' in play and number(play['cid']) != cid:
            raise DownloadError('格式与页面视频身份不符')
        descriptions = play.get('accept_description') or []
        if restricted(play, ('is_preview', 'is_pay_preview', 'is_drm', 'drm_tech_type')) or any(
                isinstance(value, str) and '试看' in value for value in descriptions):
            raise DownloadError('不将试看或受限格式作为完整视频')
        length = number(play.get('timelength'), maximum=7 * 86400 * 1000)
        if duration and length + 3000 < duration * 1000:
            raise DownloadError('播放时长少于完整视频，未采用可能的试看格式')
        result = dict(title=title, video_id=identifier, source_host='www.bilibili.com', source_url=canonical,
                      source_cid=cid,
                      extractor_version=VERSION, duration_seconds=duration, returned_formats_only=True,
                      format_source='wbi_api',
                      formats=formats(play))
        if len(json.dumps(result, ensure_ascii=False).encode('utf-8')) > OUTPUT_LIMIT:
            raise DownloadError('预览结果超过128KiB')
        check()
        return result
    except DownloadError:
        raise
    except (ValueError, TypeError, KeyError, IndexError, UnicodeError, ArithmeticError, RecursionError,
            OSError, http.client.HTTPException):
        raise DownloadError('预览未完成：网络、站点字段或格式已变化') from None
