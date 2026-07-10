"""Auth business logic (spec 2026-07-10). Routers stay thin (docs/05 D4)."""

from fastapi import HTTPException
from gulp_shared.models.user import User
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password, verify_password
from app.core.throttle import LoginThrottle
from app.schemas.auth import LoginRequest, RegisterRequest


def register(db: Session, req: RegisterRequest) -> User:
    email = req.email.lower()
    exists = db.scalar(select(User).where(User.email == email))
    if exists is not None:
        raise HTTPException(status_code=409, detail="email already registered")
    user = User(
        email=email,
        password_hash=hash_password(req.password),
        display_name=req.display_name,
        locale=req.locale,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def authenticate(db: Session, req: LoginRequest, *, throttle: LoginThrottle, ip: str) -> User:
    email = req.email.lower()
    key = f"{email}:{ip}"
    if throttle.is_locked(key):
        raise HTTPException(status_code=429, detail="too many attempts, try again later")
    user = db.scalar(select(User).where(User.email == email))
    if user is None or not verify_password(req.password, user.password_hash):
        throttle.record_failure(key)
        raise HTTPException(status_code=401, detail="invalid email or password")
    throttle.reset(key)
    return user
