import uuid

import pytest
from app.deps import get_db
from app.main import app
from fastapi.testclient import TestClient
from gulp_shared.models.knowledge_pack import (
    KnowledgePack,
    PackBlock,
    PackBlockType,
    PackSection,
    PackStatus,
    PackType,
)
from gulp_shared.models.source import SnapshotStatus, Source, SourceKind
from gulp_shared.models.user import DEV_USER_ID


@pytest.fixture
def client(db):  # type: ignore[no-untyped-def]
    app.dependency_overrides[get_db] = lambda: db
    c = TestClient(app)
    yield c
    app.dependency_overrides.clear()


def _ready_snapshot_with_pack(db) -> uuid.UUID:  # type: ignore[no-untyped-def]
    snap = Source(owner_id=DEV_USER_ID, kind=SourceKind.snapshot, title="T",
                  status=SnapshotStatus.ready)
    db.add(snap)
    db.flush()
    pack = KnowledgePack(snapshot_id=snap.id, title="BERT", pack_type=PackType.paper,
                         extras={"key_insight": "ki", "core_contributions": ["c1"]},
                         status=PackStatus.ready)
    db.add(pack)
    db.flush()
    sec = PackSection(pack_id=pack.id, heading="H", position=0)
    db.add(sec)
    db.flush()
    db.add(PackBlock(section_id=sec.id, block_type=PackBlockType.prose,
                     data={"content": "hello"}, position=0))
    db.commit()
    return snap.id


def test_get_pack_returns_report(client, db) -> None:  # type: ignore[no-untyped-def]
    sid = _ready_snapshot_with_pack(db)
    r = client.get(f"/snapshots/{sid}/pack")
    assert r.status_code == 200
    body = r.json()
    assert body["title"] == "BERT" and body["core_contributions"] == ["c1"]
    assert body["sections"][0]["blocks"][0]["content"] == "hello"
    assert body["sections"][0]["blocks"][0]["type"] == "prose"


def test_get_pack_404_when_no_pack(client, db) -> None:  # type: ignore[no-untyped-def]
    snap = Source(owner_id=DEV_USER_ID, kind=SourceKind.snapshot, title="N",
                  status=SnapshotStatus.unprocessed)
    db.add(snap)
    db.commit()
    r = client.get(f"/snapshots/{snap.id}/pack")
    assert r.status_code == 404


def test_get_pack_404_for_unknown_id(client) -> None:  # type: ignore[no-untyped-def]
    r = client.get("/snapshots/00000000-0000-0000-0000-0000000000ff/pack")
    assert r.status_code == 404


def test_get_pack_404_for_foreign_snapshot(client, db) -> None:  # type: ignore[no-untyped-def]
    foreign_snap = Source(
        owner_id=uuid.uuid4(), kind=SourceKind.snapshot, title="Foreign",
        status=SnapshotStatus.ready,
    )
    db.add(foreign_snap)
    db.commit()
    r = client.get(f"/snapshots/{foreign_snap.id}/pack")
    assert r.status_code == 404


def test_get_pack_exposes_section_and_block_ids(client, db) -> None:  # type: ignore[no-untyped-def]
    snap = Source(owner_id=DEV_USER_ID, kind=SourceKind.snapshot, title="T",
                  status=SnapshotStatus.ready)
    db.add(snap)
    db.flush()
    pack = KnowledgePack(snapshot_id=snap.id, title="BERT", pack_type=PackType.paper,
                         extras={"key_insight": "ki", "core_contributions": ["c1"]},
                         status=PackStatus.ready)
    db.add(pack)
    db.flush()
    sec = PackSection(pack_id=pack.id, heading="H", position=0)
    db.add(sec)
    db.flush()
    block = PackBlock(section_id=sec.id, block_type=PackBlockType.prose,
                      data={"content": "hello"}, position=0)
    db.add(block)
    db.commit()
    sec_id, block_id = str(sec.id), str(block.id)

    r = client.get(f"/snapshots/{snap.id}/pack")
    assert r.status_code == 200
    body = r.json()
    assert body["sections"][0]["id"] == sec_id
    assert body["sections"][0]["blocks"][0]["id"] == block_id
    assert body["sections"][0]["blocks"][0]["type"] == "prose"
