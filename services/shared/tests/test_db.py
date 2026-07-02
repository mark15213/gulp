import uuid
from datetime import datetime

from gulp_shared.db import Base, TimestampedBase
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column


class _Widget(TimestampedBase, Base):
    __tablename__ = "_widgets"
    name: Mapped[str] = mapped_column(String)


def test_timestamped_mixin_provides_implicit_fields():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()

    w = _Widget(name="x")
    session.add(w)
    session.commit()

    assert isinstance(w.id, uuid.UUID)
    assert isinstance(w.created_at, datetime)
    assert isinstance(w.updated_at, datetime)
    assert w.deleted_at is None
