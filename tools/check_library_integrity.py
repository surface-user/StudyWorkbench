"""Black-box frozen diagnostics: create fresh fixtures through HTTP, preserve all business bytes."""
import argparse
import hashlib
import json
import os
import queue
import re
import secrets
import subprocess
import threading
import urllib.request
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--exe', type=Path, required=True)
    parser.add_argument('--test-root', type=Path, required=True)
    args = parser.parse_args()
    root = args.test_root.resolve()
    root.mkdir()  # Never reuse or erase a previous fixture or personal library.
    data = root / 'data'
    command = [str(args.exe.resolve()), '--data-dir', str(data)]
    env = {**os.environ, 'PATH': str(Path(os.environ['SystemRoot']) / 'System32')}
    for key in ['PYTHONPATH', 'PYTHONHOME']:
        env.pop(key, None)
    token = secrets.token_urlsafe(32)
    process = subprocess.Popen(command, env=env, cwd=root, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, text=True, encoding='utf-8',
                               creationflags=subprocess.CREATE_NO_WINDOW)

    def inspect(expected):
        before = snapshot()
        run = subprocess.run(command + ['--check-library', '--confirm-all-workspaces'], env=env, cwd=root,
                             capture_output=True, text=True, encoding='utf-8', timeout=60,
                             creationflags=subprocess.CREATE_NO_WINDOW)
        assert run.returncode == expected, run.stderr[-1000:]
        result = json.loads(run.stdout)['result']
        assert result['complete'] and not result['data_modified'] and not result['repair_performed']
        assert snapshot() == before, 'Offline diagnostics changed business data'
        return result

    def snapshot():
        return {p.relative_to(data).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in data.rglob('*') if p.is_file() and p.name != '.study.lock'}

    try:
        process.stdin.write(json.dumps({'token': token}) + '\n')
        process.stdin.flush()
        hello = queue.Queue()
        threading.Thread(target=lambda: hello.put(process.stdout.readline()), daemon=True).start()
        port = json.loads(hello.get(timeout=30))['port']
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        request = urllib.request.Request(f'http://127.0.0.1:{port}/api/workspaces/default/markdown-notes',
            data=json.dumps({'name': '巡检样本.md', 'request_id': 'integrity-blackbox-note-0001'}).encode(),
            headers={'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json'})
        with opener.open(request, timeout=30) as response:
            node = json.load(response)['resource_item_id']
        assert re.fullmatch('[a-f0-9]{32}', node)
        blocked = subprocess.run(command + ['--check-library', '--confirm-all-workspaces'], env=env, cwd=root,
                                 capture_output=True, timeout=30, creationflags=subprocess.CREATE_NO_WINDOW)
        assert blocked.returncode != 0, 'Diagnostics bypassed the active application lock'
        process.stdin.close()
        assert process.wait(timeout=20) == 0
        assert not process.stderr.read().strip()
        healthy = inspect(0)
        assert healthy['healthy'] and not healthy['issues']
        orphan = data / 'workspaces/default/working' / node / 'orphan-generation'
        orphan.mkdir()
        (orphan / 'keep').write_bytes(b'self-authored retained orphan')
        found = inspect(1)
        assert not found['healthy']
        assert found['issues'] == [dict(code='unreferenced_derived_candidate', severity='warning',
                                       relative_path=orphan.relative_to(data).as_posix())]
        current = data / 'workspaces/default/working' / node / 'note/current.md'
        current.write_bytes(b'external workfile edit must survive diagnostics')
        changed = inspect(1)
        assert {item['code'] for item in changed['issues']} == {
            'unreferenced_derived_candidate', 'workfile_index_changed'}
        summary = dict(frozen=True, active_lock_refused=True, healthy_case_verified=True, orphan_detected=True,
                       external_edit_detected=True, business_bytes_preserved=True, repair_performed=False)
        (root / 'result.json').write_text(json.dumps(summary, indent=2) + '\n', encoding='utf-8')
        print(json.dumps(summary))
    finally:
        if process.poll() is None:
            process.stdin.close()
            try:
                process.wait(timeout=20)
            except subprocess.TimeoutExpired:
                process.kill()  # Only this script's retained fixture process.
                process.wait(timeout=10)


if __name__ == '__main__':
    main()
