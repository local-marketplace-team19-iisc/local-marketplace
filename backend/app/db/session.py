import os
from collections.abc import AsyncGenerator
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.pool import NullPool

from backend.app.core.config import settings

_on_vercel = os.environ.get("VERCEL") == "1"

# Resolve the local SQLite file to the marketplace **project root** rather
# than the process's `cwd`. `sqlite:///./local_marketplace.db` (the legacy
# URL) silently created a different file every time uvicorn was launched
# from a deeper directory, which then collided with file-locks held by
# stale processes — surfacing as `OperationalError: attempt to write a
# readonly database`. Anchoring to the package root means there is exactly
# one DB on disk no matter where the server is started from.
_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_LOCAL_SQLITE_PATH = _PROJECT_ROOT / "local_marketplace.db"
LOCAL_AUTH_DATABASE_URL = f"sqlite:///{_LOCAL_SQLITE_PATH}"


def _normalize_sqlite_url(url: str) -> str:
    """Rewrite a cwd-relative `sqlite:///./foo.db` (or bare-relative
    `sqlite:///foo.db`) URL to an absolute path anchored at the marketplace
    project root. Postgres URLs, absolute SQLite URLs (`sqlite:////abs`)
    and special forms (`:memory:`) are returned untouched.
    """
    if not url.startswith("sqlite"):
        return url
    prefix, sep, path = url.partition(":///")
    if not sep or not path:
        return url  # e.g. sqlite:// or sqlite::memory:
    if path == ":memory:" or path.startswith(":"):
        return url
    if path.startswith("/"):
        return url  # already absolute (sqlite:////abs/path)
    rel = path[2:] if path.startswith("./") else path
    return f"{prefix}:///{(_PROJECT_ROOT / rel).resolve()}"


def _sync_database_url(url: str) -> str:
    return _normalize_sqlite_url(
        url.replace("postgresql+asyncpg://", "postgresql+psycopg://")
    )


def _engine_options(url: str) -> dict:
    if url.startswith("sqlite"):
        return {"connect_args": {"check_same_thread": False}}
    if url.startswith("postgresql"):
        return {"connect_args": {"connect_timeout": 2}}
    return {}


def _create_sync_engine(url: str):
    sync_url = _sync_database_url(url)
    return create_engine(sync_url, pool_pre_ping=True, **_engine_options(sync_url))


def _select_auth_engine():
    try:
        preferred_engine = _create_sync_engine(settings.DATABASE_URL)
        with preferred_engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return preferred_engine
    except (ModuleNotFoundError, SQLAlchemyError):
        if "preferred_engine" in locals():
            preferred_engine.dispose()
        return _create_sync_engine(LOCAL_AUTH_DATABASE_URL)


def _async_database_url(url: str) -> str | None:
    if url.startswith("postgresql+asyncpg://"):
        return url
    if url.startswith("sqlite+aiosqlite://"):
        return _normalize_sqlite_url(url)
    return None


engine = _select_auth_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

_async_url = _async_database_url(settings.DATABASE_URL)
_async_engine_kwargs: dict = {"echo": False}
if _on_vercel:
    _async_engine_kwargs["poolclass"] = NullPool
    _async_engine_kwargs["connect_args"] = {"command_timeout": 7}
try:
    async_engine = create_async_engine(_async_url, **_async_engine_kwargs) if _async_url else None
except ModuleNotFoundError:
    async_engine = None
AsyncSessionLocal = (
    async_sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False)
    if async_engine
    else None
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    if AsyncSessionLocal is None:
        raise RuntimeError("Async database access requires an async DATABASE_URL")
    async with AsyncSessionLocal() as session:
        yield session
