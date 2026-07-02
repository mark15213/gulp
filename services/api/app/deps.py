"""Shared FastAPI dependencies (db session, enqueue)."""

from collections.abc import Callable, Iterator

from gulp_shared.db import SessionLocal
from sqlalchemy.orm import Session

from app.core.queue import enqueue as _enqueue


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_enqueue() -> Callable[..., None]:
    return _enqueue
