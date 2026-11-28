"""Run the site confirmation/queue/restore path on two pinned, self-authored response bodies."""
import argparse
import hashlib
import subprocess
import sys
from pathlib import Path

import pytest
from check_media_mux import FRAGMENT_FIXTURES


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime', type=Path, required=True)
    parser.add_argument('--fragment-tracks', type=Path, nargs=2, metavar=('VIDEO', 'AUDIO'), required=True)
    parser.add_argument('--test-root', type=Path, required=True)
    parser.add_argument('--mux-exe', type=Path, help='exercise the packaged native mux worker')
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[1]
    sys.path[:0] = [str(repo / 'backend'), str(repo / 'backend/tests')]
    from study_workbench import backup_store
    from test_bilibili_preview import source
    from test_explorer import client
    from test_media_downloads import wait
    from test_site_pair_download import offline_transport, selected
    from test_site_pair_selection import tracks

    bodies = []
    for path, (size, digest) in zip(args.fragment_tracks, FRAGMENT_FIXTURES, strict=True):
        assert path.stat().st_size == size
        raw = path.read_bytes()
        assert hashlib.sha256(raw).hexdigest() == digest
        bodies.append(raw)
    root = args.test_root.resolve()
    root.mkdir()  # Preserve every previous test profile and archive.
    data, restored = root / 'library', root / 'restored'
    with pytest.MonkeyPatch.context() as patch:
        patch.setenv('STUDY_FFMPEG_RUNTIME', str(args.runtime.resolve()))
        video, play, _ = tracks.__wrapped__(patch, source.__wrapped__())
        video['duration'], play['timelength'] = 1, 220
        play['dash']['video'][0].update(width=16, height=16)
        for role in ('video', 'audio'):
            play['dash'][role][0]['size'] = None
        offline_transport(patch, bodies, native=True)
        if args.mux_exe:
            exe = args.mux_exe.resolve(strict=True)
            launch = subprocess.Popen

            def packaged(command, *args, **kwargs):
                if command[-1] == '--mux-media':
                    command = [str(exe), '--mux-media']
                return launch(command, *args, **kwargs)

            patch.setattr(subprocess, 'Popen', packaged)
        with client(data) as api:
            url, body = selected(api)
            response = api.post(url + '/confirm-pair', json=body)
            assert response.status_code == 200, response.text
            identifier = response.json()['id']
            job = wait(api, identifier, {'ready', 'failed'})
            assert job['status'] == 'ready', job['error']
            output = job['result']['output']
            expected = 'd62f2c8b02e7eec8603bb2c2d2ae13928127ef23ea917d99c3f4ca4f20801731'
            assert [(t['role'], t['codec']) for t in output['metadata']['streams']] == [('video', 'h264'), ('audio', 'aac')]
            assert output['size'] == 2173 and output['sha256'] == expected
        archive = root / 'backup.zip'
        backup_store.create_backup(data, archive)
        backup_store.restore_backup(archive, restored, root / 'settings.json')
        with client(restored) as api:
            assert api.post(url + '/confirm-pair', json=body).json()['id'] == identifier
        final = restored / 'workspaces/default/downloads' / identifier / '1.mp4'
        assert hashlib.sha256(final.read_bytes()).hexdigest() == expected
        assert b'signature=' not in (restored / 'study.db').read_bytes()
    print('PASS: confirmed H.264/AAC tracks, one 2173-byte MP4, restored output and confirmation')


if __name__ == '__main__':
    main()
