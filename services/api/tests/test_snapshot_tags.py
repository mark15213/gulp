"""POST/DELETE /snapshots/{id}/tags — manual user-tag add/remove."""

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


def _snap(db):  # type: ignore[no-untyped-def]
    snap, _ = create_snapshot(db, DEV_USER_ID, CaptureRequest(url="https://a.com/1"))
    snap.status = SnapshotStatus.ready
    db.commit()
    return snap


def test_add_tag(client: TestClient, db) -> None:  # type: ignore[no-untyped-def]
    snap = _snap(db)
    r = client.post(f"/snapshots/{snap.id}/tags", json={"tag": "pretrain"})
    assert r.status_code == 200
    assert "pretrain" in r.json()["tags"]


def test_add_tag_is_idempotent(client: TestClient, db) -> None:  # type: ignore[no-untyped-def]
    snap = _snap(db)
    client.post(f"/snapshots/{snap.id}/tags", json={"tag": "rl"})
    r = client.post(f"/snapshots/{snap.id}/tags", json={"tag": "rl"})
    assert r.json()["tags"].count("rl") == 1


def test_remove_tag(client: TestClient, db) -> None:  # type: ignore[no-untyped-def]
    snap = _snap(db)
    client.post(f"/snapshots/{snap.id}/tags", json={"tag": "rl"})
    r = client.delete(f"/snapshots/{snap.id}/tags", params={"tag": "rl"})
    assert r.status_code == 200
    assert "rl" not in r.json()["tags"]


def test_empty_tag_rejected(client: TestClient, db) -> None:  # type: ignore[no-untyped-def]
    snap = _snap(db)
    r = client.post(f"/snapshots/{snap.id}/tags", json={"tag": "   "})
    assert r.status_code == 422


def test_tag_foreign_snapshot_404(client: TestClient, db) -> None:  # type: ignore[no-untyped-def]
    other = User(display_name="Other")
    db.add(other)
    db.flush()
    foreign = Source(
        owner_id=other.id, kind=SourceKind.snapshot, title="x", status=SnapshotStatus.ready
    )
    db.add(foreign)
    db.commit()
    r = client.post(f"/snapshots/{foreign.id}/tags", json={"tag": "x"})
    assert r.status_code == 404
