"""Serialize a snapshot's KnowledgePack into the PackOut contract."""

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.schemas.pack import PackOut, PackReferenceOut, PackSectionOut
from gulp_shared.models.knowledge_pack import KnowledgePack, PackBlock, PackSection


def block_dict(b: PackBlock) -> dict[str, Any]:
    return {"id": b.id, "type": b.block_type.value, **(b.data or {})}


def live_blocks_ordered(db: Session, section_id: uuid.UUID) -> list[PackBlock]:
    return list(
        db.scalars(
            select(PackBlock)
            .where(PackBlock.section_id == section_id, PackBlock.deleted_at.is_(None))
            .order_by(PackBlock.position)
        )
    )


def renumber(blocks: list[PackBlock]) -> None:
    for i, b in enumerate(blocks):
        b.position = i


def pack_out(db: Session, snapshot_id: uuid.UUID) -> PackOut | None:
    pack = db.scalar(
        select(KnowledgePack).where(
            KnowledgePack.snapshot_id == snapshot_id,
            KnowledgePack.deleted_at.is_(None),
        )
    )
    if pack is None:
        return None

    sections: list[PackSectionOut] = []
    for section in db.scalars(
        select(PackSection)
        .where(PackSection.pack_id == pack.id, PackSection.deleted_at.is_(None))
        .order_by(PackSection.position)
    ):
        blocks = [block_dict(b) for b in live_blocks_ordered(db, section.id)]
        sections.append(PackSectionOut(id=section.id, heading=section.heading, blocks=blocks))

    return PackOut(
        snapshot_id=snapshot_id,
        status=pack.status,
        title=pack.title,
        core_contributions=list(pack.core_contributions or []),
        key_insight=pack.key_insight,
        sections=sections,
        references=[PackReferenceOut(**r) for r in (pack.references or [])],
    )
