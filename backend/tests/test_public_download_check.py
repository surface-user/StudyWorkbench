import hashlib
import importlib
import io
import json
import sys
from pathlib import Path

import pytest


@pytest.fixture
def probe(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[2] / 'tools'))
    module = importlib.import_module('check_public_downloads')
    # The diagnostic installs process-local observers; never leak them into other tests.
    monkeypatch.setattr(module.transport, 'PinnedHTTPS', module.transport.PinnedHTTPS)
    return module


def test_fixture_hash_is_git_blob_not_raw_sha1(probe, monkeypatch):
    data = b'original fixture bytes'
    blob = hashlib.sha1(b'blob 22\0' + data).hexdigest()
    monkeypatch.setitem(probe.FIXTURES, probe.FLOWER, (22, blob))
    assert probe.verify_fixture(data, probe.FLOWER) == hashlib.sha256(data).hexdigest()
    for changed in (data[:-1], data[:-1] + b'X'):
        with pytest.raises(RuntimeError):
            probe.verify_fixture(changed, probe.FLOWER)
    monkeypatch.setitem(probe.FIXTURES, probe.FLOWER, (22, hashlib.sha1(data).hexdigest()))
    with pytest.raises(RuntimeError, match='Git object'):
        probe.verify_fixture(data, probe.FLOWER)


class Response:
    status = 200

    def __init__(self, data):
        self.body = io.BytesIO(data)
        self.size = len(data)

    def getheaders(self):
        return [('Content-Length', str(self.size)), ('Content-Type', 'video/webm'), ('ETag', '"fixed"')]

    def read(self, count):
        return self.body.read(count)


def connection_type(data):
    class Connection:
        def __init__(self, host, address):
            self.host, self.address = host, address

        def request(self, *args, **kwargs):
            pass

        def getresponse(self):
            return Response(data)

        def close(self):
            pass

    return Connection


def test_observer_keeps_address_and_caps_body_before_more_reads(probe, monkeypatch, tmp_path):
    monkeypatch.setattr(probe.transport, 'PinnedHTTPS', connection_type(b'1234567890'))
    monkeypatch.setattr(probe, 'BODY_BUDGET', 5)
    (tmp_path / 'body-bytes.json').write_text('0')
    probe.install_transport(tmp_path)
    connection = probe.transport.PinnedHTTPS('fixed.example', '8.8.8.8')
    connection.request('GET', '/fixed', headers={'Range': 'bytes=5-', 'If-Range': '"fixed"'})
    response = connection.getresponse()
    assert response.read(10) == b'12345'
    with pytest.raises(RuntimeError, match='budget exhausted'):
        response.read(1)
    row = json.loads((tmp_path / 'network.jsonl').read_text())
    assert row['address'] == '8.8.8.8' and row['range'] == 'bytes=5-' and row['if_range'] == '"fixed"'
    assert json.loads((tmp_path / 'body-bytes.json').read_text()) == 5


def test_real_transfer_first_block_is_saved_before_controlled_pause(probe, monkeypatch, tmp_path):
    from study_workbench import media_download_worker
    data = b'\x1aE\xdf\xa3' + b'a' * (probe.FIXTURES[probe.FLOWER][0] - 4)
    monkeypatch.setattr(probe.transport, 'PinnedHTTPS', connection_type(data))
    monkeypatch.setattr(probe.transport, 'resolve', lambda host: '8.8.8.8')
    monkeypatch.setattr(media_download_worker, 'transfer', media_download_worker.transfer)
    (tmp_path / 'body-bytes.json').write_text('0')
    emitted = []

    def checkpoint():
        if emitted and emitted[-1]['received'] == probe.transport.CHUNK:
            raise RuntimeError('intentional pause')

    def worker():
        media_download_worker.transfer(probe.FLOWER, tmp_path / 'partial.webm', '.webm', offset=0,
                                       checkpoint=checkpoint, progress=emitted.append)

    monkeypatch.setattr(media_download_worker, 'worker', worker)
    with pytest.raises(RuntimeError, match='intentional pause'):
        probe.instrument_worker(tmp_path, hold=True)
    prefix = (tmp_path / 'partial.webm').read_bytes()
    assert prefix == data[:probe.transport.CHUNK]
    assert emitted[-1]['partial_sha256'] == hashlib.sha256(prefix).hexdigest()
    assert json.loads((tmp_path / 'body-bytes.json').read_text()) == len(prefix)


