import hashlib
import io
import socket
import ssl

import pytest
from study_workbench import media_download_http as net


@pytest.mark.parametrize('url', [
    'http://example.com/a.webm', 'https://user:secret@example.com/a', 'https://@example.com/a',
    'https://example.com:8443/a', 'https://127.0.0.1/a', 'https://[::1]/a', 'https://2130706433/a',
    'https://localhost/a', 'https://media.local/a', 'https://media.example.com./a',
    'https://example.com/a#fragment', ' https://example.com/a', 'https://example.com/a\r\nInjected:1',
    'https://example.com/\\evil', 'https://example.com/%zz', 'https://例子.com/a',
])
def test_invalid_targets_fail_without_network_or_credential_echo(url):
    with pytest.raises(net.DownloadError) as error:
        net.parse_url(url)
    assert url not in str(error.value) and 'secret' not in str(error.value)


def test_url_canonicalization_keeps_path_query_and_encodes_chinese():
    canonical, host, target = net.parse_url('https://MEDIA.EXAMPLE.COM:443/中文.webm?key=a%2Fb')
    assert canonical == 'https://media.example.com/%E4%B8%AD%E6%96%87.webm?key=a%2Fb'
    assert host == 'media.example.com' and target.endswith('?key=a%2Fb')


@pytest.mark.parametrize('address', ['0.1.2.3', '10.0.0.1', '100.64.0.1', '127.0.0.1', '169.254.169.254',
    '172.31.0.1', '192.0.0.9', '192.0.2.1', '192.168.1.1', '198.18.0.1', '198.51.100.1',
    '203.0.113.1', '224.0.0.1', '255.255.255.255'])
def test_any_nonpublic_dns_answer_refuses_the_whole_target(monkeypatch, address):
    monkeypatch.setattr(socket, 'getaddrinfo', lambda *args, **kwargs: [
        (socket.AF_INET, socket.SOCK_STREAM, 6, '', ('8.8.8.8', 443)),
        (socket.AF_INET, socket.SOCK_STREAM, 6, '', (address, 443))])
    with pytest.raises(net.DownloadError):
        net.resolve('media.example.com')


def test_tls_pins_validated_address_while_preserving_certificate_host(monkeypatch):
    calls = []
    class Sock:
        def close(self):
            calls.append('closed')
    sock = Sock()
    monkeypatch.setattr(socket, 'create_connection', lambda target, **kw: calls.append(target) or sock)
    def wrap(context, raw, *, server_hostname):
        assert context.check_hostname and context.verify_mode == ssl.CERT_REQUIRED
        assert raw is sock
        calls.append(server_hostname)
        return sock
    monkeypatch.setattr(ssl.SSLContext, 'wrap_socket', wrap)
    connection = net.PinnedHTTPS('media.example.com', '8.8.8.8')
    connection.connect()
    connection.close()
    assert calls == [('8.8.8.8', 443), 'media.example.com', 'closed']


class Response(io.BytesIO):
    def __init__(self, data, status=200, fields=None):
        super().__init__(data)
        self.status = status
        self.fields = fields or [('Content-Type', 'video/webm'), ('Content-Length', str(len(data))), ('ETag', '"version1"')]

    def getheaders(self):
        return self.fields


def connections(monkeypatch, responses):
    calls = []
    class Connection:
        def __init__(self, host, address):
            calls.append(('pin', host, address))
        def request(self, method, target, headers):
            calls.append((method, target, headers))
        def getresponse(self):
            return responses.pop(0)
        def close(self):
            calls.append('closed')
    monkeypatch.setattr(net, 'PinnedHTTPS', Connection)
    monkeypatch.setattr(net, 'resolve', lambda host: '8.8.8.8')
    return calls


def test_fresh_stream_hash_header_and_progress_then_strict_resume(monkeypatch, tmp_path):
    raw = b'\x1aE\xdf\xa3' + b'self-authored fixture bytes' * 20
    file = tmp_path / 'owned.webm'
    calls = connections(monkeypatch, [Response(raw)])
    progress = []
    result = net.transfer('https://media.example.com/a?signature=private', file, '.webm', progress=progress.append)
    assert file.read_bytes() == raw and result['sha256'] == hashlib.sha256(raw).hexdigest()
    assert progress[-1]['received'] == len(raw) and result['mime'] == 'video/webm'
    assert calls[1][2] == {'Accept-Encoding': 'identity', 'User-Agent': 'StudyWorkbench/1.0', 'Connection': 'close'}
    partial = tmp_path / 'partial.webm'
    partial.write_bytes(raw[:32])
    calls = connections(monkeypatch, [Response(raw[32:], status=206, fields=[
        ('Content-Type', 'video/webm'), ('Content-Length', str(len(raw) - 32)),
        ('Content-Range', f'bytes 32-{len(raw)-1}/{len(raw)}'), ('ETag', '"version1"')])])
    resumed = net.transfer('https://media.example.com/a', partial, '.webm', offset=32, etag='"version1"',
                           partial_sha256=hashlib.sha256(raw[:32]).hexdigest())
    assert partial.read_bytes() == raw and resumed['sha256'] == result['sha256']
    assert calls[1][2]['Range'] == 'bytes=32-' and calls[1][2]['If-Range'] == '"version1"'


