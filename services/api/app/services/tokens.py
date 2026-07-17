"""Token management business logic (routers stay thin)."""

import uuid
from datetime import UTC, datetime

from gulp_shared.models.api_token import ApiToken
from gulp_shared.models.user import User
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.pat import PREFIX_LEN, hash_token, mint_token


def create_token(db: Session, user: User, name: str) -> tuple[ApiToken, str]:
    plaintext = mint_token()
    row = ApiToken(
        user_id=user.id,
        name=name,
        token_hash=hash_token(plaintext),
        prefix=plaintext[:PREFIX_LEN],
    )
    db.add(row)
    db.commit()
    return row, plaintext


def list_tokens(db: Session, user: User) -> list[ApiToken]:
    return list(
        db.scalars(
            select(ApiToken)
            .where(ApiToken.user_id == user.id, ApiToken.revoked_at.is_(None))
            .order_by(ApiToken.created_at)
        )
    )


def revoke_token(db: Session, user: User, token_id: uuid.UUID) -> bool:
    row = db.get(ApiToken, token_id)
    if row is None or row.user_id != user.id or row.revoked_at is not None:
        return False
    row.revoked_at = datetime.now(UTC)
    db.commit()
    return True
