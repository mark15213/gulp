"""Inbox endpoint — the derived view (spec C4; 2026-08-01 stage sections)."""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from gulp_shared.models.user import User
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.deps import get_db
from app.schemas.capture import InboxOut
from app.services.inbox import actionable_count, list_inbox
from app.services.snapshots import to_out

router = APIRouter()


@router.get("/inbox", response_model=InboxOut)
def inbox(
    emitted_by: uuid.UUID | None = None,
    ad_hoc_only: bool = False,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> InboxOut:
    if emitted_by is not None and ad_hoc_only:
        raise HTTPException(
            status_code=422,
            detail="emitted_by and ad_hoc_only are mutually exclusive",
        )
    sources = list_inbox(db, user.id, emitted_by=emitted_by, ad_hoc_only=ad_hoc_only)
    items = [to_out(db, s) for s in sources]
    return InboxOut(
        items=items,
        count=len(items),
        actionable_count=actionable_count(db, user.id),
    )
