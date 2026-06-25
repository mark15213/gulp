"""Serialize a snapshot's KnowledgePack into the PackOut contract."""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.schemas.pack import PackBlockOut, PackFacetOut, PackOut, PackSectionOut
from gulp_shared.models.knowledge_pack import (
    KnowledgePack,
    PackBlock,
    PackElement,
    PackSection,
)


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
        .where(PackSection.pack_id == pack.id)
        .order_by(PackSection.position)
    ):
        blocks = [
            PackBlockOut(type=b.block_type, content=b.content, anchor_id=b.anchor_id)
            for b in db.scalars(
                select(PackBlock)
                .where(PackBlock.section_id == section.id)
                .order_by(PackBlock.position)
            )
        ]
        sections.append(PackSectionOut(heading=section.heading, blocks=blocks))

    facets = [
        PackFacetOut(element_type=e.element_type, text=e.text)
        for e in db.scalars(select(PackElement).where(PackElement.pack_id == pack.id))
    ]

    return PackOut(
        snapshot_id=snapshot_id,
        status=pack.status,
        summary=pack.summary,
        background=pack.background,
        confidence=pack.confidence,
        sections=sections,
        facets=facets,
    )
