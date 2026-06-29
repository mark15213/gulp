"""Persist stage: PaperReport -> KnowledgePack + section/block rows.

Idempotent: a re-run drops the snapshot's existing pack and rebuilds it, so
re-Start cleanly regenerates. source.status is the caller's responsibility.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.pipeline.schemas import PaperReport
from gulp_shared.models.knowledge_pack import (  # type: ignore[import-untyped]
    KnowledgePack,
    PackBlock,
    PackBlockType,
    PackSection,
    PackStatus,
)
from gulp_shared.models.source import Source  # type: ignore[import-untyped]


def _delete_existing(db: Session, snapshot_id: object) -> None:
    pack = db.scalar(select(KnowledgePack).where(KnowledgePack.snapshot_id == snapshot_id))
    if pack is None:
        return
    for section in db.scalars(select(PackSection).where(PackSection.pack_id == pack.id)):
        for block in db.scalars(select(PackBlock).where(PackBlock.section_id == section.id)):
            db.delete(block)
        db.delete(section)
    db.delete(pack)
    db.flush()


def persist_pack(db: Session, source: Source, report: PaperReport) -> KnowledgePack:
    _delete_existing(db, source.id)
    pack = KnowledgePack(
        snapshot_id=source.id,
        title=report.title,
        key_insight=report.key_insight,
        core_contributions=list(report.core_contributions),
        references=[r.model_dump() for r in report.references],
        status=PackStatus.ready,
    )
    db.add(pack)
    db.flush()
    for i, section in enumerate(report.sections):
        row = PackSection(pack_id=pack.id, heading=section.heading, position=i)
        db.add(row)
        db.flush()
        for j, block in enumerate(section.blocks):
            db.add(
                PackBlock(
                    section_id=row.id,
                    block_type=PackBlockType(block.type),
                    data=block.model_dump(exclude={"type"}),
                    position=j,
                )
            )
    db.flush()
    return pack