@pytest.mark.parametrize('option', [[], ['--serve'], ['--worker']])
def test_every_entry_requires_public_opt_in(probe, monkeypatch, tmp_path, option):
    monkeypatch.setattr(sys, 'argv', ['probe', '--test-root', str(tmp_path), *option])
    with pytest.raises(SystemExit) as error:
        probe.main()
    assert error.value.code == 2
    assert not (tmp_path / 'body-bytes.json').exists()


def test_existing_test_directory_is_not_reused(probe, tmp_path):
    marker = tmp_path / 'keep.txt'
    marker.write_bytes(b'old failure')
    with pytest.raises(FileExistsError):
        probe.run(tmp_path)
    assert marker.read_bytes() == b'old failure'


@pytest.mark.parametrize('status,etag,range_value,length,body', [
    (200, '"fixed"', 'bytes 0-0/554058', '1', b'x'),
    (206, '"changed"', 'bytes 0-0/554058', '1', b'x'),
    (206, '"fixed"', 'bytes 1-1/554058', '1', b'x'),
    (206, '"fixed"', 'bytes 0-0/554058', '2', b'xx'),
    (206, '"fixed"', 'bytes 0-0/554058', '1', b''),
])
def test_preflight_rejects_false_range_evidence(probe, monkeypatch, tmp_path,
                                              status, etag, range_value, length, body):
    requests = []

    class Connection:
        def __init__(self, host, address):
            pass

        def request(self, method, target, headers):
            requests.append((method, headers))
            self.method = method

        def getresponse(self):
            response = Response(body)
            response.status = 200 if self.method == 'HEAD' else status
            values = {'ETag': '"fixed"', 'Content-Length': '554058'} if self.method == 'HEAD' else {
                'ETag': etag, 'Content-Range': range_value, 'Content-Length': length}
            values['Content-Type'] = 'video/webm'
            response.getheader = values.get
            return response

        def close(self):
            pass

    monkeypatch.setattr(probe, 'install_transport', lambda root: None)
    monkeypatch.setattr(probe.transport, 'resolve', lambda host: '8.8.8.8')
    monkeypatch.setattr(probe.transport, 'PinnedHTTPS', Connection)
    with pytest.raises(RuntimeError, match='Range'):
        probe.preflight(tmp_path)
    assert requests[1][1]['Range'] == 'bytes=0-0'
    assert requests[1][1]['If-Range'] == '"fixed"'


def test_observed_oversize_requests_pause_and_fails(probe):
    calls = []

    def request(path, body=None):
        calls.append((path, body))
        return {'status': 'running', 'progress': {'received': 0, 'total': 999999}}

    with pytest.raises(RuntimeError, match='exceeded expected size'):
        probe.wait_job(request, 'job', {'ready'})
    assert calls[-1] == (probe.PREFIX + '/job/pause', {})


@pytest.mark.parametrize('mime', ['text/plain', 'text/html', None])
def test_preflight_mime_rejection_never_reads_media_body(probe, monkeypatch, tmp_path, mime):
    requests = []

    class Connection:
        def __init__(self, host, address):
            pass

        def request(self, method, target, headers):
            requests.append(method)

        def getresponse(self):
            response = Response(b'not read')
            response.getheader = {'ETag': '"fixed"', 'Content-Length': '554058', 'Content-Type': mime}.get
            response.read = lambda *args: pytest.fail('MIME rejection must happen before a body read')
            return response

        def close(self):
            pass

    monkeypatch.setattr(probe, 'install_transport', lambda root: None)
    monkeypatch.setattr(probe.transport, 'resolve', lambda host: '8.8.8.8')
    monkeypatch.setattr(probe.transport, 'PinnedHTTPS', Connection)
    with pytest.raises(RuntimeError, match='MIME'):
        probe.preflight(tmp_path)
    assert requests == ['HEAD']


def test_source_probe_starts_real_backend_and_stops_without_downloads(probe, tmp_path):
    with probe.backend_process(tmp_path, hold=True) as (request, first_pid):
        assert request('/api/health')['status'] == 'ok'
        assert request(probe.PREFIX) == []
    with probe.backend_process(tmp_path) as (request, second_pid):
        assert first_pid != second_pid
        assert request(probe.PREFIX) == []
