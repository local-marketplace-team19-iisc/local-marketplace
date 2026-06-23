"""SBERT router — one-shot intent + entity → existing-API call.

This is the *only* place where intent, role gating, entity extraction, and
API dispatch are joined. The HTTP adapters in M5 (`api.py`,
`chat_adapter.py`, `search_adapter.py`) are thin: they parse the request,
call `route_text(...)`, and project the result into their wire envelope.

Design invariants:
- **Stateless.** No session memory, no Redis. Each call is independent.
- **No HTTP self-call.** The dispatch calls feature-006's `product_service`
  functions directly in-process against a SQLAlchemy `Session`. Cheaper,
  simpler, and means the router doesn't need an httpx client just to talk
  to itself.
- **Role gating happens *before* any API call.** A customer asking to
  `add_product` gets a polite refusal — never a 403 from the products API.
"""

from __future__ import annotations

import logging
from contextlib import contextmanager
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy.orm import Session

from backend.app.agent_router import entities, intents
from backend.app.agent_router.projection import project_listing
from backend.app.db.session import SessionLocal
from backend.app.schemas.product import ProductRead, ProductUpdate
from backend.app.services import product_service

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# Result envelope
# --------------------------------------------------------------------------- #


@dataclass
class RouterResult:
    """One-shot router output.

    The HTTP adapters project a subset of this into their wire envelopes:
    `/api/agent/route` exposes it verbose (FR-6); `/api/chat` flattens to
    `{reply, listings, sessionId, debug}` (FR-7); `/api/search` projects to
    `{products: [...]}` (FR-8).

    `confidence` is the SBERT classifier score (cosine similarity to the
    best-matching intent prototype) when the intent was classified. It is
    1.0 when an intent is forced (e.g. `/api/search` skips SBERT). UI
    surfaces can use it to render a small badge / debug tooltip.
    """

    intent: str
    confidence: float = 0.0
    entities: dict[str, Any] = field(default_factory=dict)
    reply: str = ""
    listings: list[dict[str, Any]] = field(default_factory=list)
    api_called: Optional[str] = None
    api_status: int = 200
    meta: dict[str, Any] = field(default_factory=dict)


# --------------------------------------------------------------------------- #
# Session lifecycle helper
# --------------------------------------------------------------------------- #


@contextmanager
def _db_session():
    """Yield a sync SQLAlchemy Session, ensuring it is closed even on errors.

    Mirrors the route-layer `get_db()` dependency in `api/routes/products.py`;
    used by the router itself because the router is not invoked through
    FastAPI's dependency tree (the HTTP adapters call `route_text` directly).
    """
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# --------------------------------------------------------------------------- #
# Role gating — which intents each role may execute (spec FR-4)
# --------------------------------------------------------------------------- #


_CUSTOMER_INTENTS = {"search_products", "get_categories", "unknown"}
_VENDOR_INTENTS = {
    "search_products",
    "get_categories",
    "get_my_listings",
    "add_product",
    "update_product",
    "delete_product",
    "unknown",
}


def _is_allowed(intent: str, role: str) -> bool:
    if role == "vendor":
        return intent in _VENDOR_INTENTS
    if role == "customer":
        return intent in _CUSTOMER_INTENTS
    # An unauthenticated / unknown-role caller can still browse.
    return intent in {"search_products", "get_categories", "unknown"}


# --------------------------------------------------------------------------- #
# In-Python filter helpers (006 list_products only supports vendor_id filter;
# this keeps the agent router's text-search behaviour without expanding the
# 006 service contract).
# --------------------------------------------------------------------------- #


def _filter_rows(
    rows: list[ProductRead],
    *,
    q: Optional[str] = None,
    max_price: Optional[float] = None,
    min_price: Optional[float] = None,
) -> list[ProductRead]:
    """Apply the search-bar filters in-Python on a 006 ProductRead list."""
    out = rows
    if q:
        tokens = [t for t in q.lower().split() if t]
        out = [
            p
            for p in out
            if any(
                t in f"{p.name} {p.brand} {p.description} {p.category}".lower()
                for t in tokens
            )
        ]
    if max_price is not None:
        out = [p for p in out if float(p.price) <= float(max_price)]
    if min_price is not None:
        out = [p for p in out if float(p.price) >= float(min_price)]
    return out


# --------------------------------------------------------------------------- #
# Per-intent dispatchers
# --------------------------------------------------------------------------- #


