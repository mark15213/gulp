import gulp_shared.models  # noqa: F401  (registers tables)
from gulp_shared.db import Base
from gulp_shared.models.concept import Concept, ConceptType
from gulp_shared.models.knowledge_pack import (
    KnowledgePack,
    PackBlock,
    PackBlockType,
    PackElement,
    PackElementState,
    PackElementType,
    PackSection,
    PackStatus,
)
from gulp_shared.models.source import SnapshotStatus, Source, SourceKind
from gulp_shared.models.user import DEV_USER_ID, User
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker


def _session():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)()


def test_pack_report_with_block_and_facet_annotation():
    s = _session()
    s.add(User(id=DEV_USER_ID, display_name="Dev"))
    snap = Source(
        owner_id=DEV_USER_ID,
        kind=SourceKind.snapshot,
        title="Example",
        status=SnapshotStatus.ready,
    )
    s.add(snap)
    s.flush()

    pack = KnowledgePack(
        snapshot_id=snap.id, summary="It says X.", confidence=0.8, status=PackStatus.ready
    )
    s.add(pack)
    s.flush()
    section = PackSection(pack_id=pack.id, heading="Overview", position=0)
    s.add(section)
    s.flush()
    block = PackBlock(
        section_id=section.id,
        block_type=PackBlockType.prose,
        content="Rewritten prose.",
        source_anchor={"kind": "char_range", "start": 0, "end": 42},
        anchor_id="b1",
        position=0,
    )
    s.add(block)
    concept = Concept(concept_type=ConceptType.term, name="X")
    s.add(concept)
    s.flush()
    s.add(
        PackElement(
            pack_id=pack.id,
            element_type=PackElementType.key_term,
            text="X — a thing",
            concept_id=concept.id,
            block_id=block.id,
        )
    )
    s.commit()

    got = s.scalar(select(KnowledgePack).where(KnowledgePack.snapshot_id == snap.id))
    assert got is not None and got.confidence == 0.8
    blk = s.scalar(select(PackBlock).where(PackBlock.anchor_id == "b1"))
    assert blk.source_anchor == {"kind": "char_range", "start": 0, "end": 42}
    el = s.scalar(select(PackElement))
    assert el.state == PackElementState.suggested  # default
    assert el.block_id == blk.id
