"""Patchable seams for the MCP layer. MCP tools run outside FastAPI's DI, so
tests swap these module attributes instead of dependency_overrides."""

from collections.abc import Callable

from gulp_shared.db import SessionLocal
from sqlalchemy.orm import Session

from app.core.queue import enqueue as _enqueue

session_factory: Callable[[], Session] = SessionLocal
enqueue: Callable[..., None] = _enqueue
