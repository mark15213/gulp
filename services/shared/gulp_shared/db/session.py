"""Sync engine + session factory (docs/05 §4; driver from settings)."""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from gulp_shared.settings import settings

engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
