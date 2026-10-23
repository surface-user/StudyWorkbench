"""Check a real source or frozen backend process; no credentials are logged."""
import argparse
import json
import os
import secrets
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--exe", type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parent.parent
    token = secrets.token_urlsafe(32)
    with tempfile.TemporaryDirectory(prefix="study-m0-") as data:
        command = [str(args.exe.resolve())] if args.exe else [sys.executable, "-m", "study_workbench"]
        process = subprocess.Popen(command + ["--data-dir", data], cwd=root / "backend",
                                   stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   text=True, env={**os.environ, "PYTHONIOENCODING": "utf-8"})
        try:
            process.stdin.write(json.dumps({"token": token}) + "\n")
            process.stdin.flush()
            line = process.stdout.readline()
            if not line:
                raise RuntimeError(process.stderr.read(4096))
            hello = json.loads(line)
            assert hello["api_version"] == 0
            url = f"http://127.0.0.1:{hello['port']}/api/health"
            request = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
            # Bypass any machine proxy for loopback.
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            for _ in range(50):
                try:
                    with opener.open(request, timeout=2) as response:
                        assert json.load(response)["status"] == "ok"
                    break
                except urllib.error.URLError:
                    time.sleep(0.1)
            else:
                raise RuntimeError("Backend did not become ready")
            process.stdin.close()
            process.wait(timeout=10)
            assert process.returncode == 0
            print("PASS: real process handshake, authenticated SQLite health, parent EOF shutdown")
        finally:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=5)


if __name__ == "__main__":
    main()
