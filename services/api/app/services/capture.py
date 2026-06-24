"""Capture business logic (docs/04 S1): create a Snapshot, dedupe, hand off."""

import uuid
from collections.abc import Callable
from urllib.parse import urlsplit

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

EnqueueFn = Callable[..., None]


def _host(url: str) -> str:
    return urlsplit(url).hostname or url


def create_snapshot(
    db: Session,
    owner_id: uuid.UUID,
    req: CaptureRequest,
    enqueue: EnqueueFn,
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
            title=req.title or _host(normalized),
            note=req.note,
            status=SnapshotStatus.processing,
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
            status=SnapshotStatus.processing,
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

    # The S1↔S2 seam: hand off, never process inline (docs/04 S1).
    enqueue("process_snapshot", str(source.id))
    return source, False
