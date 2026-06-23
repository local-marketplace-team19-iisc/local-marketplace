"""`/api/orders` — V1 placeholder stub.

The frontend (feature 004) wires Order history + checkout to `/api/orders`,
but Orders are NOT in V1 scope (no spec, no service, no model, no
migration). The unimplemented route was returning 404 on every page load,
flooding the dev console with errors.

This stub keeps the UI quiet by:
  * `GET /api/orders` → 200 with `{ "orders": [] }`. Auth-gated so we
    don't expose anything by accident; just signals "you have no orders".
  * `POST /api/orders` → 501 Not Implemented with a friendly body so
    a checkout attempt fails *loudly* instead of silently 404-ing.

Replace this with a real Orders feature when 009/010 lands. The stub is
explicitly logged in `docs/architecture.md` so it doesn't become a
permanent fixture by accident.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, status

from backend.app.agent_router._auth import require_principal

router = APIRouter()


@router.get("/api/orders")
def list_orders(request: Request) -> dict[str, list]:
    """Return an empty order list for the authenticated principal.

    Auth-gated so the stub mirrors the documented contract in
    FRONTEND_DOCUMENTATION.md §`/api/orders` (🔒). A 401 is therefore
    expected for anonymous calls — keeps the surface honest until a
    real Orders feature lands.
    """
    require_principal(request)
    return {"orders": []}


@router.post("/api/orders")
def place_order(request: Request) -> None:
    require_principal(request)
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail=(
            "Order placement is not yet implemented in V1. "
            "This endpoint is a placeholder; see feature 008 spec §9."
        ),
    )
