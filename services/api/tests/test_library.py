"""GET /library — the shelf: ready snapshots, owner-scoped, newest first."""

from datetime import UTC, datetime

import pytest
from app.deps import get_db
from app.main import app
from app.schemas.capture import CaptureRequest
from app.services.capture import create_snapshot
from fastapi.testclient import TestClient
from gulp_shared.models.source import SnapshotStatus, Source, SourceKind
from gulp_shared.models.user import DEV_USER_ID, User


@pytest.fixture
def client(db):  # type: ignore[no-untyped-def]
    app.dependency_overrides[get_db] = lambda: db
    yield TestClient(app)
    app.dependency_overrides.clear()


def _ready(db, url: str):  # type: ignore[no-untyped-def]
    snap, _ = create_snapshot(db, DEV_USER_ID, CaptureRequest(url=url))
    snap.status = SnapshotStatus.ready
    db.commit()
    return snap


def test_library_lists_only_ready_newest_first(client: TestClient, db) -> None:  # type: ignore[no-untyped-def]
    a = _ready(db, "https://a.com/1")
    todo, _ = create_snapshot(db, DEV_USER_ID, CaptureRequest(url="https://a.com/todo"))
    b = _ready(db, "https://a.com/2")
    r = client.get("/library")
    assert r.status_code == 200
    body = r.json()
    assert [i["id"] for i in body["items"]] == [str(b.id), str(a.id)]
    assert str(todo.id) not in {i["id"] for i in body["items"]}
    assert body["count"] == 2


def _subscription(db, title: str):  # type: ignore[no-untyped-def]
    sub = Source(
        owner_id=DEV_USER_ID,
        kind=SourceKind.subscription,
        title=title,
        status=SnapshotStatus.ready,  # constant for subscriptions; health is derived
    )
    db.add(sub)
    db.flush()
    return sub


def test_library_item_carries_source_feed(client: TestClient, db) -> None:  # type: ignore[no-untyped-def]
    sub = _subscription(db, "HuggingFace Paper Daily")
    from_feed = _ready(db, "https://hf.co/papers/1")
    from_feed.emitted_by = sub.id
    db.commit()
    plain = _ready(db, "https://blog.example/1")

    items = {i["id"]: i for i in client.get("/library").json()["items"]}
    assert items[str(from_feed.id)]["source_feed"] == {
        "id": str(sub.id),
        "title": "HuggingFace Paper Daily",
    }
    assert items[str(plain.id)]["source_feed"] is None


def test_library_excludes_foreign_and_deleted(client: TestClient, db) -> None:  # type: ignore[no-untyped-def]
    mine = _ready(db, "https://a.com/mine")
    gone = _ready(db, "https://a.com/gone")
    gone.deleted_at = datetime.now(UTC)
    other = User(display_name="Other")
    db.add(other)
    db.flush()
    db.add(
        Source(
            owner_id=other.id,
            kind=SourceKind.snapshot,
            title="theirs",
            status=SnapshotStatus.ready,
        )
    )
    db.commit()
    r = client.get("/library")
    assert {i["id"] for i in r.json()["items"]} == {str(mine.id)}
