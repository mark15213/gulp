"""Persist stage: PackDraft -> KnowledgePack + section/block rows.

Idempotent: a re-run drops the snapshot's existing pack and rebuilds it, so
re-Start cleanly regenerates. source.status is the caller's responsibility.
"""

from gulp_shared.models.knowledge_pack import (
    KnowledgePack,
    PackBlock,
    PackBlockType,
    PackSection,
    PackStatus,
    PackType,
)
from gulp_shared.models.source import Source
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.pipeline.schemas import PackDraft


def _delete_existing(db: Session, snapshot_id: object) -> None:
    pack = db.scalar(select(KnowledgePack).where(KnowledgePack.snapshot_id == snapshot_id))
    if pack is None:
        return
    # cascade="all, delete-orphan" on KnowledgePack.sections -> PackSection.blocks
    # deletes children before the pack, so the flush can't hit the
    # pack_sections/pack_blocks foreign keys in the wrong order.
    db.delete(pack)
    db.flush()


def persist_pack(db: Session, source: Source, draft: PackDraft) -> KnowledgePack:
    _delete_existing(db, source.id)
    pack = KnowledgePack(
        snapshot_id=source.id,
        title=draft.title,
        summary=draft.summary,
        pack_type=PackType(draft.pack_type),
        extras=draft.extras,
        status=PackStatus.ready,
    )
    db.add(pack)
    db.flush()
    for i, section in enumerate(draft.sections):
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
