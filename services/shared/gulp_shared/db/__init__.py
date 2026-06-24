"""ORM base and session factory, shared by api + worker."""

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from gulp_shared.settings import settings


class Base(DeclarativeBase):
    """Base for all ORM models (the docs/02 entities)."""


engine = create_engine(settings.database_url, future=True)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
