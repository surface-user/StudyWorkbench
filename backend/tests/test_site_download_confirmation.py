"""Exercise the confirmation API, durable queue, HTTP body, file publication and restart offline."""
import copy
import hashlib
import json
import sqlite3
import subprocess
import sys
from dataclasses import replace
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread

import pytest
from sqlalchemy.orm import Session
from study_workbench import bilibili_preview as preview
from study_workbench import media_download_http as transport
from study_workbench.backup_store import create_backup, restore_backup
from study_workbench.db import MediaDownloadJob
from study_workbench.media_site_previews import MediaSitePreviews
from test_bilibili_preview import PAGE, encoded, html
from test_bilibili_preview import source as metadata_fixture
from test_explorer import PREFIX, client
from test_media_downloads import wait
from test_media_inputs import box, mp4
from test_media_site_previews import ENDPOINT, body, finished

source = metadata_fixture
CDN = 'upos-test.bilivideo.com'
URL = 'https://' + CDN + '/owned.mp4?signature=ephemeral'
TARGET = dict(format_id='legacy-0', name='自编样片.mp4', request_id='owned-site-confirm-01', rights_confirmed=True)


def two_tracks():
    video, audio = mp4('video'), mp4('audio')
    movie = video.index(b'moov')
    audio_track = audio.index(b'trak') - 4
    return video[:movie - 4] + box(b'moov', video[movie + 4:] + audio[audio_track:])


@pytest.fixture
def ordinary(monkeypatch, source):
    state, nav, play = source
    data = two_tracks()
    state['videoData']['rights']['download'] = 1
    play['data'] = dict(quality=32, timelength=120000, format='mp4', durl=[dict(url=URL, size=len(data))])
    calls = []
    def fetch(self, url, **flags):
        calls.append(url.split('?')[0])
        payload = html(state) if flags.get('page') else encoded(nav if url == preview.NAV else play)
        self.requests += 1
        self.received += len(payload)
        return payload, PAGE if flags.get('page') else url
    monkeypatch.setattr(preview.Client, 'fetch', fetch)
    monkeypatch.setattr(MediaSitePreviews, 'child', lambda self, entry: preview.extract(entry['url']))
    return play['data'], data, calls


def start(c):
    response = c.post(ENDPOINT, json=body())
    assert response.status_code == 200
    key = response.json()['id']
    assert finished(c, key)['status'] == 'ready'
    return key, ENDPOINT + '/' + key + '/confirm'


def test_site_and_local_pair_keep_distinct_sources_in_one_queue(ordinary, monkeypatch, tmp_path):
    from test_media_mux import imports

    with client(tmp_path) as c:
        monkeypatch.setattr(c.app.state.downloads.pool, 'submit', lambda *args: None)
        _, confirm = start(c)
        first = c.post(confirm, json=TARGET)
        assert first.status_code == 200
        body = imports(c)
        pairs = PREFIX + '/media-downloads/local-pair'
        assert c.post(pairs, json={**body, 'request_id': TARGET['request_id']}).status_code == 409
        second = c.post(pairs, json=body)
        assert second.status_code == 200
        jobs = c.get(PREFIX + '/media-downloads').json()
        assert {row['id']: row['source_kind'] for row in jobs} == {
            first.json()['id']: 'site_progressive', second.json()['id']: 'local_pair'}
        assert c.post(confirm, json=TARGET).json()['id'] == first.json()['id']
        assert c.post(pairs, json=body).json()['id'] == second.json()['id']


