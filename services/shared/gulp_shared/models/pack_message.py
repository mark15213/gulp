"""PackMessage — one turn of a snapshot-scoped (article) chat thread; a user
turn may attach block ids in `block_refs` (spec 2026-07-10 reader redesign)."""

import enum
import uuid
from typing import Any

from sqlalchemy import JSON, Enum, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column

from gulp_shared.db import Base, TimestampedBase


class ChatRole(enum.StrEnum):
    user = "user"
    assistant = "assistant"


class PackMessage(TimestampedBase, Base):
    __tablename__ = "pack_messages"

    snapshot_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sources.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[ChatRole] = mapped_column(Enum(ChatRole, name="chat_role"))
    content: Mapped[str] = mapped_column(Text)
    # block ids (as strings) the user attached to this turn; empty otherwise.
    block_refs: Mapped[list[Any]] = mapped_column(JSON, default=list)
