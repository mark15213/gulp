"""FastAPI entry. Routers stay thin; logic in app/services, persistence in gulp_shared."""

import logging
import time
import uuid
from collections.abc import Awaitable, Callable

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from gulp_shared.logging import configure_logging, reset_request_id, set_request_id
from gulp_shared.settings import settings
from starlette.requests import Request
from starlette.responses import Response

from app.routers import (
    capture,
    cards,
    export,
    feeds,
    figures,
    gulp,
    inbox,
    library,
    pack,
    processing,
    today,
)

configure_logging("api")
logger = logging.getLogger("gulp.api")

app = FastAPI(title="Gulp API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(capture.router, tags=["capture"])
app.include_router(cards.router, tags=["cards"])
app.include_router(export.router, tags=["export"])
app.include_router(feeds.router, tags=["feeds"])
app.include_router(figures.router, tags=["figures"])
app.include_router(gulp.router, tags=["gulp"])
app.include_router(inbox.router, tags=["inbox"])
app.include_router(library.router, tags=["library"])
app.include_router(pack.router, tags=["pack"])
app.include_router(processing.router, tags=["processing"])
app.include_router(today.router, tags=["today"])


@app.middleware("http")
async def log_requests(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    request_id = request.headers.get("x-request-id") or uuid.uuid4().hex
    token = set_request_id(request_id)
    started = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        duration_ms = (time.perf_counter() - started) * 1000
        logger.exception(
            "request failed method=%s path=%s duration_ms=%.1f",
            request.method,
            request.url.path,
            duration_ms,
        )
        raise
    else:
        duration_ms = (time.perf_counter() - started) * 1000
        response.headers["X-Request-ID"] = request_id
        logger.info(
            "request completed method=%s path=%s status=%d duration_ms=%.1f",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
        )
        return response
    finally:
        reset_request_id(token)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
