"""Pydantic request/response schemas for the order placement API (feature 007)."""

from pydantic import BaseModel, Field


class OrderItemRequest(BaseModel):
    """A single line in the checkout payload."""

    product_id: str = Field(description="UUID of the product to purchase.")
    quantity: int = Field(ge=1, description="Number of units to buy (must be >= 1).")


class OrderPlacementRequest(BaseModel):
    """POST /api/orders/place — request body."""

    items: list[OrderItemRequest] = Field(
        min_length=1,
        description="One or more products to purchase in a single atomic transaction.",
    )


class OrderPlacementResponse(BaseModel):
    """201 Created — returned on successful order placement."""

    order_id: str = Field(description="Unique UUID of the newly created order.")
    message: str = Field(default="Order placed successfully.")


class OutOfStockDetail(BaseModel):
    """Structured 409 Conflict response body for client-side display."""

    message: str
    product_id: str
    requested: int
    available: int
