"""Endpoint + service tests for `/api/vendor/orders` (vendor order history).

Covered behaviour:
  * Multi-vendor order is partitioned: each vendor sees only its own lines
    and its own subtotal; the other vendor's items never appear.
  * `otherVendorsCount` reports the number of OTHER shops on the order
    (no names — privacy decision D-007-1).
  * Snapshot stability: deleting the underlying Product after the order
    was placed does not strip the line out of the vendor's history; the
    `product_name_snapshot` / `brand_snapshot` carry through.
  * Single-vendor orders work too (orderVendorsCount == 0).
  * Newest-first ordering.
  * `customer` block exposes only id + email — never full name / phone.
  * Customer calling the endpoint → 403. Anonymous → 401.

Fixtures mirror `test_orders_route.py`'s thread-safe SQLite pattern so
TestClient can share an in-memory DB across the request thread.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.api.routes import vendor_orders as vendor_orders_route
from backend.app.db.session import Base
from backend.app.main import app
from backend.app.models.product import Product
from backend.app.models.user import User
from backend.app.models.vendor import Vendor
from backend.app.services import auth_service, order_service

client = TestClient(app)

CUSTOMER_ID = "cust-a"
OTHER_CUSTOMER_ID = "cust-b"
VENDOR_A_ID = "vend-a"
VENDOR_B_ID = "vend-b"


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #
@pytest.fixture
def thread_safe_db(monkeypatch):
    """Same pattern as test_orders_route: shared in-memory engine across threads."""
    from backend.app import models  # noqa: F401  ensures all tables register

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine)

    monkeypatch.setattr(vendor_orders_route, "SessionLocal", TestSession)

    db = TestSession()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def seeded_world(thread_safe_db):
    """Two vendors, two products per vendor, one customer.

    The catalog taxonomy is seeded too because Product.subcategory_id is a FK.
    """
    from backend.app.catalog.seed_data import (
        GENERAL_CATEGORY_ID,
        GENERAL_SUBCATEGORY_ID,
        iter_categories,
        iter_subcategories,
    )
    from backend.app.models.category import Category
    from backend.app.models.subcategory import SubCategory

    if not thread_safe_db.query(Category).filter_by(category_id=GENERAL_CATEGORY_ID).first():
        for row in iter_categories():
            thread_safe_db.add(Category(**row))
        for row in iter_subcategories():
            thread_safe_db.add(SubCategory(**row))

    # Users — one customer (does the buying), two vendor owners.
    thread_safe_db.add(
        User(id=CUSTOMER_ID, email="alice@example.com", role="customer")
    )
    thread_safe_db.add(
        User(id=OTHER_CUSTOMER_ID, email="bob@example.com", role="customer")
    )
    thread_safe_db.add(
        User(id="vendor-user-a", email="shop-a@example.com", role="vendor")
    )
    thread_safe_db.add(
        User(id="vendor-user-b", email="shop-b@example.com", role="vendor")
    )

    thread_safe_db.add(
        Vendor(
            id=VENDOR_A_ID,
            user_id="vendor-user-a",
            shop_name="Shop A",
            shop_location_lat=0.0,
            shop_location_lon=0.0,
        )
    )
    thread_safe_db.add(
        Vendor(
            id=VENDOR_B_ID,
            user_id="vendor-user-b",
            shop_name="Shop B",
            shop_location_lat=0.0,
            shop_location_lon=0.0,
        )
    )

    juice_a = Product(
        product_id="prod-a-juice",
        subcategory_id=GENERAL_SUBCATEGORY_ID,
        vendor_id=VENDOR_A_ID,
        product_name="orange juice",
        brand="A-Brand",
        description="A's orange juice",
        unit_type="PIECE",
        unit_value=Decimal("1"),
        price_inr=Decimal("100.00"),
        stock_quantity=10,
    )
    milk_b = Product(
        product_id="prod-b-milk",
        subcategory_id=GENERAL_SUBCATEGORY_ID,
        vendor_id=VENDOR_B_ID,
        product_name="amul milk",
        brand="B-Brand",
        description="B's milk",
        unit_type="PIECE",
        unit_value=Decimal("1"),
        price_inr=Decimal("50.00"),
        stock_quantity=10,
    )
    thread_safe_db.add_all([juice_a, milk_b])
    thread_safe_db.commit()
    return {"juice_a": juice_a, "milk_b": milk_b}


@pytest.fixture
def vendor_a_principal(monkeypatch):
    principal = {
        "id": "vendor-user-a",
        "email": "shop-a@example.com",
        "user_type": "vendor",
        "vendor_id": VENDOR_A_ID,
    }

    def _stub(_db, token):
        if not token:
            raise auth_service.AuthUnauthorizedError("Empty token")
        return principal

    monkeypatch.setattr(auth_service, "get_current_user", _stub)
    return principal


@pytest.fixture
def vendor_b_principal(monkeypatch):
    principal = {
        "id": "vendor-user-b",
        "email": "shop-b@example.com",
        "user_type": "vendor",
        "vendor_id": VENDOR_B_ID,
    }

    def _stub(_db, token):
        if not token:
            raise auth_service.AuthUnauthorizedError("Empty token")
        return principal

    monkeypatch.setattr(auth_service, "get_current_user", _stub)
    return principal


@pytest.fixture
def customer_principal(monkeypatch):
    principal = {
        "id": CUSTOMER_ID,
        "email": "alice@example.com",
        "user_type": "customer",
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
# Service-level tests
# --------------------------------------------------------------------------- #
class TestVendorOrderService:
    def test_partitions_a_multi_vendor_order(self, thread_safe_db, seeded_world):  # noqa: ARG002
        # Customer places ONE order spanning both vendors.
        order_service.place_order(
            thread_safe_db,
            customer_id=CUSTOMER_ID,
            items=[
                {"productId": "prod-a-juice", "qty": 2},  # vendor A
                {"productId": "prod-b-milk", "qty": 3},   # vendor B
            ],
        )

        # Vendor A sees only A's line; subtotal is 200; otherVendorsCount = 1.
        a_orders = order_service.list_orders_for_vendor(
            thread_safe_db, vendor_id=VENDOR_A_ID
        )
        assert len(a_orders) == 1
        a_view = order_service.project_orders_for_vendor(
            thread_safe_db, a_orders, vendor_id=VENDOR_A_ID
        )
        assert len(a_view) == 1
        a = a_view[0]
        assert {ln["productId"] for ln in a["items"]} == {"prod-a-juice"}
        assert a["vendorSubtotal"] == 200.0
        assert a["otherVendorsCount"] == 1
        assert a["customer"] == {"id": CUSTOMER_ID, "email": "alice@example.com"}

        # Vendor B sees only B's line; subtotal is 150; otherVendorsCount = 1.
        b_orders = order_service.list_orders_for_vendor(
            thread_safe_db, vendor_id=VENDOR_B_ID
        )
        b_view = order_service.project_orders_for_vendor(
            thread_safe_db, b_orders, vendor_id=VENDOR_B_ID
        )
        assert len(b_view) == 1
        b = b_view[0]
        assert {ln["productId"] for ln in b["items"]} == {"prod-b-milk"}
        assert b["vendorSubtotal"] == 150.0
        assert b["otherVendorsCount"] == 1
        # Same order_number for both vendor views — single checkout.
        assert a["orderNumber"] == b["orderNumber"]

    def test_single_vendor_order_reports_zero_other_vendors(
        self, thread_safe_db, seeded_world  # noqa: ARG002
    ):
        order_service.place_order(
            thread_safe_db,
            customer_id=CUSTOMER_ID,
            items=[{"productId": "prod-a-juice", "qty": 1}],
        )
        orders = order_service.list_orders_for_vendor(
            thread_safe_db, vendor_id=VENDOR_A_ID
        )
        view = order_service.project_orders_for_vendor(
            thread_safe_db, orders, vendor_id=VENDOR_A_ID
        )
        assert view[0]["otherVendorsCount"] == 0

    def test_other_vendor_is_invisible(self, thread_safe_db, seeded_world):  # noqa: ARG002
        # Order placed exclusively against vendor A.
        order_service.place_order(
            thread_safe_db,
            customer_id=CUSTOMER_ID,
            items=[{"productId": "prod-a-juice", "qty": 1}],
        )
        # Vendor B has no business seeing it.
        b_view = order_service.project_orders_for_vendor(
            thread_safe_db,
            order_service.list_orders_for_vendor(thread_safe_db, vendor_id=VENDOR_B_ID),
            vendor_id=VENDOR_B_ID,
        )
        assert b_view == []

    def test_snapshots_survive_product_delete(
        self, thread_safe_db, seeded_world  # noqa: ARG001
    ):
        # Place an order, then delete the underlying product (vendor cleanup).
        order_service.place_order(
            thread_safe_db,
            customer_id=CUSTOMER_ID,
            items=[{"productId": "prod-a-juice", "qty": 1}],
        )
        product = thread_safe_db.query(Product).filter_by(product_id="prod-a-juice").one()
        thread_safe_db.delete(product)
        thread_safe_db.commit()

        view = order_service.project_orders_for_vendor(
            thread_safe_db,
            order_service.list_orders_for_vendor(thread_safe_db, vendor_id=VENDOR_A_ID),
            vendor_id=VENDOR_A_ID,
        )
        assert len(view) == 1
        line = view[0]["items"][0]
        # Snapshot is preserved even though productId FK is now SET NULL.
        assert line["name"] == "orange juice"
        assert line["brand"] == "A-Brand"

    def test_newest_first_ordering(self, thread_safe_db, seeded_world):  # noqa: ARG002
        first = order_service.place_order(
            thread_safe_db,
            customer_id=CUSTOMER_ID,
            items=[{"productId": "prod-a-juice", "qty": 1}],
        )
        second = order_service.place_order(
            thread_safe_db,
            customer_id=CUSTOMER_ID,
            items=[{"productId": "prod-a-juice", "qty": 1}],
        )
        view = order_service.project_orders_for_vendor(
            thread_safe_db,
            order_service.list_orders_for_vendor(thread_safe_db, vendor_id=VENDOR_A_ID),
            vendor_id=VENDOR_A_ID,
        )
        assert [o["orderNumber"] for o in view] == [
            second.order_number,
            first.order_number,
        ]


# --------------------------------------------------------------------------- #
# Endpoint tests (auth gating + happy path)
# --------------------------------------------------------------------------- #
class TestVendorOrdersEndpoint:
    def test_happy_path(self, thread_safe_db, seeded_world, vendor_a_principal):  # noqa: ARG002
        order_service.place_order(
            thread_safe_db,
            customer_id=CUSTOMER_ID,
            items=[
                {"productId": "prod-a-juice", "qty": 1},
                {"productId": "prod-b-milk", "qty": 2},
            ],
        )
        res = client.get("/api/vendor/orders", headers=_auth())
        assert res.status_code == 200
        body = res.json()
        assert "orders" in body
        assert len(body["orders"]) == 1
        order = body["orders"][0]
        assert {ln["productId"] for ln in order["items"]} == {"prod-a-juice"}
        assert order["otherVendorsCount"] == 1
        # Customer payload is minimal — no full name, phone, address.
        assert set(order["customer"].keys()) == {"id", "email"}

    def test_customer_is_forbidden(self, thread_safe_db, seeded_world, customer_principal):  # noqa: ARG002
        res = client.get("/api/vendor/orders", headers=_auth())
        assert res.status_code == 403

    def test_anonymous_is_unauthorized(self, thread_safe_db, seeded_world):  # noqa: ARG002
        res = client.get("/api/vendor/orders")
        assert res.status_code == 401

    def test_other_vendor_is_isolated(
        self, thread_safe_db, seeded_world, vendor_b_principal  # noqa: ARG002
    ):
        # Order on vendor A; vendor B asks for their orders → empty.
        order_service.place_order(
            thread_safe_db,
            customer_id=CUSTOMER_ID,
            items=[{"productId": "prod-a-juice", "qty": 1}],
        )
        res = client.get("/api/vendor/orders", headers=_auth())
        assert res.status_code == 200
        assert res.json() == {"orders": []}
