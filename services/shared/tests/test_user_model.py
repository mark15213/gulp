import uuid

import pytest
from gulp_shared.db import Base
from gulp_shared.models.user import User
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


def _session():  # type: ignore[no-untyped-def]
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)()


def test_email_is_unique() -> None:
    s = _session()
    s.add(User(email="a@example.com", password_hash="x"))
    s.commit()
    s.add(User(email="a@example.com", password_hash="y"))
    with pytest.raises(IntegrityError):
        s.commit()


def test_bare_user_gets_defaults() -> None:
    # ~40 test sites construct User() without credentials — defaults keep them valid.
    s = _session()
    u = User(id=uuid.uuid4())
    s.add(u)
    s.commit()
    assert u.email is not None
    assert u.password_hash is not None
