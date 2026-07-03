"""Figure gallery endpoints — thin (docs/05 D4). Ownership mirrors routers/pack.py."""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from gulp_shared.models.source import Source
from gulp_shared.models.user import User
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.deps import get_db
from app.schemas.figures import FigureAssetOut
from app.services.figures import figure_file, list_figures

router = APIRouter()


def _owned_snapshot(db: Session, snapshot_id: uuid.UUID, user: User) -> Source:
    source = db.get(Source, snapshot_id)
    if source is None or source.owner_id != user.id or source.deleted_at is not None:
        raise HTTPException(status_code=404, detail="snapshot not found")
    return source


@router.get("/snapshots/{snapshot_id}/figures", response_model=list[FigureAssetOut])
def list_figures_route(
    snapshot_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[FigureAssetOut]:
    _owned_snapshot(db, snapshot_id, user)
    return [
        FigureAssetOut.model_validate(f, from_attributes=True)
        for f in list_figures(db, snapshot_id)
    ]


@router.get("/snapshots/{snapshot_id}/figures/{figure_id}")
def get_figure_route(
    snapshot_id: uuid.UUID,
    figure_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> FileResponse:
    _owned_snapshot(db, snapshot_id, user)
    found = figure_file(db, snapshot_id, figure_id)
    if found is None:
        raise HTTPException(status_code=404, detail="figure not found")
    path, mime = found
    return FileResponse(path, media_type=mime)
