import argparse
import asyncio
import json
import socket
import sys
import threading
from pathlib import Path

import uvicorn

from .app import create_app


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--media", type=Path)
    args = parser.parse_args()
    token = json.loads(sys.stdin.readline())["token"]
    app = create_app(args.data_dir.resolve(), token, args.media.resolve() if args.media else None)
    server = uvicorn.Server(uvicorn.Config(app, log_level="warning", access_log=False))
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    print(json.dumps({"port": sock.getsockname()[1], "api_version": 0}), flush=True)

    def parent_lifetime():
        # EOF also handles an abruptly terminated desktop parent.
        sys.stdin.read()
        server.should_exit = True

    threading.Thread(target=parent_lifetime, daemon=True).start()
    try:
        asyncio.run(server.serve(sockets=[sock]))
    finally:
        sock.close()


if __name__ == "__main__":
    main()
