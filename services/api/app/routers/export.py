"""Export executor endpoints — thin (docs/05 D4)."""

import os
import uuid
from collections.abc import Callable

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from gulp_shared.models.source import Source
from gulp_shared.models.user import User
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.deps import get_db, get_enqueue
from app.schemas.capture import SnapshotOut
from app.services.export import job_path, shallow_check, stash_result
from app.services.snapshots import to_out

router = APIRouter()


def _owned(db: Session, snapshot_id: uuid.UUID, user: User) -> Source:
    source = db.get(Source, snapshot_id)
    if source is None or source.owner_id != user.id or source.deleted_at is not None:
        raise HTTPException(status_code=404, detail="snapshot not found")
    return source


@router.post("/snapshots/{snapshot_id}/export", response_model=SnapshotOut)
def export_snapshot(
    snapshot_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    enqueue: Callable[..., None] = Depends(get_enqueue),
) -> SnapshotOut:
    source = _owned(db, snapshot_id, user)
    enqueue("build_export", str(source.id))
    return to_out(db, source)


@router.get("/snapshots/{snapshot_id}/job")
def download_job(
    snapshot_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> FileResponse:
    _owned(db, snapshot_id, user)
    path = job_path(str(snapshot_id))
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="job not built yet")
    return FileResponse(
        path, media_type="application/zip", filename=f"gulp-job-{str(snapshot_id)[:8]}.zip"
    )


@router.post("/snapshots/{snapshot_id}/import", response_model=SnapshotOut)
def import_snapshot(
    snapshot_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    enqueue: Callable[..., None] = Depends(get_enqueue),
    file: UploadFile = File(...),
) -> SnapshotOut:
    # MUST be a sync endpoint: `enqueue` uses asyncio.run() internally, which
    # raises inside a running event loop (S1 note). Read via the sync file obj.
    source = _owned(db, snapshot_id, user)
    data = file.file.read()
    try:
        shallow_check(data, snapshot_id=str(source.id), owner_id=str(source.owner_id))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    path = stash_result(data, str(source.id))
    enqueue("import_result", str(source.id), path)
    return to_out(db, source)
