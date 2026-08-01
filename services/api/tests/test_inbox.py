import uuid
from datetime import UTC, datetime

from app.schemas.capture import CaptureRequest
from app.services.capture import create_snapshot
from app.services.inbox import actionable_count, list_inbox
from gulp_shared.models import Source, SourceKind
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


def _sub(db, title="少数派"):
    s = Source(
        owner_id=DEV_USER_ID,
        kind=SourceKind.subscription,
        title=title,
        status=SnapshotStatus.ready,
        feed_url=f"rsshub://{uuid.uuid4()}",
        muted=False,
    )
    db.add(s)
    db.commit()
    return s


def test_actionable_count_ignores_work_the_machine_owns(db):
    """The badge means "waiting on you" — never queued/processing (spec §4.5)."""
    for i, status in enumerate(
        [SnapshotStatus.unprocessed, SnapshotStatus.exported, SnapshotStatus.needs_attention]
    ):
        snap, _ = create_snapshot(db, DEV_USER_ID, CaptureRequest(url=f"https://a.com/y{i}"))
        snap.status = status
    for i, status in enumerate([SnapshotStatus.queued, SnapshotStatus.processing]):
        snap, _ = create_snapshot(db, DEV_USER_ID, CaptureRequest(url=f"https://a.com/n{i}"))
        snap.status = status
    db.commit()
    assert actionable_count(db, DEV_USER_ID) == 3


def test_source_filter_scopes_items_but_never_the_badge(db):
    sub = _sub(db)
    forwarded, _ = create_snapshot(db, DEV_USER_ID, CaptureRequest(url="https://a.com/feed"))
    forwarded.emitted_by = sub.id
    ad_hoc, _ = create_snapshot(db, DEV_USER_ID, CaptureRequest(url="https://a.com/mine"))
    db.commit()

    assert [i.id for i in list_inbox(db, DEV_USER_ID, emitted_by=sub.id)] == [forwarded.id]
    assert [i.id for i in list_inbox(db, DEV_USER_ID, ad_hoc_only=True)] == [ad_hoc.id]
    # the badge is computed unfiltered, so filtering must not move it
    assert actionable_count(db, DEV_USER_ID) == 2
