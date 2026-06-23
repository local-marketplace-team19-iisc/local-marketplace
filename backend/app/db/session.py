from collections.abc import AsyncGenerator

from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from backend.app.core.config import settings

LOCAL_AUTH_DATABASE_URL = "sqlite:///./local_marketplace.db"


def _sync_database_url(url: str) -> str:
    return url.replace("postgresql+asyncpg://", "postgresql+psycopg://")


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
        return url
    return None


# Sync engine — feature 003 auth. Prefer configured Postgres when reachable;
# fall back to the local auth DB so the live demo can still register/login.
engine = _select_auth_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Async engine — feature 001 marketplace entities. Only initialize when the URL
# uses an async driver; the auth demo path is sync-only.
_async_url = _async_database_url(settings.DATABASE_URL)
try:
    async_engine = create_async_engine(_async_url, echo=False) if _async_url else None
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
