"""Order placement API routes (feature 007).

Endpoint
--------
POST /api/orders/place  →  201 { order_id, message }

Auth
----
Requires a valid customer JWT in the Authorization: Bearer header.
Vendors cannot place orders (403 if user_type == "vendor").

Error mapping
-------------
service exception          HTTP status
OrderValidationError    →  422 Unprocessable Entity
ProductNotFoundError    →  404 Not Found
OutOfStockError         →  409 Conflict  (structured body with stock details)
OrderError (generic)    →  500 Internal Server Error
"""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from backend.app.db.session import SessionLocal
from backend.app.models.user import UserRole
from backend.app.schemas.order import (
    OrderPlacementRequest,
    OrderPlacementResponse,
)
from backend.app.services.order_service import (
    OrderError,
    OrderLineItem,
    OrderValidationError,
    OutOfStockError,
    ProductNotFoundError,
    place_order,
)

router = APIRouter()


# ---------------------------------------------------------------------------
# Shared dependencies
# ---------------------------------------------------------------------------

def get_db() -> Session:
    """Yield a database session; close on request teardown."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_customer(
    request: Request,
    db: Session = Depends(get_db),
) -> str:
    """Resolve the authenticated customer's user_id from the Bearer JWT.

    auth_service is imported lazily here so that the router module itself
    does not pull in bcrypt/jose at import time (those are optional heavy
    deps that are only needed at request time).

    Returns:
        user_id (str) of the verified customer.

    Raises:
        401 if the token is missing, malformed, or expired.
        403 if the token belongs to a vendor (not a customer).
    """
    from backend.app.services import auth_service  # lazy: avoids bcrypt at import time

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid Authorization header. Expected: Bearer <token>",
        )
    token = auth_header[7:]
    try:
        user = auth_service.get_current_user(db, token)
    except auth_service.AuthUnauthorizedError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
        ) from exc

    if user.get("user_type") != UserRole.customer.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only customer accounts can place orders.",
        )
    return user["id"]


# ---------------------------------------------------------------------------
# Error mapper
# ---------------------------------------------------------------------------

def _map_order_error(exc: OrderError) -> HTTPException:
    """Translate a service-layer OrderError into the appropriate HTTPException."""
    if isinstance(exc, OrderValidationError):
        return HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        )
    if isinstance(exc, ProductNotFoundError):
        return HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )
    if isinstance(exc, OutOfStockError):
        # Return structured detail so the client can show "X left in stock".
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": str(exc),
                "product_id": exc.product_id,
                "requested": exc.requested,
                "available": exc.available,
            },
        )
    # Catch-all: unexpected persistence failure already had db.rollback() called.
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=f"Order placement failed: {exc}",
    )


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------

@router.post(
    "/place",
    response_model=OrderPlacementResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Place a new order",
    description=(
        "Atomically purchases one or more products for the authenticated customer. "
        "Acquires pessimistic row-locks on each product, validates stock, decrements "
        "inventory, and records the Order + OrderItem rows in a single savepoint. "
        "Returns the unique order_id on success."
    ),
    responses={
        201: {"description": "Order created. Body contains `order_id`."},
        401: {"description": "Missing or invalid JWT."},
        403: {"description": "Token does not belong to a customer account."},
        404: {"description": "One or more product_ids not found in the catalog."},
        409: {"description": "Insufficient stock for a requested product."},
        422: {"description": "Validation error: empty items list or quantity < 1."},
        500: {"description": "Unexpected server-side failure (transaction rolled back)."},
    },
)
def place_order_endpoint(
    payload: OrderPlacementRequest,
    user_id: str = Depends(get_current_customer),
    db: Session = Depends(get_db),
) -> OrderPlacementResponse:
    line_items = [
        OrderLineItem(product_id=item.product_id, quantity=item.quantity)
        for item in payload.items
    ]
    try:
        order_id = place_order(db, user_id=user_id, items=line_items)
        return OrderPlacementResponse(order_id=order_id)
    except OrderError as exc:
        raise _map_order_error(exc) from exc
