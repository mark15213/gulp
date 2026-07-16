"""AgentJob — queue truth for the MCP agent channel (spec 2026-07-16 §2)."""

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from gulp_shared.db import Base, TimestampedBase


class AgentJobKind(enum.StrEnum):
    digest = "digest"
    cards = "cards"


class AgentJobState(enum.StrEnum):
    """building → pending → leased → done | failed; failures during execution
    return to `pending` so the job resurfaces instead of silently dying."""

    building = "building"
    pending = "pending"
    leased = "leased"
    done = "done"
    failed = "failed"


class AgentJob(TimestampedBase, Base):
    __tablename__ = "agent_jobs"

    owner_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), index=True)
    snapshot_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("sources.id"), index=True)
    kind: Mapped[AgentJobKind] = mapped_column(Enum(AgentJobKind, name="agent_job_kind"))
    state: Mapped[AgentJobState] = mapped_column(
        Enum(AgentJobState, name="agent_job_state"), default=AgentJobState.building
    )
    lease_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str | None] = mapped_column(Text, default=None)
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
