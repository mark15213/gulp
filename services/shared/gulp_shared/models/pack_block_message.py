"""PackBlockMessage — one turn of a per-block chat thread (S2 design §3.3/§3.4, S6 anchor)."""

import enum
import uuid

from sqlalchemy import Enum, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column

from gulp_shared.db import Base, TimestampedBase


class ChatRole(str, enum.Enum):
    user = "user"
    assistant = "assistant"


class PackBlockMessage(TimestampedBase, Base):
    __tablename__ = "pack_block_messages"

    block_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("pack_blocks.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[ChatRole] = mapped_column(Enum(ChatRole, name="chat_role"))
    content: Mapped[str] = mapped_column(Text)
