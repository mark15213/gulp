"""FeedEntry — lightweight, prunable feed items (spec 2026-07-09 §1.4).
Browsed on Feeds; an explicit gulp promotes one to a Source(snapshot)."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from gulp_shared.db import Base, TimestampedBase


class FeedEntry(TimestampedBase, Base):
    __tablename__ = "feed_entries"
    __table_args__ = (
        UniqueConstraint("subscription_id", "guid", name="uq_feed_entries_sub_guid"),
    )

    subscription_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sources.id", ondelete="CASCADE"), index=True
    )
    guid: Mapped[str] = mapped_column(String(512))
    title: Mapped[str] = mapped_column(String)
    url: Mapped[str | None] = mapped_column(String, default=None)
    author: Mapped[str | None] = mapped_column(String, default=None)
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    content_html: Mapped[str | None] = mapped_column(Text, default=None)
    read_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    promoted_source_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("sources.id", ondelete="SET NULL"), default=None
    )
