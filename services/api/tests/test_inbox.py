from app.services.capture import create_snapshot
from app.schemas.capture import CaptureRequest
from app.services.inbox import list_inbox
from gulp_shared.models.source import SnapshotStatus
from gulp_shared.models.user import DEV_USER_ID


def _noop(*a):
    return None


def test_inbox_lists_uncommitted_newest_first(db):
    a, _ = create_snapshot(db, DEV_USER_ID, CaptureRequest(url="https://a.com/1"), _noop)
    b, _ = create_snapshot(db, DEV_USER_ID, CaptureRequest(url="https://a.com/2"), _noop)
    items = list_inbox(db, DEV_USER_ID)
    assert [i.id for i in items] == [b.id, a.id]  # newest first


def test_inbox_excludes_in_library_and_soft_deleted(db):
    a, _ = create_snapshot(db, DEV_USER_ID, CaptureRequest(url="https://a.com/keep"), _noop)
    committed, _ = create_snapshot(db, DEV_USER_ID, CaptureRequest(url="https://a.com/done"), _noop)
    committed.status = SnapshotStatus.in_library
    db.commit()
    items = list_inbox(db, DEV_USER_ID)
    assert [i.id for i in items] == [a.id]
