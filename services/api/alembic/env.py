import gulp_shared.models  # noqa: F401  (registers all tables on Base.metadata)
from alembic import context
from gulp_shared.db import Base
from gulp_shared.settings import settings
from sqlalchemy import engine_from_config, pool

config = context.config
config.set_main_option("sqlalchemy.url", settings.database_url)
target_metadata = Base.metadata


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


run_migrations_online()
