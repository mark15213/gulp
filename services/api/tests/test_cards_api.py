"""Cards endpoints: generate / import / list / patch / delete (spec §④/§⑤)."""

import uuid

import pytest
from app.deps import get_db, get_enqueue
from app.main import app
from fastapi.testclient import TestClient
from gulp_shared.models.card import Card, CardOrigin, CardType
from gulp_shared.models.knowledge_pack import KnowledgePack, PackStatus
from gulp_shared.models.source import CardsStatus, SnapshotStatus, Source, SourceKind
from gulp_shared.models.user import User


@pytest.fixture
def client(db):  # type: ignore[no-untyped-def]
    calls: list[tuple[object, ...]] = []
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_enqueue] = lambda: (lambda *a: calls.append(a))
    c = TestClient(app)
    c.enqueue_calls = calls  # type: ignore[attr-defined]
    yield c
    app.dependency_overrides.clear()


def _capture(client: TestClient) -> str:
    r = client.post("/capture", json={"url": "https://a.com/x"})
    client.enqueue_calls.clear()  # type: ignore[attr-defined]
    return r.json()["snapshot"]["id"]


def _ready_pack(db, sid: str) -> KnowledgePack:  # type: ignore[no-untyped-def]
    pack = KnowledgePack(
        snapshot_id=uuid.UUID(sid),
        title="T",
        key_insight="k",
        core_contributions=["c"],
        references=[],
        status=PackStatus.ready,
    )
    db.add(pack)
    db.commit()
    return pack


_IMPORT = {
    "cards": [
        {
            "card_type": "flashcard",
            "prompt": "Q1?",
            "answer": "A1",
            "explanation": "e",
        },
        {
            "card_type": "mcq",
            "prompt": "Q2?",
            "answer": "B",
            "options": ["A", "B", "C"],
        },
    ]
}


# -- generate ---------------------------------------------------------------


def test_generate_enqueues_and_sets_generating(client: TestClient, db) -> None:  # type: ignore[no-untyped-def]
    sid = _capture(client)
    _ready_pack(db, sid)
    r = client.post(f"/snapshots/{sid}/cards/generate")
    assert r.status_code == 202
    assert r.json()["cards_status"] == "generating"
    assert client.enqueue_calls == [("generate_cards", sid)]


def test_generate_without_ready_pack_400(client: TestClient) -> None:
    sid = _capture(client)
    r = client.post(f"/snapshots/{sid}/cards/generate")
    assert r.status_code == 400


def test_generate_while_generating_409(client: TestClient, db) -> None:  # type: ignore[no-untyped-def]
    sid = _capture(client)
    _ready_pack(db, sid)
    assert client.post(f"/snapshots/{sid}/cards/generate").status_code == 202
    r = client.post(f"/snapshots/{sid}/cards/generate")
    assert r.status_code == 409


def test_generate_after_failed_is_allowed(client: TestClient, db) -> None:  # type: ignore[no-untyped-def]
    sid = _capture(client)
    _ready_pack(db, sid)
    source = db.get(Source, uuid.UUID(sid))
    source.cards_status = CardsStatus.failed
    db.commit()
    assert client.post(f"/snapshots/{sid}/cards/generate").status_code == 202


def test_generate_unknown_snapshot_404(client: TestClient) -> None:
    r = client.post("/snapshots/00000000-0000-0000-0000-0000000000ff/cards/generate")
    assert r.status_code == 404


# -- export (cards job for Claude Code) -------------------------------------


def test_export_cards_enqueues(client: TestClient, db) -> None:  # type: ignore[no-untyped-def]
    sid = _capture(client)
    _ready_pack(db, sid)
    r = client.post(f"/snapshots/{sid}/cards/export")
    assert r.status_code == 202
    assert client.enqueue_calls == [("build_cards_export", sid)]  # type: ignore[attr-defined]


def test_export_cards_without_ready_pack_400(client: TestClient) -> None:
    sid = _capture(client)
    r = client.post(f"/snapshots/{sid}/cards/export")
    assert r.status_code == 400


def test_download_cards_job_404_when_not_built(client: TestClient) -> None:
    sid = _capture(client)
    r = client.get(f"/snapshots/{sid}/cards/job")
    assert r.status_code == 404


# -- import -----------------------------------------------------------------


def test_import_appends_imported_drafts_without_pack(client: TestClient) -> None:
    sid = _capture(client)  # no pack needed
    r = client.post(f"/snapshots/{sid}/cards/import", json=_IMPORT)
    assert r.status_code == 201
    cards = r.json()
    assert len(cards) == 2
    assert all(c["origin"] == "imported" and c["status"] == "draft" for c in cards)


