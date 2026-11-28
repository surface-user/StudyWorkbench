"""Owned offline page/API responses. No media connection or download is allowed for selection."""
import copy
import json
import time
from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from study_workbench import bilibili_preview as preview
from study_workbench.db import MediaDownloadJob, MediaEntry
from study_workbench.media_download_http import LIMIT
from study_workbench.site_pair_selection import digest
from test_bilibili_preview import network
from test_bilibili_preview import source as metadata_fixture
from test_explorer import PREFIX, client
from test_media_site_previews import ENDPOINT, body, finished

source = metadata_fixture
HOST = 'upos-owned.bilivideo.com'


@pytest.fixture
def tracks(monkeypatch, source):
    state, _, envelope = source
    state['videoData']['rights']['download'] = 1
    dash = envelope['data']['dash']
    video, audio = dash['video'][0], dash['audio'][0]
    for item, name, codec in [(video, 'video', 'avc1.64001f'), (audio, 'audio', 'mp4a.40.2')]:
        item.update(baseUrl=f'https://{HOST}/{name}.m4s?signature=owned', codecs=codec, size=128)
    dash['video'].append(dict(video, id=80, width=1920, height=1080, baseUrl=f'https://{HOST}/higher.m4s'))
    hosts = []

    def extract(self, entry, selected_refs=()):
        calls, _, _ = network(monkeypatch, source)
        result = preview.extract(entry['url'], selected_refs=selected_refs)
        hosts.extend(call[0] for call in calls)
        return result

    monkeypatch.setattr('study_workbench.media_site_previews.MediaSitePreviews.child', extract)
    return state['videoData'], envelope['data'], hosts


def prepared(api):
    response = api.post(ENDPOINT, json=body())
    assert response.status_code == 200
    key = response.json()['id']
    public = finished(api, key)['result']
    refs = {row['source_format_id']: row['pair_track_ref'] for row in public['formats'] if 'pair_track_ref' in row}
    return key, public, refs


def choice(refs):
    return dict(request_id='self-owned-pair-0001', video_ref=refs[64], audio_ref=refs[30280], rights_confirmed=True)


def test_pick_pair_recheck_and_replay_without_media_transfer(tmp_path, tracks):
    _, play, hosts = tracks
    with client(tmp_path) as api:
        key, public, refs = prepared(api)
        assert len(refs) == 3 and all(not item['download_supported'] for item in public['formats'])
        internal = api.app.state.site_previews.entries[key]['result']
        assert 'signature=' not in json.dumps(internal)
        assert 'pair_selection' not in public
        dash = play['dash']
        dash['video'].reverse()
        dash['audio'][0]['baseUrl'] = f'https://{HOST}/audio.m4s?signature=rotated'
        endpoint = ENDPOINT + '/' + key + '/pair-selection'
        first = api.post(endpoint, json=choice(refs))
        assert first.status_code == 200, first.text
        receipt = first.json()
        assert receipt['aid'] == 7 and receipt['cid'] == 9 and receipt['delivery'] == 'dash_pair'
        assert receipt['rights_confirmed'] is True and receipt['download_supported'] is True
        assert [r['source_format_id'] for r in receipt['tracks']] == [64, 30280]
        assert receipt['selection_sha256'] == digest({k: v for k, v in receipt.items() if k != 'selection_sha256'})
        assert api.post(endpoint, json=choice(refs)).json() == receipt
        assert api.get(ENDPOINT + '/' + key).json()['result']['pair_selection'] == receipt
        assert api.post(endpoint, json={**choice(refs), 'video_ref': refs[80]}).status_code == 409
        assert all(word not in json.dumps(receipt) for word in (HOST, 'signature=', 'https://', '_pair_resource'))
        assert hosts == ['www.bilibili.com', 'api.bilibili.com', 'api.bilibili.com'] * 2
        with Session(api.app.state.engine) as db:
            for table in (MediaDownloadJob, MediaEntry):
                assert db.scalar(select(func.count()).select_from(table)) == 0
    with client(tmp_path) as api:
        assert api.get(ENDPOINT + '/' + key).status_code == 404


