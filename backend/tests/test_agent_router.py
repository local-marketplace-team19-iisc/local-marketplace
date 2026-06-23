"""Unit tests for `backend.app.agent_router.route.route_text`.

These tests pin the dispatch logic (role gating, intent → API binding,
entity → query mapping, error mapping) **without** loading the real SBERT
model. The intent is forced via a `monkeypatch` of `intents.classify`,
which lets us focus on the router's per-intent dispatch rather than the
classifier's accuracy (covered separately in `test_intent_classifier.py`).

The router talks to feature 006's `product_service` against
`SessionLocal()`; here we monkey-patch `SessionLocal` to return the
in-memory SQLite session built by the `catalog_db` fixture (defined in
`conftest.py`), so each test gets a fresh, isolated taxonomy + two
vendors.

Read this file together with `specs/008-sbert-intent-router/spec.md §1`:
each test name maps to one of the six user scenarios + edge cases.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from backend.app.agent_router import intents, route
from backend.app.models.product import Product

SEED_VENDOR_A = "vend-1"
SEED_VENDOR_B = "vend-2"


@pytest.fixture
def patched_session(catalog_db, monkeypatch):
    """Wire `route._db_session` to yield the shared `catalog_db` Session.

    The router uses a context-managed `SessionLocal()` per request; we
    redirect that to the test session so seeded rows and writes are
    visible to every dispatch in the same test.
    """
    from contextlib import contextmanager

    @contextmanager
    def _fake():
        yield catalog_db

    monkeypatch.setattr(route, "_db_session", _fake)
    yield catalog_db


def _seed_products(db):
    """Seed a handful of products across the two vendors for search/update tests."""
    from backend.app.catalog.seed_data import GENERAL_SUBCATEGORY_ID

    def add(vendor_id, name, price, brand="Generic"):
        p = Product(
            subcategory_id=GENERAL_SUBCATEGORY_ID,
            vendor_id=vendor_id,
            product_name=name,
            brand=brand,
            description=name,
            unit_type="PIECE",
            unit_value=Decimal("1"),
            price_inr=Decimal(str(price)),
            stock_quantity=10,
        )
        db.add(p)
        db.commit()
        db.refresh(p)
        return p

    return {
        "iphone": add(SEED_VENDOR_A, "iPhone 15", 57999, brand="Apple"),
        "asus": add(SEED_VENDOR_A, "ASUS ROG Laptop", 89999, brand="ASUS"),
        "milk": add(SEED_VENDOR_B, "Amul Milk 1L", 65, brand="Amul"),
        "rice": add(SEED_VENDOR_B, "Sona Masuri Rice 5kg", 450, brand="India Gate"),
    }


def _force_intent(monkeypatch: pytest.MonkeyPatch, label: str, score: float = 0.9):
    """Pin the classifier's output for a single test."""
    monkeypatch.setattr(intents, "classify", lambda _t: (label, score))


# --------------------------------------------------------------------------- #
# Scenario 1 — customer search with max-price extraction
# --------------------------------------------------------------------------- #


def test_customer_search_with_max_price(patched_session, monkeypatch):
    _seed_products(patched_session)
    _force_intent(monkeypatch, "search_products")
    result = route.route_text("Show me iPhone 15 under ₹60,000", role="customer")
    assert result.intent == "search_products"
    assert result.api_called == "GET /api/products"
    assert result.api_status == 200
    assert result.entities["keywords"] and "iphone" in result.entities["keywords"]
    assert result.entities["max_price"] == 60000.0
    names = [listing["name"] for listing in result.listings]
    assert any("iPhone 15" in n for n in names)


def test_customer_search_empty_query_does_not_error(patched_session, monkeypatch):
    _seed_products(patched_session)
    _force_intent(monkeypatch, "search_products")
    result = route.route_text("show me something", role="customer")
    assert result.intent == "search_products"
    assert result.api_called == "GET /api/products"
    assert result.listings


def test_customer_search_near_me_records_ignored(patched_session, monkeypatch):
    _seed_products(patched_session)
    _force_intent(monkeypatch, "search_products")
    result = route.route_text("find second-hand laptops near me", role="customer")
    assert "near_me" in result.meta.get("ignored", [])


# --------------------------------------------------------------------------- #
# Scenario 3 — vendor add-from-description
# --------------------------------------------------------------------------- #


def test_vendor_add_product_happy(patched_session, monkeypatch):
    _force_intent(monkeypatch, "add_product")
    # NOTE: feature 006's `catalog/parser.py` does not currently handle thousands
    # separators ("₹45,000" parses as 45.00) — tracked upstream. The 008 router
    # itself delegates to 006 here, so we exercise it with a price the
    # upstream parser already accepts.
    result = route.route_text(
        "Add a new Samsung S24 for ₹45000",
        role="vendor",
        vendor_id=SEED_VENDOR_A,
    )
    assert result.intent == "add_product"
    assert result.api_called == "POST /api/products/from-description"
    assert result.api_status == 201
    assert result.entities["price"] == 45000.0
    assert "Samsung S24" in result.listings[0]["name"]


def test_vendor_add_no_price_returns_400_reply(patched_session, monkeypatch):
    _force_intent(monkeypatch, "add_product")
    result = route.route_text(
        "Add a fancy new gadget",
        role="vendor",
        vendor_id=SEED_VENDOR_A,
    )
    assert result.api_status == 400
    assert "price" in result.reply.lower()


def test_customer_add_product_is_blocked_no_api_call(patched_session, monkeypatch):
    _force_intent(monkeypatch, "add_product")
    result = route.route_text(
        "Add a new Samsung S24 for ₹45,000",
        role="customer",
    )
    assert result.api_called is None
    assert result.api_status == 403


