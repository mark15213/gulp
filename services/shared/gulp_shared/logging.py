"""Shared logging configuration for API and worker processes."""

from __future__ import annotations

import logging
from contextvars import ContextVar, Token
from logging.config import dictConfig
from typing import Any

from gulp_shared.settings import settings

_request_id: ContextVar[str] = ContextVar("gulp_request_id", default="-")

_LEVELS = {"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG", "NOTSET"}


class _ContextFilter(logging.Filter):
    def __init__(self, service: str) -> None:
        super().__init__()
        self.service = service

    def filter(self, record: logging.LogRecord) -> bool:
        record.service = self.service
        record.request_id = _request_id.get()
        return True


def set_request_id(request_id: str) -> Token[str]:
    return _request_id.set(request_id)


def reset_request_id(token: Token[str]) -> None:
    _request_id.reset(token)


def _normalized_level(level: str) -> str:
    value = level.upper()
    if value not in _LEVELS:
        return "INFO"
    return value


def configure_logging(service: str, *, level: str | None = None) -> None:
    """Configure process-wide console logging with service/request context."""

    log_level = _normalized_level(level or settings.log_level)
    config: dict[str, Any] = {
        "version": 1,
        "disable_existing_loggers": False,
        "filters": {
            "gulp_context": {
                "()": _ContextFilter,
                "service": service,
            },
        },
        "formatters": {
            "standard": {
                "format": (
                    "%(asctime)s %(levelname)s [%(service)s] "
                    "[request_id=%(request_id)s] %(name)s: %(message)s"
                ),
                "datefmt": "%Y-%m-%dT%H:%M:%S%z",
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "standard",
                "filters": ["gulp_context"],
            },
        },
        "root": {
            "level": log_level,
            "handlers": ["console"],
        },
        "loggers": {
            "arq": {
                "level": log_level,
                "handlers": ["console"],
                "propagate": False,
            },
            "uvicorn": {
                "level": log_level,
                "handlers": ["console"],
                "propagate": False,
            },
            "uvicorn.access": {
                "level": log_level,
                "handlers": ["console"],
                "propagate": False,
            },
            "uvicorn.error": {
                "level": log_level,
                "handlers": ["console"],
                "propagate": False,
            },
        },
    }
    dictConfig(config)
    logging.captureWarnings(True)
    logging.getLogger("gulp").debug("logging configured at %s", log_level)
