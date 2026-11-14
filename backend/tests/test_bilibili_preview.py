"""Self-authored page/API fixtures; these tests do not contact a video site."""
import json

import pytest
from study_workbench import bilibili_preview as preview
from study_workbench import media_download_http as transport

PAGE = 'https://www.bilibili.com/video/BV1234567890'


@pytest.fixture
def source():
    state = {'videoData': {'bvid': 'BV1234567890', 'aid': 7, 'cid': 9,
                          'title': '自编公开视频样本', 'duration': 120,
                          'pages': [{'cid': 9}], 'rights': {}}}
    nav = {'code': -101, 'data': {'wbi_img': {
        'img_url': 'https://i0.hdslb.com/bfs/wbi/' + 'a' * 32 + '.png',
        'sub_url': 'https://i0.hdslb.com/bfs/wbi/' + 'b' * 32 + '.png'}}}
    play = {'code': 0, 'data': {'timelength': 120000, 'dash': {
        'video': [{'id': 64, 'baseUrl': 'https://media.example.org/fixture.m4s?private=fixture',
                   'mimeType': 'video/mp4', 'codecs': 'avc1.fixture', 'width': 1280, 'height': 720,
                   'frameRate': '30', 'bandwidth': 800000}],
        'audio': [{'id': 30280, 'baseUrl': 'https://media.example.org/audio.m4s',
                   'mimeType': 'audio/mp4', 'codecs': 'mp4a.fixture'}]}}}
    return state, nav, play


def encoded(value):
    return json.dumps(value, ensure_ascii=False).encode('utf-8')


class Response:
    def __init__(self, data, mime='application/json', status=200, extra=()):
        self.data, self.position, self.status = data, 0, status
        self.fields = [('Content-Type', mime), ('Content-Length', str(len(data))), *extra]

    def getheaders(self):
        return self.fields

    def read(self, size):
        result = self.data[self.position:self.position + size]
        self.position += len(result)
        return result


def network(monkeypatch, source, *, page_extra='', responses=None):
    state, nav, play = source
    if page_extra:
        state['videoData']['ignored_script'] = page_extra
    view = {'code': state.get('error', {}).get('trueCode', 0),
            'data': {'View': state.get('videoData'), 'extra': state.get('extra')}}
    defaults = [Response(encoded(nav)), Response(encoded(view)), Response(encoded(play))]
    pending, calls, closed = list(responses or defaults), [], []

    class Connection:
        def __init__(self, host, address):
            assert address == '93.184.216.34'
            self.host = host

        def request(self, method, target, headers):
            calls.append((self.host, method, target, dict(headers)))

        def getresponse(self):
            assert pending, 'Unexpected additional resource request'
            return pending.pop(0)

        def close(self):
            closed.append(self.host)

    monkeypatch.setattr(preview, 'resolve', lambda host: '93.184.216.34')
    monkeypatch.setattr(preview, 'PinnedHTTPS', Connection)
    monkeypatch.setattr(preview.time, 'time', lambda: 1700000000)
    return calls, closed, pending


def test_fixed_nav_view_and_signed_playinfo_only(monkeypatch, source):
    calls, closed, pending = network(monkeypatch, source, page_extra='throw new Error("must not execute");')
    result = preview.extract(PAGE)
    assert result['title'] == '自编公开视频样本' and result['video_id'] == 'BV1234567890'
    assert result['extractor_version'] == preview.VERSION
    assert len(result['formats']) == 2 and all(x['requires_merge'] for x in result['formats'])
    assert result['formats'][0]['height'] == 720
    assert result['formats'][1]['container'] == 'm4a'
    assert len(calls) == len(closed) == 3 and not pending
    assert [c[0] for c in calls] == ['api.bilibili.com'] * 3
    assert all(c[3]['User-Agent'] == preview.USER_AGENT for c in calls)
    assert all(c[1] == 'GET' and c[3]['Accept-Encoding'] == 'identity' for c in calls)
    assert all('Cookie' not in c[3] and 'Authorization' not in c[3] for c in calls)
    assert 'w_rid=' in calls[2][2] and 'wts=1700000000' in calls[2][2]
    assert 'try_look' not in calls[2][2] and 'dm_img' not in calls[2][2]


@pytest.mark.parametrize('url', ['https://evil.example.org/video/BV1234567890',
                                  'http://www.bilibili.com/video/BV1234567890',
                                  PAGE + '?p=2', PAGE + '?p=1&p=2',
                                  'https://www.bilibili.com/bangumi/play/ep123',
                                  'https://live.bilibili.com/123',
                                  'https://user:secret@www.bilibili.com/video/BV1234567890'])
def test_unsupported_input_never_resolves(monkeypatch, url):
    monkeypatch.setattr(preview, 'resolve', lambda _: pytest.fail('Must reject before DNS'))
    with pytest.raises(preview.DownloadError):
        preview.extract(url)