def _handle_search(text: str, intent_label: str) -> RouterResult:
    """Customer / anonymous search (006 GET /api/products + in-Python filters)."""
    q = entities.extract_keywords(text, intent_label)
    max_p = entities.extract_max_price(text)
    min_p = entities.extract_min_price(text)
    ignored: list[str] = []
    if "near me" in text.lower():
        ignored.append("near_me")

    with _db_session() as db:
        all_rows = product_service.list_products(db)

    rows = _filter_rows(all_rows, q=q or None, max_price=max_p, min_price=min_p)
    if not rows and q:
        # Fallback: drop the keyword filter and just apply price (so
        # "show me X under ₹50000" returns *something* if nothing matches X).
        rows = _filter_rows(all_rows, max_price=max_p, min_price=min_p)
        ignored.append("query_relaxed")

    listings = [project_listing(p) for p in rows]
    if listings:
        reply = f"Found {len(listings)} match{'es' if len(listings) != 1 else ''}."
    else:
        reply = (
            "I couldn't find anything matching that — try a different brand or budget."
        )
    return RouterResult(
        intent="search_products",
        entities={"keywords": q, "max_price": max_p, "min_price": min_p},
        reply=reply,
        listings=listings,
        api_called="GET /api/products",
        api_status=200,
        meta={"ignored": ignored} if ignored else {},
    )


def _handle_add_product(text: str, vendor_id: Optional[str]) -> RouterResult:
    """Vendor add-by-description (006 POST /api/products/from-description)."""
    if not vendor_id:
        return RouterResult(
            intent="add_product",
            reply="Only vendors can add products.",
            api_called=None,
            api_status=403,
        )
    try:
        with _db_session() as db:
            product = product_service.create_from_description(db, vendor_id, text)
    except product_service.ProductValidationError as e:
        return RouterResult(
            intent="add_product",
            reply=str(e),
            api_called="POST /api/products/from-description",
            api_status=400,
        )
    return RouterResult(
        intent="add_product",
        entities={"name": product.name, "price": float(product.price)},
        reply=f"Added: {product.name} (₹{product.price}).",
        listings=[project_listing(product)],
        api_called="POST /api/products/from-description",
        api_status=201,
    )


def _handle_update_product(text: str, vendor_id: Optional[str]) -> RouterResult:
    """Vendor update-by-id or update-by-name-disambiguation (006 PUT /api/products/{id})."""
    if not vendor_id:
        return RouterResult(
            intent="update_product",
            reply="Only vendors can update products.",
            api_called=None,
            api_status=403,
        )
    new_price = entities.extract_price(text)
    if new_price is None:
        return RouterResult(
            intent="update_product",
            reply=(
                "Please tell me the new price — for example: "
                "'update product 12345 to ₹50,000'."
            ),
            api_called=None,
            api_status=400,
        )
    product_id = entities.extract_product_id(text)

    with _db_session() as db:
        if not product_id:
            # Scenario 4 edge: vendor said "update my iPhone listing" with no id.
            # Try a single-candidate vendor-scoped lookup.
            q = entities.extract_keywords(text, "update_product")
            mine = product_service.list_products(db, vendor_id=vendor_id)
            candidates = _filter_rows(mine, q=q or None) if q else []
            if len(candidates) == 0:
                return RouterResult(
                    intent="update_product",
                    reply=(
                        "I couldn't find any of your products matching that — "
                        "please give me the product ID."
                    ),
                    api_called=None,
                    api_status=404,
                )
            if len(candidates) > 1:
                return RouterResult(
                    intent="update_product",
                    reply=(
                        f"I found {len(candidates)} candidates matching that — "
                        "please give me the product ID."
                    ),
                    api_called=None,
                    api_status=409,
                )
            product_id = candidates[0].id

        try:
            product = product_service.update_product(
                db,
                vendor_id,
                product_id,
                ProductUpdate(price=Decimal(str(new_price))),
            )
        except product_service.ProductNotFoundError:
            return RouterResult(
                intent="update_product",
                reply=f"No product with id {product_id} found.",
                api_called=f"PUT /api/products/{product_id}",
                api_status=404,
            )
        except product_service.ProductForbiddenError:
            return RouterResult(
                intent="update_product",
                reply="You can only update your own products.",
                api_called=f"PUT /api/products/{product_id}",
                api_status=403,
            )

    return RouterResult(
        intent="update_product",
        entities={"product_id": product_id, "price": new_price},
        reply=f"Updated {product.name} to ₹{product.price}.",
        listings=[project_listing(product)],
        api_called=f"PUT /api/products/{product_id}",
        api_status=200,
    )


