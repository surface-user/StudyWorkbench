"""Real HTTP/native mux, cancellation and restored restart on pinned self-authored fixtures."""
import argparse
import hashlib
import json
import os
import queue
import secrets
import sqlite3
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from contextlib import closing, contextmanager
from pathlib import Path

FIXTURES = (
    (1479, '45fdb2e24994372e8b7568399e5c57e016550bd80ec60d10dc13dbc3a4929d7a'),
    (911, '9bfd9f2c05af35aeb733ba0cd9d7de3eb62437390326607da0ce327a5e245352'),
    (3175864, '67d7cc9c80a0e3a4c4fc68dcfc034da899b0a1deeea1df2c16ff47f64c758c16'),
    (480835, '5e893c9a36d56b0d33a63375d9f901745e8b33be1b760038a5454c7ff3288467'),
)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--exe', type=Path)
    parser.add_argument('--runtime', type=Path, required=True)
    parser.add_argument('--video-file', type=Path, required=True)
    parser.add_argument('--audio-file', type=Path, required=True)
    parser.add_argument('--long-video-file', type=Path, required=True)
    parser.add_argument('--long-audio-file', type=Path, required=True)
    parser.add_argument('--test-root', type=Path, required=True)
    args = parser.parse_args()
    inputs = [args.video_file, args.audio_file, args.long_video_file, args.long_audio_file]
    for path, (size, sha) in zip(inputs, FIXTURES, strict=True):
        assert path.stat().st_size == size and hashlib.sha256(path.read_bytes()).hexdigest() == sha
    root = args.test_root.resolve()
    root.mkdir()  # Refuse reuse of every previous profile, including failed ones.
    repo = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(repo / 'backend'))
    from study_workbench import media_probe_runtime as runtime
    from study_workbench.backup_store import connect, table_summary
    component = runtime.verify_component(args.runtime.resolve(), lambda: None)
    command = [str(args.exe.resolve())] if args.exe else [sys.executable, '-m', 'study_workbench']
    env = {**os.environ, 'PYTHONUTF8': '1', 'PYTHONIOENCODING': 'utf-8', 'STUDY_FFMPEG_RUNTIME': str(component)}
    if args.exe:
        env['PATH'] = str(Path(os.environ['SystemRoot']) / 'System32')
        env.pop('PYTHONPATH', None)
        env.pop('PYTHONHOME', None)
    cwd = root if args.exe else repo / 'backend'
    requests = 0
    prefix = '/api/workspaces/default'
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    @contextmanager
    def backend(data):
        token = secrets.token_urlsafe(32)
        process = subprocess.Popen(command + ['--data-dir', str(data)], cwd=cwd, env=env,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8',
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        try:
            process.stdin.write(json.dumps({'token': token}) + '\n')
            process.stdin.flush()
            hello = queue.Queue()
            threading.Thread(target=lambda: hello.put(process.stdout.readline()), daemon=True).start()
            port = json.loads(hello.get(timeout=30))['port']
            def request(path, body=None, expected=200, method=None):
                nonlocal requests
                payload = json.dumps(body).encode() if isinstance(body, dict) else body
                req = urllib.request.Request(f'http://127.0.0.1:{port}' + path, data=payload, method=method,
                    headers={'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json'})
                try:
                    response = opener.open(req, timeout=30)
                except urllib.error.HTTPError as error:
                    response = error
                with response:
                    status, value = response.status, json.load(response)
                requests += 1
                assert status == expected, (status, value)
                return value
            yield request, process
        finally:
            if not process.stdin.closed:
                process.stdin.close()
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
                raise AssertionError('Backend failed to stop after EOF') from None
            assert process.returncode == 0
            assert not process.stderr.read().strip(), 'Backend emitted unexpected stderr'

    def selected(request, paths):
        items = []
        for i, path in enumerate(paths):
            name = 'video.mp4' if i == 0 else 'audio.m4a'
            items.append(request(prefix + '/media/import?filename=' + name, path.read_bytes()))
        return dict(video=dict(media_id=items[0]['id'], expected_sha256=items[0]['sha256'], stream_index=0),
                    audio=dict(media_id=items[1]['id'], expected_sha256=items[1]['sha256'], stream_index=0),
                    rights_confirmed=True)

    def enqueue(request, selection, label):
        body = {**selection, 'name': label + '.mp4', 'request_id': 'owned-native-mux-' + label}
        job = request(prefix + '/media-downloads/local-pair', body)
        return body, job['id']

    def wait(request, identifier, state):
        until = time.monotonic() + 45
        while time.monotonic() < until:
            job = request(prefix + '/media-downloads/' + identifier)
            if job['status'] not in {'queued', 'running'}:
                assert job['status'] == state, job
                return job
            time.sleep(.02)
        raise AssertionError('Media task failed to reach its bounded terminal state')

    def first_probe(data, identifier):
        path = data / f'workspaces/default/downloads/{identifier}/1/1/probe0.json'
        until = time.monotonic() + 20
        while time.monotonic() < until:
            try:
                value = json.loads(path.read_text('utf-8'))
                assert value['streams'][0]['codec_type'] == 'video'
                return
            except (FileNotFoundError, json.JSONDecodeError):
                time.sleep(.002)
        raise AssertionError('Real native input probe did not start')

    def packet_hashes(path):
        result = subprocess.run([str(component / 'bin/ffprobe.exe'), '-v', 'error', '-protocol_whitelist', 'file',
            '-f', 'mov', '-enable_drefs', '0', '-use_absolute_path', '0', '-show_packets', '-show_data_hash', 'sha256',
            '-show_entries', 'packet=codec_type,data_hash', '-of', 'json', str(path.resolve())],
            cwd=root, env={**runtime.environment(root)}, capture_output=True, timeout=20,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        assert result.returncode == 0
        packets = json.loads(result.stdout)['packets']
        return {role: [p['data_hash'] for p in packets if p['codec_type'] == role] for role in ('video', 'audio')}

    def offline(options):
        result = subprocess.run(command + options, cwd=cwd, env=env, capture_output=True, timeout=60,
                                text=True, encoding='utf-8', creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        assert result.returncode == 0, result.stderr[-1000:]
        return json.loads(result.stdout.splitlines()[-1])['result']

    def files(data):
        excluded = {'.study.lock', 'study.db', 'study.db-wal', 'study.db-shm', 'study.db-journal'}
        return {p.relative_to(data).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in data.rglob('*') if p.is_file() and p.name not in excluded}

    (root / 'tmp').mkdir()
    data = root / 'data'
    with backend(data) as (request, process):
        short = selected(request, inputs[:2])
        body, identifier = enqueue(request, short, 'baseline-pair')
        ready = wait(request, identifier, 'ready')
        assert ready['result']['native_mux_performed'] is True
        output = ready['result']['output']
        assert output['metadata']['duration_ms'] == 200
        assert [(s['index'], s['role'], s['codec']) for s in output['metadata']['streams']] == [(0, 'video', 'h264'), (1, 'audio', 'aac')]
        assert request(prefix + '/media-downloads/local-pair', body)['id'] == identifier
        output_path = data / f'workspaces/default/downloads/{identifier}/1.mp4'
        actual_packets = packet_hashes(output_path)
        assert actual_packets['video'] == packet_hashes(inputs[0])['video']
        assert actual_packets['audio'] == packet_hashes(inputs[1])['audio']
        reused = dict(video=dict(media_id=ready['result']['media_id'], expected_sha256=output['sha256'], stream_index=0),
                      audio=dict(media_id=ready['result']['media_id'], expected_sha256=output['sha256'], stream_index=1),
                      rights_confirmed=True)
        _, reselected = enqueue(request, reused, 'selected-existing-tracks')
        selected_result = wait(request, reselected, 'ready')
        assert selected_result['result']['deduplicated'] and selected_result['result']['media_id'] == ready['result']['media_id']
        long = selected(request, inputs[2:])
        _, cancelled = enqueue(request, long, 'cancelled-pair')
        first_probe(data, cancelled)
        request(prefix + '/media-downloads/' + cancelled + '/pause', {})
        paused = wait(request, cancelled, 'paused')
        assert not paused['result'] and not paused['can_resume']
        retained = files(data)
        request(prefix + '/media-downloads/' + cancelled + '/retry', {'mode': 'resume'}, expected=409)
        request(prefix + '/media-downloads/' + cancelled + '/retry', {'mode': 'restart'})
        resumed = wait(request, cancelled, 'ready')
        assert resumed['attempt'] == 2
        assert all((data / p).is_file() and hashlib.sha256((data / p).read_bytes()).hexdigest() == sha for p, sha in retained.items())
        _, interrupted = enqueue(request, long, 'parent-eof-pair')
        first_probe(data, interrupted)
        process.stdin.close()
        process.wait(timeout=15)
        assert process.returncode == 0
    with sqlite3.connect(data / 'study.db') as db:
        row = db.execute('SELECT status,result FROM media_download_jobs WHERE id=?', (interrupted,)).fetchone()
        assert row[0] == 'interrupted' and json.loads(row[1]) == {}
    retained = files(data)
    package, restored = root / 'full.zip', root / 'restored'
    saved = offline(['--data-dir', str(data), '--backup-to', str(package), '--confirm-all-workspaces'])
    result = offline(['--data-dir', str(restored), '--restore-backup', str(package), '--config', str(root / 'settings.json')])
    assert saved['schema_revision'] == result['schema_revision'] == '0018'
    assert files(data) == retained == files(restored)
    with closing(connect(data / 'study.db')) as original, closing(connect(restored / 'study.db')) as copied:
        assert table_summary(original) == table_summary(copied)
    with backend(restored) as (request, _):
        interrupted_row = request(prefix + '/media-downloads/' + interrupted)
        assert interrupted_row['status'] == 'interrupted' and not interrupted_row['result']
        request(prefix + '/media-downloads/' + interrupted + '/retry', {'mode': 'restart'})
        recovered = wait(request, interrupted, 'ready')
        assert recovered['attempt'] == 2 and recovered['result']['native_mux_performed'] is True
    assert all((restored / p).is_file() and hashlib.sha256((restored / p).read_bytes()).hexdigest() == sha for p, sha in retained.items())
    for path, (size, sha) in zip(inputs, FIXTURES, strict=True):
        assert path.stat().st_size == size and hashlib.sha256(path.read_bytes()).hexdigest() == sha
    summary = dict(checks=10, http_requests=requests, frozen=bool(args.exe), real_dual_track_mux=True,
                   native_packet_hashes_retained=True, pause_after_native_probe=True, parent_eof_after_native_probe=True,
                   explicit_stream_selection_and_dedup=True,
                   explicit_restart=True, full_backup_restore=True, recovered_restart=True, original_fixtures_retained=True,
                   baseline_output=output)
    (root / 'result.json').write_text(json.dumps(summary, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(summary))


if __name__ == '__main__':
    main()
