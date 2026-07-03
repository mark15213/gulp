import uuid

import pytest
from app.deps import get_db
from app.main import app
from app.schemas.pack import BlockCreate, BlockUpdate, BlockWriteAdapter
from app.services.pack import block_dict, renumber
from fastapi.testclient import TestClient
from gulp_shared.models.knowledge_pack import (
    KnowledgePack,
    PackBlock,
    PackBlockType,
    PackSection,
    PackStatus,
)
from gulp_shared.models.source import SnapshotStatus, Source, SourceKind
from gulp_shared.models.source_figure import SourceFigure
from gulp_shared.models.user import DEV_USER_ID
from sqlalchemy import select


@pytest.fixture
def client(db):  # type: ignore[no-untyped-def]
    app.dependency_overrides[get_db] = lambda: db
    c = TestClient(app)
    yield c
    app.dependency_overrides.clear()


def _pack_with_blocks(db):  # type: ignore[no-untyped-def]
    """snapshot -> pack -> one section with two prose blocks (b0,b1). Returns ids."""
    snap = Source(owner_id=DEV_USER_ID, kind=SourceKind.snapshot, title="T",
                  status=SnapshotStatus.ready)
    db.add(snap)
    db.flush()
    pack = KnowledgePack(snapshot_id=snap.id, title="T", key_insight="ki",
                         core_contributions=[], references=[], status=PackStatus.ready)
    db.add(pack)
    db.flush()
    sec = PackSection(pack_id=pack.id, heading="H", position=0)
    db.add(sec)
    db.flush()
    b0 = PackBlock(section_id=sec.id, block_type=PackBlockType.prose,
                   data={"content": "b0"}, position=0)
    b1 = PackBlock(section_id=sec.id, block_type=PackBlockType.prose,
                   data={"content": "b1"}, position=1)
    db.add_all([b0, b1])
    db.commit()
    return {"snap": snap.id, "sec": sec.id, "b0": b0.id, "b1": b1.id}


def _figure_block(db):  # type: ignore[no-untyped-def]
    """snapshot -> pack -> section -> one figure block, plus a SourceFigure on the snapshot."""
    snap = Source(owner_id=DEV_USER_ID, kind=SourceKind.snapshot, title="T",
                  status=SnapshotStatus.ready)
    db.add(snap)
    db.flush()
    pack = KnowledgePack(snapshot_id=snap.id, title="T", key_insight="ki",
                         core_contributions=[], references=[], status=PackStatus.ready)
    db.add(pack)
    db.flush()
    sec = PackSection(pack_id=pack.id, heading="H", position=0)
    db.add(sec)
    db.flush()
    block = PackBlock(section_id=sec.id, block_type=PackBlockType.figure,
                      data={"label": "F1", "explanation": "e"}, position=0)
    db.add(block)
    fig = SourceFigure(source_id=snap.id, ext="png", mime_type="image/png")
    db.add(fig)
    db.commit()
    return {"snap": snap.id, "block": block.id, "figure_id": fig.id}


def test_update_figure_block_stores_figure_id(db) -> None:  # type: ignore[no-untyped-def]
    from app.services.pack import update_block
    ids = _figure_block(db)
    out = update_block(db, ids["snap"], ids["block"], BlockUpdate.model_validate(
        {"content": {"type": "figure", "label": "F1", "explanation": "e",
                     "figure_id": str(ids["figure_id"])}}))
    assert str(out["figure_id"]) == str(ids["figure_id"])


def test_figure_id_round_trips_through_pack_out(db) -> None:  # type: ignore[no-untyped-def]
    """After update, the read path serializes figure_id back through FigureBlockOut."""
    from app.services.pack import pack_out, update_block
    ids = _figure_block(db)
    update_block(db, ids["snap"], ids["block"], BlockUpdate.model_validate(
        {"content": {"type": "figure", "label": "F1", "explanation": "e",
                     "figure_id": str(ids["figure_id"])}}))
    pack = pack_out(db, ids["snap"])
    assert pack is not None
    fig_block = pack.sections[0].blocks[0]
    assert fig_block.type == "figure"
    assert str(fig_block.figure_id) == str(ids["figure_id"])


