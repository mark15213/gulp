"""Start-processing business logic (S2 manual trigger, design §2.4)."""

import uuid
from collections.abc import Callable

from gulp_shared.models.source import SnapshotStatus, Source
from sqlalchemy import select
from sqlalchemy.orm import Session

_STARTABLE = {
    SnapshotStatus.unprocessed,
    SnapshotStatus.needs_attention,
    SnapshotStatus.ready,  # allow re-generation
    # `processing` is startable so a snapshot stranded by a dead worker can be
    # re-enqueued without manual DB surgery.  The persist step is idempotent
    # (deletes and rebuilds the KnowledgePack), so re-running is safe.
    # Caveat: re-Starting a *live* job can double-enqueue — tolerated in v1.
    # The KnowledgePack.snapshot_id unique constraint self-heals the persist
    # step, and a job-lock/reaper is a later refinement.
    SnapshotStatus.processing,
}


def start_processing(db: Session, source: Source, enqueue: Callable[..., None]) -> None:
    if source.status not in _STARTABLE:
        raise ValueError(f"snapshot in status {source.status.value} is not startable")
    source.status = SnapshotStatus.processing
    db.commit()
    enqueue("process_snapshot", str(source.id))


def start_processing_batch(
    db: Session,
    owner_id: uuid.UUID,
    ids: list[uuid.UUID],
    enqueue: Callable[..., None],
) -> tuple[list[uuid.UUID], list[tuple[uuid.UUID, str]]]:
    """Start many at once (the Inbox `Start N` bar). One unstartable or unknown
    id must not fail the rest — it comes back in `skipped` with a reason."""
    found = {
        s.id: s
        for s in db.scalars(
            select(Source).where(
                Source.id.in_(ids),
                Source.owner_id == owner_id,
                Source.deleted_at.is_(None),
            )
        )
    }
    started: list[uuid.UUID] = []
    skipped: list[tuple[uuid.UUID, str]] = []
    for snapshot_id in ids:
        source = found.get(snapshot_id)
        if source is None:
            skipped.append((snapshot_id, "snapshot not found"))
            continue
        try:
            start_processing(db, source, enqueue)
        except ValueError as exc:
            skipped.append((snapshot_id, str(exc)))
        else:
            started.append(snapshot_id)
    return started, skipped
