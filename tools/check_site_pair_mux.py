"""Feed two fixed, self-authored DASH responses through the public selection API and the native mux worker."""
import argparse
import hashlib
import subprocess
import sys
from pathlib import Path

from check_media_mux import FRAGMENT_FIXTURES

ROOT = Path(__file__).resolve().parents[1]
REORDERED = (
    (49454, 'f59e2ac309ff07bf18a3bd5c4873d6641969618cbb23bbee9b908ff45fed205f'),
    (23000, 'a6a2062ba000265790dc8ec2b5ef5dd8e4068e794a88776be6738b2d64a871d0'),
)


def fixture_data(paths):
    sizes = tuple(p.stat().st_size for p in paths)
    for case in (FRAGMENT_FIXTURES, REORDERED):
        if sizes == tuple(size for size, _ in case):
            bodies = [p.read_bytes() for p in paths]
            if all(hashlib.sha256(raw).hexdigest() == digest for raw, (_, digest) in zip(bodies, case, strict=True)):
                return case, bodies
    raise ValueError('Unexpected generated fixture sizes or contents')


def acquisition_worker(video, audio):
    from pytest import MonkeyPatch
    from study_workbench.media_download_worker import worker
    from test_media_download_http import Response, connections

    responses = []
    _, bodies = fixture_data((video, audio))
    for data in bodies:
        responses.append(Response(data, fields=[('Content-Type', 'application/octet-stream'),
                                                ('Content-Length', str(len(data)))]))
    with MonkeyPatch.context() as patch:
        connections(patch, responses)
        worker()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime', required=True, type=Path)
    parser.add_argument('--fragment-tracks', required=True, type=Path, nargs=2, metavar=('VIDEO', 'AUDIO'))
    parser.add_argument('--test-root', required=True, type=Path)
    parser.add_argument('--mux-exe', type=Path, help='Use this packaged backend for its native mux worker.')
    args = parser.parse_args()
    video_file, audio_file = [p.resolve(strict=True) for p in args.fragment_tracks]
    case, _ = fixture_data((video_file, audio_file))
    test_root = args.test_root.resolve()
    test_root.mkdir()
    from pytest import MonkeyPatch
    from study_workbench import backup_store
    from test_bilibili_preview import source
    from test_explorer import client
    from test_media_downloads import wait
    from test_site_pair_download import selected
    from test_site_pair_selection import tracks

    profile = test_root / 'library'
    with MonkeyPatch.context() as patch:
        patch.setenv('STUDY_FFMPEG_RUNTIME', str(args.runtime.resolve(strict=True)))
        video, play, _ = tracks.__wrapped__(patch, source.__wrapped__())
        if case == REORDERED:
            video['duration'], play['timelength'] = 2, 2400
            play['dash']['video'][0].update(width=320, height=180)
            expected = (71599, '0d9eeb248cb2130a09c21d8e2561b7e96a95803e148c35a47c774c47f5e5f51b')
        else:
            video['duration'], play['timelength'] = 1, 220
            play['dash']['video'][0].update(width=16, height=16)
            expected = (2173, 'd62f2c8b02e7eec8603bb2c2d2ae13928127ef23ea917d99c3f4ca4f20801731')
        for kind in ('video', 'audio'):
            play['dash'][kind][0]['size'] = None
        launch = subprocess.Popen
        workers = []

        def launch_worker(command, *a, **kw):
            if command[-1] == '--download-media':
                workers.append('acquire')
                command = [sys.executable, str(Path(__file__).resolve()), '--fixture-transport',
                           str(video_file), str(audio_file)]
            elif command[-1] == '--mux-media':
                workers.append('mux')
                if args.mux_exe:
                    command = [str(args.mux_exe.resolve(strict=True)), '--mux-media']
            return launch(command, *a, **kw)

        patch.setattr(subprocess, 'Popen', launch_worker)
        with client(profile) as api:
            endpoint, confirmation = selected(api)
            response = api.post(endpoint + '/confirm-pair', json=confirmation)
            assert response.status_code == 200, response.text
            identifier = response.json()['id']
            job = wait(api, identifier, {'ready', 'failed'})
            assert job['status'] == 'ready', job['error']
            receipt = job['result']['output']
            assert [(s['role'], s['codec']) for s in receipt['metadata']['streams']] == [('video', 'h264'), ('audio', 'aac')]
            assert (receipt['size'], receipt['sha256']) == expected
            assert workers == ['acquire', 'mux']
        archive, restored = test_root / 'backup.zip', test_root / 'restored'
        backup_store.create_backup(profile, archive)
        backup_store.restore_backup(archive, restored, test_root / 'settings.json')
        with client(restored) as api:
            replay = api.post(endpoint + '/confirm-pair', json=confirmation)
            assert replay.status_code == 200, replay.text
            assert replay.json()['id'] == identifier
        output = restored / 'workspaces/default/downloads' / identifier / '1.mp4'
        assert hashlib.sha256(output.read_bytes()).hexdigest() == expected[1]
        assert b'signature=' not in (restored / 'study.db').read_bytes()
    print(f'PASS: confirmed H.264/AAC tracks, one {expected[0]}-byte MP4, restored output and confirmation')


if __name__ == '__main__':
    sys.path[:0] = [str(ROOT / 'backend'), str(ROOT / 'backend/tests')]
    if len(sys.argv) == 4 and sys.argv[1] == '--fixture-transport':
        acquisition_worker(Path(sys.argv[2]), Path(sys.argv[3]))
    else:
        main()
