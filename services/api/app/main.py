"""FastAPI entry. Routers stay thin; logic in app/services, persistence in gulp_shared."""

import logging
import time
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from gulp_shared.llm.base import LLMAuthError, LLMNotConfiguredError, LLMRateLimitError
from gulp_shared.logging import configure_logging, reset_request_id, set_request_id
from gulp_shared.settings import settings
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.mcp.auth import PATAuthMiddleware
from app.mcp.server import mcp as mcp_server
from app.routers import (
    auth,
    capture,
    cards,
    export,
    feeds,
    figures,
    gulp,
    inbox,
    library,
    llm,
    pack,
    processing,
    today,
    tokens,
)

configure_logging("api")
logger = logging.getLogger("gulp.api")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # the MCP session manager must be running for /mcp to serve requests
    manager = mcp_server.session_manager
    try:
        async with manager.run():
            yield
    finally:
        # The SDK guards run() as one-shot per instance (_has_started, never
        # reset on exit), but the test suite re-enters this lifespan once per
        # `with TestClient(app)`, each on a fresh event loop. Stateless mode
        # keeps no cross-request state, so clearing the guard lets the next
        # startup re-run the same instance with a fresh task group. In
        # production the app starts once, so this is a harmless no-op.
        manager._has_started = False


app = FastAPI(title="Gulp API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(LLMNotConfiguredError)
async def _llm_not_configured(request: Request, exc: LLMNotConfiguredError) -> JSONResponse:
    return JSONResponse(status_code=409, content={"detail": "llm_not_configured"})


@app.exception_handler(LLMAuthError)
async def _llm_auth(request: Request, exc: LLMAuthError) -> JSONResponse:
    return JSONResponse(status_code=409, content={"detail": "llm_key_invalid"})


@app.exception_handler(LLMRateLimitError)
async def _llm_rate_limited(request: Request, exc: LLMRateLimitError) -> JSONResponse:
    return JSONResponse(status_code=429, content={"detail": "llm_rate_limited"})

app.include_router(auth.router, tags=["auth"])
app.include_router(capture.router, tags=["capture"])
app.include_router(cards.router, tags=["cards"])
app.include_router(export.router, tags=["export"])
app.include_router(feeds.router, tags=["feeds"])
app.include_router(figures.router, tags=["figures"])
app.include_router(gulp.router, tags=["gulp"])
app.include_router(inbox.router, tags=["inbox"])
app.include_router(library.router, tags=["library"])
app.include_router(llm.router, tags=["llm"])
app.include_router(pack.router, tags=["pack"])
app.include_router(processing.router, tags=["processing"])
app.include_router(today.router, tags=["today"])
app.include_router(tokens.router, tags=["tokens"])


class RequestLogMiddleware:
    """Request logging as *pure ASGI*, deliberately not `@app.middleware("http")`.

    That decorator installs Starlette's BaseHTTPMiddleware, which relays the
    response through memory streams — and cannot carry a long-lived streaming
    response. The MCP client opens `GET /mcp` for its server→client stream
    during the handshake; under BaseHTTPMiddleware that stream ended as
    `anyio.EndOfStream` → `RuntimeError: No response returned.`, so every real
    client connection logged a 500. Wrapping send/receive instead leaves the
    stream untouched."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        headers = {k.decode().lower(): v.decode() for k, v in scope["headers"]}
        request_id = headers.get("x-request-id") or uuid.uuid4().hex
        token = set_request_id(request_id)
        started = time.perf_counter()
        status = 0

        async def send_with_request_id(message: Message) -> None:
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
                message["headers"] = [
                    *message["headers"],
                    (b"x-request-id", request_id.encode()),
                ]
            await send(message)

        method, path = scope["method"], scope["path"]
        try:
            await self.app(scope, receive, send_with_request_id)
        except Exception:
            duration_ms = (time.perf_counter() - started) * 1000
            logger.exception(
                "request failed method=%s path=%s duration_ms=%.1f",
                method,
                path,
                duration_ms,
            )
            raise
        else:
            duration_ms = (time.perf_counter() - started) * 1000
            logger.info(
                "request completed method=%s path=%s status=%d duration_ms=%.1f",
                method,
                path,
                status,
                duration_ms,
            )
        finally:
            reset_request_id(token)


app.add_middleware(RequestLogMiddleware)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


# Attached as a Route scoped to exactly /mcp (FastMCP's default
# streamable_http_path), not a root Mount: a Mount("/") is a full match for
# every path and would shadow FastAPI's 405 semantics on real routes (a POST to
# a GET-only endpoint would 404 through the sub-app instead of 405). A Route
# matches only "/mcp" for any method, so unknown paths still 404 and method
# mismatches on other routes still 405. The PAT middleware guards it; the
# wrapped sub-app routes "/mcp" internally to the streamable-HTTP handler.
app.router.routes.append(
    Route("/mcp", PATAuthMiddleware(mcp_server.streamable_http_app()))
)