def test_import_twice_appends(client: TestClient) -> None:
    sid = _capture(client)
    client.post(f"/snapshots/{sid}/cards/import", json=_IMPORT)
    client.post(f"/snapshots/{sid}/cards/import", json=_IMPORT)
    r = client.get(f"/snapshots/{sid}/cards")
    assert len(r.json()) == 4


def test_import_invalid_payload_422(client: TestClient) -> None:
    sid = _capture(client)
    bad = {"cards": [{"card_type": "mcq", "prompt": "Q?", "answer": "A"}]}  # no options
    r = client.post(f"/snapshots/{sid}/cards/import", json=bad)
    assert r.status_code == 422


# -- list -------------------------------------------------------------------


def test_list_returns_all_cards(client: TestClient, db) -> None:  # type: ignore[no-untyped-def]
    sid = _capture(client)
    client.post(f"/snapshots/{sid}/cards/import", json=_IMPORT)
    db.add(
        Card(
            source_id=uuid.UUID(sid),
            card_type=CardType.flashcard,
            prompt="gen",
            answer="a",
            origin=CardOrigin.pack,
        )
    )
    db.commit()
    r = client.get(f"/snapshots/{sid}/cards")
    assert r.status_code == 200
    assert {c["prompt"] for c in r.json()} == {"Q1?", "Q2?", "gen"}


def test_list_foreign_snapshot_404(client: TestClient, db) -> None:  # type: ignore[no-untyped-def]
    other = User(display_name="Other")
    db.add(other)
    db.flush()
    foreign = Source(
        owner_id=other.id,
        kind=SourceKind.snapshot,
        title="F",
        status=SnapshotStatus.ready,
    )
    db.add(foreign)
    db.commit()
    r = client.get(f"/snapshots/{foreign.id}/cards")
    assert r.status_code == 404


# -- patch ------------------------------------------------------------------


def _one_card_id(client: TestClient, sid: str) -> str:
    client.post(
        f"/snapshots/{sid}/cards/import",
        json={"cards": [{"card_type": "flashcard", "prompt": "Q?", "answer": "A"}]},
    )
    return client.get(f"/snapshots/{sid}/cards").json()[0]["id"]


def test_patch_status_accepts_card(client: TestClient) -> None:
    sid = _capture(client)
    cid = _one_card_id(client, sid)
    r = client.patch(f"/snapshots/{sid}/cards/{cid}", json={"status": "accepted"})
    assert r.status_code == 200
    assert r.json()["status"] == "accepted"


def test_patch_content_is_revalidated_per_type(client: TestClient) -> None:
    sid = _capture(client)
    cid = _one_card_id(client, sid)
    ok = client.patch(f"/snapshots/{sid}/cards/{cid}", json={"prompt": "New Q?"})
    assert ok.status_code == 200 and ok.json()["prompt"] == "New Q?"
    bad = client.patch(f"/snapshots/{sid}/cards/{cid}", json={"answer": None})
    assert bad.status_code == 422  # flashcard requires an answer


def test_patch_card_of_other_snapshot_404(client: TestClient) -> None:
    sid_a = _capture(client)
    r = client.post("/capture", json={"url": "https://a.com/y"})
    sid_b = r.json()["snapshot"]["id"]
    cid_b = _one_card_id(client, sid_b)
    r = client.patch(f"/snapshots/{sid_a}/cards/{cid_b}", json={"status": "accepted"})
    assert r.status_code == 404


# -- delete -----------------------------------------------------------------


def test_delete_removes_card(client: TestClient) -> None:
    sid = _capture(client)
    cid = _one_card_id(client, sid)
    r = client.delete(f"/snapshots/{sid}/cards/{cid}")
    assert r.status_code == 204
    assert client.get(f"/snapshots/{sid}/cards").json() == []


# -- snapshot exposure --------------------------------------------------------


def test_snapshot_out_carries_cards_status(client: TestClient, db) -> None:  # type: ignore[no-untyped-def]
    sid = _capture(client)
    r = client.get(f"/snapshots/{sid}")
    assert r.status_code == 200
    assert r.json()["cards_status"] is None
    _ready_pack(db, sid)
    client.post(f"/snapshots/{sid}/cards/generate")
    r = client.get(f"/snapshots/{sid}")
    assert r.json()["cards_status"] == "generating"