# --------------------------------------------------------------------------- #
# Scenario 4 — vendor update (by id + by single-match fallback)
# --------------------------------------------------------------------------- #


def test_vendor_update_by_id(patched_session, monkeypatch):
    seeded = _seed_products(patched_session)
    _force_intent(monkeypatch, "update_product")
    target = str(seeded["iphone"].product_id)
    result = route.route_text(
        f"Update product {target} to ₹50,000",
        role="vendor",
        vendor_id=SEED_VENDOR_A,
    )
    assert result.api_status == 200
    assert result.api_called == f"PUT /api/products/{target}"
    assert result.entities["price"] == 50000.0


def test_vendor_update_no_id_single_match_resolves(patched_session, monkeypatch):
    _seed_products(patched_session)
    _force_intent(monkeypatch, "update_product")
    result = route.route_text(
        "update my iPhone listing to ₹55,000",
        role="vendor",
        vendor_id=SEED_VENDOR_A,
    )
    assert result.api_status == 200
    assert "PUT /api/products/" in (result.api_called or "")


def test_vendor_update_no_id_no_match_asks_for_id(patched_session, monkeypatch):
    _seed_products(patched_session)
    _force_intent(monkeypatch, "update_product")
    result = route.route_text(
        "update my spaceship to ₹999",
        role="vendor",
        vendor_id=SEED_VENDOR_A,
    )
    assert result.api_status == 404
    assert "product ID" in result.reply or "product id" in result.reply.lower()


def test_vendor_update_missing_price_asks_for_one(patched_session, monkeypatch):
    _seed_products(patched_session)
    _force_intent(monkeypatch, "update_product")
    result = route.route_text(
        "update my iPhone listing",
        role="vendor",
        vendor_id=SEED_VENDOR_A,
    )
    assert result.api_status == 400
    assert "price" in result.reply.lower()


# --------------------------------------------------------------------------- #
# Scenario 5 — vendor delete (by id + by description)
# --------------------------------------------------------------------------- #


def test_vendor_delete_by_id(patched_session, monkeypatch):
    seeded = _seed_products(patched_session)
    _force_intent(monkeypatch, "delete_product")
    target = str(seeded["rice"].product_id)
    result = route.route_text(
        f"Delete product {target}",
        role="vendor",
        vendor_id=SEED_VENDOR_B,
    )
    assert result.api_status == 204
    assert result.api_called == f"DELETE /api/products/{target}"


def test_vendor_delete_by_description(patched_session, monkeypatch):
    _seed_products(patched_session)
    _force_intent(monkeypatch, "delete_product")
    result = route.route_text(
        "delete the milk listing",
        role="vendor",
        vendor_id=SEED_VENDOR_B,
    )
    assert result.api_status == 200
    assert result.api_called == "POST /api/products/delete-by-description"
    assert "milk" in result.reply.lower() or "Amul" in result.reply


def test_vendor_delete_by_description_owned_by_other_misses(patched_session, monkeypatch):
    _seed_products(patched_session)
    _force_intent(monkeypatch, "delete_product")
    # Vendor A asks to delete "milk" — only vendor B owns milk, so 404.
    result = route.route_text(
        "delete the milk listing",
        role="vendor",
        vendor_id=SEED_VENDOR_A,
    )
    assert result.api_status == 404


# --------------------------------------------------------------------------- #
# Scenario 6/7 — get_my_listings + get_categories
# --------------------------------------------------------------------------- #


def test_vendor_get_my_listings(patched_session, monkeypatch):
    _seed_products(patched_session)
    _force_intent(monkeypatch, "get_my_listings")
    result = route.route_text("show my listings", role="vendor", vendor_id=SEED_VENDOR_A)
    assert result.api_called == "GET /api/products"
    assert result.listings
    for listing in result.listings:
        assert "iPhone" in listing["name"] or "ASUS" in listing["name"]


def test_customer_get_categories(patched_session, monkeypatch):
    _force_intent(monkeypatch, "get_categories")
    result = route.route_text("what categories do you have", role="customer")
    assert result.api_called == "GET /api/catalog/categories"
    # The 006 taxonomy includes "General", "Groceries", "Vegetables", etc.
    assert result.meta["categories"]
    assert any(c.lower() in result.reply.lower() for c in result.meta["categories"])


# --------------------------------------------------------------------------- #
# Scenario 8 — unknown
# --------------------------------------------------------------------------- #


def test_unknown_does_not_call_api(patched_session, monkeypatch):
    _force_intent(monkeypatch, "unknown", score=0.2)
    result = route.route_text("what's the weather tomorrow?", role="customer")
    assert result.intent == "unknown"
    assert result.api_called is None
    assert "search" in result.reply.lower() or "help" in result.reply.lower()


# --------------------------------------------------------------------------- #
# Cross-vendor protection — A can't update/delete B's products
# --------------------------------------------------------------------------- #


def test_cross_vendor_update_forbidden(patched_session, monkeypatch):
    seeded = _seed_products(patched_session)
    _force_intent(monkeypatch, "update_product")
    target = str(seeded["rice"].product_id)  # owned by B
    result = route.route_text(
        f"update product {target} to ₹999",
        role="vendor",
        vendor_id=SEED_VENDOR_A,  # A trying to touch B's row
    )
    assert result.api_status == 403


def test_cross_vendor_delete_forbidden(patched_session, monkeypatch):
    seeded = _seed_products(patched_session)
    _force_intent(monkeypatch, "delete_product")
    target = str(seeded["rice"].product_id)  # owned by B
    result = route.route_text(
        f"delete product {target}",
        role="vendor",
        vendor_id=SEED_VENDOR_A,
    )
    assert result.api_status == 403
