from app.schemas.capture import CaptureRequest
from app.services.capture import create_snapshot
from gulp_shared.models.source import CapturedVia, MediaType, SnapshotStatus
from gulp_shared.models.user import DEV_USER_ID


def _enqueue_spy():
    calls = []
    return calls, (lambda *a: calls.append(a))


def test_link_capture_creates_processing_webpage_and_enqueues(db):
    calls, enq = _enqueue_spy()
    snap, dup = create_snapshot(
        db,
        DEV_USER_ID,
        CaptureRequest(url="https://Example.com/x/?utm_source=z", captured_via=CapturedVia.paste),
        enq,
    )
    assert dup is False
    assert snap.media_type == MediaType.webpage
    assert snap.status == SnapshotStatus.processing
    assert snap.origin_url == "https://example.com/x"  # normalized
    assert snap.title == "example.com"  # host default
    assert calls == [("process_snapshot", str(snap.id))]


def test_note_capture_stores_body_and_does_not_enqueue_a_pack_for_url(db):
    calls, enq = _enqueue_spy()
    snap, dup = create_snapshot(
        db,
        DEV_USER_ID,
        CaptureRequest(text="first line\nsecond", captured_via=CapturedVia.manual),
        enq,
    )
    assert snap.media_type == MediaType.note
    assert snap.content_body == "first line\nsecond"
    assert snap.title == "first line"
    assert len(calls) == 1  # still enqueued (the seam runs for every fresh snapshot)


def test_duplicate_url_returns_existing_and_does_not_enqueue(db):
    calls, enq = _enqueue_spy()
    first, _ = create_snapshot(db, DEV_USER_ID, CaptureRequest(url="https://a.com/p"), enq)
    again, dup = create_snapshot(
        db, DEV_USER_ID, CaptureRequest(url="https://a.com/p?utm_x=1"), enq
    )
    assert dup is True
    assert again.id == first.id
    assert len(calls) == 1  # only the first enqueued


def test_tags_are_persisted_as_rows(db):
    from app.services.snapshots import _tags_for

    _, enq = _enqueue_spy()
    snap, _ = create_snapshot(
        db, DEV_USER_ID, CaptureRequest(url="https://a.com/t", tags=["ml", "memory"]), enq
    )
    assert sorted(_tags_for(db, snap.id)) == ["memory", "ml"]
