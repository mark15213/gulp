"""Shared FastAPI dependencies (db session, current user, …)."""

from collections.abc import Iterator

from gulp_shared.db import SessionLocal


def get_db() -> Iterator[object]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
