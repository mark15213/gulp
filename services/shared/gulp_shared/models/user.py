"""User — the account (docs/02 §4.1). S1 fills only what `owner` needs."""

import enum
import uuid

from sqlalchemy import Enum, String
from sqlalchemy.orm import Mapped, mapped_column

from gulp_shared.db import Base, TimestampedBase

DEV_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


class Locale(str, enum.Enum):
    zh = "zh"
    en = "en"


class User(TimestampedBase, Base):
    __tablename__ = "users"

    display_name: Mapped[str | None] = mapped_column(String, default=None)
    locale: Mapped[Locale] = mapped_column(Enum(Locale, name="locale"), default=Locale.en)
