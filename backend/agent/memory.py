"""Session store: Redis in production, in-memory dict for local dev.

The store is keyed by session_id and persists the full Session pydantic
model as JSON. TTL is configured in `config/agent.yaml`.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Protocol

from backend.agent.schemas import Channel, Role, Session


class SessionStore(Protocol):
    async def get(self, session_id: str) -> Session | None: ...
    async def save(self, session: Session) -> None: ...
    async def delete(self, session_id: str) -> None: ...


class InMemoryStore:
    """Dev-only; lost on process restart."""

    def __init__(self, ttl_seconds: int = 1800) -> None:
        self._data: dict[str, str] = {}
        self._ttl = ttl_seconds

    async def get(self, session_id: str) -> Session | None:
        raw = self._data.get(session_id)
        return Session.model_validate_json(raw) if raw else None

    async def save(self, session: Session) -> None:
        self._data[session.session_id] = session.model_dump_json()

    async def delete(self, session_id: str) -> None:
        self._data.pop(session_id, None)


class RedisStore:
    """Production session store. Lazy-imports redis so dev doesn't need it."""

    def __init__(self, url: str, ttl_seconds: int = 1800) -> None:
        import redis.asyncio as redis  # type: ignore
        self._r = redis.from_url(url, decode_responses=True)
        self._ttl = ttl_seconds

    def _key(self, sid: str) -> str:
        return f"session:{sid}"

    async def get(self, session_id: str) -> Session | None:
        raw = await self._r.get(self._key(session_id))
        return Session.model_validate_json(raw) if raw else None

    async def save(self, session: Session) -> None:
        await self._r.set(
            self._key(session.session_id),
            session.model_dump_json(),
            ex=self._ttl,
        )

    async def delete(self, session_id: str) -> None:
        await self._r.delete(self._key(session_id))


def build_store(cfg) -> SessionStore:
    """Pick a SessionStore based on config.

    `RedisStore.__init__` only constructs a lazy connection pool — it
    won't surface an unreachable Redis until the first `save()`. To avoid
    crashing mid-turn we explicitly ping Redis at startup and fall back
    to `InMemoryStore` (with a stderr warning) when the ping fails.
    Tests inject a store directly so this code path is dev/REPL-only.
    """
    import sys

    ttl = int(cfg.session.ttl_seconds)
    if cfg.session.store == "redis":
        try:
            store = RedisStore(cfg.session.redis_url, ttl_seconds=ttl)
            import asyncio
            asyncio.run(store._r.ping())
            return store
        except Exception as exc:
            print(
                f"warn: Redis unreachable at {cfg.session.redis_url} ({exc!s}) "
                "— falling back to in-memory session store (sessions lost "
                "on restart). Set session.store=\"inmem\" in config/agent.yaml "
                "to silence this.",
                file=sys.stderr,
            )
            return InMemoryStore(ttl_seconds=ttl)
    return InMemoryStore(ttl_seconds=ttl)


def new_session(*, user_id: str | None, channel: Channel, role: Role = "unknown") -> Session:
    now = datetime.now(timezone.utc)
    return Session(
        session_id=f"sess_{uuid.uuid4().hex[:12]}",
        user_id=user_id, role=role, channel=channel,
        created_at=now, last_active_at=now,
    )