@pytest.mark.parametrize('kind', ['paid', 'interactive', 'multiple_pages', 'supporter',
                                  'wrong_video', 'bangumi_redirect', 'missing_state',
                                  'trial_flag', 'trial_duration', 'trial_description', 'page_identity'])
def test_restricted_or_changed_source_never_produces_candidates(monkeypatch, source, kind):
    state, _, play = source
    video = state['videoData']
    if kind == 'paid':
        video['rights']['pay'] = 1
    elif kind == 'interactive':
        video['rights']['is_stein_gate'] = 1
    elif kind == 'multiple_pages':
        video['pages'].append({'cid': 10})
    elif kind == 'supporter':
        video['is_upower_exclusive'] = 1
    elif kind == 'wrong_video':
        video['bvid'] = 'BV0000000000'
    elif kind == 'bangumi_redirect':
        video['redirect_url'] = 'https://www.bilibili.com/bangumi/play/ep1'
    elif kind == 'missing_state':
        state.pop('videoData')
    elif kind == 'trial_flag':
        play['data']['is_preview'] = True
    elif kind == 'trial_duration':
        play['data']['timelength'] = 10000
    elif kind == 'trial_description':
        play['data']['accept_description'] = ['试看']
    elif kind == 'page_identity':
        video['pages'][0]['cid'] = 10
    network(monkeypatch, source)
    with pytest.raises(preview.DownloadError):
        preview.extract(PAGE)


@pytest.mark.parametrize('target', ['https://private.example.org/video/BV1234567890',
                                    'http://www.bilibili.com/video/BV1234567890',
                                    'https://api.bilibili.com/private',
                                    'https://www.bilibili.com/bangumi/play/ep1'])
def test_redirect_destination_is_checked_before_dns(monkeypatch, source, target):
    calls, _, _ = network(monkeypatch, source, responses=[Response(b'', status=302, extra=[('Location', target)])])
    with pytest.raises(preview.DownloadError):
        preview.extract('https://b23.tv/selfauthored')
    assert len(calls) == 1


def test_valid_short_redirect_keeps_fixed_headers_and_connection_policy(monkeypatch, source):
    state, nav, play = source
    responses = [Response(b'', status=302, extra=[('Location', PAGE)]),
                 Response(encoded(nav)), Response(encoded({'code': 0, 'data': {'View': state['videoData']}})),
                 Response(encoded(play))]
    calls, closed, pending = network(monkeypatch, source, responses=responses)
    result = preview.extract('https://b23.tv/selfauthored')
    assert result['video_id'] == 'BV1234567890' and len(calls) == len(closed) == 4 and not pending


@pytest.mark.parametrize('kind', ['compressed', 'duplicate_length', 'too_big', 'formats', 'title'])
def test_response_and_result_budgets_fail_without_truncation(monkeypatch, source, kind):
    if kind == 'formats':
        source[2]['data']['dash']['video'] *= 65
    elif kind == 'title':
        source[0]['videoData']['title'] = 'x' * 513
    calls, _, _ = network(monkeypatch, source)
    if kind in {'compressed', 'duplicate_length', 'too_big'}:
        extra = [('Content-Encoding', 'gzip')] if kind == 'compressed' else [('Content-Length', '999')]
        response = Response(b'x' * (preview.RESPONSE_LIMIT + 1)) if kind == 'too_big' else Response(b'{}', extra=extra)
        calls, _, _ = network(monkeypatch, source, responses=[response])
    with pytest.raises(preview.DownloadError):
        preview.extract(PAGE)


def test_legacy_segmented_format_is_one_candidate_and_not_a_silent_quality_choice(monkeypatch, source):
    source[2]['data'] = {'timelength': 120000, 'quality': 32, 'durl': [
        {'url': 'https://media.example.org/one.mp4', 'size': 100},
        {'url': 'https://media.example.org/two.mp4', 'size': 200}]}
    network(monkeypatch, source)
    formats = preview.extract(PAGE)['formats']
    assert len(formats) == 1 and formats[0]['delivery'] == 'segments'
    assert formats[0]['requires_merge'] and formats[0]['size_bytes'] == 300


def test_parent_cancellation_prevents_another_request(monkeypatch, source):
    calls, _, _ = network(monkeypatch, source)

    def cancelled():
        raise preview.DownloadError('预览已取消')

    with pytest.raises(preview.DownloadError, match='取消'):
        preview.extract(PAGE, checkpoint=cancelled)
    assert not calls


def test_only_predeclared_api_paths_receive_requests(monkeypatch, source):
    calls, _, pending = network(monkeypatch, source)
    result = preview.extract(PAGE)
    assert len(result['formats']) == 2 and result['format_source'] == 'wbi_api'
    assert calls[0][2] == '/x/web-interface/nav'
    assert calls[1][2].startswith('/x/web-interface/wbi/view/detail?')
    assert calls[2][2].startswith('/x/player/wbi/playurl?')
    assert len(calls) == 3 and not pending


