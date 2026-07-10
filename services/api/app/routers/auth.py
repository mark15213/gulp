"""Auth endpoints — thin (docs/05 D4): parse, call service, set/clear cookie."""

from fastapi import APIRouter, Depends, Request, Response
from gulp_shared.models.user import User
from gulp_shared.settings import settings
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.sessions import SessionStore, get_sessions
from app.core.throttle import LoginThrottle, get_throttle
from app.deps import get_db
from app.schemas.auth import LoginRequest, RegisterRequest, UserPublic
from app.services import auth as auth_service

router = APIRouter(prefix="/auth")


def _set_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=settings.session_cookie_name,
        value=token,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="lax",
        max_age=settings.session_ttl_days * 86400,
        path="/",
    )


@router.post("/register", response_model=UserPublic, status_code=201)
def register(
    req: RegisterRequest,
    response: Response,
    db: Session = Depends(get_db),
    sessions: SessionStore = Depends(get_sessions),
) -> User:
    user = auth_service.register(db, req)
    _set_cookie(response, sessions.create(user.id))
    return user


@router.post("/login", response_model=UserPublic)
def login(
    req: LoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    sessions: SessionStore = Depends(get_sessions),
    throttle: LoginThrottle = Depends(get_throttle),
) -> User:
    ip = request.client.host if request.client else "unknown"
    user = auth_service.authenticate(db, req, throttle=throttle, ip=ip)
    _set_cookie(response, sessions.create(user.id))
    return user


@router.post("/logout", status_code=204)
def logout(
    request: Request,
    response: Response,
    sessions: SessionStore = Depends(get_sessions),
) -> None:
    token = request.cookies.get(settings.session_cookie_name)
    if token:
        sessions.revoke(token)
    response.delete_cookie(settings.session_cookie_name, path="/")


@router.get("/me", response_model=UserPublic)
def me(user: User = Depends(get_current_user)) -> User:
    return user