def test_figure_block_without_figure_id_defaults_to_none(db) -> None:  # type: ignore[no-untyped-def]
    """A figure block that never set figure_id reads back as None (optional field)."""
    from app.services.pack import pack_out
    ids = _figure_block(db)  # helper builds the block with no figure_id in data
    pack = pack_out(db, ids["snap"])
    assert pack is not None
    fig_block = pack.sections[0].blocks[0]
    assert fig_block.type == "figure"
    assert fig_block.figure_id is None


def test_block_dict_shape(db) -> None:  # type: ignore[no-untyped-def]
    b = PackBlock(section_id=uuid.uuid4(), block_type=PackBlockType.prose,
                  data={"content": "x"}, position=0)
    b.id = uuid.uuid4()
    d = block_dict(b)
    assert d == {"id": b.id, "type": "prose", "content": "x"}


def test_renumber_makes_positions_dense() -> None:
    blocks = [
        PackBlock(section_id=uuid.uuid4(), block_type=PackBlockType.prose, data={}, position=5),
        PackBlock(section_id=uuid.uuid4(), block_type=PackBlockType.prose, data={}, position=9),
        PackBlock(section_id=uuid.uuid4(), block_type=PackBlockType.prose, data={}, position=2),
    ]
    renumber(blocks)
    assert [b.position for b in blocks] == [0, 1, 2]


def test_write_union_discriminates_and_drops_type() -> None:
    w = BlockWriteAdapter.validate_python({"type": "table", "headers": ["a"], "rows": [["1"]]})
    assert w.type == "table"
    assert w.model_dump(exclude={"type"}) == {"headers": ["a"], "rows": [["1"]], "caption": None}


def test_block_update_and_create_optional_fields() -> None:
    u = BlockUpdate(position=3)
    assert u.content is None and u.position == 3
    c = BlockCreate(content={"type": "prose", "content": "hi"}, position=0)
    assert c.content.type == "prose" and c.position == 0


def test_delete_block_soft_deletes_and_renumbers(client, db) -> None:  # type: ignore[no-untyped-def]
    ids = _pack_with_blocks(db)
    r = client.delete(f"/snapshots/{ids['snap']}/blocks/{ids['b0']}")
    assert r.status_code == 204
    # gone from the read contract, and the survivor is renumbered to position 0
    body = client.get(f"/snapshots/{ids['snap']}/pack").json()
    blocks = body["sections"][0]["blocks"]
    assert [b["id"] for b in blocks] == [str(ids["b1"])]
    survivor = db.scalar(
        select(PackBlock).where(PackBlock.id == ids["b1"], PackBlock.deleted_at.is_(None))
    )
    assert survivor is not None and survivor.position == 0


def test_delete_block_404_for_foreign_snapshot(client, db) -> None:  # type: ignore[no-untyped-def]
    foreign = Source(owner_id=uuid.uuid4(), kind=SourceKind.snapshot, title="F",
                     status=SnapshotStatus.ready)
    db.add(foreign)
    db.commit()
    r = client.delete(f"/snapshots/{foreign.id}/blocks/{uuid.uuid4()}")
    assert r.status_code == 404


def test_delete_block_404_when_block_not_in_snapshot(client, db) -> None:  # type: ignore[no-untyped-def]
    ids = _pack_with_blocks(db)
    r = client.delete(f"/snapshots/{ids['snap']}/blocks/{uuid.uuid4()}")
    assert r.status_code == 404


def test_delete_block_404_for_block_in_another_snapshot(client, db) -> None:  # type: ignore[no-untyped-def]
    a = _pack_with_blocks(db)
    b = _pack_with_blocks(db)  # a second owned snapshot + pack + blocks
    r = client.delete(f"/snapshots/{a['snap']}/blocks/{b['b0']}")
    assert r.status_code == 404
    # b's block is untouched
    body = client.get(f"/snapshots/{b['snap']}/pack").json()
    assert any(bl["id"] == str(b["b0"]) for bl in body["sections"][0]["blocks"])


