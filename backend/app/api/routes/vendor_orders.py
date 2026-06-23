"""`/api/vendor/orders` — vendor-scoped order history (V1).

A customer's checkout can span multiple vendors but produces a single Order
row. From the vendor's perspective the same order is partitioned: each
vendor sees only its own lines, its own subtotal, the customer's id +
email, and a *count* of other vendors on that order (without naming them).

Design notes:
  * Vendor-only. Customers and anonymous callers get 403/401.
  * Read-only. Status transitions (acknowledge / ship / deliver) are
    explicitly deferred — V1 keeps Order.status == "placed" everywhere.
  * Snapshot fields on OrderItem (product_name, brand, vendor_name, unit
    price) mean order history is stable even if the underlying product is
    later edited or deleted by the vendor.

The route is intentionally thin: it auth-gates, validates the role, and
delegates everything else to `order_service`.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request, status

from backend.app.agent_router._auth import require_principal
from backend.app.db.session import SessionLocal
from backend.app.services import order_service

router = APIRouter()


def _require_vendor(request: Request) -> str:
    """Resolve the principal and require the vendor role.

    Returns the vendor's `vendor_id` (i.e. `Vendor.id`, the same value that
    `OrderItem.vendor_id` stores). Customers hit 403; an authenticated user
    with no `vendor_id` claim hits 401, since that points to a corrupt or
    half-provisioned vendor account.
    """
    principal = require_principal(request)
    role = principal.get("user_type") or "unknown"
    if role != "vendor":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only vendors can view their own order history.",
        )
    vendor_id = principal.get("vendor_id")
    if not vendor_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not resolve the authenticated vendor.",
        )
    return vendor_id


@router.get("/api/vendor/orders")
def list_vendor_orders(request: Request) -> dict[str, list[dict[str, Any]]]:
    """Return orders containing this vendor's line items, newest-first.

    Each order in the response is filtered to this vendor's lines only,
    with a vendor-scoped subtotal and an anonymized count of other vendors
    that shared the same customer checkout. See
    `order_service.project_orders_for_vendor` for the exact shape.
    """
    vendor_id = _require_vendor(request)
    db = SessionLocal()
    try:
        rows = order_service.list_orders_for_vendor(db, vendor_id=vendor_id)
        return {"orders": order_service.project_orders_for_vendor(db, rows, vendor_id=vendor_id)}
    finally:
        db.close()
