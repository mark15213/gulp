"""PAT guard for the /mcp mount (spec 2026-07-16 §3/§5): Bearer PAT → user id
stashed on the request scope; anything else is 401. Non-/mcp paths pass
through untouched (the sub-app 404s them)."""

import json
from typing import Any

from app.core.pat import resolve_pat
from app.mcp import deps

MAX_BODY_BYTES = 5 * 1024 * 1024

Scope = dict[str, Any]


async def _reject(send: Any, status: int, detail: str) -> None:
    body = json.dumps({"detail": detail}).encode()
    await send(
        {
            "type": "http.response.start",
            "status": status,
            "headers": [(b"content-type", b"application/json")],
        }
    )
    await send({"type": "http.response.body", "body": body})


class PATAuthMiddleware:
    def __init__(self, app: Any) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Any, send: Any) -> None:
        if scope["type"] != "http" or not scope["path"].startswith("/mcp"):
            await self.app(scope, receive, send)
            return
        headers = {k.decode().lower(): v.decode() for k, v in scope["headers"]}
        length = headers.get("content-length")
        if length and length.isdigit() and int(length) > MAX_BODY_BYTES:
            await _reject(send, 413, "request body too large")
            return
        auth = headers.get("authorization", "")
        user = None
        if auth.startswith("Bearer "):
            db = deps.session_factory()
            try:
                user = resolve_pat(db, auth.removeprefix("Bearer "))
            finally:
                db.close()
        if user is None:
            await _reject(send, 401, "not authenticated")
            return
        scope.setdefault("state", {})["gulp_user_id"] = user.id

        # Content-Length lies or is absent under chunked transfer, so buffer the
        # body here (up to the cap) BEFORE handing off — the downstream MCP app
        # swallows exceptions raised from `receive` and would turn an over-cap
        # abort into a 500, so we must reject before it ever runs, then replay the
        # buffered body to it.
        chunks: list[bytes] = []
        received = 0
        more_body = True
        while more_body:
            message = await receive()
            if message["type"] == "http.disconnect":
                return  # client hung up mid-body
            if message["type"] != "http.request":
                break
            chunks.append(message.get("body", b""))
            received += len(chunks[-1])
            if received > MAX_BODY_BYTES:
                await _reject(send, 413, "request body too large")
                return
            more_body = message.get("more_body", False)

        body = b"".join(chunks)
        replayed = False

        async def replay_receive() -> Any:
            nonlocal replayed
            if not replayed:
                replayed = True
                return {"type": "http.request", "body": body, "more_body": False}
            return {"type": "http.disconnect"}

        await self.app(scope, replay_receive, send)
