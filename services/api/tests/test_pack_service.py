import uuid

from app.services.pack import pack_out
from gulp_shared.models.knowledge_pack import (
    KnowledgePack,
    PackBlock,
    PackBlockType,
    PackElement,
    PackElementType,
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
        snapshot_id=snapshot_id, summary="sum", background="bg",
        confidence=0.8, status=PackStatus.ready,
    )
    db.add(pack)
    db.flush()
    s0 = PackSection(pack_id=pack.id, heading="Overview", position=0)
    s1 = PackSection(pack_id=pack.id, heading="Details", position=1)
    db.add_all([s0, s1])
    db.flush()
    db.add(PackBlock(section_id=s0.id, block_type=PackBlockType.prose, content="b0",
                     anchor_id="s0b0", position=0))
    db.add(PackBlock(section_id=s0.id, block_type=PackBlockType.quote, content="b1",
                     anchor_id="s0b1", position=1))
    # PackElement.state defaults to `suggested`, so the seed omits it.
    db.add(PackElement(pack_id=pack.id, element_type=PackElementType.key_term, text="attention"))
    db.add(PackElement(pack_id=pack.id, element_type=PackElementType.claim, text="claim-x"))
    db.commit()


def test_pack_out_serializes_ordered_report_and_facets(db) -> None:
    snap = _snapshot(db)
    _seed_pack(db, snap.id)
    out = pack_out(db, snap.id)
    assert out is not None
    assert out.status == PackStatus.ready and out.summary == "sum" and out.confidence == 0.8
    assert [s.heading for s in out.sections] == ["Overview", "Details"]
    assert [b.anchor_id for b in out.sections[0].blocks] == ["s0b0", "s0b1"]
    assert out.sections[0].blocks[0].type == PackBlockType.prose
    assert {f.text for f in out.facets} == {"attention", "claim-x"}
    assert {f.element_type for f in out.facets} == {PackElementType.key_term, PackElementType.claim}


def test_pack_out_returns_none_when_no_pack(db) -> None:
    snap = _snapshot(db)
    db.commit()
    assert pack_out(db, snap.id) is None
