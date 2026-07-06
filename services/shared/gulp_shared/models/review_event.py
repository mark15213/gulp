"""ReviewEvent — the append-only source of truth for review history.
`Card.scheduling`/`Card.mastery` are a fold over these (S4 design §3.1, C2).
Never updated, never soft-deleted."""

import enum
import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column

from gulp_shared.db import Base, TimestampedBase


def _now() -> datetime:
    return datetime.now(UTC)


class ReviewGrade(enum.StrEnum):
    got_it = "got_it"
    fuzzy = "fuzzy"
    missed = "missed"


class ReviewEvent(TimestampedBase, Base):
    __tablename__ = "review_events"

    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("gulp_sessions.id"), index=True
    )
    card_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cards.id"), index=True)
    grade: Mapped[ReviewGrade] = mapped_column(Enum(ReviewGrade, name="review_grade"))
    response: Mapped[str | None] = mapped_column(Text, default=None)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
