"""User — the account (docs/02 §4.1). S1 fills only what `owner` needs."""

import enum
import uuid

from sqlalchemy import Enum, String
from sqlalchemy.orm import Mapped, mapped_column

from gulp_shared.db import Base, TimestampedBase

DEV_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


class Locale(enum.StrEnum):
    zh = "zh"
    en = "en"


class User(TimestampedBase, Base):
    __tablename__ = "users"

    # Identity/credentials (spec 2026-07-10). Defaults fire only for test/seed
    # rows — `register` always sets both explicitly; prod emails are all real.
    email: Mapped[str] = mapped_column(
        String, unique=True, index=True, default=lambda: f"user-{uuid.uuid4()}@example.invalid"
    )
    password_hash: Mapped[str] = mapped_column(String, default="")
    display_name: Mapped[str | None] = mapped_column(String, default=None)
    locale: Mapped[Locale] = mapped_column(Enum(Locale, name="locale"), default=Locale.en)
    gulp_session_minutes: Mapped[int] = mapped_column(default=5)
    # BYOK default model selection (spec 2026-07-13 §4.1); NULL = not configured.
    llm_provider: Mapped[str | None] = mapped_column(String, default=None)
    llm_model: Mapped[str | None] = mapped_column(String, default=None)
