import gulp_shared.models  # noqa: F401  (registers tables)
from gulp_shared.db import Base
from gulp_shared.models.knowledge_pack import (
    KnowledgePack,
    PackBlock,
    PackBlockType,
    PackSection,
    PackStatus,
    PackType,
)
from gulp_shared.models.source import SnapshotStatus, Source, SourceKind
from gulp_shared.models.user import DEV_USER_ID, User
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker


def _session():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)()


def test_pack_stores_report_fields_and_typed_blocks():
    s = _session()
    s.add(User(id=DEV_USER_ID, display_name="Dev"))
    snap = Source(owner_id=DEV_USER_ID, kind=SourceKind.snapshot, title="Example",
                  status=SnapshotStatus.ready)
    s.add(snap)
    s.flush()

    pack = KnowledgePack(
        snapshot_id=snap.id,
        title="BERT",
        pack_type=PackType.paper,
        extras={
            "key_insight": "Change the objective, not the architecture.",
            "core_contributions": ["MLM enables bidirectionality."],
            "references": [{"citation": "Vaswani 2017", "why_interesting": "Transformer."}],
        },
        status=PackStatus.ready,
    )
    s.add(pack)
    s.flush()
    section = PackSection(pack_id=pack.id, heading="Mathematical Formulation", position=0)
    s.add(section)
    s.flush()
    s.add(PackBlock(section_id=section.id, block_type=PackBlockType.formula,
                    data={"latex": "a=b", "explanation": "trivial"}, position=0))
    s.commit()

    got = s.scalar(select(KnowledgePack).where(KnowledgePack.snapshot_id == snap.id))
    assert got is not None
    assert got.title == "BERT"
    assert got.extras["core_contributions"] == ["MLM enables bidirectionality."]
    assert got.extras["references"][0]["citation"] == "Vaswani 2017"
    blk = s.scalar(select(PackBlock))
    assert blk.block_type == PackBlockType.formula
    assert blk.data == {"latex": "a=b", "explanation": "trivial"}
