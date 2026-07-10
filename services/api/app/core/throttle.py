"""Fixed-window login throttle (spec 2026-07-10 §5.5). Keyed by email+IP."""

from typing import cast

import redis
from fastapi import Depends
from gulp_shared.settings import settings

from app.deps import get_redis


class LoginThrottle:
    def __init__(self, client: redis.Redis, max_attempts: int, window_seconds: int) -> None:
        self._r = client
        self._max = max_attempts
        self._window = window_seconds

    def is_locked(self, key: str) -> bool:
        raw = cast(str | None, self._r.get(f"login_fail:{key}"))
        return raw is not None and int(raw) >= self._max

    def record_failure(self, key: str) -> None:
        k = f"login_fail:{key}"
        count = cast(int, self._r.incr(k))
        if count == 1:
            self._r.expire(k, self._window)

    def reset(self, key: str) -> None:
        self._r.delete(f"login_fail:{key}")


def get_throttle(r: redis.Redis = Depends(get_redis)) -> LoginThrottle:
    return LoginThrottle(r, settings.login_max_attempts, settings.login_lockout_seconds)
