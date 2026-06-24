"""Tags as a join (docs/02 §2.3) so membership unions under sync, not LWW-clobbers."""

import uuid

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from gulp_shared.db import Base, TimestampedBase


class SourceTag(TimestampedBase, Base):
    __tablename__ = "source_tags"

    source_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sources.id"), index=True)
    tag: Mapped[str] = mapped_column(String)
