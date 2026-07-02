import uuid

import pytest
from fastapi.testclient import TestClient

from app.deps import get_db
from app.main import app
from app.schemas.pack import BlockCreate, BlockUpdate, BlockWriteAdapter
from app.services.pack import block_dict, renumber
from gulp_shared.models.knowledge_pack import (
    KnowledgePack,
    PackBlock,
    PackBlockType,
    PackSection,
    PackStatus,
)
from gulp_shared.models.source import Source, SnapshotStatus, SourceKind
from gulp_shared.models.user import DEV_USER_ID


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
