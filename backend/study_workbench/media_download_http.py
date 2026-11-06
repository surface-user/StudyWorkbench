"""Pinned HTTPS transport. Queue ownership, rights consent and media publication stay in business code."""
import hashlib
import http.client
import ipaddress
import os
import re
import socket
import ssl
from urllib.parse import quote, urljoin, urlsplit, urlunsplit

LIMIT = 512 * 1024 * 1024
CHUNK = 256 * 1024
DENIED = tuple(ipaddress.ip_network(value) for value in (
    '0.0.0.0/8', '10.0.0.0/8', '100.64.0.0/10', '127.0.0.0/8', '169.254.0.0/16', '172.16.0.0/12',
    '192.0.0.0/24', '192.0.2.0/24', '192.88.99.0/24', '192.168.0.0/16', '198.18.0.0/15',
    '198.51.100.0/24', '203.0.113.0/24', '224.0.0.0/4', '240.0.0.0/4'))


class DownloadError(ValueError):
    """Deliberately excludes URLs, credentials, socket addresses and remote response bodies."""


def parse_url(value):
    if (not isinstance(value, str) or not 0 < len(value) <= 8192 or '#' in value or '\\' in value
            or any(c.isspace() or ord(c) < 32 or ord(c) == 127 for c in value)):
        raise DownloadError('下载网址无效或含控制字符')
    try:
        parts = urlsplit(value)
        host = parts.hostname or ''
        if parts.scheme != 'https' or parts.port not in {None, 443} or parts.username is not None or parts.password is not None:
            raise ValueError()
        labels = host.split('.')
        if (len(host) > 253 or len(labels) < 2 or not host.isascii() or not re.search('[a-z]', labels[-1])
                or any(not re.fullmatch(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?', label) for label in labels)
                or host.endswith(('.localhost', '.local', '.internal', '.home.arpa'))):
            raise ValueError()
        path = quote(parts.path or '/', safe="/%:@!$&'()*+,;=-._~")
        query = quote(parts.query, safe="/%?:@!$&'()*+,;=-._~")
        if re.search(r'%(?![0-9A-Fa-f]{2})', path + query):
            raise ValueError()
        canonical = urlunsplit(('https', host, path, query, ''))
        if len(canonical) > 8192:
            raise ValueError()
        return canonical, host, path + ('?' + query if query else '')
    except (ValueError, UnicodeError):
        raise DownloadError('仅支持无凭据的HTTPS/443域名直链') from None


def resolve(host):
    try:
        answers = socket.getaddrinfo(host, 443, family=socket.AF_INET, type=socket.SOCK_STREAM)
        addresses = list(dict.fromkeys(answer[4][0] for answer in answers))
        if not 0 < len(addresses) <= 16:
            raise ValueError()
        for value in addresses:
            address = ipaddress.IPv4Address(value)
            if not address.is_global or any(address in network for network in DENIED):
                raise ValueError()
        return addresses[0]
    except (OSError, ValueError):
        raise DownloadError('下载域名无法解析为允许的公网IPv4地址') from None


class PinnedHTTPS(http.client.HTTPSConnection):
    def __init__(self, host, address):
        self.address = address
        self.tls = ssl.create_default_context()
        self.tls.set_alpn_protocols(['http/1.1'])
        super().__init__(host, port=443, timeout=10, context=self.tls)

    def connect(self):
        raw = socket.create_connection((self.address, 443), timeout=10)
        try:
            self.sock = self.tls.wrap_socket(raw, server_hostname=self.host)
        except BaseException:
            raw.close()
            raise


def strong_etag(value):
    return isinstance(value, str) and bool(re.fullmatch(r'"[\x21\x23-\x7e]{0,510}"', value))


def transfer(url, path, suffix, *, offset=0, etag=None, partial_sha256=None, checkpoint=lambda: None, progress=lambda value: None):
    """Write only a caller-owned fresh/partial file. Failure never truncates existing bytes."""
    from .media_library import media_mime

    allowed = {'.mp4': {'video/mp4'}, '.webm': {'video/webm'}, '.m4a': {'audio/mp4', 'audio/x-m4a'}}
    if (suffix not in allowed or type(offset) is not int or not 0 <= offset < LIMIT
            or offset and (not strong_etag(etag) or not isinstance(partial_sha256, str)
                           or not re.fullmatch('[a-f0-9]{64}', partial_sha256))):
        raise DownloadError('恢复参数或媒体格式无效')
    if offset:
        try:
            info = path.lstat()
            if not path.is_file() or path.is_symlink() or getattr(info, 'st_file_attributes', 0) & 0x400 or info.st_size != offset:
                raise ValueError()
        except (OSError, ValueError):
            raise DownloadError('已存部分长度或文件状态变化，未追加') from None
    current, connection = url, None
    try:
        for redirects in range(4):
            checkpoint()
            current, host, target = parse_url(current)
            address = resolve(host)
            checkpoint()
            connection = PinnedHTTPS(host, address)
            headers = {'Accept-Encoding': 'identity', 'User-Agent': 'StudyWorkbench/1.0', 'Connection': 'close'}
            if offset:
                headers.update({'Range': f'bytes={offset}-', 'If-Range': etag})
            connection.request('GET', target, headers=headers)
            response = connection.getresponse()
            fields = response.getheaders()
            if sum(len(k) + len(v) for k, v in fields) > 32768:
                raise DownloadError('下载响应头超限')
            values = {}
            for key, value in fields:
                key = key.lower()
                if key in values and key in {'content-length', 'content-range', 'transfer-encoding', 'content-encoding', 'location', 'etag', 'content-type'}:
                    raise DownloadError('下载响应头重复或存在歧义')
                values[key] = value.strip()
            if response.status in {301, 302, 303, 307, 308}:
                location = values.get('location')
                if not location or redirects == 3:
                    raise DownloadError('下载重定向缺失或次数超限')
                current = urljoin(current, location)
                connection.close()
                connection = None
                continue
            if response.status != (206 if offset else 200):
                raise DownloadError('下载响应不支持当前请求；旧部分保留')
            encoding, chunked = values.get('content-encoding', 'identity').lower(), values.get('transfer-encoding', '').lower()
            length = values.get('content-length')
            if (encoding != 'identity' or chunked not in {'', 'chunked'} or chunked and length is not None
                    or length is not None and not re.fullmatch(r'[0-9]{1,10}', length)):
                raise DownloadError('下载响应编码或长度无效')
            length = int(length) if length is not None else None
            total = offset + length if length is not None else None
            if values.get('content-type', '').split(';', 1)[0].strip().lower() not in allowed[suffix] | {'application/octet-stream'}:
                raise DownloadError('下载响应不是所选媒体格式')
            returned_etag = values.get('etag')
            if offset:
                match = re.fullmatch(r'bytes ([0-9]{1,10})-([0-9]{1,10})/([0-9]{1,10})', values.get('content-range', ''))
                if (not match or returned_etag != etag or not strong_etag(returned_etag)
                        or int(match[1]) != offset or int(match[2]) != int(match[3]) - 1
                        or length != int(match[3]) - offset):
                    raise DownloadError('恢复范围或版本变化，旧部分未追加')
                total = int(match[3])
            elif 'content-range' in values:
                raise DownloadError('未请求的媒体范围响应')
            if total is not None and not offset < total <= LIMIT:
                raise DownloadError('下载为空或超过512MiB')
            received, header, checksum = offset, b'', hashlib.sha256()
            if offset:
                with path.open('rb') as old:
                    while chunk := old.read(CHUNK):
                        checkpoint()
                        header = (header + chunk[:32])[:32]
                        checksum.update(chunk)
                if checksum.hexdigest() != partial_sha256 or path.stat().st_size != offset:
                    raise DownloadError('已存部分内容变化，未追加')
            progress({'received': received, 'total': total, 'etag': returned_etag if strong_etag(returned_etag) else None,
                      'partial_sha256': checksum.hexdigest()})
            with path.open('ab' if offset else 'xb') as output:
                while True:
                    checkpoint()
                    chunk = response.read(CHUNK)
                    if not chunk:
                        break
                    received += len(chunk)
                    if received > LIMIT or total is not None and received > total:
                        raise DownloadError('下载实际字节超过预算，已存部分保留')
                    header = (header + chunk[:32])[:32]
                    checksum.update(chunk)
                    output.write(chunk)
                    progress({'received': received, 'total': total, 'etag': returned_etag if strong_etag(returned_etag) else None,
                              'partial_sha256': checksum.hexdigest()})
                output.flush()
                os.fsync(output.fileno())
            if total is not None and received != total:
                raise DownloadError('下载长度不足，已存部分保留')
            mime = media_mime(suffix, header, received)
            return {'size': received, 'sha256': checksum.hexdigest(), 'mime': mime,
                    'etag': returned_etag if strong_etag(returned_etag) else None, 'final_url': current}
        raise DownloadError('下载重定向次数超限')
    except (OSError, http.client.HTTPException):
        raise DownloadError('下载网络或写入失败，已存部分保留') from None
    finally:
        if connection is not None:
            connection.close()
