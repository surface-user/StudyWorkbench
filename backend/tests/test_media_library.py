from urllib.parse import urlsplit

from sqlalchemy.orm import Session
from study_workbench.db import MediaEntry
from test_imports import SCOPE, TOKEN, client

# Container-transport fixture only. This does not prove a browser can decode its codec.
MP4 = b'\x00\x00\x00\x18ftypisom' + b'\x00' * 128


def player(c, media_id):
    url = c.get(f'{SCOPE}/media/{media_id}/player').json()['url']
    parsed = urlsplit(url)
    return parsed.path.removesuffix('/player'), parsed.query


def test_local_media_range_capability_and_playback_survive_restart(tmp_path):
    with client(tmp_path) as c:
        saved = c.post(f'{SCOPE}/media/import?filename=local.mp4', content=MP4)
        assert saved.status_code == 200, saved.text
        item = saved.json()
        assert item['status'] == 'ready' and item['size'] == len(MP4)
        assert len(c.get(f'{SCOPE}/media').json()) == 1
        prefix, cap = player(c, item['id'])
        html = c.get(prefix + '/player?' + cap)
        assert html.status_code == 200 and TOKEN not in html.text
        assert '/api/' not in html.text
        response = c.get(prefix + '/content?' + cap, headers={'Range': 'bytes=8-19'})
        assert response.status_code == 206 and response.content == MP4[8:20]
        assert c.head(prefix + '/content?' + cap).headers['content-length'] == str(len(MP4))
        assert c.get(prefix + '/content?cap=wrong').status_code == 403
        assert c.get('/api/health?'+cap, headers={'Authorization': 'bad'}).status_code == 401
        body = {'position': 12.5, 'speed': 1.5, 'subtitle': 'WEBVTT\n\n00:00:00.000 --> 00:00:02.000\n中文字幕\n'}
        assert c.post(prefix + '/state?' + cap, json=body).json() == {'saved': True}
        assert c.get(prefix + '/state?' + cap).json() == body
        assert c.post(prefix + '/state?' + cap, json={**body, 'position': -1}).status_code == 422
        assert c.post(prefix + '/state?' + cap, json={**body, 'subtitle': '<script/>'}).status_code == 422
        other = c.post('/api/workspaces', json={'name': '隔离媒体'}).json()['id']
        assert c.get(f'/api/workspaces/{other}/media').json() == []
        assert c.get(f"/api/workspaces/{other}/media/{item['id']}/player").status_code == 404
        second = c.post(f'{SCOPE}/media/import?filename=second.mp4', content=MP4).json()
        assert c.get(f"/media/library/{second['id']}/content?{cap}").status_code == 403
    with client(tmp_path) as c:
        assert c.get(prefix + '/content?' + cap).status_code == 403
        new_prefix, new_cap = player(c, item['id'])
        assert c.get(new_prefix + '/state?' + new_cap).json() == body
        assert c.get(new_prefix + '/content?' + new_cap).content == MP4
        (tmp_path / f"workspaces/default/media/{item['id']}.mp4").write_bytes(b'x' * len(MP4))
        assert c.get(new_prefix + '/content?' + new_cap).status_code == 409
        assert c.get(f"{SCOPE}/media/{item['id']}/player").status_code == 409


def test_media_stream_limits_unsupported_formats_and_auth(tmp_path, monkeypatch):
    import study_workbench.media_library as media
    monkeypatch.setattr(media, 'MEDIA_LIMIT', 32)
    with client(tmp_path) as c:
        assert c.post(f'{SCOPE}/media/import?filename=local.mp4', content=MP4, headers={'Origin': 'https://example.com'}).status_code == 403
        assert c.post(f'{SCOPE}/media/import?filename=local.mp4', content=MP4, headers={'Authorization': 'bad'}).status_code == 401
        assert c.get(f'{SCOPE}/media').json() == []
        assert c.post(f'{SCOPE}/media/import?filename=../file.mp4', content=MP4).status_code == 422
        assert c.post(f'{SCOPE}/media/import?filename=local.mkv', content=MP4).status_code == 422
        assert c.post(f'{SCOPE}/media/import?filename=local.mp4', content=iter([MP4[:24], MP4[24:]])).status_code == 413
        assert c.get(f'{SCOPE}/media').json()[0]['status'] == 'failed'
        assert c.post(f'{SCOPE}/media/import?filename=bad.mp4', content=b'not an mp4').status_code == 422
        assert c.post(f'{SCOPE}/media/import?filename=empty.mp4', content=b'').status_code == 422


def test_interrupted_media_is_marked_failed_without_deleting_bytes(tmp_path):
    with client(tmp_path) as c:
        item = c.post(f'{SCOPE}/media/import?filename=local.mp4', content=MP4).json()
        with Session(c.app.state.engine) as session, session.begin():
            session.get(MediaEntry, item['id']).status = 'importing'
    with client(tmp_path) as c:
        assert c.get(f'{SCOPE}/media').json()[0]['status'] == 'failed'
        assert (tmp_path / f"workspaces/default/media/{item['id']}.mp4").read_bytes() == MP4