def _handle_delete_product(text: str, vendor_id: Optional[str]) -> RouterResult:
    """Vendor delete-by-id (if id present) or delete-by-description."""
    if not vendor_id:
        return RouterResult(
            intent="delete_product",
            reply="Only vendors can delete products.",
            api_called=None,
            api_status=403,
        )
    product_id = entities.extract_product_id(text)

    if product_id:
        with _db_session() as db:
            # Look up name *before* deletion so we can echo it back.
            mine = product_service.list_products(db, vendor_id=vendor_id)
            target_name = next(
                (p.name for p in mine if p.id == product_id), None
            )
            try:
                product_service.delete_product(db, vendor_id, product_id)
            except product_service.ProductNotFoundError:
                return RouterResult(
                    intent="delete_product",
                    reply=f"No product with id {product_id} found.",
                    api_called=f"DELETE /api/products/{product_id}",
                    api_status=404,
                )
            except product_service.ProductForbiddenError:
                return RouterResult(
                    intent="delete_product",
                    reply="You can only delete your own products.",
                    api_called=f"DELETE /api/products/{product_id}",
                    api_status=403,
                )
        return RouterResult(
            intent="delete_product",
            entities={"product_id": product_id},
            reply=f"Deleted: {target_name or product_id}.",
            api_called=f"DELETE /api/products/{product_id}",
            api_status=204,
        )

    # No id — fall back to 006 FR-9 description-based delete.
    try:
        with _db_session() as db:
            deleted = product_service.delete_by_description(db, vendor_id, text)
    except product_service.ProductNotFoundError as e:
        return RouterResult(
            intent="delete_product",
            reply=str(e),
            api_called="POST /api/products/delete-by-description",
            api_status=404,
        )
    except product_service.ProductValidationError as e:
        return RouterResult(
            intent="delete_product",
            reply=str(e),
            api_called="POST /api/products/delete-by-description",
            api_status=400,
        )
    return RouterResult(
        intent="delete_product",
        entities={"description": text.strip()},
        reply=f"Deleted: {deleted.name}.",
        api_called="POST /api/products/delete-by-description",
        api_status=200,
    )


def _handle_get_my_listings(vendor_id: Optional[str]) -> RouterResult:
    if not vendor_id:
        return RouterResult(
            intent="get_my_listings",
            reply="Only vendors have listings.",
            api_called=None,
            api_status=403,
        )
    with _db_session() as db:
        rows = product_service.list_products(db, vendor_id=vendor_id)
    listings = [project_listing(p) for p in rows]
    if listings:
        reply = f"You have {len(listings)} listing{'s' if len(listings) != 1 else ''}."
    else:
        reply = "You don't have any listings yet."
    return RouterResult(
        intent="get_my_listings",
        reply=reply,
        listings=listings,
        api_called="GET /api/products",
        api_status=200,
    )


def _handle_get_categories() -> RouterResult:
    with _db_session() as db:
        cats = [c.category_name for c in product_service.list_categories(db)]
    if cats:
        reply = "Available categories: " + ", ".join(cats) + "."
    else:
        reply = "No categories are configured yet."
    return RouterResult(
        intent="get_categories",
        reply=reply,
        listings=[],
        api_called="GET /api/catalog/categories",
        api_status=200,
        meta={"categories": cats},
    )


def _handle_unknown(text: str) -> RouterResult:
    return RouterResult(
        intent="unknown",
        reply=(
            "I can help you search, add, update, or delete products, "
            "or list your own listings. What would you like to do?"
        ),
        listings=[],
        api_called=None,
        api_status=200,
        meta={"raw_text": text},
    )


# --------------------------------------------------------------------------- #
# Top-level entry point — the only function the HTTP adapters call
# --------------------------------------------------------------------------- #


def route_text(
    text: str,
    role: str,
    vendor_id: Optional[str] = None,
    *,
    forced_intent: Optional[str] = None,
) -> RouterResult:
    """Classify, gate, extract, dispatch — one round trip, stateless.

    Args:
        text: the user's natural-language utterance (already transcribed if
            it came from voice).
        role: `"customer"`, `"vendor"`, or `"unknown"` (anonymous browse).
        vendor_id: the JWT-derived vendor id when `role == "vendor"`; None
            otherwise. Required for `add/update/delete_product` and
            `get_my_listings` — the dispatcher refuses if it's None.
        forced_intent: skip SBERT classification and use this intent
            directly. Used by `/api/search` (which is *defined* to be
            `search_products`) so we don't pay the model latency twice.

    Returns:
        `RouterResult`. Even errors (no-price, wrong-role) come back as a
        result, never an exception — the HTTP layer translates the result's
        `api_status` to an HTTP code only when it's a true 4xx/5xx, otherwise
        wraps it in HTTP 200 with a friendly reply.
    """
    if forced_intent:
        intent_label, score = forced_intent, 1.0
    else:
        intent_label, score = intents.classify(text)
    if not _is_allowed(intent_label, role):
        result = RouterResult(
            intent=intent_label,
            reply={
                "search_products": "Sign in to search for products.",
                "get_categories": "Sign in to see categories.",
            }.get(
                intent_label,
                f"Only vendors can do that ('{intent_label}').",
            ),
            api_called=None,
            api_status=403,
            meta={"role_denied": role},
        )
    elif intent_label == "search_products":
        result = _handle_search(text, intent_label)
    elif intent_label == "add_product":
        result = _handle_add_product(text, vendor_id)
    elif intent_label == "update_product":
        result = _handle_update_product(text, vendor_id)
    elif intent_label == "delete_product":
        result = _handle_delete_product(text, vendor_id)
    elif intent_label == "get_my_listings":
        result = _handle_get_my_listings(vendor_id)
    elif intent_label == "get_categories":
        result = _handle_get_categories()
    else:
        result = _handle_unknown(text)

    # Stamp the SBERT confidence on the result so HTTP adapters can surface
    # it. Float so JSON-encoding doesn't need a numpy shim.
    result.confidence = float(score)
    return result
