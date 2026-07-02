"""GET /today — the "what should I do right now?" aggregate (docs/03 §7.9)."""

from datetime import UTC, datetime

import pytest
from app.deps import get_db
from app.main import app
from app.schemas.capture import CaptureRequest
from app.services.capture import create_snapshot
from fastapi.testclient import TestClient
from gulp_shared.models.card import Card, CardOrigin, CardStatus, CardType
from gulp_shared.models.source import SnapshotStatus, Source, SourceKind
from gulp_shared.models.user import DEV_USER_ID, User


@pytest.fixture
def client(db):  # type: ignore[no-untyped-def]
    app.dependency_overrides[get_db] = lambda: db
    yield TestClient(app)
    app.dependency_overrides.clear()


def _snap(db, url: str, *, status: SnapshotStatus = SnapshotStatus.ready):  # type: ignore[no-untyped-def]
    snap, _ = create_snapshot(db, DEV_USER_ID, CaptureRequest(url=url))
    snap.status = status
    db.commit()
    return snap


def _card(db, source, *, status: CardStatus = CardStatus.accepted) -> Card:  # type: ignore[no-untyped-def]
    card = Card(
        source_id=source.id,
        card_type=CardType.flashcard,
        prompt="q",
        origin=CardOrigin.pack,
        status=status,
    )
    db.add(card)
    db.commit()
    return card


def test_today_counts_accepted_cards_only(client: TestClient, db) -> None:  # type: ignore[no-untyped-def]
    snap = _snap(db, "https://a.com/1")
    _card(db, snap)
    _card(db, snap)
    _card(db, snap, status=CardStatus.draft)
    _card(db, snap, status=CardStatus.rejected)
    r = client.get("/today")
    assert r.status_code == 200
    body = r.json()
    assert body["accepted_cards"] == 2
    assert body["card_sources"] == 1
    assert body["digest"][0]["accepted_cards"] == 2


def test_today_excludes_deleted_cards_and_foreign_sources(client: TestClient, db) -> None:  # type: ignore[no-untyped-def]
    snap = _snap(db, "https://a.com/1")
    gone = _card(db, snap)
    gone.deleted_at = datetime.now(UTC)
    other = User(display_name="Other")
    db.add(other)
    db.flush()
    theirs = Source(
        owner_id=other.id,
        kind=SourceKind.snapshot,
        title="theirs",
        status=SnapshotStatus.ready,
    )
    db.add(theirs)
    db.flush()
    _card(db, theirs)
    db.commit()
    r = client.get("/today")
    body = r.json()
    assert body["accepted_cards"] == 0
    assert body["card_sources"] == 0
    assert [d["snapshot"]["id"] for d in body["digest"]] == [str(snap.id)]


def test_today_digest_is_ready_only_newest_first_capped_at_3(client: TestClient, db) -> None:  # type: ignore[no-untyped-def]
    snaps = [_snap(db, f"https://a.com/{i}") for i in range(4)]
    _snap(db, "https://a.com/todo", status=SnapshotStatus.unprocessed)
    r = client.get("/today")
    body = r.json()
    ids = [d["snapshot"]["id"] for d in body["digest"]]
    assert ids == [str(s.id) for s in reversed(snaps)][:3]
    assert body["ready_count"] == 4


def test_today_recent_is_inbox_newest_first_capped_at_3(client: TestClient, db) -> None:  # type: ignore[no-untyped-def]
    todos = [
        _snap(db, f"https://b.com/{i}", status=SnapshotStatus.unprocessed) for i in range(4)
    ]
    r = client.get("/today")
    body = r.json()
    assert body["inbox_count"] == 4
    assert [s["id"] for s in body["recent"]] == [str(s.id) for s in reversed(todos)][:3]
