"""Pack read endpoint — thin (docs/05 D4)."""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.deps import get_db
from app.schemas.pack import PackOut
from app.services.pack import pack_out
from gulp_shared.models.source import Source
from gulp_shared.models.user import User

router = APIRouter()


@router.get("/snapshots/{snapshot_id}/pack", response_model=PackOut)
def get_pack(
    snapshot_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> PackOut:
    source = db.get(Source, snapshot_id)
    if source is None or source.owner_id != user.id or source.deleted_at is not None:
        raise HTTPException(status_code=404, detail="snapshot not found")
    pack = pack_out(db, snapshot_id)
    if pack is None:
        raise HTTPException(status_code=404, detail="no pack for this snapshot")
    return pack
