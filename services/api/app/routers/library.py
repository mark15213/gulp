"""Library endpoint — thin (docs/05 D4)."""

from fastapi import APIRouter, Depends
from gulp_shared.models.user import User
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.deps import get_db
from app.schemas.capture import LibraryOut
from app.services.library import list_library
from app.services.snapshots import to_out

router = APIRouter()


@router.get("/library", response_model=LibraryOut)
def get_library(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> LibraryOut:
    items = [to_out(db, s) for s in list_library(db, user.id)]
    return LibraryOut(items=items, count=len(items))
