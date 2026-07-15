"""DSN normalization: managed providers (Railway) inject a bare `postgresql://`
DSN, but SQLAlchemy needs the psycopg-3 driver prefix. The Settings validator
rewrites it; an already-prefixed or non-postgres DSN is left untouched."""

from gulp_shared.settings import Settings


def test_bare_postgresql_gets_psycopg_prefix() -> None:
    s = Settings(database_url="postgresql://u:p@host:5432/db")
    assert s.database_url == "postgresql+psycopg://u:p@host:5432/db"


def test_postgres_scheme_alias_gets_psycopg_prefix() -> None:
    s = Settings(database_url="postgres://u:p@host:5432/db")
    assert s.database_url == "postgresql+psycopg://u:p@host:5432/db"


def test_already_prefixed_dsn_unchanged() -> None:
    dsn = "postgresql+psycopg://u:p@host:5432/db"
    assert Settings(database_url=dsn).database_url == dsn


def test_non_postgres_dsn_unchanged() -> None:
    assert Settings(database_url="sqlite://").database_url == "sqlite://"
