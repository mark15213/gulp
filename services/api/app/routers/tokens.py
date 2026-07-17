"""PAT endpoints — thin (docs/05 D4). Cookie-session authed: tokens are
managed from the browser, then used by MCP clients."""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from gulp_shared.models.user import User
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.deps import get_db
from app.schemas.tokens import TokenCreatedOut, TokenIn, TokenOut
from app.services.tokens import create_token, list_tokens, revoke_token

router = APIRouter(prefix="/me/tokens")


@router.post("", response_model=TokenCreatedOut, status_code=201)
def create_token_route(
    body: TokenIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> TokenCreatedOut:
    row, plaintext = create_token(db, user, body.name)
    return TokenCreatedOut(
        id=row.id,
        name=row.name,
        prefix=row.prefix,
        created_at=row.created_at,
        last_used_at=row.last_used_at,
        token=plaintext,
    )


@router.get("", response_model=list[TokenOut])
def list_tokens_route(
    db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> list[TokenOut]:
    return [TokenOut.model_validate(t) for t in list_tokens(db, user)]


@router.delete("/{token_id}", status_code=204)
def revoke_token_route(
    token_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    if not revoke_token(db, user, token_id):
        raise HTTPException(status_code=404, detail="token not found")
