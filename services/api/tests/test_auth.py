import fakeredis
import pytest
from app.core.auth import get_current_user
from app.core.sessions import RedisSessionStore
from fastapi import HTTPException
from gulp_shared.models.user import DEV_USER_ID
from gulp_shared.settings import settings
from starlette.requests import Request


def _request_with_cookie(token: str | None) -> Request:
    headers = []
    if token is not None:
        headers.append((b"cookie", f"{settings.session_cookie_name}={token}".encode()))
    return Request({"type": "http", "headers": headers})


def _store() -> RedisSessionStore:
    return RedisSessionStore(fakeredis.FakeStrictRedis(decode_responses=True), ttl_seconds=3600)


def test_get_current_user_resolves_session(db) -> None:  # type: ignore[no-untyped-def]
    store = _store()
    token = store.create(DEV_USER_ID)
    user = get_current_user(request=_request_with_cookie(token), db=db, sessions=store)
    assert user.id == DEV_USER_ID


def test_get_current_user_without_cookie_401(db) -> None:  # type: ignore[no-untyped-def]
    with pytest.raises(HTTPException) as exc:
        get_current_user(request=_request_with_cookie(None), db=db, sessions=_store())
    assert exc.value.status_code == 401


def test_get_current_user_invalid_token_401(db) -> None:  # type: ignore[no-untyped-def]
    with pytest.raises(HTTPException) as exc:
        get_current_user(request=_request_with_cookie("bogus"), db=db, sessions=_store())
    assert exc.value.status_code == 401
