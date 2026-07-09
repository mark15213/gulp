"""Serialize a snapshot's KnowledgePack into the PackOut contract."""

import uuid
from datetime import UTC, datetime
from typing import Any

from gulp_shared.models.knowledge_pack import KnowledgePack, PackBlock, PackBlockType, PackSection
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.schemas.pack import BlockCreate, BlockUpdate, PackOut, PackReferenceOut, PackSectionOut


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
        sections.append(
            # model_validate parses the raw block dicts into the typed union.
            PackSectionOut.model_validate(
                {"id": section.id, "heading": section.heading, "blocks": blocks}
            )
        )

    extras = pack.extras or {}
    return PackOut(
        snapshot_id=snapshot_id,
        status=pack.status,
        pack_type=pack.pack_type,
        title=pack.title,
        summary=pack.summary,
        core_contributions=list(extras.get("core_contributions") or []),
        key_insight=extras.get("key_insight"),
        sections=sections,
        references=[PackReferenceOut(**r) for r in (extras.get("references") or [])],
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
    block = load_block_scoped(db, snapshot_id, block_id)
    if update.content is not None:
        block.block_type = PackBlockType(update.content.type)
        block.data = update.content.model_dump(exclude={"type"}, mode="json")
    if update.position is not None:
        others = [b for b in live_blocks_ordered(db, block.section_id) if b.id != block.id]
        pos = max(0, min(update.position, len(others)))
        others.insert(pos, block)
        renumber(others)
    db.commit()
    db.refresh(block)
    return block_dict(block)


def load_section_scoped(db: Session, snapshot_id: uuid.UUID, section_id: uuid.UUID) -> PackSection:
    """Load a live section that belongs to the given snapshot's pack, or raise LookupError."""
    section = db.scalar(
        select(PackSection)
        .join(KnowledgePack, PackSection.pack_id == KnowledgePack.id)
        .where(
            PackSection.id == section_id,
            PackSection.deleted_at.is_(None),
            KnowledgePack.deleted_at.is_(None),
            KnowledgePack.snapshot_id == snapshot_id,
        )
    )
    if section is None:
        raise LookupError("section not found")
    return section


def create_block(
    db: Session, snapshot_id: uuid.UUID, section_id: uuid.UUID, create: BlockCreate
) -> dict[str, Any]:
    load_section_scoped(db, snapshot_id, section_id)
    block = PackBlock(
        section_id=section_id,
        block_type=PackBlockType(create.content.type),
        data=create.content.model_dump(exclude={"type"}, mode="json"),
        position=0,
    )
    db.add(block)
    db.flush()
    blocks = [b for b in live_blocks_ordered(db, section_id) if b.id != block.id]
    pos = max(0, min(create.position, len(blocks)))
    blocks.insert(pos, block)
    renumber(blocks)
    db.commit()
    db.refresh(block)
    return block_dict(block)