@pytest.mark.parametrize('fields,status', [
    ([('Content-Type', 'text/html')], 200),
    ([('Content-Type', 'video/webm'), ('Content-Encoding', 'gzip')], 200),
    ([('Content-Type', 'video/webm'), ('Content-Length', '4'), ('Content-Length', '4')], 200),
    ([('Content-Type', 'video/webm'), ('Content-Length', '4'), ('Transfer-Encoding', 'chunked')], 200),
    ([('Content-Type', 'video/webm'), ('Content-Length', 'NaN')], 200),
    ([('Content-Type', 'video/webm'), ('Content-Length', str(net.LIMIT + 1))], 200),
    ([('Content-Type', 'video/webm'), ('Content-Range', 'bytes 0-3/4')], 200),
    ([('Content-Type', 'video/webm')], 500),
])
def test_bad_response_never_creates_destination(monkeypatch, tmp_path, fields, status):
    connections(monkeypatch, [Response(b'bytes', status=status, fields=fields)])
    path = tmp_path / 'never-created.webm'
    with pytest.raises(net.DownloadError):
        net.transfer('https://media.example.com/a', path, '.webm')
    assert not path.exists()


def test_redirect_revalidation_and_limit(monkeypatch, tmp_path):
    connections(monkeypatch, [Response(b'', 302, [('Location', 'http://127.0.0.1/secret')])])
    with pytest.raises(net.DownloadError):
        net.transfer('https://media.example.com/a', tmp_path / 'new', '.webm')
    calls = connections(monkeypatch, [Response(b'', 302, [('Location', '/again')]) for _ in range(4)])
    with pytest.raises(net.DownloadError, match='次数'):
        net.transfer('https://media.example.com/a', tmp_path / 'new', '.webm')
    assert sum(call == 'closed' for call in calls) == 4


@pytest.mark.parametrize('status,etag,content_range', [(200, '"v1"', 'bytes 8-11/12'),
    (206, '"changed"', 'bytes 8-11/12'), (206, '"v1"', 'bytes 7-10/12'), (206, '"v1"', 'bytes 8-11/*')])
def test_resume_version_or_range_mismatch_preserves_prefix(monkeypatch, tmp_path, status, etag, content_range):
    path = tmp_path / 'owned'
    path.write_bytes(b'original')
    connections(monkeypatch, [Response(b'tail', status, [('Content-Type', 'video/webm'), ('Content-Length', '4'),
        ('ETag', etag), ('Content-Range', content_range)])])
    with pytest.raises(net.DownloadError):
        net.transfer('https://media.example.com/a', path, '.webm', offset=8, etag='"v1"',
                     partial_sha256=hashlib.sha256(b'original').hexdigest())
    assert path.read_bytes() == b'original'


def test_unknown_length_actual_budget_and_cancel_preserve_written_bytes(monkeypatch, tmp_path):
    raw = b'\x1aE\xdf\xa3' + b'x' * 100
    connections(monkeypatch, [Response(raw, fields=[('Content-Type', 'video/webm')])])
    monkeypatch.setattr(net, 'LIMIT', 64)
    with pytest.raises(net.DownloadError, match='实际字节'):
        net.transfer('https://media.example.com/a', tmp_path / 'too-large', '.webm')
    assert (tmp_path / 'too-large').read_bytes() == b''
    monkeypatch.setattr(net, 'CHUNK', 16)
    connections(monkeypatch, [Response(raw, fields=[('Content-Type', 'video/webm')])])
    def progress(value):
        if value['received'] == 16:
            raise RuntimeError('test cancellation')
    with pytest.raises(RuntimeError, match='cancellation'):
        net.transfer('https://media.example.com/a', tmp_path / 'cancelled', '.webm', progress=progress)
    assert (tmp_path / 'cancelled').read_bytes() == raw[:16]


def test_resume_refuses_modified_prefix_even_with_matching_size_and_etag(monkeypatch, tmp_path):
    path = tmp_path / 'modified'
    path.write_bytes(b'changed!')
    connections(monkeypatch, [Response(b'tail', 206, [('Content-Type', 'video/webm'), ('Content-Length', '4'),
        ('ETag', '"v1"'), ('Content-Range', 'bytes 8-11/12')])])
    with pytest.raises(net.DownloadError, match='内容变化'):
        net.transfer('https://media.example.com/a', path, '.webm', offset=8, etag='"v1"',
                     partial_sha256=hashlib.sha256(b'original').hexdigest())
    assert path.read_bytes() == b'changed!'
