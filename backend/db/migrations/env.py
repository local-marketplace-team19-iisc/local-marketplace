import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

from backend.app.core.config import settings
from backend.app.models.base import Base
import backend.app.models.models  # noqa: F401 — registers all 9 entities on Base.metadata

config = context.config
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def render_item(_type, obj, autogen_context):
    try:
        from pgvector.sqlalchemy import Vector
        if isinstance(obj, Vector):
            autogen_context.imports.add("from pgvector.sqlalchemy import Vector")
            return f"Vector({obj.dim})"
    except ImportError:
        pass

    try:
        from geoalchemy2 import Geography
        if isinstance(obj, Geography):
            autogen_context.imports.add("from geoalchemy2 import Geography")
            return f"Geography(geometry_type='{obj.geometry_type}', srid={obj.srid})"
    except ImportError:
        pass

    return False


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_item=render_item,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        render_item=render_item,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
