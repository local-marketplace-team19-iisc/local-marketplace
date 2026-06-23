"""`/api/orders` — V1 customer order placement + history.

Replaces the earlier placeholder stub. V1 scope (per user decision,
2026-06-23):
  * Customer can place an order from their cart (all-or-nothing).
  * Stock is decremented in the same transaction.
  * `GET /api/orders` returns the customer's own orders, newest-first.
  * No status transitions, vendor-side view, cancellation, or payment.
  * Customers only. Vendors and anonymous callers get 403/401.

The route layer is intentionally thin: it auth-gates, validates the role,
delegates to `order_service`, and maps typed service errors to HTTP codes.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, HTTPException, Request, status

from backend.app.agent_router._auth import require_principal
from backend.app.db.session import SessionLocal
from backend.app.services import order_service

router = APIRouter()


def _require_customer(request: Request) -> str:
    """Resolve the principal and require the customer role.

    Returns the customer's user-id (used as `customer_id` on the Order).
    Vendors hit 403 — they have their own dashboard for incoming orders
    (deferred until the vendor-side feature lands).
    """
    principal = require_principal(request)
    role = principal.get("user_type") or "unknown"
    if role != "customer":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only customers can place or view their own orders.",
        )
    customer_id = principal.get("id")
    if not customer_id:
        # require_principal returns a populated dict; this is just defensive
        # so a mis-configured auth backend can't silently break ownership.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not resolve the authenticated customer.",
        )
    return customer_id


@router.get("/api/orders")
def list_orders(request: Request) -> dict[str, list[dict[str, Any]]]:
    """Return this customer's orders, newest-first."""
    customer_id = _require_customer(request)
    db = SessionLocal()
    try:
        rows = order_service.list_orders_for_customer(db, customer_id=customer_id)
        return {"orders": [order_service.project_order(o) for o in rows]}
    finally:
        db.close()


@router.post("/api/orders", status_code=status.HTTP_201_CREATED)
def place_order(
    request: Request,
    payload: dict[str, Any] = Body(...),
) -> dict[str, Any]:
    """Place a multi-vendor order. Returns the persisted order envelope.

    Request shape (camelCase, matches the existing frontend service):
        { "items": [ { "productId": "...", "qty": 1 }, ... ] }

    A legacy `vendorId` field on each item is silently ignored — the
    authoritative vendor is read from the product row.
    """
    customer_id = _require_customer(request)
    items = payload.get("items")

    db = SessionLocal()
    try:
        try:
            order = order_service.place_order(
                db, customer_id=customer_id, items=items
            )
        except order_service.OrderValidationError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        except order_service.OrderNotFoundError as e:
            raise HTTPException(status_code=404, detail=str(e)) from e
        except order_service.OrderOutOfStockError as e:
            raise HTTPException(
                status_code=409,
                detail={"message": str(e), "lines": e.lines},
            ) from e

        return {"order": order_service.project_order(order)}
    finally:
        db.close()
