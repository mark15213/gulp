import gulp_shared.models  # noqa: F401
from app.pipeline.persist import persist_pack
from app.pipeline.schemas import (
    FormulaBlock,
    PaperReport,
    ProseBlock,
    Reference,
    Section,
)
from gulp_shared.db import Base
from gulp_shared.models.knowledge_pack import (
    KnowledgePack,
    PackBlock,
    PackBlockType,
    PackSection,
    PackStatus,
)
from gulp_shared.models.source import (
    SnapshotStatus,
    Source,
    SourceKind,
)
from gulp_shared.models.user import DEV_USER_ID, User
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import sessionmaker


def _session():  # type: ignore[no-untyped-def]
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)()


def _fk_session():  # type: ignore[no-untyped-def]
    # SQLite ignores foreign keys unless PRAGMA foreign_keys=ON is set per
    # connection. Production is PostgreSQL, which always enforces them — so
    # without this the delete-ordering bug in _delete_existing is invisible
    # to tests but crashes on re-import in production.
    engine = create_engine("sqlite://")

    @event.listens_for(engine, "connect")
    def _enable_fk(dbapi_conn, _rec):  # type: ignore[no-untyped-def]
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

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


def test_persist_reimport_replaces_cleanly_under_fk_enforcement() -> None:
    # Reproduces the production import_result crash: re-importing a result when a
    # pack already exists must delete the old pack's children before the pack
    # itself, or the knowledge_packs -> pack_sections FK is violated. SQLite must
    # have FK enforcement on (like PostgreSQL) for this to be exercised.
    s = _fk_session()
    # Parents committed before children: User/Source have no relationship, so a
    # single-flush insert order isn't guaranteed under FK enforcement.
    s.add(User(id=DEV_USER_ID, display_name="Dev"))
    s.commit()
    snap = Source(
        owner_id=DEV_USER_ID, kind=SourceKind.snapshot, title="T",
        status=SnapshotStatus.processing,
    )
    s.add(snap)
    s.commit()

    persist_pack(s, snap, _REPORT)
    s.commit()
    persist_pack(s, snap, _REPORT)  # re-import must not raise a ForeignKeyViolation
    s.commit()

    packs = list(s.scalars(select(KnowledgePack).where(KnowledgePack.snapshot_id == snap.id)))
    assert len(packs) == 1
    assert len(list(s.scalars(select(PackSection)))) == 1
    assert len(list(s.scalars(select(PackBlock)))) == 2