@pytest.mark.parametrize('kind', ['access_denied', 'play_denied', 'wrong_cid', 'boolean_code'])
def test_explicit_api_restriction_does_not_try_other_endpoints(monkeypatch, source, kind):
    state, _, play = source
    if kind == 'access_denied':
        state['error'] = {'trueCode': -403}
    elif kind == 'play_denied':
        play['code'] = -403
    elif kind == 'wrong_cid':
        play['data']['cid'] = 10
    else:
        play['code'] = False
    calls, _, _ = network(monkeypatch, source)
    with pytest.raises(preview.DownloadError):
        preview.extract(PAGE)
    assert len(calls) == (2 if kind == 'access_denied' else 3)


@pytest.mark.parametrize('addresses', [['127.0.0.1'], ['198.18.0.1'], ['93.184.216.34', '10.0.0.1']])
def test_every_preview_request_keeps_existing_all_address_dns_guard(monkeypatch, addresses):
    monkeypatch.setattr(transport.socket, 'getaddrinfo', lambda *_a, **_k: [
        (2, 1, 6, '', (address, 443)) for address in addresses])
    monkeypatch.setattr(preview, 'PinnedHTTPS', lambda *_: pytest.fail('Forbidden DNS reached transport'))
    with pytest.raises(preview.DownloadError, match='公网IPv4'):
        preview.extract(PAGE)


def test_request_and_redirect_budgets_count_actual_requests(monkeypatch, source):
    calls, _, _ = network(monkeypatch, source, responses=[Response(b'{}') for _ in range(10)])
    client = preview.Client(lambda: None)
    for _ in range(10):
        client.fetch(preview.NAV)
    with pytest.raises(preview.DownloadError, match='10次'):
        client.fetch(preview.NAV)
    assert len(calls) == 10
    calls, _, _ = network(monkeypatch, source, responses=[
        Response(b'', status=302, extra=[('Location', 'https://b23.tv/again')]) for _ in range(4)])
    with pytest.raises(preview.DownloadError, match='3跳'):
        preview.extract('https://b23.tv/selfauthored')
    assert len(calls) == 4


@pytest.mark.parametrize('kind', ['json_depth', 'json_nodes', 'bad_fps', 'drm', 'range'])
def test_additional_source_boundaries_are_not_silently_ignored(monkeypatch, source, kind):
    state, _, play = source
    if kind == 'json_depth':
        value = {}
        for _ in range(66):
            value = {'child': value}
        state['extra'] = value
    elif kind == 'json_nodes':
        state['extra'] = [0] * 50001
    elif kind == 'bad_fps':
        play['data']['dash']['video'][0]['frameRate'] = '0/0'
    elif kind == 'drm':
        play['data']['dash']['video'][0]['drm_tech_type'] = 1
    network(monkeypatch, source)
    if kind == 'range':
        network(monkeypatch, source, responses=[Response(b'{}', extra=[('Content-Range', 'bytes 0-1/2')])])
    with pytest.raises(preview.DownloadError):
        preview.extract(PAGE)


def test_returned_dolby_and_flac_audio_are_not_omitted(monkeypatch, source):
    dash = source[2]['data']['dash']
    dash['dolby'] = {'audio': [dict(dash['audio'][0], id=30250)]}
    dash['flac'] = {'audio': dict(dash['audio'][0], id=30251, mimeType='audio/flac', codecs='flac')}
    network(monkeypatch, source)
    result = preview.extract(PAGE)['formats']
    assert len(result) == 4
    assert [row['source_format_id'] for row in result] == [64, 30280, 30250, 30251]
    assert result[-1]['container'] == 'flac' and result[-1]['requires_merge']


def test_av_identity_and_tracking_parameters_are_not_forwarded(monkeypatch, source):
    calls, _, _ = network(monkeypatch, source)
    result = preview.extract('https://bilibili.com/video/av7?spm_id_from=private-tracker')
    assert result['video_id'] == 'BV1234567890' and result['source_cid'] == 9
    assert result['source_url'] == 'https://www.bilibili.com/video/av7'
    assert 'aid=7' in calls[1][2] and 'bvid=' not in calls[1][2]
    assert all('private-tracker' not in str(call) for call in calls)


def test_view_data_shape_change_is_a_bounded_error(monkeypatch, source):
    calls, _, _ = network(monkeypatch, source, responses=[Response(encoded(source[1])),
        Response(encoded({'code': 0, 'data': None}))])
    with pytest.raises(preview.DownloadError):
        preview.extract(PAGE)
    assert len(calls) == 2


def test_navigation_rejection_stops_before_any_alternate_request(monkeypatch, source):
    source[1]['code'] = -352
    calls, _, _ = network(monkeypatch, source)
    with pytest.raises(preview.DownloadError, match='暂不允许预览'):
        preview.extract(PAGE)
    assert len(calls) == 1
