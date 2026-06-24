"""Inbox endpoint — the derived view (spec C4)."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.deps import get_db
from app.schemas.capture import InboxOut
from app.services.inbox import list_inbox
from app.services.snapshots import to_out
from gulp_shared.models.user import User

router = APIRouter()


@router.get("/inbox", response_model=InboxOut)
def inbox(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> InboxOut:
    sources = list_inbox(db, user.id)
    items = [to_out(db, s) for s in sources]
    return InboxOut(items=items, count=len(items))
