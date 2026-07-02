from datetime import UTC, datetime

from app.schemas.capture import CaptureRequest
from app.services.capture import create_snapshot
from app.services.inbox import list_inbox
from gulp_shared.models.source import SnapshotStatus
from gulp_shared.models.user import DEV_USER_ID


def test_inbox_lists_todo_newest_first(db):
    a, _ = create_snapshot(db, DEV_USER_ID, CaptureRequest(url="https://a.com/1"))
    b, _ = create_snapshot(db, DEV_USER_ID, CaptureRequest(url="https://a.com/2"))
    items = list_inbox(db, DEV_USER_ID)
    assert [i.id for i in items] == [b.id, a.id]  # newest first


def test_inbox_is_the_todo_set(db):
    """Single-gate lifecycle: `ready` = shelved in Library, everything else is to-do."""
    keep_statuses = [
        SnapshotStatus.queued,
        SnapshotStatus.unprocessed,
        SnapshotStatus.processing,
        SnapshotStatus.exported,
        SnapshotStatus.needs_attention,
    ]
    kept = []
    for i, status in enumerate(keep_statuses):
        snap, _ = create_snapshot(db, DEV_USER_ID, CaptureRequest(url=f"https://a.com/{i}"))
        snap.status = status
        kept.append(snap.id)
    shelved, _ = create_snapshot(db, DEV_USER_ID, CaptureRequest(url="https://a.com/done"))
    shelved.status = SnapshotStatus.ready
    db.commit()

    ids = [i.id for i in list_inbox(db, DEV_USER_ID)]
    assert shelved.id not in ids
    assert set(kept) <= set(ids)


def test_inbox_excludes_soft_deleted(db):
    gone, _ = create_snapshot(db, DEV_USER_ID, CaptureRequest(url="https://a.com/gone"))
    gone.deleted_at = datetime.now(UTC)
    db.commit()
    assert gone.id not in [i.id for i in list_inbox(db, DEV_USER_ID)]
