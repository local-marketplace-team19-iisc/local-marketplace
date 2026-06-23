"""Concurrency tests for place_order (feature 007).

Two scenarios are covered:

1. test_concurrent_purchase_one_wins_one_loses  (ThreadPoolExecutor, Barrier)
   Both buyers submit simultaneously. Proves that regardless of which thread
   wins the SQLite write lock, exactly one order is created and stock reaches
   zero — no double-selling.

2. test_serial_depletion_raises_out_of_stock  (deterministic)
   Buyer A exhausts the last unit. Buyer B's subsequent call must raise
   OutOfStockError with the correct diagnostic attributes.

SQLite vs PostgreSQL note
--------------------------
with_for_update() is a no-op on SQLite; SQLite serialises writers via a
database-level write lock instead. On PostgreSQL (production) the FOR UPDATE
row lock provides identical single-winner semantics with row-level precision.
The stock_quantity == 0 assertion is the canonical proof of correctness on
both engines.
"""

import threading
import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import backend.app.models  # noqa: F401 — registers all ORM classes with Base
from backend.app.db.session import Base
from backend.app.models.product import Product
from backend.app.models.user import User, UserRole
from backend.app.models.vendor import Vendor
from backend.app.services.order_service import (
    OrderError,
    OrderLineItem,
    OutOfStockError,
    place_order,
)

# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------

INITIAL_STOCK = 1
ORDER_QTY = 1
PRODUCT_PRICE = "99.00"


@pytest.fixture
def concurrency_db(tmp_path):
    """Isolated file-based SQLite engine seeded with the minimum data needed.

    Yields:
        (engine, SessionFactory, ids) where ids is a dict with
        buyer_a_id, buyer_b_id, vendor_id, product_id.

    File-based (not :memory:) so separate per-thread connections share the
    same on-disk state — required for cross-thread transaction visibility.
    """
    db_path = tmp_path / "concurrency_test.db"
    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
        echo=False,
    )
    Base.metadata.create_all(engine)
    SessionFactory = sessionmaker(bind=engine)

    # ---- seed ----
    seed = SessionFactory()

    buyer_a_id = str(uuid.uuid4())
    buyer_b_id = str(uuid.uuid4())
    vendor_user_id = str(uuid.uuid4())
    vendor_id = str(uuid.uuid4())
    product_id = str(uuid.uuid4())

    seed.add(User(
        id=buyer_a_id, email="buyer_a@test.com",
        password_hash="x", role=UserRole.customer.value,
    ))
    seed.add(User(
        id=buyer_b_id, email="buyer_b@test.com",
        password_hash="x", role=UserRole.customer.value,
    ))
    seed.add(User(
        id=vendor_user_id, email="vendor@test.com",
        password_hash="x", role=UserRole.vendor.value,
    ))
    seed.flush()

    seed.add(Vendor(
        id=vendor_id, user_id=vendor_user_id,
        shop_name="Concurrency Test Shop",
        shop_location_lat=12.9716, shop_location_lon=77.5946,
    ))
    seed.flush()

    seed.add(Product(
        product_id=product_id,
        subcategory_id=str(uuid.uuid4()),   # soft FK; SQLite won't enforce
        product_name="Last-Unit Widget",
        brand="TestBrand",
        description="Only one in stock — perfect for race-condition tests.",
        unit_type="PIECE",
        unit_value="1.000",
        price_inr=PRODUCT_PRICE,
        vendor_id=vendor_id,
        stock_quantity=INITIAL_STOCK,       # exactly 1 unit
    ))
    seed.commit()
    seed.close()

    yield engine, SessionFactory, {
        "buyer_a_id": buyer_a_id,
        "buyer_b_id": buyer_b_id,
        "product_id": product_id,
    }

    engine.dispose()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _stock(SessionFactory, product_id: str) -> int:
    """Read the current stock_quantity for product_id in a fresh session."""
    db = SessionFactory()
    try:
        row = db.query(Product).filter(Product.product_id == product_id).first()
        return row.stock_quantity
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Test 1 — true concurrent execution
# ---------------------------------------------------------------------------

