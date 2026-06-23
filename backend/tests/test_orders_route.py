"""Endpoint + service tests for `/api/orders` (V1 customer orders).

Covered behaviour (per the user-approved V1 scope, 2026-06-23):

  * `POST /api/orders` happy path — creates Order + OrderItems, decrements
    stock, returns the projection envelope the frontend consumes.
  * Empty / malformed cart → 400.
  * Unknown product → 404.
  * Insufficient stock → 409 (all-or-nothing, all offending lines reported).
  * Vendor calling either endpoint → 403.
  * Anonymous caller → 401.
  * `GET /api/orders` returns the customer's own orders newest-first, and
    never leaks another customer's orders.

We build a **thread-safe** SQLite engine here (StaticPool +
`check_same_thread=False`) because `TestClient` runs the request in a
separate thread from the test body, and the default sqlite3 driver refuses
to share Connections across threads. The fixtures yield a Session bound to
that engine and monkey-patch `orders_route.SessionLocal` to hand out
sessions from the same engine.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.api.routes import orders as orders_route
from backend.app.db.session import Base
from backend.app.main import app
from backend.app.models.product import Product
from backend.app.models.user import User
from backend.app.models.vendor import Vendor
from backend.app.services import auth_service, order_service

client = TestClient(app)

CUSTOMER_ID = "cust-1"
OTHER_CUSTOMER_ID = "cust-2"
VENDOR_ID = "vend-1"


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #
@pytest.fixture
def thread_safe_db(monkeypatch):
    """A SQLite engine usable across the TestClient request thread.

    The default sqlite3 driver rejects cross-thread Connection use; we
    disable that check and use a StaticPool so every Session sees the same
    in-memory database. The fixture also monkey-patches the orders route's
    `SessionLocal` so the route hits this engine for the duration of the
    test.
    """
    from backend.app import models  # noqa: F401  ensures all tables register

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine)

    monkeypatch.setattr(orders_route, "SessionLocal", TestSession)

    db = TestSession()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def seeded_customer(thread_safe_db):
    """Two customer users so we can prove order ownership isolation."""
    thread_safe_db.add(
        User(id=CUSTOMER_ID, email="c1@example.com", role="customer")
    )
    thread_safe_db.add(
        User(id=OTHER_CUSTOMER_ID, email="c2@example.com", role="customer")
    )
    thread_safe_db.commit()
    return CUSTOMER_ID


@pytest.fixture
def seeded_products(thread_safe_db, seeded_customer):  # noqa: ARG001
    """Two products on vendor-1 (auto-seeded) with known stock."""
    from backend.app.catalog.seed_data import (
        GENERAL_CATEGORY_ID,
        GENERAL_SUBCATEGORY_ID,
        iter_categories,
        iter_subcategories,
    )
    from backend.app.models.category import Category
    from backend.app.models.subcategory import SubCategory

    # Seed taxonomy (required for the FK from products → subcategories)
    if not thread_safe_db.query(Category).filter_by(category_id=GENERAL_CATEGORY_ID).first():
        for row in iter_categories():
            thread_safe_db.add(Category(**row))
        for row in iter_subcategories():
            thread_safe_db.add(SubCategory(**row))

    # Need a vendor row referenced by the products
    thread_safe_db.add(
        Vendor(
            id=VENDOR_ID,
            user_id="vendor-user-1",
            shop_name="Shop One",
            shop_location_lat=0.0,
            shop_location_lon=0.0,
        )
    )
    # The vendor's owning user must exist (users.id FK)
    thread_safe_db.add(
        User(id="vendor-user-1", email="v@example.com", role="vendor")
    )

    juice = Product(
        product_id="prod-juice",
        subcategory_id=GENERAL_SUBCATEGORY_ID,
        vendor_id=VENDOR_ID,
        product_name="orange juice",
        brand="Generic",
        description="orange juice 1L",
        unit_type="PIECE",
        unit_value=Decimal("1"),
        price_inr=Decimal("120.00"),
        stock_quantity=5,
    )
    milk = Product(
        product_id="prod-milk",
        subcategory_id=GENERAL_SUBCATEGORY_ID,
        vendor_id=VENDOR_ID,
        product_name="amul milk",
        brand="Amul",
        description="amul milk 1L",
        unit_type="PIECE",
        unit_value=Decimal("1"),
        price_inr=Decimal("29.00"),
        stock_quantity=1,
    )
    thread_safe_db.add_all([juice, milk])
    thread_safe_db.commit()
    return {"juice": juice, "milk": milk}


@pytest.fixture
def customer_principal(monkeypatch):
    principal = {
        "id": CUSTOMER_ID,
        "email": "c1@example.com",
        "user_type": "customer",
    }

    def _stub(_db, token):
        if not token:
            raise auth_service.AuthUnauthorizedError("Empty token")
        return principal

    monkeypatch.setattr(auth_service, "get_current_user", _stub)
    return principal


@pytest.fixture
def vendor_principal(monkeypatch):
    principal = {
        "id": "user-v",
        "email": "v@example.com",
        "user_type": "vendor",
        "vendor_id": VENDOR_ID,
    }

    def _stub(_db, token):
        if not token:
            raise auth_service.AuthUnauthorizedError("Empty token")
        return principal

    monkeypatch.setattr(auth_service, "get_current_user", _stub)
    return principal


def _auth() -> dict[str, str]:
    return {"Authorization": "Bearer fake"}


# --------------------------------------------------------------------------- #
# Service-level tests (no HTTP — fast, focused)
# --------------------------------------------------------------------------- #
class TestOrderService:
    def test_place_order_happy_path(self, thread_safe_db, seeded_products):  # noqa: ARG002
        order = order_service.place_order(
            thread_safe_db,
            customer_id=CUSTOMER_ID,
            items=[{"productId": "prod-juice", "qty": 2}],
        )
        assert order.order_number.startswith("ORD-")
        assert Decimal(order.total_inr) == Decimal("240.00")
        assert len(order.items) == 1
        assert order.items[0].product_name_snapshot == "orange juice"
        assert order.items[0].qty == 2
        # Stock decremented from 5 to 3
        juice = thread_safe_db.query(Product).filter_by(product_id="prod-juice").one()
        assert juice.stock_quantity == 3

    def test_place_order_multi_vendor_sums_correctly(
        self, thread_safe_db, seeded_products  # noqa: ARG002
    ):
        order = order_service.place_order(
            thread_safe_db,
            customer_id=CUSTOMER_ID,
            items=[
                {"productId": "prod-juice", "qty": 1},
                {"productId": "prod-milk", "qty": 1},
            ],
        )
        assert Decimal(order.total_inr) == Decimal("149.00")
        assert len(order.items) == 2

    def test_empty_cart_rejected(self, thread_safe_db, seeded_products):  # noqa: ARG002
        with pytest.raises(order_service.OrderValidationError):
            order_service.place_order(thread_safe_db, customer_id=CUSTOMER_ID, items=[])

    def test_unknown_product_rejected(self, thread_safe_db, seeded_products):  # noqa: ARG002
        with pytest.raises(order_service.OrderNotFoundError):
            order_service.place_order(
                thread_safe_db,
                customer_id=CUSTOMER_ID,
                items=[{"productId": "does-not-exist", "qty": 1}],
            )

    def test_insufficient_stock_rejected_all_or_nothing(
        self, thread_safe_db, seeded_products  # noqa: ARG002
    ):
        with pytest.raises(order_service.OrderOutOfStockError) as exc:
            order_service.place_order(
                thread_safe_db,
                customer_id=CUSTOMER_ID,
                items=[
                    {"productId": "prod-juice", "qty": 1},  # ok
                    {"productId": "prod-milk", "qty": 10},  # not ok (stock=1)
                ],
            )
        # No partial application: juice stock untouched, no order rows persisted.
        assert exc.value.lines[0]["product_name"] == "amul milk"
        juice = thread_safe_db.query(Product).filter_by(product_id="prod-juice").one()
        assert juice.stock_quantity == 5
        from backend.app.models.order import Order

        assert thread_safe_db.query(Order).count() == 0


# --------------------------------------------------------------------------- #
# Endpoint tests
# --------------------------------------------------------------------------- #
class TestPostOrders:
    def test_requires_bearer(self, thread_safe_db, seeded_products):  # noqa: ARG002
        r = client.post("/api/orders", json={"items": []})
        assert r.status_code == 401

    def test_vendor_forbidden(
        self, thread_safe_db, seeded_products, vendor_principal  # noqa: ARG002
    ):
        r = client.post(
            "/api/orders",
            json={"items": [{"productId": "prod-juice", "qty": 1}]},
            headers=_auth(),
        )
        assert r.status_code == 403

    def test_happy_path_returns_201_with_order_envelope(
        self, thread_safe_db, seeded_products, customer_principal  # noqa: ARG002
    ):
        r = client.post(
            "/api/orders",
            json={"items": [{"productId": "prod-juice", "qty": 1}]},
            headers=_auth(),
        )
        assert r.status_code == 201
        body = r.json()
        assert "order" in body
        order = body["order"]
        assert order["orderNumber"].startswith("ORD-")
        assert order["total"] == 120.0
        assert order["status"] == "placed"
        assert len(order["items"]) == 1
        assert order["items"][0]["name"] == "orange juice"
        assert order["items"][0]["qty"] == 1
        assert "Shop One" in order["vendors"]

    def test_empty_cart_returns_400(
        self, thread_safe_db, seeded_products, customer_principal  # noqa: ARG002
    ):
        r = client.post("/api/orders", json={"items": []}, headers=_auth())
        assert r.status_code == 400

    def test_unknown_product_returns_404(
        self, thread_safe_db, seeded_products, customer_principal  # noqa: ARG002
    ):
        r = client.post(
            "/api/orders",
            json={"items": [{"productId": "no-such", "qty": 1}]},
            headers=_auth(),
        )
        assert r.status_code == 404

    def test_insufficient_stock_returns_409_with_offending_lines(
        self, thread_safe_db, seeded_products, customer_principal  # noqa: ARG002
    ):
        r = client.post(
            "/api/orders",
            json={"items": [{"productId": "prod-milk", "qty": 99}]},
            headers=_auth(),
        )
        assert r.status_code == 409
        detail = r.json()["detail"]
        assert "lines" in detail
        assert detail["lines"][0]["product_name"] == "amul milk"
        assert detail["lines"][0]["requested"] == 99
        assert detail["lines"][0]["available"] == 1

    def test_legacy_vendor_id_field_is_ignored(
        self, thread_safe_db, seeded_products, customer_principal  # noqa: ARG002
    ):
        """Old frontend used to send vendorId; backend now authoritative."""
        r = client.post(
            "/api/orders",
            json={
                "items": [
                    {
                        "productId": "prod-juice",
                        "vendorId": "wrong-vendor",
                        "qty": 1,
                    }
                ]
            },
            headers=_auth(),
        )
        assert r.status_code == 201
        assert r.json()["order"]["items"][0]["vendorId"] == VENDOR_ID


class TestGetOrders:
    def test_requires_bearer(self, thread_safe_db, seeded_products):  # noqa: ARG002
        r = client.get("/api/orders")
        assert r.status_code == 401

    def test_vendor_forbidden(
        self, thread_safe_db, seeded_products, vendor_principal  # noqa: ARG002
    ):
        r = client.get("/api/orders", headers=_auth())
        assert r.status_code == 403

    def test_empty_history_returns_empty_list(
        self, thread_safe_db, seeded_products, customer_principal  # noqa: ARG002
    ):
        r = client.get("/api/orders", headers=_auth())
        assert r.status_code == 200
        assert r.json() == {"orders": []}

    def test_returns_own_orders_newest_first(
        self,
        thread_safe_db,
        seeded_products,  # noqa: ARG002
        customer_principal,  # noqa: ARG002
    ):
        order_service.place_order(
            thread_safe_db,
            customer_id=CUSTOMER_ID,
            items=[{"productId": "prod-juice", "qty": 1}],
        )
        order_service.place_order(
            thread_safe_db,
            customer_id=CUSTOMER_ID,
            items=[{"productId": "prod-milk", "qty": 1}],
        )
        # One order for the *other* customer (must not leak)
        order_service.place_order(
            thread_safe_db,
            customer_id=OTHER_CUSTOMER_ID,
            items=[{"productId": "prod-juice", "qty": 1}],
        )

        r = client.get("/api/orders", headers=_auth())
        assert r.status_code == 200
        payload = r.json()["orders"]
        assert len(payload) == 2  # not 3 — other customer's order excluded
        # Newest first → milk order is the most recent
        assert payload[0]["items"][0]["name"] == "amul milk"
        assert payload[1]["items"][0]["name"] == "orange juice"
