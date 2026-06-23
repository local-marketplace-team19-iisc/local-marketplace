"""Map a feature-006 `ProductRead` into the frontend's `Listing` wire shape.

Spec FR-10 — the chat / search responses MUST keep feature 007's `Listing`
field map so the existing `ProductCard` renders unchanged. The mapping is:

    ProductRead.id           → Listing.id
    ProductRead.name         → Listing.name
    ProductRead.price        → Listing.price
    ProductRead.brand        → Listing.vendor   (no separate vendor-name in v1)
    (computed)               → Listing.rating   (defaults to 0.0 — no rating column)
    ProductRead.stock > 0    → Listing.availability

Lives in its own module so the chat/search adapters in M5 can re-use it
without going through the router's `RouterResult`.
"""

from __future__ import annotations

from typing import Any

from backend.app.schemas.product import ProductRead


def project_listing(p: ProductRead) -> dict[str, Any]:
    """Project a 006 `ProductRead` into the wire `Listing` dict."""
    return {
        "id": p.id,
        "name": p.name,
        "price": float(p.price),
        "vendor": p.brand or "",
        "rating": 0.0,
        "availability": p.stock > 0,
    }
