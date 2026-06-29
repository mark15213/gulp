import uuid

from app.services.pack import pack_out
from gulp_shared.models.knowledge_pack import (
    KnowledgePack,
    PackBlock,
    PackBlockType,
    PackSection,
    PackStatus,
)
from gulp_shared.models.source import Source, SnapshotStatus, SourceKind
from gulp_shared.models.user import DEV_USER_ID


def _snapshot(db) -> Source:
    snap = Source(
        owner_id=DEV_USER_ID, kind=SourceKind.snapshot, title="T",
        status=SnapshotStatus.ready,
    )
    db.add(snap)
    db.flush()
    return snap


def _seed_pack(db, snapshot_id: uuid.UUID) -> None:
    pack = KnowledgePack(
        snapshot_id=snapshot_id, title="BERT", key_insight="ki",
        core_contributions=["c1", "c2"],
        references=[{"citation": "V2017", "why_interesting": "t"}],
        status=PackStatus.ready,
    )
    db.add(pack)
    db.flush()
    s0 = PackSection(pack_id=pack.id, heading="Overview", position=0)
    s1 = PackSection(pack_id=pack.id, heading="Details", position=1)
    db.add_all([s0, s1])
    db.flush()
    db.add(PackBlock(section_id=s0.id, block_type=PackBlockType.prose,
                     data={"content": "b0"}, position=0))
    db.add(PackBlock(section_id=s0.id, block_type=PackBlockType.formula,
                     data={"latex": "a=b", "explanation": "x"}, position=1))
    db.commit()


def test_pack_out_serializes_ordered_report(db) -> None:
    snap = _snapshot(db)
    _seed_pack(db, snap.id)
    out = pack_out(db, snap.id)
    assert out is not None
    assert out.status == PackStatus.ready and out.title == "BERT"
    assert out.core_contributions == ["c1", "c2"] and out.key_insight == "ki"
    assert [s.heading for s in out.sections] == ["Overview", "Details"]
    b0, b1 = out.sections[0].blocks
    assert b0.type == "prose" and b0.content == "b0"
    assert b1.type == "formula" and b1.latex == "a=b" and b1.explanation == "x"
    assert out.references[0].citation == "V2017"


def test_pack_out_returns_none_when_no_pack(db) -> None:
    snap = _snapshot(db)
    db.commit()
    assert pack_out(db, snap.id) is None
