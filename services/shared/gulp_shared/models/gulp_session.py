"""GulpSession — a daily practice run (docs/02 §4.10, S4 design §4.1).
Persisted + resumable; `planned_card_ids` freezes the composition for resume,
misses are re-queued live at the service layer (C6)."""

import enum
import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from gulp_shared.db import Base, TimestampedBase


class SessionScope(enum.StrEnum):
    daily = "daily"
    knowledge_base = "knowledge_base"  # parked (S3) — API returns 400 for now
    concept = "concept"  # parked (S3)
    free_explore = "free_explore"
    at_risk = "at_risk"


class SessionStatus(enum.StrEnum):
    building = "building"
    active = "active"
    complete = "complete"
    abandoned = "abandoned"


class GulpSession(TimestampedBase, Base):
    __tablename__ = "gulp_sessions"

    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    scope_type: Mapped[SessionScope] = mapped_column(
        Enum(SessionScope, name="session_scope"), default=SessionScope.daily
    )
    scope_ref: Mapped[uuid.UUID | None] = mapped_column(Uuid, default=None)
    target_minutes: Mapped[int] = mapped_column(default=5)
    planned_card_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    status: Mapped[SessionStatus] = mapped_column(
        Enum(SessionStatus, name="session_status"), default=SessionStatus.building
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
