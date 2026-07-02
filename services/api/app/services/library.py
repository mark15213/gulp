"""The Library derived view — the shelf: `ready` snapshots (single-gate spec 2026-07-02)."""

import uuid

from gulp_shared.models.source import SnapshotStatus, Source, SourceKind
from sqlalchemy import select
from sqlalchemy.orm import Session


def list_library(db: Session, owner_id: uuid.UUID) -> list[Source]:
    stmt = (
        select(Source)
        .where(
            Source.owner_id == owner_id,
            Source.kind == SourceKind.snapshot,
            Source.deleted_at.is_(None),
            Source.status == SnapshotStatus.ready,
        )
        .order_by(Source.created_at.desc())
    )
    return list(db.scalars(stmt))
