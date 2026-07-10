"""Cards endpoints — thin (docs/05 D4)."""

import os
import uuid
from collections.abc import Callable

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from gulp_shared.contracts.cards import CardsPayload
from gulp_shared.models.source import Source
from gulp_shared.models.user import User
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.deps import get_db, get_enqueue
from app.schemas.capture import SnapshotOut
from app.schemas.cards import CardOut, CardPatch
from app.services.cards import (
    GenerationInFlightError,
    NoReadyPackError,
    delete_card,
    get_card,
    import_cards,
    list_cards,
    start_card_generation,
    start_cards_export,
    to_card_out,
    update_card,
)
from app.services.export import cards_job_path
from app.services.snapshots import to_out

router = APIRouter()


def _owned_snapshot(db: Session, snapshot_id: uuid.UUID, user: User) -> Source:
    source = db.get(Source, snapshot_id)
    if source is None or source.owner_id != user.id or source.deleted_at is not None:
        raise HTTPException(status_code=404, detail="snapshot not found")
    return source


def _validation_detail(exc: ValidationError) -> list[dict[str, object]]:
    return [{"loc": list(e["loc"]), "msg": e["msg"]} for e in exc.errors()]


@router.post(
    "/snapshots/{snapshot_id}/cards/generate", response_model=SnapshotOut, status_code=202
)
def generate_cards_route(
    snapshot_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    enqueue: Callable[..., None] = Depends(get_enqueue),
) -> SnapshotOut:
    source = _owned_snapshot(db, snapshot_id, user)
    try:
        start_card_generation(db, source, enqueue)
    except NoReadyPackError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except GenerationInFlightError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return to_out(db, source)


@router.post(
    "/snapshots/{snapshot_id}/cards/export", response_model=SnapshotOut, status_code=202
)
def export_cards_job_route(
    snapshot_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    enqueue: Callable[..., None] = Depends(get_enqueue),
) -> SnapshotOut:
    source = _owned_snapshot(db, snapshot_id, user)
    try:
        start_cards_export(db, source, enqueue)
    except NoReadyPackError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return to_out(db, source)


# GET streams the built zip; HEAD is the client's readiness probe (cardsJobReady),
# so the route must answer HEAD (200 vs 404) rather than 405 Method Not Allowed.
@router.get(
    "/snapshots/{snapshot_id}/cards/job",
    operation_id="download_cards_job_route",
)
@router.head(
    "/snapshots/{snapshot_id}/cards/job",
    operation_id="head_cards_job_route",
)
def download_cards_job_route(
    snapshot_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> FileResponse:
    _owned_snapshot(db, snapshot_id, user)
    path = cards_job_path(str(snapshot_id))
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="cards job not built yet")
    return FileResponse(
        path,
        media_type="application/zip",
        filename=f"gulp-cards-{str(snapshot_id)[:8]}.zip",
    )


@router.post(
    "/snapshots/{snapshot_id}/cards/import",
    response_model=list[CardOut],
    status_code=201,
)
def import_cards_route(
    snapshot_id: uuid.UUID,
    payload: CardsPayload,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[CardOut]:
    source = _owned_snapshot(db, snapshot_id, user)
    return [to_card_out(c) for c in import_cards(db, source, payload)]


@router.get("/snapshots/{snapshot_id}/cards", response_model=list[CardOut])
def list_cards_route(
    snapshot_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[CardOut]:
    source = _owned_snapshot(db, snapshot_id, user)
    return [to_card_out(c) for c in list_cards(db, source)]


@router.patch("/snapshots/{snapshot_id}/cards/{card_id}", response_model=CardOut)
def update_card_route(
    snapshot_id: uuid.UUID,
    card_id: uuid.UUID,
    patch: CardPatch,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> CardOut:
    source = _owned_snapshot(db, snapshot_id, user)
    try:
        card = get_card(db, source, card_id)
    except LookupError:
        raise HTTPException(status_code=404, detail="card not found") from None
    try:
        return to_card_out(update_card(db, card, patch))
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=_validation_detail(exc)) from exc


@router.delete("/snapshots/{snapshot_id}/cards/{card_id}", status_code=204)
def delete_card_route(
    snapshot_id: uuid.UUID,
    card_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    source = _owned_snapshot(db, snapshot_id, user)
    try:
        card = get_card(db, source, card_id)
    except LookupError:
        raise HTTPException(status_code=404, detail="card not found") from None
    delete_card(db, card)