def test_offline_http_transfer_replay_and_backup(monkeypatch, ordinary, tmp_path):
    _, data, calls = ordinary
    requests = []
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass
        def do_GET(self):
            requests.append((self.path, dict(self.headers)))
            self.send_response(200)
            self.send_header('Content-Type', 'video/mp4')
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    # Only the child test launcher changes its connection factory to reach the owned local HTTP server.
    # The API, real disposable worker, JSON pipe, redirect budget, stream and publication run normally.
    original_popen = subprocess.Popen
    setup = '''import http.client, sys
from study_workbench import media_download_http as net
from study_workbench.media_download_worker import worker
def connect(host, address):
    assert host == sys.argv[2] and address == "93.184.216.34"
    return http.client.HTTPConnection("127.0.0.1", int(sys.argv[1]), timeout=5)
net.PinnedHTTPS = connect
net.resolve = lambda host: "93.184.216.34"
worker()
'''
    def offline_worker(args, *more, **options):
        if args[-1] == '--download-media':
            args = [sys.executable, '-c', setup, str(server.server_port), CDN]
        return original_popen(args, *more, **options)
    monkeypatch.setattr(subprocess, 'Popen', offline_worker)
    root = tmp_path / 'data'
    try:
        with client(root) as c:
            key, endpoint = start(c)
            assert len(calls) == 3
            assert finished(c, key)['result']['formats'][0]['download_supported']
            other = c.post('/api/workspaces', json={'name': '隔离'}).json()['id']
            assert c.post(endpoint.replace('/default/', f'/{other}/'), json=TARGET).status_code == 404
            for invalid in ({'rights_confirmed': False}, {'url': URL}, {'name': 'wrong.m4a'}):
                assert c.post(endpoint, json={**TARGET, **invalid}).status_code == 422
            created = c.post(endpoint, json=TARGET)
            assert created.status_code == 200, created.text
            job_id = created.json()['id']
            ready = wait(c, job_id, {'ready','failed'})
            assert ready['status'] == 'ready', ready
            assert ready['source_kind'] == 'site_progressive' and not ready['can_resume']
            assert len(calls) == 6
            assert requests[0][0].endswith('signature=ephemeral') and len(requests) == 1
            assert not {'referer','origin','cookie','authorization'} & {name.lower() for name in requests[0][1]}
            with Session(c.app.state.engine) as session:
                job = session.get(MediaDownloadJob, job_id)
                assert job.source_url == PAGE and job.site_receipt['size'] == len(data)
                assert hashlib.sha256((root / job.relative_path).read_bytes()).digest() == hashlib.sha256(data).digest()
            assert c.post(endpoint, json=TARGET).json()['id'] == job_id
            assert c.post(endpoint, json={**TARGET,'name':'changed.mp4'}).status_code == 409
            assert c.post(endpoint, json={**TARGET,'request_id':'owned-site-confirm-02'}).status_code == 409
            direct = {k:v for k,v in TARGET.items() if k != 'format_id'}
            assert c.post(PREFIX+'/media-downloads', json={**direct,'url':PAGE}).status_code == 409
        for path in [root, tmp_path / 'restored']:
            if path != root:
                package = tmp_path / 'library.zip'
                create_backup(root, package)
                assert restore_backup(package, path, tmp_path/'settings.json')['schema_revision'] == '0022'
            with client(path) as c:
                assert c.get(ENDPOINT+'/'+key).status_code == 404
                assert c.post(endpoint, json=TARGET).json()['id'] == job_id
                assert c.post(endpoint, json={**TARGET,'request_id':'owned-site-confirm-03'}).status_code == 404
            with sqlite3.connect(path/'study.db') as db:
                fields = db.execute('SELECT source_url, site_receipt FROM media_download_jobs').fetchall()
                assert len(fields) == 1 and 'signature=' not in str(fields)
                assert json.loads(fields[0][1])['cdn_host'] == CDN
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


