import pathlib
import sys

# Both gulp-api and gulp-worker expose a top-level `app`; put services/api first.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import gulp_shared.models  # noqa: F401
import pytest
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
