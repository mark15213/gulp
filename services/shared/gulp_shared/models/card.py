"""Card — the atomic testable unit; S2 drafts cards (docs/02 §4.5, S2 design §4)."""

import enum
import uuid

from sqlalchemy import JSON, Enum, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column

from gulp_shared.db import Base, TimestampedBase


class CardType(str, enum.Enum):
    short_answer = "short_answer"
    mcq = "mcq"
    cloze = "cloze"
    explain = "explain"
    apply = "apply"
    recall = "recall"


class CardOrigin(str, enum.Enum):
    pack = "pack"  # inline generation (worker) — regeneration's replace scope
    conversation = "conversation"
    user = "user"
    imported = "imported"  # external cards.json (NotebookLM et al.)


class CardStatus(str, enum.Enum):
    draft = "draft"
    accepted = "accepted"
    rejected = "rejected"


class Card(TimestampedBase, Base):
    __tablename__ = "cards"

    source_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("sources.id"), default=None, index=True
    )
    card_type: Mapped[CardType] = mapped_column(Enum(CardType, name="card_type"))
    prompt: Mapped[str] = mapped_column(Text)
    answer: Mapped[str | None] = mapped_column(Text, default=None)
    explanation: Mapped[str | None] = mapped_column(Text, default=None)
    options: Mapped[list[str] | None] = mapped_column(JSON, default=None)
    origin: Mapped[CardOrigin] = mapped_column(Enum(CardOrigin, name="card_origin"))
    status: Mapped[CardStatus] = mapped_column(
        Enum(CardStatus, name="card_status"), default=CardStatus.draft
    )
    # Deferred: scheduling / mastery value objects — added by S5.
