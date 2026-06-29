from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.pipeline.persist import persist_pack
from app.pipeline.schemas import (
    FormulaBlock,
    PaperReport,
    ProseBlock,
    Reference,
    Section,
)
from gulp_shared.db import Base  # type: ignore[import-untyped]
import gulp_shared.models  # type: ignore[import-untyped]  # noqa: F401
from gulp_shared.models.knowledge_pack import (  # type: ignore[import-untyped]
    KnowledgePack,
    PackBlock,
    PackBlockType,
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


_REPORT = PaperReport(
    title="BERT",
    key_insight="ki",
    core_contributions=["c1", "c2"],
    sections=[Section(heading="H", blocks=[
        ProseBlock(content="b0"),
        FormulaBlock(latex="a=b", explanation="x"),
    ])],
    references=[Reference(citation="V2017", why_interesting="t")],
)


def test_persist_writes_report_fields_and_typed_blocks() -> None:
    s = _session()
    snap = _snapshot(s)
    pack = persist_pack(s, snap, _REPORT)
    s.commit()

    got = s.scalar(select(KnowledgePack).where(KnowledgePack.snapshot_id == snap.id))
    assert got is not None
    assert got.status == PackStatus.ready
    assert got.title == "BERT" and got.key_insight == "ki"
    assert got.core_contributions == ["c1", "c2"]
    assert got.references == [{"citation": "V2017", "why_interesting": "t"}]
    sections = list(s.scalars(select(PackSection).where(PackSection.pack_id == pack.id)))
    assert len(sections) == 1 and sections[0].heading == "H"
    blocks = sorted(
        s.scalars(select(PackBlock).where(PackBlock.section_id == sections[0].id)),
        key=lambda b: b.position,
    )
    assert [b.block_type for b in blocks] == [PackBlockType.prose, PackBlockType.formula]
    assert blocks[0].data == {"content": "b0"}
    assert blocks[1].data == {"latex": "a=b", "explanation": "x"}


def test_persist_is_idempotent_and_replaces() -> None:
    s = _session()
    snap = _snapshot(s)
    persist_pack(s, snap, _REPORT)
    s.commit()
    persist_pack(s, snap, _REPORT)  # second run
    s.commit()
    packs = list(s.scalars(select(KnowledgePack).where(KnowledgePack.snapshot_id == snap.id)))
    assert len(packs) == 1  # replaced, not duplicated
    blocks = list(s.scalars(select(PackBlock)))
    assert len(blocks) == 2  # not 4
