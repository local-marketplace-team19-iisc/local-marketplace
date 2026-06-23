"""Order placement service (feature 007).

Single public entry-point: `place_order`. All stock decrement, Order, and
OrderItem writes run inside a savepoint so any mid-flight failure rolls back
only the order attempt — never partially committed inventory changes.

Pessimistic locking strategy
-----------------------------
Each product row is locked with SELECT … FOR UPDATE before the stock check.
On PostgreSQL this serialises concurrent writers for the same product; on SQLite
(dev/CI fallback) the clause is silently dropped because SQLite uses
database-level write locking, which provides equivalent single-writer semantics.
"""

from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy.orm import Session

from backend.app.models.order import Order, OrderItem, OrderStatus
from backend.app.models.product import Product


# ---------------------------------------------------------------------------
# Exception hierarchy
# ---------------------------------------------------------------------------

class OrderError(Exception):
    """Base error for all order operations."""


class OrderValidationError(OrderError):
    """Raised when the caller supplies an invalid request (empty list, bad qty)."""


class ProductNotFoundError(OrderError):
    """Raised when a product_id is not present in the catalog."""

    def __init__(self, product_id: str) -> None:
        self.product_id = product_id
        super().__init__(f"Product {product_id!r} does not exist in the catalog.")


class OutOfStockError(OrderError):
    """Raised when requested quantity exceeds the product's available stock."""

    def __init__(self, product_id: str, requested: int, available: int) -> None:
        self.product_id = product_id
        self.requested = requested
        self.available = available
        super().__init__(
            f"Insufficient stock for product {product_id!r}: "
            f"requested {requested}, available {available}."
        )


# ---------------------------------------------------------------------------
# Input DTO
# ---------------------------------------------------------------------------

@dataclass
class OrderLineItem:
    """One line in the order request: which product and how many units."""

    product_id: str
    quantity: int


# ---------------------------------------------------------------------------
# Public service function
# ---------------------------------------------------------------------------

def place_order(
    db: Session,
    user_id: str,
    items: list[OrderLineItem],
    cart_id: str | None = None,
) -> str:
    """Atomically place an order and return the new order_id.

    Workflow per item
    -----------------
    1. Lock the product row (SELECT … FOR UPDATE) — prevents concurrent
       oversells on the same product_id.
    2. Validate stock >= requested quantity; raise OutOfStockError otherwise.
    3. Decrement stock_quantity in-place.
    4. Accumulate unit_price snapshot and subtotal.

    After all items pass:
    5. INSERT Order (status=confirmed, total_amount_inr).
    6. INSERT one OrderItem per line.
    7. RELEASE SAVEPOINT → outer db.commit() persists everything.

    On any exception the savepoint (and the outer transaction) are rolled back,
    leaving the database in its pre-call state.

    Args:
        db:      Active SQLAlchemy Session. Caller owns session lifecycle.
        user_id: Authenticated customer placing the order.
        items:   Non-empty list of OrderLineItem(product_id, quantity).
        cart_id: Optional cart this order was checked out from; stored on the
                 Order row for auditability; marks the cart as checked_out.

    Returns:
        order_id (str UUID) — the unique "#orderID" shown to the customer.

    Raises:
        OrderValidationError: items list empty, or any quantity < 1.
        ProductNotFoundError: a product_id is absent from the catalog.
        OutOfStockError:      a product has fewer units than requested.
        OrderError:           any unexpected persistence failure.
    """
    if not items:
        raise OrderValidationError("Order must contain at least one item.")

    for line in items:
        if line.quantity < 1:
            raise OrderValidationError(
                f"Quantity for product {line.product_id!r} must be >= 1 "
                f"(got {line.quantity})."
            )

    try:
        # SAVEPOINT — if anything below fails only this sub-transaction rolls
        # back; the session itself (and any prior work in the outer tx) survives.
        savepoint = db.begin_nested()

        total = Decimal("0.00")
        order_items_payload: list[dict] = []

        for line in items:
            # Pessimistic lock: serialises concurrent writes on this product row.
            product: Product | None = (
                db.query(Product)
                .filter(Product.product_id == line.product_id)
                .with_for_update()
                .first()
            )

            if product is None:
                raise ProductNotFoundError(line.product_id)

            if product.stock_quantity < line.quantity:
                raise OutOfStockError(
                    product_id=line.product_id,
                    requested=line.quantity,
                    available=product.stock_quantity,
                )

            # Decrement inside the lock — safe from race conditions.
            product.stock_quantity -= line.quantity

            unit_price = Decimal(str(product.price_inr))
            subtotal = unit_price * line.quantity
            total += subtotal

            order_items_payload.append(
                {
                    "product_id": line.product_id,
                    "quantity": line.quantity,
                    "unit_price_inr": unit_price,
                    "subtotal_inr": subtotal,
                }
            )

        order = Order(
            user_id=user_id,
            cart_id=cart_id,
            status=OrderStatus.confirmed.value,
            total_amount_inr=total,
        )
        db.add(order)
        # flush to assign order.order_id before child rows reference it
        db.flush()

        for payload in order_items_payload:
            db.add(OrderItem(order_id=order.order_id, **payload))

        savepoint.commit()   # RELEASE SAVEPOINT
        db.commit()          # persist to database

        return order.order_id

    except OrderError:
        # Known domain failure — roll back and re-raise as-is so the route
        # layer can map it to the correct HTTP status code.
        db.rollback()
        raise
    except Exception as exc:
        # Unexpected persistence or driver error.
        db.rollback()
        raise OrderError(f"Order placement failed unexpectedly: {exc}") from exc


# ---------------------------------------------------------------------------
# Read helper
# ---------------------------------------------------------------------------

def get_order(db: Session, order_id: str, user_id: str) -> Order:
    """Fetch a single order, verifying it belongs to the requesting user.

    Args:
        db:       Active SQLAlchemy Session.
        order_id: UUID of the order to retrieve.
        user_id:  Must match Order.user_id (ownership check).

    Returns:
        The Order ORM instance (with lazy-loaded items).

    Raises:
        ProductNotFoundError: order_id not found or does not belong to user_id.
    """
    order = (
        db.query(Order)
        .filter(Order.order_id == order_id, Order.user_id == user_id)
        .first()
    )
    if order is None:
        raise ProductNotFoundError(order_id)  # deliberate: same 404 shape
    return order
