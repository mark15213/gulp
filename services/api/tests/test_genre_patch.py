"""Source.genre exposure + correction endpoint."""

import pytest
from app.deps import get_db
from app.main import app
from fastapi.testclient import TestClient
from gulp_shared.models.source import SnapshotStatus, Source, SourceGenre, SourceKind
from gulp_shared.models.user import DEV_USER_ID


@pytest.fixture
def client(db):  # type: ignore[no-untyped-def]
    app.dependency_overrides[get_db] = lambda: db
    c = TestClient(app)
    yield c
    app.dependency_overrides.clear()


def _snap(db, **kw):  # type: ignore[no-untyped-def]
    s = Source(owner_id=DEV_USER_ID, kind=SourceKind.snapshot, title="N",
               status=SnapshotStatus.ready, content_body="body", **kw)
    db.add(s)
    db.commit()
    return s


def test_snapshot_out_includes_genre(client, db):  # type: ignore[no-untyped-def]
    s = _snap(db, genre=SourceGenre.article)
    r = client.get(f"/snapshots/{s.id}")
    assert r.status_code == 200
    assert r.json()["genre"] == "article"


def test_patch_genre_updates_and_returns_snapshot(client, db):  # type: ignore[no-untyped-def]
    s = _snap(db, genre=SourceGenre.article)
    r = client.patch(f"/snapshots/{s.id}", json={"genre": "paper"})
    assert r.status_code == 200
    assert r.json()["genre"] == "paper"
    db.refresh(s)
    assert s.genre == SourceGenre.paper


def test_patch_genre_rejects_unknown_value(client, db):  # type: ignore[no-untyped-def]
    s = _snap(db)
    r = client.patch(f"/snapshots/{s.id}", json={"genre": "sitcom"})
    assert r.status_code == 422


def test_patch_genre_404_for_missing_snapshot(client, db):  # type: ignore[no-untyped-def]
    r = client.patch(
        "/snapshots/00000000-0000-0000-0000-000000000001", json={"genre": "paper"}
    )
    assert r.status_code == 404
