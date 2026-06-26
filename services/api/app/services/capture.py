"""Capture business logic (docs/04 S1): create a Snapshot, dedupe, hand off."""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.schemas.capture import CaptureRequest
from gulp_shared.domain.urls import normalize_url
from gulp_shared.models.source import (
    CapturedVia,
    MediaType,
    SnapshotStatus,
    Source,
    SourceKind,
)
from gulp_shared.models.source_tag import SourceTag
from gulp_shared.urls import host_of


def create_snapshot(
    db: Session,
    owner_id: uuid.UUID,
    req: CaptureRequest,
) -> tuple[Source, bool]:
    if req.url and req.url.strip():
        normalized = normalize_url(req.url)
        existing = db.scalar(
            select(Source).where(
                Source.owner_id == owner_id,
                Source.origin_url == normalized,
                Source.deleted_at.is_(None),
            )
        )
        if existing is not None:
            return existing, True
        source = Source(
            owner_id=owner_id,
            kind=SourceKind.snapshot,
            title=req.title or host_of(normalized),
            note=req.note,
            status=SnapshotStatus.unprocessed,
            media_type=MediaType.webpage,
            origin_url=normalized,
            captured_via=req.captured_via or CapturedVia.in_app,
        )
    else:
        text = (req.text or "").strip()
        default_title = text.splitlines()[0][:80] if text else "Untitled note"
        source = Source(
            owner_id=owner_id,
            kind=SourceKind.snapshot,
            title=req.title or default_title,
            note=req.note,
            status=SnapshotStatus.unprocessed,
            media_type=MediaType.note,
            content_body=text,
            captured_via=req.captured_via or CapturedVia.manual,
        )

    db.add(source)
    db.flush()  # assign source.id
    for tag in req.tags:
        db.add(SourceTag(source_id=source.id, tag=tag))
    db.commit()
    db.refresh(source)
    # Manual trigger (S2 design §2.4): the snapshot rests at `unprocessed` until
    # the user Starts it (POST /snapshots/{id}/process). Capture never enqueues.
    return source, False
