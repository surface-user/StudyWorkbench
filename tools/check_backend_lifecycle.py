"""Real source/frozen lifecycle, lock, append/restart and crash recovery check."""
import argparse
import hashlib
import json
import os
import secrets
import socket
import sqlite3
import struct
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from contextlib import closing
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--exe", type=Path)
    parser.add_argument("--seed-db", type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parent.parent
    command = [str(args.exe.resolve())] if args.exe else [sys.executable, "-m", "study_workbench"]
    environment = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}
    # The executable must work without the source directory or a developer Python on PATH.
    if args.exe:
        environment["PATH"] = str(Path(os.environ["SystemRoot"]) / "System32")
        environment.pop("PYTHONPATH", None)
        environment.pop("PYTHONHOME", None)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with tempfile.TemporaryDirectory(prefix="study-lifecycle-中文-") as temporary:
        data = Path(temporary) / "data space"
        baseline = 0
        if args.seed_db:
            data.mkdir()
            with closing(sqlite3.connect(args.seed_db.resolve().as_uri() + "?mode=ro", uri=True)) as original:
                with closing(sqlite3.connect(data / "study.db")) as copied:
                    original.backup(copied)
                    baseline = copied.execute("SELECT count(*) FROM attempts").fetchone()[0]
        processes = []

        def launch():
            process = subprocess.Popen(command + ["--data-dir", str(data)],
                                       cwd=temporary if args.exe else root / "backend", env=environment,
                                       stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                       text=True, encoding="utf-8")
            processes.append(process)
            token = secrets.token_urlsafe(32)
            process.stdin.write(json.dumps({"token": token}) + "\n")
            process.stdin.flush()
            return process, token

        def ready(process, token):
            hello = process.stdout.readline()
            if not hello:
                raise RuntimeError(process.stderr.read())
            port = json.loads(hello)["port"]

            def request(path, body=None, bearer=token, origin=None, *, raw=None, binary=False, timeout=5):
                headers = {"Authorization": f"Bearer {bearer}", "Content-Type": "application/json"}
                if origin:
                    headers["Origin"] = origin
                if raw is not None:
                    headers["Content-Type"] = "application/octet-stream"
                req = urllib.request.Request(f"http://127.0.0.1:{port}{path}", headers=headers,
                                             data=raw if raw is not None else json.dumps(body).encode() if body is not None else None)
                with opener.open(req, timeout=timeout) as response:
                    return response.read() if binary else json.load(response)
            for _ in range(50):
                try:
                    assert request("/api/health")["status"] == "ok"
                    return request, port
                except urllib.error.URLError:
                    time.sleep(0.1)
            raise RuntimeError("Backend not ready")

        try:
            first, token = launch()
            request, port = ready(first, token)
            state = request("/api/workbench")
            assert state["active_workspace_id"] in {space["id"] for space in state["workspaces"]}
            second, _ = launch()
            second.wait(timeout=10)
            assert second.returncode != 0
            assert "实例" in second.stderr.read()
            for bearer, origin, status in [("wrong", None, 401), (token, "https://example.com", 403)]:
                try:
                    request("/api/health", bearer=bearer, origin=origin)
                    raise AssertionError("Unauthorized request accepted")
                except urllib.error.HTTPError as error:
                    assert error.code == status
            assert request("/api/attempts", {"question_id": "demo-integral", "response": {"selected": ["a"]}})["score"] == 1
            assert request("/api/attempts", {"question_id": "demo-proof", "response": {"text": "中文进程测试"}})["status"] == "pending_review"
            assert len(request("/api/attempts")) == baseline + 2
            existing_notes = request("/api/workspaces/default/notes")
            md_scope = '/api/workspaces/default'
            # A transport-only MP4 header fixture; codec playback is tested in the Windows integration suite.
            media_fixture = b'\x00\x00\x00\x18ftypisom' + b'\x00' * 128
            media_item = request(f'{md_scope}/media/import?filename=transport.mp4', raw=media_fixture)
            assert media_item['status'] == 'ready'
            media_player = urllib.parse.urlsplit(request(f"{md_scope}/media/{media_item['id']}/player")['url'])
            media_prefix = media_player.path.removesuffix('/player')
            playback = {'position': 2.0, 'speed': 1.5, 'subtitle': 'WEBVTT\n\n00:00:00.000 --> 00:00:03.000\nlocal\n'}
            assert request(f'{media_prefix}/content?{media_player.query}', binary=True) == media_fixture
            assert request(f'{media_prefix}/state?{media_player.query}', playback)['saved']
            baseline_markdown = len(request(f'{md_scope}/question-markdown'))
            markdown_bytes = {}
            for suffix in ('docx', 'pdf'):
                sample = (root / f'contracts/samples/numbered-questions.{suffix}').read_bytes()
                split_job = request(f'{md_scope}/imports?filename=numbered.{suffix}', raw=sample, timeout=35)
                assert split_job['status'] == 'preview' and len(split_job['preview']['question_drafts']) == 2
                selection = {'expected_revision': split_job['draft_revision'], 'selected': [0, 1], 'confirm': True}
                items = request(f"{md_scope}/imports/{split_job['id']}/question-markdown", selection)
                assert len(items) == 2
                assert request(f"{md_scope}/imports/{split_job['id']}/question-markdown", selection) == items
                for item in items:
                    url = f"{md_scope}/resources/{item['markdown_resource_id']}"
                    markdown_bytes[url] = request(url, binary=True)
                    detail = request(f"{md_scope}/question-markdown/{item['id']}")
                    assert (b'assets/' in markdown_bytes[url]) == any(b['type'] == 'image' for b in detail['blocks'])
                    assert b'not_inferred' in markdown_bytes[url]
            original = ("冻结进程原件与迁移保留-" + secrets.token_hex(8)).encode("utf-8")
            job = request("/api/workspaces/default/imports?filename=note.md", raw=original)
            assert job["status"] == "preview"
            assert request("/api/workspaces/default/notes") == existing_notes
            assert request(f"/api/workspaces/default/imports/{job['id']}/confirm", {})["status"] == "confirmed"
            assert request(f"/api/workspaces/default/imports/{job['id']}/confirm", {})["status"] == "confirmed"
            resource_url = f"/api/workspaces/default/resources/{job['resource_id']}"
            assert request(resource_url, binary=True) == original
            # Abort an actual TCP response before EOF; Windows Proactor previously hung here.
            with socket.create_connection(("127.0.0.1", port), timeout=5) as aborted:
                aborted.sendall(b"GET /api/health HTTP/1.1\r\nHost: 127.0.0.1\r\n\r\n")
                assert aborted.recv(512)
                linger = struct.pack("HH" if os.name == "nt" else "ii", 1, 0)
                aborted.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, linger)
            first.stdin.close()
            first.wait(timeout=10)
            assert first.returncode == 0
            print("PASS: reset TCP connection followed by parent EOF exits within 10 seconds")
            restarted, token = launch()
            request, _ = ready(restarted, token)
            assert len(request("/api/attempts")) == baseline + 2
            assert request(resource_url, binary=True) == original
            restarted.kill()
            restarted.wait(timeout=5)
            recovered, token = launch()
            request, _ = ready(recovered, token)
            assert len(request("/api/attempts")) == baseline + 2
            assert request(resource_url, binary=True) == original
            recovered.stdin.close()
            recovered.wait(timeout=10)
            assert recovered.returncode == 0
            settings = Path(temporary) / "settings.json"
            settings.write_text(json.dumps({"version": 1, "data_dir": str(data)}), encoding="utf-8")
            for name in ("relocated-first", "relocated-second"):
                target = Path(temporary) / name
                old_receipts = {p.name: p.read_bytes() for p in data.glob("migration-receipt*.json")}
                moved = subprocess.run(command + ["--data-dir", str(data), "--move-data", str(target),
                                                  "--config", str(settings)],
                                       cwd=temporary if args.exe else root / "backend", env=environment,
                                       capture_output=True, text=True, encoding="utf-8", timeout=30)
                assert moved.returncode == 0, moved.stderr
                assert json.loads(moved.stdout)["source_retained"]
                assert (data / "study.db").is_file()
                assert json.loads(settings.read_text(encoding="utf-8"))["data_dir"] == str(target)
                for receipt_name, content in old_receipts.items():
                    assert (target / receipt_name).read_bytes() == content
                added = [p for p in target.glob("migration-receipt*.json") if p.name not in old_receipts]
                assert len(added) == 1
                for relative, expected in json.loads(added[0].read_text(encoding="utf-8"))["files"].items():
                    with (target / relative).open("rb") as handle:
                        assert hashlib.file_digest(handle, "sha256").hexdigest() == expected, relative
                data = target
            relocated, token = launch()
            request, _ = ready(relocated, token)
            assert len(request("/api/attempts")) == baseline + 2
            assert request(resource_url, binary=True) == original
            notes = request("/api/workspaces/default/notes")
            assert len(request(f'{md_scope}/question-markdown')) == baseline_markdown + 4
            for url, expected in markdown_bytes.items():
                assert request(url, binary=True) == expected
            media_player = urllib.parse.urlsplit(request(f"{md_scope}/media/{media_item['id']}/player")['url'])
            assert request(f'{media_prefix}/state?{media_player.query}') == playback
            assert request(f'{media_prefix}/content?{media_player.query}', binary=True) == media_fixture
            assert len(notes) == len(existing_notes) + 1
            assert next(note for note in notes if note["id"] == job["id"])["content"][0]["text"] == original.decode("utf-8")
            relocated.stdin.close()
            relocated.wait(timeout=10)
            assert relocated.returncode == 0
            print("PASS: two CLI relocations preserve old receipts, hashes and all attempts; restart succeeds")
            print("PASS: import preview/confirmation, idempotency, original bytes and note survive restart, crash and relocations")
            print('PASS: DOCX/PDF each split into two independent Markdown files; bytes survive restart/crash/two relocations')
            print('PASS: local media import, scoped capability, bytes and playback state survive restart/crash/two relocations')
            abandoned = subprocess.run(command + ["--data-dir", str(data), "--move-data", str(Path(temporary) / "abandoned"),
                                                  "--config", str(settings), "--parent-pipe"],
                                       cwd=temporary if args.exe else root / "backend", env=environment,
                                       stdin=subprocess.DEVNULL, capture_output=True, text=True, encoding="utf-8", timeout=20)
            assert abandoned.returncode != 0
            assert "桌面进程已退出" in abandoned.stderr
            assert json.loads(settings.read_text(encoding="utf-8"))["data_dir"] == str(data)
            print("PASS: exclusive data lock; auth/origin; objective+Chinese subjective; EOF; restart; crash recovery")
            print("PASS: relocation parent EOF cancels before switching configuration")
            if args.seed_db:
                print(f"PASS: read-only legacy snapshot retained all {baseline} attempts; original database unchanged")
        finally:
            for process in processes:
                if process.poll() is None:
                    process.kill()
                    process.wait(timeout=5)
                    diagnostic = process.stderr.read()
                    if diagnostic:
                        print("Backend stderr on forced cleanup:", diagnostic[-8192:], file=sys.stderr)
                for pipe in (process.stdin, process.stdout, process.stderr):
                    if pipe and not pipe.closed:
                        pipe.close()


if __name__ == "__main__":
    main()
