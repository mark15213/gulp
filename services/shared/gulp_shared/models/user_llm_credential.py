"""UserLLMCredential — one encrypted BYOK API key per (user, provider)
(spec 2026-07-13 §4.1). The plaintext never leaves `gulp_shared.llm.crypto`."""

import uuid

from sqlalchemy import ForeignKey, LargeBinary, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from gulp_shared.db import Base, TimestampedBase


class UserLLMCredential(TimestampedBase, Base):
    __tablename__ = "user_llm_credentials"
    __table_args__ = (
        UniqueConstraint("user_id", "provider", name="uq_user_llm_credentials_user_provider"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    provider: Mapped[str] = mapped_column(String)
    api_key_encrypted: Mapped[bytes] = mapped_column(LargeBinary)
