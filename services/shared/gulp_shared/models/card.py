"""Card — the atomic testable unit; S2 drafts cards (docs/02 §4.5, S2 design §4)."""

import enum
import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, Enum, Float, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column

from gulp_shared.db import Base, TimestampedBase


class CardType(enum.StrEnum):
    # type = review-interaction contract (docs/03 review UI, deferred to S5):
    # flashcard — front → flip → self-grade; the home for free-recall cards.
    # mcq — pick one option, auto-graded. cloze — fill a ____ blank.
    flashcard = "flashcard"
    mcq = "mcq"
    cloze = "cloze"


class CardOrigin(enum.StrEnum):
    pack = "pack"  # inline generation (worker) — regeneration's replace scope
    conversation = "conversation"
    user = "user"
    imported = "imported"  # external cards.json (NotebookLM et al.)


class CardStatus(enum.StrEnum):
    draft = "draft"
    accepted = "accepted"
    rejected = "rejected"


class MasteryLadder(enum.StrEnum):
    # 7-rung ladder (docs/02 §5.1). S4 enters cards at `read` on accept and
    # practice-advances the upper rungs; `unread`/`summarized` are reserved
    # for future reading subsystems (S3). `daily`/`due`/`at_risk` derive from
    # this + scheduling and are NEVER stored (S4 design §3.3, C4).
    unread = "unread"
    read = "read"
    summarized = "summarized"
    can_recall = "can_recall"
    can_distinguish = "can_distinguish"
    can_apply = "can_apply"
    mastered = "mastered"


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
    # ── Scheduling fold (SM-2-lite; S4 design §3.2) — a recompute over the
    # card's ReviewEvents, persisted so next_review_at is indexable. Null
    # until status=accepted (docs/02 §9 invariant). ──
    interval_days: Mapped[float] = mapped_column(Float, default=0.0)
    ease: Mapped[float] = mapped_column(Float, default=2.3)
    next_review_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None, index=True
    )
    last_reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    reps: Mapped[int] = mapped_column(default=0)
    lapses: Mapped[int] = mapped_column(default=0)
    stability: Mapped[float | None] = mapped_column(Float, default=None)  # FSRS-reserved
    difficulty: Mapped[float | None] = mapped_column(Float, default=None)  # FSRS-reserved
    ladder: Mapped[MasteryLadder | None] = mapped_column(
        Enum(MasteryLadder, name="mastery_ladder"), default=None
    )
    mastery_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
