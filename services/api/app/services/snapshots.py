"""Serialize a Source (+ its tags) to the SnapshotOut contract; cascade-delete a snapshot."""

import uuid
from datetime import UTC, datetime

from gulp_shared.db import TimestampedBase
from gulp_shared.models.card import Card
from gulp_shared.models.concept import SourceConcept
from gulp_shared.models.knowledge_pack import KnowledgePack, PackBlock, PackSection
from gulp_shared.models.pack_block_message import PackBlockMessage
from gulp_shared.models.source import Source
from gulp_shared.models.source_figure import SourceFigure
from gulp_shared.models.source_tag import SourceTag
from sqlalchemy import ColumnElement, select, update
from sqlalchemy.orm import Session

from app.schemas.capture import SnapshotOut, SnapshotPatch, SourceFeedOut


def update_snapshot(db: Session, source: Source, patch: SnapshotPatch) -> Source:
    source.genre = patch.genre
    db.commit()
    db.refresh(source)
    return source


def _tags_for(db: Session, source_id: uuid.UUID) -> list[str]:
    return list(
        db.scalars(
            select(SourceTag.tag).where(
                SourceTag.source_id == source_id,
                SourceTag.deleted_at.is_(None),
            )
        )
    )


def add_tag(db: Session, source: Source, tag: str) -> Source:
    """Idempotent: no-op if a live row already exists for (source, tag)."""
    live = db.scalar(
        select(SourceTag.id).where(
            SourceTag.source_id == source.id,
            SourceTag.tag == tag,
            SourceTag.deleted_at.is_(None),
        )
    )
    if live is None:
        db.add(SourceTag(source_id=source.id, tag=tag))
        db.commit()
    return source


def remove_tag(db: Session, source: Source, tag: str) -> Source:
    """Soft-delete every live row for (source, tag). No-op if none match."""
    db.execute(
        update(SourceTag)
        .where(
            SourceTag.source_id == source.id,
            SourceTag.tag == tag,
            SourceTag.deleted_at.is_(None),
        )
        .values(deleted_at=datetime.now(UTC))
    )
    db.commit()
    return source


def delete_snapshot(db: Session, source: Source) -> None:
    """Cascade soft-delete: the snapshot + every derivative, in one transaction."""
    now = datetime.now(UTC)

    def _stamp(model: type[TimestampedBase], *conditions: ColumnElement[bool]) -> None:
        db.execute(
            update(model).where(*conditions, model.deleted_at.is_(None)).values(deleted_at=now)
        )

    # Resolve the pack tree top-down while its rows are still live.
    pack_ids = list(
        db.scalars(select(KnowledgePack.id).where(KnowledgePack.snapshot_id == source.id))
    )
    section_ids = (
        list(db.scalars(select(PackSection.id).where(PackSection.pack_id.in_(pack_ids))))
        if pack_ids
        else []
    )
    block_ids = (
        list(db.scalars(select(PackBlock.id).where(PackBlock.section_id.in_(section_ids))))
        if section_ids
        else []
    )

    if block_ids:
        _stamp(PackBlockMessage, PackBlockMessage.block_id.in_(block_ids))
        _stamp(PackBlock, PackBlock.id.in_(block_ids))
    if section_ids:
        _stamp(PackSection, PackSection.id.in_(section_ids))
    if pack_ids:
        _stamp(KnowledgePack, KnowledgePack.id.in_(pack_ids))

    _stamp(Card, Card.source_id == source.id)
    _stamp(SourceFigure, SourceFigure.source_id == source.id)
    _stamp(SourceTag, SourceTag.source_id == source.id)
    _stamp(SourceConcept, SourceConcept.source_id == source.id)

    source.deleted_at = now
    db.commit()


def _source_feed(
    db: Session,
    source: Source,
    feed_titles: dict[uuid.UUID, str] | None = None,
) -> SourceFeedOut | None:
    """The subscription that emitted this snapshot. Batch callers pass
    `feed_titles` (id -> title) to avoid an N+1; single-item callers fall back
    to a PK lookup."""
    if source.emitted_by is None:
        return None
    if feed_titles is not None:
        title = feed_titles.get(source.emitted_by)
        return SourceFeedOut(id=source.emitted_by, title=title) if title is not None else None
    sub = db.get(Source, source.emitted_by)
    return SourceFeedOut(id=sub.id, title=sub.title) if sub is not None else None


def to_out(
    db: Session,
    source: Source,
    feed_titles: dict[uuid.UUID, str] | None = None,
) -> SnapshotOut:
    return SnapshotOut(
        id=source.id,
        kind=source.kind,
        title=source.title,
        note=source.note,
        status=source.status,
        media_type=source.media_type,
        genre=source.genre,
        origin_url=source.origin_url,
        content_body=source.content_body,
        captured_via=source.captured_via,
        cards_status=source.cards_status,
        tags=_tags_for(db, source.id),
        source_feed=_source_feed(db, source, feed_titles),
        created_at=source.created_at,
        updated_at=source.updated_at,
    )
