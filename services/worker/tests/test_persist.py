from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.pipeline.persist import persist_pack
from app.pipeline.schemas import DigestBlock, DigestFacet, DigestResult, DigestSection
from gulp_shared.db import Base  # type: ignore[import-untyped]
import gulp_shared.models  # type: ignore[import-untyped]  # noqa: F401
from gulp_shared.models.knowledge_pack import (  # type: ignore[import-untyped]
    KnowledgePack,
    PackBlock,
    PackElement,
    PackElementState,
    PackSection,
    PackStatus,
)
from gulp_shared.models.source import Source, SnapshotStatus, SourceKind  # type: ignore[import-untyped]
from gulp_shared.models.user import DEV_USER_ID, User  # type: ignore[import-untyped]


def _session():  # type: ignore[no-untyped-def]
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)()


def _snapshot(s):  # type: ignore[no-untyped-def]
    s.add(User(id=DEV_USER_ID, display_name="Dev"))
    snap = Source(
        owner_id=DEV_USER_ID, kind=SourceKind.snapshot, title="T",
        status=SnapshotStatus.processing,
    )
    s.add(snap)
    s.flush()
    return snap


_DIGEST = DigestResult(
    summary="sum", background="bg", confidence=1.5,  # out of range on purpose
    sections=[DigestSection(heading="H", blocks=[
        DigestBlock(type="prose", content="b0"), DigestBlock(type="quote", content="b1")])],
    facets=[DigestFacet(element_type="key_term", text="term"),
            DigestFacet(element_type="claim", text="claim-x")],
)


def test_persist_writes_report_and_facets_with_clamped_confidence() -> None:
    s = _session()
    snap = _snapshot(s)
    pack = persist_pack(s, snap, _DIGEST)
    s.commit()

    got = s.scalar(select(KnowledgePack).where(KnowledgePack.snapshot_id == snap.id))
    assert got is not None
    assert got.status == PackStatus.ready
    assert got.confidence == 1.0  # clamped
    sections = list(s.scalars(select(PackSection).where(PackSection.pack_id == pack.id)))
    assert len(sections) == 1 and sections[0].heading == "H"
    blocks = list(s.scalars(select(PackBlock).where(PackBlock.section_id == sections[0].id)))
    assert [b.anchor_id for b in sorted(blocks, key=lambda b: b.position)] == ["s0b0", "s0b1"]
    facets = list(s.scalars(select(PackElement).where(PackElement.pack_id == pack.id)))
    assert {f.text for f in facets} == {"term", "claim-x"}
    assert all(f.state == PackElementState.suggested for f in facets)
    assert all(f.concept_id is None and f.block_id is None for f in facets)


def test_persist_is_idempotent_and_replaces() -> None:
    s = _session()
    snap = _snapshot(s)
    persist_pack(s, snap, _DIGEST)
    s.commit()
    persist_pack(s, snap, _DIGEST)  # second run
    s.commit()
    packs = list(s.scalars(select(KnowledgePack).where(KnowledgePack.snapshot_id == snap.id)))
    assert len(packs) == 1  # replaced, not duplicated
    blocks = list(s.scalars(select(PackBlock)))
    assert len(blocks) == 2  # not 4
