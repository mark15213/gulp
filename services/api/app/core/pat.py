"""PAT mint/verify — the auth surface for non-browser clients (spec 2026-07-16 §2).
v1: PATs are accepted only by the /mcp mount, never by the REST routers."""

import hashlib
import secrets
from datetime import UTC, datetime

from gulp_shared.models.api_token import ApiToken
from gulp_shared.models.user import User
from sqlalchemy import select
from sqlalchemy.orm import Session

TOKEN_PREFIX = "gulp_pat_"
# prefix column stores TOKEN_PREFIX + 8 chars of the random part, for display
PREFIX_LEN = len(TOKEN_PREFIX) + 8


def mint_token() -> str:
    return TOKEN_PREFIX + secrets.token_urlsafe(32)


def hash_token(plaintext: str) -> str:
    return hashlib.sha256(plaintext.encode()).hexdigest()


def resolve_pat(db: Session, plaintext: str) -> User | None:
    """Bearer value → owning user; None for malformed/unknown/revoked.
    Touches last_used_at so Settings can show token liveness."""
    if not plaintext.startswith(TOKEN_PREFIX):
        return None
    row = db.scalar(
        select(ApiToken).where(
            ApiToken.token_hash == hash_token(plaintext),
            ApiToken.revoked_at.is_(None),
        )
    )
    if row is None:
        return None
    row.last_used_at = datetime.now(UTC)
    db.commit()
    return db.get(User, row.user_id)
