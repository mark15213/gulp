"""Persist stage: DigestResult -> KnowledgePack + report rows + facet rows.

Idempotent: a re-run drops the snapshot's existing pack and rebuilds it, so
re-Start cleanly regenerates. source.status is the caller's responsibility.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.pipeline.schemas import DigestResult
from gulp_shared.models.knowledge_pack import (  # type: ignore[import-untyped]
    KnowledgePack,
    PackBlock,
    PackBlockType,
    PackElement,
    PackElementState,
    PackElementType,
    PackSection,
    PackStatus,
)
from gulp_shared.models.source import Source  # type: ignore[import-untyped]


def _clamp(x: float) -> float:
    return max(0.0, min(1.0, x))


def _delete_existing(db: Session, snapshot_id: object) -> None:
    pack = db.scalar(select(KnowledgePack).where(KnowledgePack.snapshot_id == snapshot_id))
    if pack is None:
        return
    sections = list(db.scalars(select(PackSection).where(PackSection.pack_id == pack.id)))
    for section in sections:
        for block in db.scalars(select(PackBlock).where(PackBlock.section_id == section.id)):
            db.delete(block)
        db.delete(section)
    for element in db.scalars(select(PackElement).where(PackElement.pack_id == pack.id)):
        db.delete(element)
    db.delete(pack)
    db.flush()


def persist_pack(db: Session, source: Source, digest: DigestResult) -> KnowledgePack:
    _delete_existing(db, source.id)
    pack = KnowledgePack(
        snapshot_id=source.id,
        summary=digest.summary,
        background=digest.background,
        confidence=_clamp(digest.confidence),
        status=PackStatus.ready,
    )
    db.add(pack)
    db.flush()
    for i, section in enumerate(digest.sections):
        row = PackSection(pack_id=pack.id, heading=section.heading, position=i)
        db.add(row)
        db.flush()
        for j, block in enumerate(section.blocks):
            db.add(
                PackBlock(
                    section_id=row.id,
                    block_type=PackBlockType(block.type),
                    content=block.content,
                    source_anchor=None,
                    anchor_id=f"s{i}b{j}",
                    position=j,
                )
            )
    for facet in digest.facets:
        db.add(
            PackElement(
                pack_id=pack.id,
                element_type=PackElementType(facet.element_type),
                text=facet.text,
                state=PackElementState.suggested,
            )
        )
    db.flush()
    return pack
