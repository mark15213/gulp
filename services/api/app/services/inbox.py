"""The Inbox derived view — the whole intake surface (spec 2026-08-01).

Never an entity — a query. The web client groups one response into the stage
sections `Kept` / `Needs you` / `In flight`; the `New` section is fed
separately by the pending feed entries."""

import uuid

from gulp_shared.models.source import SnapshotStatus, Source, SourceKind
from sqlalchemy import ColumnElement, select
from sqlalchemy.orm import Session

# Everything that has not reached the shelf; `ready` lives in Library.
_TODO = (
    SnapshotStatus.queued,
    SnapshotStatus.unprocessed,
    SnapshotStatus.processing,
    SnapshotStatus.exported,
    SnapshotStatus.needs_attention,
)

# What actually waits on the owner. `queued`/`processing` are the machine's
# work — visible in the In-flight section, never in the badge (spec §4.5).
_ACTIONABLE = (
    SnapshotStatus.unprocessed,
    SnapshotStatus.exported,
    SnapshotStatus.needs_attention,
)


def _base(owner_id: uuid.UUID) -> tuple[ColumnElement[bool], ...]:
    return (
        Source.owner_id == owner_id,
        Source.kind == SourceKind.snapshot,
        Source.deleted_at.is_(None),
    )


def list_inbox(
    db: Session,
    owner_id: uuid.UUID,
    emitted_by: uuid.UUID | None = None,
    ad_hoc_only: bool = False,
) -> list[Source]:
    """Optionally scoped by the source rail: one subscription, or the
    `Captured` bucket (snapshots with no emitting subscription)."""
    stmt = select(Source).where(*_base(owner_id), Source.status.in_(_TODO))
    if emitted_by is not None:
        stmt = stmt.where(Source.emitted_by == emitted_by)
    elif ad_hoc_only:
        stmt = stmt.where(Source.emitted_by.is_(None))
    return list(db.scalars(stmt.order_by(Source.created_at.desc())))


def actionable_count(db: Session, owner_id: uuid.UUID) -> int:
    """Deliberately unfiltered: the badge must not change when the user
    filters the surface by source (spec §3.2)."""
    stmt = select(Source.id).where(*_base(owner_id), Source.status.in_(_ACTIONABLE))
    return len(list(db.scalars(stmt)))
