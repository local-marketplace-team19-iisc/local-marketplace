from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from backend.app import models  # noqa: F401  registers models on Base.metadata
from backend.app.core.config import settings
from backend.app.db.session import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Use DATABASE_URL_DIRECT (sync psycopg, port 5432) for migrations when available,
# otherwise fall back to DATABASE_URL normalised to psycopg driver.
import os as _os

_raw_url = _os.environ.get("DATABASE_URL_DIRECT") or settings.DATABASE_URL_DIRECT or settings.DATABASE_URL
# Normalise asyncpg → psycopg so Alembic's sync engine can connect
_sync_url = (
    _raw_url
    .replace("postgresql+asyncpg://", "postgresql+psycopg://")
    .replace("?pgbouncer=true", "")
)
# configparser uses % for interpolation; escape any % in the URL (e.g. URL-encoded passwords)
config.set_main_option("sqlalchemy.url", _sync_url.replace("%", "%%"))

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


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


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
