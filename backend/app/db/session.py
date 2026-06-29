import logging
import os
from collections.abc import AsyncGenerator
from urllib.parse import quote_plus

from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.pool import NullPool

from backend.app.core.config import settings

logger = logging.getLogger(__name__)

_on_vercel = os.environ.get("VERCEL") == "1"


def _strip_pgbouncer(url: str) -> str:
    """Remove ?pgbouncer=true / &pgbouncer=true — neither asyncpg nor psycopg accepts it."""
    return url.replace("?pgbouncer=true", "").replace("&pgbouncer=true", "")


def _asyncpg_to_psycopg(url: str) -> str:
    return url.replace("postgresql+asyncpg://", "postgresql+psycopg://")


def _sync_url(url: str) -> str:
    return _asyncpg_to_psycopg(_strip_pgbouncer(url))


def _async_url(url: str) -> str:
    return _strip_pgbouncer(url)


# ---------------------------------------------------------------------------
# Sync engine — used by SessionLocal (auth routes, sync ORM calls)
# ---------------------------------------------------------------------------
_raw_db_url = settings.DATABASE_URL
if not _raw_db_url.startswith("postgresql"):
    raise RuntimeError(
        f"DATABASE_URL must be a PostgreSQL URL (got: {_raw_db_url[:30]!r}). "
        "Set DATABASE_URL=postgresql+asyncpg://... in your environment."
    )

_sync_db_url = _sync_url(_raw_db_url)

_engine_kwargs: dict = {
    "pool_pre_ping": True,
    "connect_args": {"connect_timeout": 15},
}
if _on_vercel:
    _engine_kwargs["poolclass"] = NullPool

engine = create_engine(_sync_db_url, **_engine_kwargs)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# ---------------------------------------------------------------------------
# Async engine — used by get_db() (most API routes)
# ---------------------------------------------------------------------------
_async_db_url = _async_url(_raw_db_url)

_async_engine_kwargs: dict = {"echo": False}
if _on_vercel:
    _async_engine_kwargs["poolclass"] = NullPool
    _async_engine_kwargs["connect_args"] = {"command_timeout": 15}

async_engine = create_async_engine(_async_db_url, **_async_engine_kwargs)
AsyncSessionLocal = async_sessionmaker(
    async_engine, class_=AsyncSession, expire_on_commit=False
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session
