"""KnowledgePack — a structured paper report (docs/02 §4.4, S2 design §3)."""

import enum
import uuid
from typing import Any

from sqlalchemy import JSON, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from gulp_shared.db import Base, TimestampedBase


class PackStatus(str, enum.Enum):
    generating = "generating"
    ready = "ready"


class PackBlockType(str, enum.Enum):
    prose = "prose"
    formula = "formula"
    table = "table"
    figure = "figure"
    list = "list"


class KnowledgePack(TimestampedBase, Base):
    __tablename__ = "knowledge_packs"

    snapshot_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sources.id"), unique=True, index=True
    )
    title: Mapped[str] = mapped_column(Text)
    key_insight: Mapped[str] = mapped_column(Text)
    core_contributions: Mapped[list[str]] = mapped_column(JSON, default=list)
    references: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
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
    data: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    position: Mapped[int] = mapped_column(Integer, default=0)
