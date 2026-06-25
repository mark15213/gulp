from app.schemas.capture import CaptureRequest
from app.services.capture import create_snapshot
from gulp_shared.models.source import CapturedVia, MediaType, SnapshotStatus
from gulp_shared.models.user import DEV_USER_ID


def test_link_capture_creates_unprocessed_webpage(db) -> None:  # type: ignore[no-untyped-def]
    snap, dup = create_snapshot(
        db, DEV_USER_ID,
        CaptureRequest(url="https://Example.com/x/?utm_source=z", captured_via=CapturedVia.paste),
    )
    assert dup is False
    assert snap.media_type == MediaType.webpage
    assert snap.status == SnapshotStatus.unprocessed
    assert snap.origin_url == "https://example.com/x"
    assert snap.title == "example.com"


def test_note_capture_stores_body_unprocessed(db) -> None:  # type: ignore[no-untyped-def]
    snap, dup = create_snapshot(
        db, DEV_USER_ID, CaptureRequest(text="first line\nsecond", captured_via=CapturedVia.manual),
    )
    assert snap.media_type == MediaType.note
    assert snap.content_body == "first line\nsecond"
    assert snap.title == "first line"
    assert snap.status == SnapshotStatus.unprocessed


def test_duplicate_url_returns_existing(db) -> None:  # type: ignore[no-untyped-def]
    first, _ = create_snapshot(db, DEV_USER_ID, CaptureRequest(url="https://a.com/p"))
    again, dup = create_snapshot(db, DEV_USER_ID, CaptureRequest(url="https://a.com/p?utm_x=1"))
    assert dup is True
    assert again.id == first.id


def test_tags_are_persisted_as_rows(db) -> None:  # type: ignore[no-untyped-def]
    from app.services.snapshots import _tags_for

    snap, _ = create_snapshot(
        db, DEV_USER_ID, CaptureRequest(url="https://a.com/t", tags=["ml", "memory"]),
    )
    assert sorted(_tags_for(db, snap.id)) == ["memory", "ml"]
