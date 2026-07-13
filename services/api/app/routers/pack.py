"""Pack read endpoint — thin (docs/05 D4)."""

import json
import uuid
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import StreamingResponse
from gulp_shared.models.source import Source
from gulp_shared.models.user import User
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.deps import get_db
from app.schemas.chat import MessageCreate, MessageOut
from app.schemas.pack import BlockCreate, BlockOut, BlockUpdate, PackOut
from app.services.chat import answer_stream, list_messages
from app.services.pack import create_block, delete_block, pack_out, update_block

router = APIRouter()


def _owned_snapshot(db: Session, snapshot_id: uuid.UUID, user: User) -> Source:
    source = db.get(Source, snapshot_id)
    if source is None or source.owner_id != user.id or source.deleted_at is not None:
        raise HTTPException(status_code=404, detail="snapshot not found")
    return source


@router.get("/snapshots/{snapshot_id}/pack", response_model=PackOut)
def get_pack(
    snapshot_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> PackOut:
    _owned_snapshot(db, snapshot_id, user)
    pack = pack_out(db, snapshot_id)
    if pack is None:
        raise HTTPException(status_code=404, detail="no pack for this snapshot")
    return pack


@router.patch("/snapshots/{snapshot_id}/blocks/{block_id}", response_model=BlockOut)
def update_block_route(
    snapshot_id: uuid.UUID,
    block_id: uuid.UUID,
    update: BlockUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    _owned_snapshot(db, snapshot_id, user)
    try:
        return update_block(db, snapshot_id, block_id, update)
    except LookupError:
        raise HTTPException(status_code=404, detail="block not found") from None


@router.delete("/snapshots/{snapshot_id}/blocks/{block_id}", status_code=204)
def delete_block_route(
    snapshot_id: uuid.UUID,
    block_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Response:
    _owned_snapshot(db, snapshot_id, user)
    try:
        delete_block(db, snapshot_id, block_id)
    except LookupError:
        raise HTTPException(status_code=404, detail="block not found") from None
    return Response(status_code=204)


@router.post(
    "/snapshots/{snapshot_id}/sections/{section_id}/blocks",
    response_model=BlockOut,
    status_code=201,
)
def create_block_route(
    snapshot_id: uuid.UUID,
    section_id: uuid.UUID,
    create: BlockCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    _owned_snapshot(db, snapshot_id, user)
    try:
        return create_block(db, snapshot_id, section_id, create)
    except LookupError:
        raise HTTPException(status_code=404, detail="section not found") from None


@router.get("/snapshots/{snapshot_id}/messages", response_model=list[MessageOut])
def list_messages_route(
    snapshot_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[Any]:
    _owned_snapshot(db, snapshot_id, user)
    return list_messages(db, snapshot_id)


@router.post("/snapshots/{snapshot_id}/messages/stream")
async def stream_message_route(
    snapshot_id: uuid.UUID,
    body: MessageCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> StreamingResponse:
    _owned_snapshot(db, snapshot_id, user)

    async def gen() -> AsyncIterator[str]:
        async for ev in answer_stream(db, snapshot_id, body.content, body.block_refs):
            yield f"data: {json.dumps(ev)}\n\n"

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
