import uuid

import fakeredis
import pytest
from app.core.sessions import RedisSessionStore
from app.core.throttle import LoginThrottle


@pytest.fixture
def r():  # type: ignore[no-untyped-def]
    return fakeredis.FakeStrictRedis(decode_responses=True)


def test_create_resolve_round_trip(r) -> None:  # type: ignore[no-untyped-def]
    store = RedisSessionStore(r, ttl_seconds=3600)
    uid = uuid.uuid4()
    token = store.create(uid)
    assert store.resolve(token) == uid


def test_resolve_unknown_token_is_none(r) -> None:  # type: ignore[no-untyped-def]
    store = RedisSessionStore(r, ttl_seconds=3600)
    assert store.resolve("nope") is None


def test_revoke_kills_the_session(r) -> None:  # type: ignore[no-untyped-def]
    store = RedisSessionStore(r, ttl_seconds=3600)
    uid = uuid.uuid4()
    token = store.create(uid)
    store.revoke(token)
    assert store.resolve(token) is None


def test_revoke_all_kills_every_session_for_user(r) -> None:  # type: ignore[no-untyped-def]
    store = RedisSessionStore(r, ttl_seconds=3600)
    uid = uuid.uuid4()
    t1, t2 = store.create(uid), store.create(uid)
    store.revoke_all(uid)
    assert store.resolve(t1) is None
    assert store.resolve(t2) is None


def test_throttle_locks_after_max(r) -> None:  # type: ignore[no-untyped-def]
    throttle = LoginThrottle(r, max_attempts=3, window_seconds=900)
    assert throttle.is_locked("k") is False
    for _ in range(3):
        throttle.record_failure("k")
    assert throttle.is_locked("k") is True
    throttle.reset("k")
    assert throttle.is_locked("k") is False
