"""Shared JWT principal resolution for the agent_router HTTP adapters.

Three endpoints (`/api/agent/route`, `/api/chat`, `/api/search`) need the
same authentication treatment:
  * `/api/chat` and `/api/agent/route` **require** a valid Bearer token.
  * `/api/search` is anonymous-friendly (frontend uses it on public pages).

The principal dict mirrors the shape `auth_service.get_current_user`
returns (`{id, email, user_type, vendor_id?, ...}`).

The DB session is acquired and released inside the helpers so each
HTTP adapter has its own scoped Session; auth_service / SessionLocal are
imported lazily to keep this module light on import.
"""

from __future__ import annotations

from typing import Any, Optional

from fastapi import HTTPException, Request


def _principal_from_token(token: str) -> dict[str, Any]:
    """Resolve a principal from a bearer token, raising 401 on failure."""
    from backend.app.db.session import SessionLocal
    from backend.app.services import auth_service

    db = SessionLocal()
    try:
        try:
            return auth_service.get_current_user(db, token)
        except auth_service.AuthUnauthorizedError as e:
            raise HTTPException(status_code=401, detail=str(e)) from e
    finally:
        db.close()


def require_principal(request: Request) -> dict[str, Any]:
    """Require a Bearer token; return the principal dict."""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=401, detail="Missing or invalid authorization header"
        )
    return _principal_from_token(auth_header[7:])


def optional_principal(request: Request) -> Optional[dict[str, Any]]:
    """Return the principal if a Bearer token is present and valid, else None.

    Used by `/api/search` so customers and anonymous browsers both work.
    A *present but invalid* token returns None too (rather than 401) —
    the search page is intentionally permissive.
    """
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None
    try:
        return _principal_from_token(auth_header[7:])
    except HTTPException:
        return None


def role_and_vendor(principal: Optional[dict[str, Any]]) -> tuple[str, Optional[str]]:
    """Return `(role, vendor_id)` for the router."""
    if not principal:
        return "unknown", None
    role = principal.get("user_type") or "unknown"
    vendor_id = principal.get("vendor_id")
    return role, vendor_id
