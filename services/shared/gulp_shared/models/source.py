"""Source — single table + `kind` discriminator (docs/02 D1). S1 writes snapshots."""

import enum
import uuid

from sqlalchemy import Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from gulp_shared.db import Base, TimestampedBase


class SourceKind(enum.StrEnum):
    snapshot = "snapshot"
    conversation = "conversation"
    subscription = "subscription"


class SnapshotStatus(enum.StrEnum):
    """Single-gate lifecycle: `ready` IS "in the library" — the snapshot-level
    review gate is parked (spec 2026-07-02-single-gate-lifecycle-design.md)."""

    queued = "queued"
    unprocessed = "unprocessed"
    processing = "processing"
    ready = "ready"
    exported = "exported"
    needs_attention = "needs_attention"


class MediaType(enum.StrEnum):
    article = "article"
    pdf = "pdf"
    video = "video"
    podcast = "podcast"
    note = "note"
    screenshot = "screenshot"
    audio = "audio"
    webpage = "webpage"


class CardsStatus(enum.StrEnum):
    """Inline card-generation job state; null = never triggered. Imports don't touch it."""

    generating = "generating"
    ready = "ready"
    failed = "failed"


class CapturedVia(enum.StrEnum):
    share_sheet = "share_sheet"
    wechat = "wechat"
    email = "email"
    in_app = "in_app"
    paste = "paste"
    manual = "manual"
    screenshot = "screenshot"
    audio_memo = "audio_memo"


class Source(TimestampedBase, Base):
    __tablename__ = "sources"

    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    kind: Mapped[SourceKind] = mapped_column(Enum(SourceKind, name="source_kind"), index=True)
    title: Mapped[str] = mapped_column(String)
    note: Mapped[str | None] = mapped_column(Text, default=None)
    status: Mapped[SnapshotStatus] = mapped_column(
        Enum(SnapshotStatus, name="snapshot_status"), index=True
    )
    # snapshot-specific (docs/02 §4.3); nullable for other kinds.
    media_type: Mapped[MediaType | None] = mapped_column(
        Enum(MediaType, name="media_type"), default=None
    )
    origin_url: Mapped[str | None] = mapped_column(String, default=None, index=True)
    content_body: Mapped[str | None] = mapped_column(Text, default=None)
    content_ref: Mapped[str | None] = mapped_column(String, default=None)
    captured_via: Mapped[CapturedVia | None] = mapped_column(
        Enum(CapturedVia, name="captured_via"), default=None
    )
    cards_status: Mapped[CardsStatus | None] = mapped_column(
        Enum(CardsStatus, name="cards_status"), default=None
    )
    # 1–1 KnowledgePack is modeled from KnowledgePack.snapshot_id (S2). Deferred: emitted_by (S7).