def test_update_block_content(client, db) -> None:  # type: ignore[no-untyped-def]
    ids = _pack_with_blocks(db)
    r = client.patch(
        f"/snapshots/{ids['snap']}/blocks/{ids['b0']}",
        json={"content": {"type": "prose", "content": "edited"}},
    )
    assert r.status_code == 200
    assert r.json() == {"id": str(ids["b0"]), "type": "prose", "content": "edited"}
    body = client.get(f"/snapshots/{ids['snap']}/pack").json()
    assert body["sections"][0]["blocks"][0]["content"] == "edited"


def test_update_block_changes_type(client, db) -> None:  # type: ignore[no-untyped-def]
    ids = _pack_with_blocks(db)
    r = client.patch(
        f"/snapshots/{ids['snap']}/blocks/{ids['b0']}",
        json={"content": {"type": "list", "items": ["x", "y"], "ordered": True}},
    )
    assert r.status_code == 200
    assert r.json() == {"id": str(ids["b0"]), "type": "list", "items": ["x", "y"], "ordered": True}


def test_update_block_position_reorders(client, db) -> None:  # type: ignore[no-untyped-def]
    ids = _pack_with_blocks(db)  # b0@0, b1@1
    r = client.patch(f"/snapshots/{ids['snap']}/blocks/{ids['b0']}", json={"position": 1})
    assert r.status_code == 200
    body = client.get(f"/snapshots/{ids['snap']}/pack").json()
    assert [b["id"] for b in body["sections"][0]["blocks"]] == [str(ids["b1"]), str(ids["b0"])]


def test_update_block_404_when_not_in_snapshot(client, db) -> None:  # type: ignore[no-untyped-def]
    ids = _pack_with_blocks(db)
    r = client.patch(f"/snapshots/{ids['snap']}/blocks/{uuid.uuid4()}", json={"position": 0})
    assert r.status_code == 404


def test_create_block_inserts_at_position(client, db) -> None:  # type: ignore[no-untyped-def]
    ids = _pack_with_blocks(db)  # b0@0, b1@1
    r = client.post(
        f"/snapshots/{ids['snap']}/sections/{ids['sec']}/blocks",
        json={"content": {"type": "prose", "content": "mid"}, "position": 1},
    )
    assert r.status_code == 201
    new_id = r.json()["id"]
    assert r.json()["content"] == "mid"
    body = client.get(f"/snapshots/{ids['snap']}/pack").json()
    order = [b["id"] for b in body["sections"][0]["blocks"]]
    assert order == [str(ids["b0"]), new_id, str(ids["b1"])]


def test_create_block_position_clamped_to_end(client, db) -> None:  # type: ignore[no-untyped-def]
    ids = _pack_with_blocks(db)
    r = client.post(
        f"/snapshots/{ids['snap']}/sections/{ids['sec']}/blocks",
        json={"content": {"type": "figure", "label": "F1", "explanation": "e"}, "position": 99},
    )
    assert r.status_code == 201
    body = client.get(f"/snapshots/{ids['snap']}/pack").json()
    assert body["sections"][0]["blocks"][-1]["id"] == r.json()["id"]


def test_create_block_404_when_section_not_in_snapshot(client, db) -> None:  # type: ignore[no-untyped-def]
    ids = _pack_with_blocks(db)
    r = client.post(
        f"/snapshots/{ids['snap']}/sections/{uuid.uuid4()}/blocks",
        json={"content": {"type": "prose", "content": "x"}, "position": 0},
    )
    assert r.status_code == 404


def test_create_block_404_for_section_in_another_snapshot(client, db) -> None:  # type: ignore[no-untyped-def]
    a = _pack_with_blocks(db)
    b = _pack_with_blocks(db)  # a second owned snapshot + pack + section
    r = client.post(
        f"/snapshots/{a['snap']}/sections/{b['sec']}/blocks",
        json={"content": {"type": "prose", "content": "x"}, "position": 0},
    )
    assert r.status_code == 404
