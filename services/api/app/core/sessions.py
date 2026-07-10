"""Server-side session store (spec 2026-07-10 §5.2). Opaque tokens in Redis;
the cookie carries the token, never user data. Revocable per-token and per-user."""

import uuid
from typing import Protocol, cast

import redis
from fastapi import Depends
from gulp_shared.settings import settings

from app.core.security import new_session_token
from app.deps import get_redis


class SessionStore(Protocol):
    def create(self, user_id: uuid.UUID) -> str: ...
    def resolve(self, token: str) -> uuid.UUID | None: ...
    def revoke(self, token: str) -> None: ...
    def revoke_all(self, user_id: uuid.UUID) -> None: ...


class RedisSessionStore:
    def __init__(self, client: redis.Redis, ttl_seconds: int) -> None:
        self._r = client
        self._ttl = ttl_seconds

    def create(self, user_id: uuid.UUID) -> str:
        token = new_session_token()
        self._r.set(f"session:{token}", str(user_id), ex=self._ttl)
        self._r.sadd(f"user_sessions:{user_id}", token)
        return token

    def resolve(self, token: str) -> uuid.UUID | None:
        raw = cast(str | None, self._r.get(f"session:{token}"))
        if raw is None:
            return None
        self._r.expire(f"session:{token}", self._ttl)  # sliding TTL
        return uuid.UUID(raw)

    def revoke(self, token: str) -> None:
        raw = cast(str | None, self._r.get(f"session:{token}"))
        self._r.delete(f"session:{token}")
        if raw is not None:
            self._r.srem(f"user_sessions:{raw}", token)

    def revoke_all(self, user_id: uuid.UUID) -> None:
        key = f"user_sessions:{user_id}"
        for token in cast(set[str], self._r.smembers(key)):
            self._r.delete(f"session:{token}")
        self._r.delete(key)


def get_sessions(r: redis.Redis = Depends(get_redis)) -> SessionStore:
    return RedisSessionStore(r, settings.session_ttl_days * 86400)
