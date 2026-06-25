"""Processing trigger endpoint — thin (docs/05 D4)."""

import uuid
from collections.abc import Callable

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.deps import get_db, get_enqueue
from app.schemas.capture import SnapshotOut
from app.services.processing import start_processing
from app.services.snapshots import to_out
from gulp_shared.models.source import Source
from gulp_shared.models.user import User

router = APIRouter()


@router.post("/snapshots/{snapshot_id}/process", response_model=SnapshotOut)
def process_snapshot_endpoint(
    snapshot_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    enqueue: Callable[..., None] = Depends(get_enqueue),
) -> SnapshotOut:
    source = db.get(Source, snapshot_id)
    if source is None or source.owner_id != user.id or source.deleted_at is not None:
        raise HTTPException(status_code=404, detail="snapshot not found")
    try:
        start_processing(db, source, enqueue)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return to_out(db, source)