@pytest.mark.parametrize('change', ['expired','cancelled','changed_size','changed_cid','changed_path','changed_query','lost_rights'])
def test_changed_or_expired_candidate_never_enqueues(monkeypatch, ordinary, tmp_path, change):
    metadata, _, _ = ordinary
    with client(tmp_path) as c:
        key, endpoint = start(c)
        service = c.app.state.site_previews
        before = service.child
        def recheck(entry):
            fresh = copy.deepcopy(before(entry))
            if change == 'expired':
                entry['expires'] = 0
            elif change == 'cancelled':
                entry['cancel'].set()
            elif change == 'changed_size':
                fresh['formats'][0]['size_bytes'] += 1
            elif change == 'changed_cid':
                fresh['source_cid'] += 1
            elif change == 'changed_query':
                fresh['formats'][0]['url'] = URL.replace('signature=ephemeral','asset=changed')
            elif change == 'changed_path':
                fresh['formats'][0]['url'] = URL.replace('owned.mp4','other.mp4')
            else:
                fresh['formats'][0]['download_supported'] = False
            return fresh
        monkeypatch.setattr(service, 'child', recheck)
        assert c.post(endpoint, json=TARGET).status_code == 409
        assert c.get(PREFIX+'/media-downloads').json() == []


@pytest.mark.parametrize('change', ['foreign','lookalike','header','flv','segmented','oversize','drm'])
def test_ineligible_format(ordinary, change):
    metadata, _, _ = ordinary
    item = metadata['durl'][0]
    if change in {'foreign','lookalike'}:
        item['url'] = URL.replace(CDN, 'cdn.example.org' if change == 'foreign' else CDN+'.example.org')
    elif change == 'header':
        item['http_headers'] = {'Referer': 'required'}
    elif change == 'flv':
        metadata['format'] = 'flv'
    elif change == 'segmented':
        metadata['durl'].append(dict(item))
    elif change == 'oversize':
        item['size'] = transport.LIMIT + 1
    else:
        item['is_drm'] = 1
        with pytest.raises(transport.DownloadError):
            preview.extract(PAGE)
        return
    assert not preview.extract(PAGE)['formats'][0]['download_supported']




def test_redirect_outside_confirmed_origin_stops_before_dns(monkeypatch, tmp_path):
    from test_media_download_http import Response, connections
    calls = connections(monkeypatch, [Response(b'', 302, [('Location', 'https://other.example.org/new.mp4')])])
    dns = []
    monkeypatch.setattr(transport, 'resolve', lambda host: dns.append(host) or '93.184.216.34')
    with pytest.raises(transport.DownloadError, match='重新预览'):
        transport.transfer(URL, tmp_path / 'site.mp4', '.mp4', site_host=CDN)
    assert dns == [CDN] and sum(isinstance(x, tuple) and x[0] == 'GET' for x in calls) == 1
    assert not (tmp_path / 'site.mp4').exists()


def test_queued_restart_keeps_confirmation_but_requires_new_preview(monkeypatch, ordinary, tmp_path):
    with client(tmp_path) as c:
        key, endpoint = start(c)
        submitted = []
        monkeypatch.setattr(c.app.state.downloads.pool, 'submit', lambda *args: submitted.append(args))
        job = c.post(endpoint, json=TARGET).json()
        assert job['status'] == 'queued' and len(submitted) == 1
    with client(tmp_path) as c:
        old = c.post(endpoint, json=TARGET).json()
        assert old['id'] == job['id'] and old['status'] == 'interrupted'
        for mode in ['resume','restart']:
            assert c.post(PREFIX+'/media-downloads/'+job['id']+'/retry', json={'mode':mode}).status_code == 409
        assert c.get(ENDPOINT+'/'+key).status_code == 404


