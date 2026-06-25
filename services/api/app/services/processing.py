"""Start-processing business logic (S2 manual trigger, design §2.4)."""

from collections.abc import Callable

from sqlalchemy.orm import Session

from gulp_shared.models.source import SnapshotStatus, Source

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
