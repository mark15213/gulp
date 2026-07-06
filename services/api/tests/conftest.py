import pathlib
import sys

# Both gulp-api and gulp-worker expose a top-level `app`; put services/api first.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import gulp_shared.models  # noqa: F401
import pytest
from app.deps import get_db, get_enqueue
from app.main import app
from fastapi.testclient import TestClient
from gulp_shared.db import Base
from gulp_shared.models.user import DEV_USER_ID, User
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    session.add(User(id=DEV_USER_ID, display_name="Dev"))
    session.commit()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def owner(db):  # type: ignore[no-untyped-def]
    return db.get(User, DEV_USER_ID)


@pytest.fixture
def client(db):  # type: ignore[no-untyped-def]
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_enqueue] = lambda: (lambda *a: None)
    c = TestClient(app)
    yield c
    app.dependency_overrides.clear()


@pytest.fixture
def make_accepted_card(db):  # type: ignore[no-untyped-def]
    """Factory: make_accepted_card(db, owner, **card_kw) -> accepted Card, schedule initialized."""
    from app.services.gulp import init_scheduling_on_accept
    from gulp_shared.models import (
        Card,
        CardOrigin,
        CardStatus,
        CardType,
        SnapshotStatus,
        Source,
        SourceKind,
    )

    def _make(db_, owner_, **kw):  # type: ignore[no-untyped-def]
        s = Source(
            owner_id=owner_.id, kind=SourceKind.snapshot, title="src",
            status=SnapshotStatus.ready,
        )
        db_.add(s)
        db_.flush()
        c = Card(
            source_id=s.id, card_type=CardType.flashcard, prompt="q",
            origin=CardOrigin.pack, status=CardStatus.accepted, **kw,
        )
        db_.add(c)
        db_.flush()
        init_scheduling_on_accept(c)
        db_.flush()
        return c

    return _make
