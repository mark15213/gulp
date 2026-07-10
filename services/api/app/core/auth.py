"""Session-cookie auth (spec 2026-07-10). Resolves the session cookie to a user;
raises 401 when the cookie is absent, unknown, or expired. Every router depends
on this, so the whole API is multi-user through this one function."""

from fastapi import Depends, HTTPException, Request
from gulp_shared.models.user import User
from gulp_shared.settings import settings
from sqlalchemy.orm import Session

from app.core.sessions import SessionStore, get_sessions
from app.deps import get_db

_UNAUTH = HTTPException(status_code=401, detail="not authenticated")


def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
    sessions: SessionStore = Depends(get_sessions),
) -> User:
    token = request.cookies.get(settings.session_cookie_name)
    if not token:
        raise _UNAUTH
    user_id = sessions.resolve(token)
    if user_id is None:
        raise _UNAUTH
    user = db.get(User, user_id)
    if user is None:
        raise _UNAUTH
    return user
