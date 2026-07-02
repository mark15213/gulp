"""Serialize a snapshot's KnowledgePack into the PackOut contract."""

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.schemas.pack import BlockCreate, BlockUpdate, PackOut, PackReferenceOut, PackSectionOut
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


def load_block_scoped(db: Session, snapshot_id: uuid.UUID, block_id: uuid.UUID) -> PackBlock:
    """Load a live block that belongs to the given snapshot's pack, or raise LookupError."""
    block = db.scalar(
        select(PackBlock)
        .join(PackSection, PackBlock.section_id == PackSection.id)
        .join(KnowledgePack, PackSection.pack_id == KnowledgePack.id)
        .where(
            PackBlock.id == block_id,
            PackBlock.deleted_at.is_(None),
            PackSection.deleted_at.is_(None),
            KnowledgePack.deleted_at.is_(None),
            KnowledgePack.snapshot_id == snapshot_id,
        )
    )
    if block is None:
        raise LookupError("block not found")
    return block


def delete_block(db: Session, snapshot_id: uuid.UUID, block_id: uuid.UUID) -> None:
    block = load_block_scoped(db, snapshot_id, block_id)
    section_id = block.section_id
    block.deleted_at = datetime.now(UTC)
    db.flush()
    renumber(live_blocks_ordered(db, section_id))
    db.commit()


def update_block(
    db: Session, snapshot_id: uuid.UUID, block_id: uuid.UUID, update: BlockUpdate
) -> dict[str, Any]:
    """Stub for Task 3 (PATCH block) — real signature, not yet implemented."""
    raise NotImplementedError


def create_block(
    db: Session, snapshot_id: uuid.UUID, section_id: uuid.UUID, create: BlockCreate
) -> dict[str, Any]:
    """Stub for Task 4 (POST create block) — real signature, not yet implemented."""
    raise NotImplementedError