@pytest.mark.parametrize('change', ['rights', 'identity', 'dimensions', 'codec', 'host', 'path', 'size',
                                   'duplicate', 'restricted', 'header', 'missing', 'shared', 'total'])
def test_selection_drift_never_silently_substitutes(tmp_path, tracks, change):
    video, play, _ = tracks
    with client(tmp_path) as api:
        key, _, refs = prepared(api)
        v, a = play['dash']['video'][0], play['dash']['audio'][0]
        if change == 'rights':
            video['rights']['download'] = 0
        elif change == 'identity':
            video['aid'] += 1
        elif change == 'dimensions':
            v['height'] -= 1
        elif change == 'codec':
            v['codecs'] = 'av01.0.04M.08'
        elif change == 'host':
            a['baseUrl'] = 'https://example.org/other.m4s'
        elif change == 'path':
            a['baseUrl'] = f'https://{HOST}/alternate.m4s'
        elif change == 'size':
            a['size'] += 1
        elif change == 'duplicate':
            play['dash']['audio'].append(copy.deepcopy(a))
        elif change == 'restricted':
            a['is_drm'] = 1
        elif change == 'header':
            a['http_headers'] = {'Referer': 'owned'}
        elif change == 'missing':
            del play['dash']['audio']
        elif change == 'shared':
            a['baseUrl'] = v['baseUrl']
        elif change == 'total':
            a['size'] = LIMIT
        endpoint = ENDPOINT + '/' + key
        assert api.post(endpoint + '/pair-selection', json=choice(refs)).status_code == 409
        assert 'pair_selection' not in api.get(endpoint).json()['result']


def test_selection_requires_confirmed_rights_roles_space_and_live_preview(tmp_path, tracks):
    _, _, hosts = tracks
    with client(tmp_path) as api:
        key, _, refs = prepared(api)
        body = choice(refs)
        endpoint = ENDPOINT + '/' + key + '/pair-selection'
        for invalid in (dict(rights_confirmed=1), dict(rights_confirmed=False), dict(video_ref=refs[30280]),
                        dict(audio_ref=refs[64]), dict(headers={'Cookie': 'owned'})):
            assert api.post(endpoint, json={**body, **invalid}).status_code == 422
        assert api.post(endpoint.replace(PREFIX, '/api/workspaces/other'), json=body).status_code == 404
        assert api.post(endpoint, json={**body, 'video_ref': 'video-' + '0' * 64}).status_code == 409
        service = api.app.state.site_previews
        service.entries[key]['checking'] = True
        assert api.post(endpoint, json=body).status_code == 429
        service.entries[key].pop('checking')
        service.entries[key]['expires'] = time.monotonic() - 1
        assert api.post(endpoint, json=body).status_code == 404
        assert len(hosts) == 3


@pytest.mark.parametrize('end', ['cancel', 'expire'])
def test_recheck_cannot_publish_after_preview_ends(tmp_path, tracks, monkeypatch, end):
    with client(tmp_path) as api, ThreadPoolExecutor(max_workers=1) as pool:
        key, _, refs = prepared(api)
        service = api.app.state.site_previews
        child = service.child
        entered, release = Event(), Event()

        def delayed(entry):
            entered.set()
            assert release.wait(5)
            return child(entry)

        monkeypatch.setattr(service, 'child', delayed)
        endpoint = ENDPOINT + '/' + key
        request = pool.submit(api.post, endpoint + '/pair-selection', json=choice(refs))
        try:
            assert entered.wait(3)
            if end == 'cancel':
                assert api.post(endpoint + '/cancel').json()['status'] == 'cancelled'
            else:
                service.entries[key]['expires'] = time.monotonic() - 1
        finally:
            release.set()
        assert request.result(timeout=5).status_code == 409
        assert not service.entries.get(key, {}).get('pair_selection')
