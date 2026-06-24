"""Shared FastAPI dependencies (db session, enqueue)."""

from collections.abc import Callable, Iterator

from sqlalchemy.orm import Session

from app.core.queue import enqueue as _enqueue
from gulp_shared.db import SessionLocal


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_enqueue() -> Callable[..., None]:
    return _enqueue
