"""Password hashing (argon2id) + opaque session-token minting (spec 2026-07-10 §D2/§5.2)."""

import secrets

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError

_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, InvalidHashError):
        return False


def new_session_token() -> str:
    """URL-safe opaque token; ~43 chars for 32 bytes of entropy."""
    return secrets.token_urlsafe(32)