def test_concurrent_purchase_one_wins_one_loses(concurrency_db):
    """Submitting two simultaneous orders for a single remaining unit must result
    in exactly one success and one failure, with final stock == 0.

    The threading.Barrier synchronises both threads so they call place_order
    at the same instant, maximising the overlap window for lock contention.

    On SQLite the loser receives either:
    - OutOfStockError  — when it reads after the winner commits (stock = 0)
    - OrderError       — when it collides on the write lock (wrapped OperationalError)

    Both are valid; the stock == 0 assertion is the definitive correctness proof.
    """
    engine, SessionFactory, ids = concurrency_db
    buyer_a_id = ids["buyer_a_id"]
    buyer_b_id = ids["buyer_b_id"]
    product_id = ids["product_id"]

    barrier = threading.Barrier(2)   # both threads start place_order together

    def attempt_order(user_id: str):
        """Each thread owns its own Session — sessions are not thread-safe to share."""
        db = SessionFactory()
        try:
            barrier.wait(timeout=5)          # synchronise thread entry
            order_id = place_order(
                db,
                user_id=user_id,
                items=[OrderLineItem(product_id=product_id, quantity=ORDER_QTY)],
            )
            return ("success", order_id)
        except (OutOfStockError, OrderError) as exc:
            return ("failure", exc)
        finally:
            db.close()

    with ThreadPoolExecutor(max_workers=2) as executor:
        fut_a = executor.submit(attempt_order, buyer_a_id)
        fut_b = executor.submit(attempt_order, buyer_b_id)
        result_a = fut_a.result(timeout=10)
        result_b = fut_b.result(timeout=10)

    results = [result_a, result_b]
    successes = [r for r in results if r[0] == "success"]
    failures  = [r for r in results if r[0] == "failure"]

    # -- winner invariant --
    assert len(successes) == 1, (
        f"Expected exactly 1 successful order, got {len(successes)}. "
        f"Possible double-sell! Results: {results}"
    )

    # -- loser invariant --
    assert len(failures) == 1, (
        f"Expected exactly 1 failure, got {len(failures)}. Results: {results}"
    )

    # The winning order_id must be a 36-character UUID string.
    winning_order_id = successes[0][1]
    assert len(winning_order_id) == 36, (
        f"Order ID is not UUID-shaped: {winning_order_id!r}"
    )

    # The loser must have raised a recognised order error (OutOfStockError is a
    # subclass of OrderError, so this single isinstance covers both).
    losing_exc = failures[0][1]
    assert isinstance(losing_exc, OrderError), (
        f"Expected OrderError (or subclass), got {type(losing_exc).__name__}: {losing_exc}"
    )

    # -- database state invariant (the canonical no-double-sell proof) --
    final_stock = _stock(SessionFactory, product_id)
    assert final_stock == 0, (
        f"Expected stock=0 after exactly one purchase of the last unit, "
        f"got stock={final_stock}. A double-sell may have occurred."
    )


# ---------------------------------------------------------------------------
# Test 2 — deterministic depletion → OutOfStockError
# ---------------------------------------------------------------------------

def test_serial_depletion_raises_out_of_stock(concurrency_db):
    """After Buyer A purchases the last unit, Buyer B's call must raise
    OutOfStockError with accurate diagnostic attributes.

    This test is deterministic: A completes before B starts, so B is guaranteed
    to read stock=0 and trigger the guard in place_order.
    """
    engine, SessionFactory, ids = concurrency_db
    buyer_a_id = ids["buyer_a_id"]
    buyer_b_id = ids["buyer_b_id"]
    product_id = ids["product_id"]

    db_a = SessionFactory()
    db_b = SessionFactory()
    try:
        # -- Buyer A exhausts the last unit --
        with ThreadPoolExecutor(max_workers=1) as executor:
            fut = executor.submit(
                place_order, db_a, buyer_a_id,
                [OrderLineItem(product_id=product_id, quantity=ORDER_QTY)],
            )
            order_id = fut.result(timeout=10)

        assert order_id and len(order_id) == 36, (
            f"Buyer A should have received a valid order_id, got {order_id!r}"
        )
        assert _stock(SessionFactory, product_id) == 0

        # -- Buyer B attempts to buy the now-depleted product --
        with pytest.raises(OutOfStockError) as exc_info:
            place_order(
                db_b,
                user_id=buyer_b_id,
                items=[OrderLineItem(product_id=product_id, quantity=ORDER_QTY)],
            )

        exc = exc_info.value
        assert exc.product_id == product_id, (
            f"OutOfStockError.product_id mismatch: {exc.product_id!r}"
        )
        assert exc.requested == ORDER_QTY, (
            f"OutOfStockError.requested should be {ORDER_QTY}, got {exc.requested}"
        )
        assert exc.available == 0, (
            f"OutOfStockError.available should be 0 (stock depleted), got {exc.available}"
        )

        # -- stock remains zero after the failed attempt --
        assert _stock(SessionFactory, product_id) == 0

    finally:
        db_a.close()
        db_b.close()
