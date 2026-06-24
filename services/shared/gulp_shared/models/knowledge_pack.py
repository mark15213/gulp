"""KnowledgePack — readable report + facet-annotations (docs/02 §4.4, S2 design §3)."""

import enum
import uuid
from typing import Any

from sqlalchemy import JSON, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from gulp_shared.db import Base, TimestampedBase


class PackStatus(str, enum.Enum):
    generating = "generating"
    ready = "ready"


class PackBlockType(str, enum.Enum):
    prose = "prose"
    figure = "figure"
    callout = "callout"
    quote = "quote"


class PackElementType(str, enum.Enum):
    key_term = "key_term"
    person_org = "person_org"
    claim = "claim"
    counter_view = "counter_view"
    connection = "connection"


class PackElementState(str, enum.Enum):
    suggested = "suggested"
    kept = "kept"
    dismissed = "dismissed"


class KnowledgePack(TimestampedBase, Base):
    __tablename__ = "knowledge_packs"

    snapshot_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sources.id"), unique=True, index=True
    )
    summary: Mapped[str] = mapped_column(Text)
    background: Mapped[str | None] = mapped_column(Text, default=None)
    confidence: Mapped[float | None] = mapped_column(Float, default=None)
    status: Mapped[PackStatus] = mapped_column(Enum(PackStatus, name="pack_status"))


class PackSection(TimestampedBase, Base):
    __tablename__ = "pack_sections"

    pack_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("knowledge_packs.id"), index=True)
    heading: Mapped[str | None] = mapped_column(String, default=None)
    position: Mapped[int] = mapped_column(Integer, default=0)


class PackBlock(TimestampedBase, Base):
    __tablename__ = "pack_blocks"

    section_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("pack_sections.id"), index=True)
    block_type: Mapped[PackBlockType] = mapped_column(Enum(PackBlockType, name="pack_block_type"))
    content: Mapped[str | None] = mapped_column(Text, default=None)
    content_ref: Mapped[str | None] = mapped_column(String, default=None)
    source_anchor: Mapped[dict[str, Any] | None] = mapped_column(JSON, default=None)
    anchor_id: Mapped[str] = mapped_column(String, index=True)
    position: Mapped[int] = mapped_column(Integer, default=0)


class PackElement(TimestampedBase, Base):
    __tablename__ = "pack_elements"

    pack_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("knowledge_packs.id"), index=True)
    element_type: Mapped[PackElementType] = mapped_column(
        Enum(PackElementType, name="pack_element_type")
    )
    text: Mapped[str | None] = mapped_column(Text, default=None)
    concept_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("concepts.id"), default=None, index=True
    )
    block_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("pack_blocks.id"), default=None
    )
    section_label: Mapped[str | None] = mapped_column(String, default=None)
    state: Mapped[PackElementState] = mapped_column(
        Enum(PackElementState, name="pack_element_state"),
        default=PackElementState.suggested,
    )
