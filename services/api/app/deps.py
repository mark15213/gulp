"""Shared FastAPI dependencies (db session, enqueue, redis)."""

from collections.abc import Callable, Iterator

import redis
from gulp_shared.db import SessionLocal
from gulp_shared.settings import settings
from sqlalchemy.orm import Session

from app.core.queue import enqueue as _enqueue

_redis: redis.Redis | None = None


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_enqueue() -> Callable[..., None]:
    return _enqueue


def get_redis() -> redis.Redis:
    global _redis
    if _redis is None:
        _redis = redis.Redis.from_url(settings.redis_url, decode_responses=True)
    return _redis
