"""Capture endpoints — thin (docs/05 D4): parse, call service, return."""

import uuid
from collections.abc import Callable

from fastapi import APIRouter, Depends, HTTPException
from gulp_shared.models.source import Source
from gulp_shared.models.user import User
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.deps import get_db, get_enqueue
from app.schemas.capture import CaptureRequest, CaptureResponse, SnapshotOut
from app.services.capture import create_snapshot
from app.services.snapshots import to_out

router = APIRouter()


@router.post("/capture", response_model=CaptureResponse)
def capture(
    req: CaptureRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    enqueue: Callable[..., None] = Depends(get_enqueue),
) -> CaptureResponse:
    source, duplicate = create_snapshot(db, user.id, req)
    if not duplicate and source.origin_url:
        enqueue("resolve_metadata", str(source.id))
    return CaptureResponse(snapshot=to_out(db, source), duplicate=duplicate)


@router.get("/snapshots/{snapshot_id}", response_model=SnapshotOut)
def get_snapshot(
    snapshot_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> SnapshotOut:
    source = db.get(Source, snapshot_id)
    if source is None or source.owner_id != user.id or source.deleted_at is not None:
        raise HTTPException(status_code=404, detail="snapshot not found")
    return to_out(db, source)
