"""The Inbox derived view (docs/02 D3 / spec C4). Never an entity — a query."""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from gulp_shared.models.source import SnapshotStatus, Source, SourceKind


def list_inbox(db: Session, owner_id: uuid.UUID) -> list[Source]:
    # `no KBMembership` clause arrives with S3 (the table doesn't exist yet).
    stmt = (
        select(Source)
        .where(
            Source.owner_id == owner_id,
            Source.kind == SourceKind.snapshot,
            Source.deleted_at.is_(None),
            Source.status != SnapshotStatus.in_library,
        )
        .order_by(Source.created_at.desc())
    )
    return list(db.scalars(stmt))
