"""Bound actual ASGI body bytes, including requests without Content-Length."""
from starlette.responses import JSONResponse

IMPORT_LIMIT = 8 * 1024 * 1024


class RequestLimits:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        path = scope["path"]
        if path.startswith('/api/workspaces/') and path.endswith('/media/import'):
            # The authorized streaming handler enforces MEDIA_LIMIT on actual chunks, without buffering video in RAM.
            return await self.app(scope, receive, send)
        limit = (32 * 1024 * 1024 if path.startswith('/api/workspaces/') and path.endswith('/layout')
                 else 8 * 1024 * 1024 if path.startswith('/api/workspaces/') and path.endswith('/document')
                 else IMPORT_LIMIT if path.startswith("/api/workspaces/") and path.endswith("/imports")
                 else 2 * 1024 * 1024 if path.startswith("/api/workspaces/") and
                 "/notes/" in path
                 else 65536)
        chunks = []
        size = 0
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            chunk = message.get("body", b"")
            size += len(chunk)
            if size > limit:
                return await JSONResponse({"detail": "Request too large"}, status_code=413)(scope, receive, send)
            chunks.append(chunk)
            if not message.get("more_body", False):
                break
        sent = False

        async def replay():
            nonlocal sent
            if not sent:
                sent = True
                return {"type": "http.request", "body": b"".join(chunks), "more_body": False}
            return await receive()

        await self.app(scope, replay, send)
