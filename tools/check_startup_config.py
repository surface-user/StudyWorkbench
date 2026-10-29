"""Exercise a selected data root with a real profile path; never use a personal database."""
import argparse
import json
import os
import secrets
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--exe', type=Path, required=True)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--data-dir', type=Path, required=True)
    parser.add_argument('--expect-warning', action='store_true')
    args = parser.parse_args()
    data, config = args.data_dir.resolve(), args.config.absolute()
    if data.exists():
        raise ValueError('Use a fresh diagnostic data directory, never personal data')
    before = config.read_bytes() if config.is_file() else None
    environment = {**os.environ, 'PYTHONUTF8': '1', 'PYTHONIOENCODING': 'utf-8',
                   'PATH': str(Path(os.environ['SystemRoot']) / 'System32')}
    environment.pop('PYTHONPATH', None)
    environment.pop('PYTHONHOME', None)
    command = [str(args.exe.resolve()), '--data-dir', str(data), '--config', str(config)]
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    for run in range(2):
        process = subprocess.Popen(command, cwd=args.exe.resolve().parent, env=environment,
                                   stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   text=True, encoding='utf-8')
        try:
            token = secrets.token_urlsafe(32)
            process.stdin.write(json.dumps({'token': token}) + '\n')
            process.stdin.flush()
            hello = process.stdout.readline()
            if not hello:
                raise RuntimeError(process.stderr.read())
            hello = json.loads(hello)
            assert Path(hello['data_dir']) == data
            assert bool(hello.get('startup_warning')) == args.expect_warning
            if args.expect_warning:
                assert str(config) in hello['startup_warning']

            def request(path, body=None):
                req = urllib.request.Request(
                    f'http://127.0.0.1:{hello["port"]}{path}',
                    headers={'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json'},
                    data=json.dumps(body).encode() if body is not None else None)
                with opener.open(req, timeout=5) as response:
                    return json.load(response)

            for _ in range(50):
                try:
                    assert request('/api/health')['status'] == 'ok'
                    break
                except urllib.error.URLError:
                    time.sleep(.1)
            else:
                raise AssertionError('not ready')
            if run == 0:
                result = request('/api/attempts', {
                    'question_id': 'demo-proof', 'response': {'text': '配置不可写仍保存作答'}})
                assert result['status'] == 'pending_review'
            else:
                assert request('/api/attempts')[0]['response']['text'] == '配置不可写仍保存作答'
            process.stdin.close()
            process.wait(timeout=10)
            assert process.returncode == 0, process.stderr.read()
            print(f'PASS: frozen startup/health/selected directory/EOF, run {run + 1}, warning={args.expect_warning}')
        finally:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=5)
            for pipe in (process.stdin, process.stdout, process.stderr):
                if not pipe.closed:
                    pipe.close()
    if args.expect_warning:
        assert (config.read_bytes() if config.is_file() else None) == before
    else:
        assert Path(json.loads(config.read_text(encoding='utf-8'))['data_dir']) == data
    print('PASS: restart retained answer; configuration preservation/save expectation met')


if __name__ == '__main__':
    main()
