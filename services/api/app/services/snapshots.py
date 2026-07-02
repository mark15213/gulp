"""Serialize a Source (+ its tags) to the SnapshotOut contract."""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.schemas.capture import SnapshotOut
from gulp_shared.models.source import Source
from gulp_shared.models.source_tag import SourceTag


def _tags_for(db: Session, source_id: uuid.UUID) -> list[str]:
    return list(
        db.scalars(
            select(SourceTag.tag).where(
                SourceTag.source_id == source_id,
                SourceTag.deleted_at.is_(None),
            )
        )
    )


def to_out(db: Session, source: Source) -> SnapshotOut:
    return SnapshotOut(
        id=source.id,
        kind=source.kind,
        title=source.title,
        note=source.note,
        status=source.status,
        media_type=source.media_type,
        origin_url=source.origin_url,
        content_body=source.content_body,
        captured_via=source.captured_via,
        cards_status=source.cards_status,
        tags=_tags_for(db, source.id),
        created_at=source.created_at,
        updated_at=source.updated_at,
    )
