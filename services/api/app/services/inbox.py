"""The Inbox derived view — the to-do set (single-gate spec 2026-07-02).

Never an entity — a query."""

import uuid

from gulp_shared.models.source import SnapshotStatus, Source, SourceKind
from sqlalchemy import select
from sqlalchemy.orm import Session

# Everything that still needs the owner's attention; `ready` lives in Library.
_TODO = (
    SnapshotStatus.queued,
    SnapshotStatus.unprocessed,
    SnapshotStatus.processing,
    SnapshotStatus.exported,
    SnapshotStatus.needs_attention,
)


def list_inbox(db: Session, owner_id: uuid.UUID) -> list[Source]:
    stmt = (
        select(Source)
        .where(
            Source.owner_id == owner_id,
            Source.kind == SourceKind.snapshot,
            Source.deleted_at.is_(None),
            Source.status.in_(_TODO),
        )
        .order_by(Source.created_at.desc())
    )
    return list(db.scalars(stmt))
