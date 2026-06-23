"""Customer order placement service (V1).

Plain functions over a SQLAlchemy Session, mirroring `auth_service` and
`product_service`. Order placement is **all-or-nothing**: if any line fails
validation (unknown product, insufficient stock), the whole call rolls back
and a typed error is raised. The route layer maps each error to its HTTP
status code.

Stock decrement is part of the same DB transaction as the Order/OrderItem
inserts, so a customer cannot accidentally "win" stock that another
concurrent order also won. We use a single SELECT-then-UPDATE per product;
SQLite serializes writes, and Postgres serializes via row-level locks once
we add `with_for_update()` (deferred until prod runs on Postgres, since
SQLite doesn't honour the hint).

V1 scope (per spec session 13 / user decision):
* Customer places an order.
* Stock decrements.
* One order_number per call.
* GET returns the customer's own orders newest-first.
* No status transitions, vendor-side view, cancellation, or payment.
"""

from __future__ import annotations

import secrets
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Iterable

from sqlalchemy.orm import Session

from backend.app.models.order import Order
from backend.app.models.order_item import OrderItem
from backend.app.models.product import Product
from backend.app.models.user import User
from backend.app.models.vendor import Vendor


# --------------------------------------------------------------------------- #
# Typed errors (mapped to HTTP status codes in the route layer)
# --------------------------------------------------------------------------- #
class OrderError(Exception):
    """Base error for order operations."""


class OrderValidationError(OrderError):
    """Bad request shape (empty cart, non-positive qty, missing fields)."""


class OrderNotFoundError(OrderError):
    """A referenced product no longer exists."""


class OrderOutOfStockError(OrderError):
    """One or more lines exceed available stock.

    The `lines` payload describes the offending lines so the frontend can
    show "orange juice: requested 2, available 1" toasts.
    """

    def __init__(self, lines: list[dict[str, Any]]):
        self.lines = lines
        msg = "; ".join(
            f"{ln['product_name']}: requested {ln['requested']}, available {ln['available']}"
            for ln in lines
        )
        super().__init__(f"Insufficient stock — {msg}")


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _order_number() -> str:
    """Human-friendly, unguessable, sortable. e.g. `ORD-20260623-A1B2C3D4`.

    The date prefix is informational only; uniqueness is guaranteed by the
    8-char hex suffix from `secrets.token_hex(4)` (2^32 space — safe for V1).
    The `unique=True` constraint on `Order.order_number` is the real guard.
    """
    return f"ORD-{datetime.utcnow():%Y%m%d}-{secrets.token_hex(4).upper()}"


