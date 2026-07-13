"""FastAPI entry. Routers stay thin; logic in app/services, persistence in gulp_shared."""

import logging
import time
import uuid
from collections.abc import Awaitable, Callable

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from gulp_shared.llm.base import LLMAuthError, LLMNotConfiguredError, LLMRateLimitError
from gulp_shared.logging import configure_logging, reset_request_id, set_request_id
from gulp_shared.settings import settings
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

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