def test_cancel_during_repeat_check_never_commits(monkeypatch, ordinary, tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event
    with client(tmp_path) as c, ThreadPoolExecutor(max_workers=1) as pool:
        key, endpoint = start(c)
        service = c.app.state.site_previews
        before = service.child
        entered, resume = Event(), Event()
        def child(entry):
            entered.set()
            assert resume.wait(5)
            return before(entry)
        monkeypatch.setattr(service, 'child', child)
        pending = pool.submit(c.post, endpoint, json=TARGET)
        try:
            assert entered.wait(5)
            assert c.post(endpoint, json=TARGET).status_code == 429
            assert c.post(ENDPOINT+'/'+key+'/cancel').status_code == 200
        finally:
            resume.set()
        assert pending.result(timeout=5).status_code == 409
        assert c.get(PREFIX+'/media-downloads').json() == []


def test_migrating_0021_keeps_existing_direct_job_and_protects_receipt(tmp_path):
    from alembic import command
    from study_workbench.db import database as open_database
    from test_media_sources import config
    database = tmp_path / 'study.db'
    cfg = config()
    engine = open_database(database)
    with engine.begin() as connection:
        connection.exec_driver_sql('BEGIN')
        cfg.attributes['connection'] = connection
        command.upgrade(cfg, '0021')
    with sqlite3.connect(database) as db:
        db.execute("""INSERT INTO media_download_jobs
            (id, workspace_id, name, request_id, source_url, status, cancel_requested, attempt,
             relative_path, progress, result, created_at)
            VALUES ('legacy', 'default', 'old.mp4', 'migration-request', 'https://example.org/old.mp4',
                    'ready', 0, 1, 'old.mp4', '{}', '{}', '2026-01-01')""")
    with engine.begin() as connection:
        connection.exec_driver_sql('BEGIN')
        cfg.attributes['connection'] = connection
        command.upgrade(cfg, 'head')
    engine.dispose()
    with sqlite3.connect(database) as db:
        assert db.execute('SELECT source_kind,site_receipt FROM media_download_jobs').fetchall() == [('direct_https',None)]
        with pytest.raises(sqlite3.IntegrityError):
            db.execute("UPDATE media_download_jobs SET site_receipt='{}' WHERE id='legacy'")



def test_empty_audio_track_is_not_published(monkeypatch, ordinary, tmp_path):
    from study_workbench.media_downloads import MediaDownloads
    metadata, _, _ = ordinary
    raw = mp4('video')
    metadata['durl'][0]['size'] = len(raw)
    def single_track(self, job, path, *, transfer, deadline):
        path.write_bytes(raw)
        return {'size': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}
    monkeypatch.setattr(MediaDownloads, 'child', single_track)
    with client(tmp_path) as c:
        _, endpoint = start(c)
        job = c.post(endpoint, json=TARGET).json()
        value = wait(c, job['id'], {'ready','failed'})
        assert value['status'] == 'failed' and '轨道' in value['error']
    with sqlite3.connect(tmp_path/'study.db') as db:
        assert db.execute('SELECT count(*) FROM media_entries').fetchone() == (0,)


def test_expired_waiting_job_never_connects(monkeypatch, ordinary, tmp_path):
    with client(tmp_path) as c:
        _, endpoint = start(c)
        scheduled = []
        downloads = c.app.state.downloads
        monkeypatch.setattr(downloads.pool, 'submit', lambda *args: scheduled.append(args))
        monkeypatch.setattr(downloads, 'child', lambda *a, **k: pytest.fail('expired transfer started'))
        job = c.post(endpoint, json=TARGET).json()
        run, identifier, transfer = scheduled[0]
        assert identifier == job['id']
        run(identifier, replace(transfer, expires=0))
        value = wait(c, identifier, {'failed'})
        assert '重新预览' in value['error'] and not value['can_resume']


def test_declared_size_disagreement_creates_no_file(monkeypatch, tmp_path):
    from test_media_download_http import Response, connections
    raw = two_tracks()
    connections(monkeypatch, [Response(raw, fields=[('Content-Type', 'video/mp4'), ('Content-Length', str(len(raw)))])])
    path = tmp_path/'rejected.mp4'
    with pytest.raises(transport.DownloadError, match='大小'):
        transport.transfer(URL, path, '.mp4', site_host=CDN, expected_size=len(raw)+1)
    assert not path.exists()



@pytest.mark.parametrize('usage', [None, {'requests': True, 'bytes': 12}, {'requests': 9, 'bytes': 0},
                                   {'requests': 10, 'bytes': 12}, {'requests': 9, 'bytes': 8388609}])
def test_confirmation_requires_remaining_verified_metadata_budget(monkeypatch, ordinary, tmp_path, usage):
    with client(tmp_path) as c:
        identifier, endpoint = start(c)
        monkeypatch.setattr(c.app.state.downloads.pool, 'submit', lambda *args: None)
        assert 'metadata_usage' not in finished(c, identifier)['result']
        service = c.app.state.site_previews
        original = service.child
        def fresh(entry):
            result = original(entry)
            result['metadata_usage'] = usage
            return result
        monkeypatch.setattr(service, 'child', fresh)
        assert c.post(endpoint, json=TARGET).status_code == 409
        assert c.get(PREFIX+'/media-downloads').json() == []


def test_media_declaration_and_metadata_bytes_must_fit_together(ordinary, tmp_path):
    metadata, _, _ = ordinary
    metadata['durl'][0]['size'] = transport.LIMIT
    with client(tmp_path) as c:
        _, endpoint = start(c)
        response = c.post(endpoint, json=TARGET)
        assert response.status_code == 409 and '额度' in response.text
        assert c.get(PREFIX+'/media-downloads').json() == []


def test_transfer_keeps_the_same_request_and_byte_counters(monkeypatch, tmp_path):
    from test_media_download_http import Response, connections
    raw = two_tracks()
    def blob():
        return Response(raw, fields=[('Content-Type','video/mp4'),('Content-Length',str(len(raw)))])
    budget = transport.SiteNetworkBudget(3, 2*len(raw))
    calls = connections(monkeypatch, [Response(b'', 302, [('Location','/again.mp4')]),blob(),blob()])
    for name in ('first','second'):
        result = transport.transfer(URL, tmp_path/name,'.mp4',site_host=CDN,expected_size=len(raw),budget=budget)
        assert result['size'] == len(raw) and (tmp_path/name).read_bytes() == raw
    assert budget.requests_left == budget.bytes_left == 0
    assert sum(isinstance(x,tuple) and x[0]=='GET' for x in calls) == 3
    with pytest.raises(transport.DownloadError, match='额度'):
        transport.transfer(URL,tmp_path/'third','.mp4',site_host=CDN,expected_size=len(raw),budget=budget)
    assert not (tmp_path/'third').exists()


def test_redirect_after_last_shared_request_does_not_resolve(monkeypatch, tmp_path):
    from test_media_download_http import Response, connections
    connections(monkeypatch,[Response(b'',302,[('Location','/again.mp4')])])
    resolved = []
    monkeypatch.setattr(transport,'resolve',lambda host: resolved.append(host) or '93.184.216.34')
    with pytest.raises(transport.DownloadError,match='10次请求'):
        transport.transfer(URL,tmp_path/'blocked','.mp4',site_host=CDN,expected_size=100,
                           budget=transport.SiteNetworkBudget(1,100))
    assert resolved == [CDN] and not (tmp_path/'blocked').exists()


def test_queue_time_and_validation_share_confirmation_deadline(monkeypatch, ordinary, tmp_path):
    from types import SimpleNamespace

    from study_workbench import media_downloads
    _, data, _ = ordinary
    clock = [0]
    with client(tmp_path) as c:
        _, endpoint = start(c)
        downloads = c.app.state.downloads
        scheduled = []
        monkeypatch.setattr(downloads.pool,'submit',lambda *args: scheduled.append(args))
        job = c.post(endpoint,json=TARGET).json()
        run, identifier, grant = scheduled[0]
        assert 0 < grant.budget.requests_left == 7 and grant.budget.bytes_left < transport.LIMIT
        clock[0] = min(grant.expires, grant.deadline)-1
        monkeypatch.setattr(media_downloads,'time',SimpleNamespace(monotonic=lambda: clock[0]))
        def delayed(self, job, path, *, deadline, transfer):
            assert deadline == grant.deadline and transfer is grant
            path.write_bytes(data)
            clock[0] = deadline
            return {'size':len(data),'sha256':hashlib.sha256(data).hexdigest()}
        monkeypatch.setattr(media_downloads.MediaDownloads,'child',delayed)
        run(identifier,grant)
        failed = wait(c,job['id'],{'failed'})
        assert '共用时限' in failed['error']
        assert c.get(PREFIX+'/media-downloads').json()[0]['result'] == {}