def _money(amount: Decimal | float | int) -> Decimal:
    """Round to 2 decimal places, banker-safe."""
    return Decimal(str(amount)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _normalize_items(raw: Iterable[Any] | None) -> list[dict[str, Any]]:
    """Validate the request shape and return a clean list of `{product_id, qty}`.

    The frontend may send `productId` (camelCase) or `product_id`; both are
    accepted. `vendorId` from the old cart shape is intentionally ignored —
    the backend looks up the authoritative vendor_id from the product row.
    """
    if not raw:
        raise OrderValidationError("Cart is empty — add at least one item.")
    cleaned: list[dict[str, Any]] = []
    for idx, item in enumerate(raw):
        if not isinstance(item, dict):
            raise OrderValidationError(f"Line {idx}: expected an object.")
        product_id = item.get("product_id") or item.get("productId")
        qty = item.get("qty") or item.get("quantity") or 1
        try:
            qty_int = int(qty)
        except (TypeError, ValueError) as exc:
            raise OrderValidationError(
                f"Line {idx}: qty must be a positive integer."
            ) from exc
        if not product_id or not isinstance(product_id, str):
            raise OrderValidationError(f"Line {idx}: product_id is required.")
        if qty_int <= 0:
            raise OrderValidationError(f"Line {idx}: qty must be > 0.")
        cleaned.append({"product_id": product_id, "qty": qty_int})
    return cleaned


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #
def place_order(
    db: Session,
    *,
    customer_id: str,
    items: Iterable[Any] | None,
) -> Order:
    """Place an order for `customer_id`. All-or-nothing.

    Steps:
      1. Validate the request shape.
      2. Look up every product in one go; reject if any are missing.
      3. Verify stock for every line; collect failures, raise if any.
      4. Decrement stock + insert Order + OrderItem rows in one transaction.
      5. Return the persisted Order (with `items` eagerly loaded via the
         relationship's `lazy="joined"` config).
    """
    cleaned = _normalize_items(items)

    product_ids = [ln["product_id"] for ln in cleaned]
    rows = (
        db.query(Product)
        .filter(Product.product_id.in_(product_ids))
        .all()
    )
    by_id = {p.product_id: p for p in rows}

    missing = [pid for pid in product_ids if pid not in by_id]
    if missing:
        raise OrderNotFoundError(
            f"Product(s) not found: {', '.join(missing[:5])}"
            + (f" (+{len(missing) - 5} more)" if len(missing) > 5 else "")
        )

    # Stock validation (all-or-nothing). Collect *all* failures so the user
    # can see every problem in one shot rather than fixing them one by one.
    out_of_stock: list[dict[str, Any]] = []
    for ln in cleaned:
        product = by_id[ln["product_id"]]
        if product.stock_quantity < ln["qty"]:
            out_of_stock.append(
                {
                    "product_id": product.product_id,
                    "product_name": product.product_name,
                    "requested": ln["qty"],
                    "available": int(product.stock_quantity),
                }
            )
    if out_of_stock:
        raise OrderOutOfStockError(out_of_stock)

    # Resolve vendor display names from a single bulk lookup.
    vendor_ids = list({by_id[ln["product_id"]].vendor_id for ln in cleaned})
    vendor_rows = (
        db.query(Vendor).filter(Vendor.id.in_(vendor_ids)).all() if vendor_ids else []
    )
    vendor_name_by_id = {v.id: v.shop_name for v in vendor_rows}

    # Build the Order + OrderItem graph in-memory, then commit once.
    order = Order(
        order_number=_order_number(),
        customer_id=customer_id,
        total_inr=Decimal("0.00"),
        status="placed",
    )
    db.add(order)
    db.flush()  # so order.id is available for FKs

    total = Decimal("0.00")
    for ln in cleaned:
        product = by_id[ln["product_id"]]
        unit_price = _money(product.price_inr)
        line_total = _money(unit_price * ln["qty"])
        total += line_total

        product.stock_quantity = int(product.stock_quantity) - ln["qty"]

        db.add(
            OrderItem(
                order_id=order.id,
                product_id=product.product_id,
                vendor_id=product.vendor_id,
                product_name_snapshot=product.product_name,
                brand_snapshot=product.brand or "Generic",
                vendor_name_snapshot=vendor_name_by_id.get(
                    product.vendor_id, "Vendor"
                ),
                unit_price_inr=unit_price,
                qty=ln["qty"],
                line_total_inr=line_total,
            )
        )

    order.total_inr = _money(total)
    db.commit()
    db.refresh(order)
    return order


def list_orders_for_customer(db: Session, *, customer_id: str) -> list[Order]:
    """Return the customer's orders newest-first."""
    return (
        db.query(Order)
        .filter(Order.customer_id == customer_id)
        .order_by(Order.placed_at.desc())
        .all()
    )


def list_orders_for_vendor(db: Session, *, vendor_id: str) -> list[Order]:
    """Return orders that contain at least one line belonging to `vendor_id`.

    A customer's checkout can span multiple vendors but produces a single
    Order row (SPEC §3 — "one unique order number"). For the vendor view we
    want that same order back, but it isn't the vendor's job to know which
    other shops the customer also bought from — so the **projection layer**
    (`project_order_for_vendor`) drops items that aren't this vendor's.

    Query strategy: an EXISTS sub-query on `order_items.vendor_id`. We rely
    on the existing `ix_order_items_vendor_id` index to keep this cheap even
    when the orders table grows. We avoid a join+DISTINCT because that would
    eagerly load every line item; the Order.items relationship is
    `lazy="joined"`, so SQLAlchemy already fetches the full item set in one
    follow-up query — fine for V1 cardinalities. If/when this gets noisy on
    Postgres we'll swap to a single explicit JOIN + GROUP BY + array_agg.
    """
    return (
        db.query(Order)
        .filter(
            db.query(OrderItem.id)
            .filter(
                OrderItem.order_id == Order.id,
                OrderItem.vendor_id == vendor_id,
            )
            .exists()
        )
        .order_by(Order.placed_at.desc())
        .all()
    )


# --------------------------------------------------------------------------- #
# Wire projection
# --------------------------------------------------------------------------- #
def project_order(order: Order) -> dict[str, Any]:
    """Project an ORM Order to the frontend's expected envelope.

    Matches the shape `OrdersPage.jsx` already consumes:
        { orderNumber, items, vendors, total, placedAt, status }
    """
    items_payload = [
        {
            "id": it.id,
            "productId": it.product_id,
            "vendorId": it.vendor_id,
            "name": it.product_name_snapshot,
            "brand": it.brand_snapshot,
            "vendor": it.vendor_name_snapshot,
            "qty": int(it.qty),
            "unitPrice": float(it.unit_price_inr),
            "lineTotal": float(it.line_total_inr),
        }
        for it in order.items
    ]
    vendors = sorted({it["vendor"] for it in items_payload})
    return {
        "orderNumber": order.order_number,
        "status": order.status,
        "items": items_payload,
        "vendors": vendors,
        "total": float(order.total_inr),
        "placedAt": order.placed_at.isoformat() + "Z",
    }


def project_orders_for_vendor(
    db: Session,
    orders: list[Order],
    *,
    vendor_id: str,
) -> list[dict[str, Any]]:
    """Vendor-scoped projection of an Order list.

    For each order we:
      * keep ONLY items whose `vendor_id` matches the calling vendor;
      * compute a vendor-scoped subtotal (sum of `lineTotal` for those items);
      * report `otherVendorsCount` so the vendor knows whether the order has
        other shops on it, without naming them (privacy decision: a vendor
        does not learn the competitive set from this view);
      * surface the customer's id + email only — minimum needed to recognise
        repeat buyers or follow up. Full name / phone / address are
        intentionally omitted (privacy + data-protection).

    Customer emails are bulk-resolved in one query, not per-row.
    """
    if not orders:
        return []

    customer_ids = list({o.customer_id for o in orders})
    email_by_id: dict[str, str] = {
        u.id: (u.email or "")
        for u in db.query(User).filter(User.id.in_(customer_ids)).all()
    }

    out: list[dict[str, Any]] = []
    for order in orders:
        # Partition the items: mine vs. the rest. We never expose the rest.
        my_items: list[dict[str, Any]] = []
        other_vendor_ids: set[str | None] = set()
        for it in order.items:
            if it.vendor_id == vendor_id:
                my_items.append(
                    {
                        "id": it.id,
                        "productId": it.product_id,
                        "name": it.product_name_snapshot,
                        "brand": it.brand_snapshot,
                        "qty": int(it.qty),
                        "unitPrice": float(it.unit_price_inr),
                        "lineTotal": float(it.line_total_inr),
                    }
                )
            else:
                other_vendor_ids.add(it.vendor_id)

        # Defence in depth: list_orders_for_vendor() should already exclude
        # orders with no matching items, but a stale relationship-load can't
        # be ruled out. If we somehow have zero items for this vendor, skip.
        if not my_items:
            continue

        vendor_subtotal = round(sum(it["lineTotal"] for it in my_items), 2)
        out.append(
            {
                "orderNumber": order.order_number,
                "status": order.status,
                "placedAt": order.placed_at.isoformat() + "Z",
                "items": my_items,
                "vendorSubtotal": vendor_subtotal,
                "otherVendorsCount": len(other_vendor_ids),
                "customer": {
                    "id": order.customer_id,
                    "email": email_by_id.get(order.customer_id, ""),
                },
            }
        )
    return out
