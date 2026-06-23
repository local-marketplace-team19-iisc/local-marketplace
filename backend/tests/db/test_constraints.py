"""
M4 — Isolated constraint verification tests.

Every test uses the `db_session` fixture (function-scoped, always rolled back).
CASCADE and SET NULL tests use raw SQL DELETEs to bypass ORM cascades and
exercise the DB-level ON DELETE rules directly.
"""
import uuid
from decimal import Decimal

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError, ProgrammingError

from backend.app.models.models import (
    Cart,
    CartLine,
    Category,
    Inventory,
    Order,
    OrderLine,
    Product,
    User,
    Vendor,
)
from backend.tests.db.conftest import build_chain


# ---------------------------------------------------------------------------
# CHECK constraints
# ---------------------------------------------------------------------------

async def test_check_inventory_stock_negative(db_session):
    """stock_quantity = -1 violates CHECK (stock_quantity >= 0)."""
    uid = uuid.uuid4
    cat = Category(id=uid(), name=f"c-{uid()}")
    vendor = Vendor(id=uid(), name="v")
    db_session.add_all([cat, vendor])
    await db_session.flush()
    product = Product(id=uid(), category_id=cat.id, name="p")
    db_session.add(product)
    await db_session.flush()

    inv = Inventory(
        id=uid(),
        vendor_id=vendor.id,
        product_id=product.id,
        price=Decimal("1.00"),
        stock_quantity=-1,
    )
    db_session.add(inv)
    with pytest.raises(IntegrityError):
        await db_session.flush()
    await db_session.rollback()


async def test_check_inventory_price_negative(db_session):
    """price = -0.01 violates CHECK (price >= 0)."""
    uid = uuid.uuid4
    cat = Category(id=uid(), name=f"c-{uid()}")
    vendor = Vendor(id=uid(), name="v")
    db_session.add_all([cat, vendor])
    await db_session.flush()
    product = Product(id=uid(), category_id=cat.id, name="p")
    db_session.add(product)
    await db_session.flush()

    inv = Inventory(
        id=uid(),
        vendor_id=vendor.id,
        product_id=product.id,
        price=Decimal("-0.01"),
        stock_quantity=5,
    )
    db_session.add(inv)
    with pytest.raises(IntegrityError):
        await db_session.flush()
    await db_session.rollback()


async def test_check_cart_line_quantity_zero(db_session):
    """CartLine quantity = 0 violates CHECK (quantity > 0)."""
    e = await build_chain(db_session)
    line = CartLine(id=uuid.uuid4(), cart_id=e.cart.id, inventory_id=e.inventory.id, quantity=0)
    db_session.add(line)
    with pytest.raises(IntegrityError):
        await db_session.flush()
    await db_session.rollback()


async def test_check_order_line_quantity_zero(db_session):
    """OrderLine quantity = 0 violates CHECK (quantity > 0)."""
    e = await build_chain(db_session)
    line = OrderLine(
        id=uuid.uuid4(),
        order_id=e.order.id,
        vendor_id=e.vendor.id,
        inventory_id=e.inventory.id,
        product_id=e.product.id,
        quantity=0,
        purchase_price=Decimal("1.00"),
    )
    db_session.add(line)
    with pytest.raises(IntegrityError):
        await db_session.flush()
    await db_session.rollback()


async def test_check_order_line_purchase_price_negative(db_session):
    """OrderLine purchase_price = -1 violates CHECK (purchase_price >= 0)."""
    e = await build_chain(db_session)
    line = OrderLine(
        id=uuid.uuid4(),
        order_id=e.order.id,
        vendor_id=e.vendor.id,
        inventory_id=e.inventory.id,
        product_id=e.product.id,
        quantity=1,
        purchase_price=Decimal("-1.00"),
    )
    db_session.add(line)
    with pytest.raises(IntegrityError):
        await db_session.flush()
    await db_session.rollback()


# ---------------------------------------------------------------------------
# UNIQUE constraints
# ---------------------------------------------------------------------------

async def test_unique_cart_lines_composite(db_session):
    """Two CartLine rows with same (cart_id, inventory_id) violate composite unique."""
    e = await build_chain(db_session)
    duplicate = CartLine(
        id=uuid.uuid4(), cart_id=e.cart.id, inventory_id=e.inventory.id, quantity=2
    )
    db_session.add(duplicate)
    with pytest.raises(IntegrityError):
        await db_session.flush()
    await db_session.rollback()


async def test_unique_cart_one_per_user(db_session):
    """Second Cart for the same user_id violates UNIQUE on carts.user_id."""
    e = await build_chain(db_session)
    second_cart = Cart(id=uuid.uuid4(), user_id=e.user.id)
    db_session.add(second_cart)
    with pytest.raises(IntegrityError):
        await db_session.flush()
    await db_session.rollback()


async def test_unique_user_email(db_session):
    """Second User with duplicate email violates UNIQUE on users.email."""
    e = await build_chain(db_session)
    dup = User(id=uuid.uuid4(), email=e.user.email, password_hash="other")
    db_session.add(dup)
    with pytest.raises(IntegrityError):
        await db_session.flush()
    await db_session.rollback()


async def test_unique_category_name(db_session):
    """Second Category with same name violates UNIQUE on categories.name."""
    e = await build_chain(db_session)
    dup = Category(id=uuid.uuid4(), name=e.category.name)
    db_session.add(dup)
    with pytest.raises(IntegrityError):
        await db_session.flush()
    await db_session.rollback()


# ---------------------------------------------------------------------------
# FK ON DELETE CASCADE — orders → order_lines
# ---------------------------------------------------------------------------

async def test_cascade_delete_order_removes_order_lines(db_session):
    """Deleting an Order removes its OrderLine rows via ON DELETE CASCADE."""
    e = await build_chain(db_session)
    order_line_id = e.order_line.id

    await db_session.execute(
        text("DELETE FROM orders WHERE id = :id"), {"id": str(e.order.id)}
    )
    db_session.expire_all()

    result = await db_session.execute(
        select(OrderLine).where(OrderLine.id == order_line_id)
    )
    assert result.scalar_one_or_none() is None


# ---------------------------------------------------------------------------
# FK ON DELETE CASCADE — users → carts → cart_lines
# ---------------------------------------------------------------------------

async def test_cascade_delete_user_removes_cart_and_cart_lines(db_session):
    """Deleting a User removes their Cart and CartLine rows via ON DELETE CASCADE."""
    e = await build_chain(db_session)
    cart_id = e.cart.id
    cart_line_id = e.cart_line.id

    # Must also remove order (SET NULL on orders.user_id, so order stays)
    # but cart has CASCADE from users → carts
    await db_session.execute(
        text("DELETE FROM orders WHERE id = :id"), {"id": str(e.order.id)}
    )
    await db_session.execute(
        text("DELETE FROM users WHERE id = :id"), {"id": str(e.user.id)}
    )
    db_session.expire_all()

    cart_result = await db_session.execute(select(Cart).where(Cart.id == cart_id))
    assert cart_result.scalar_one_or_none() is None

    line_result = await db_session.execute(select(CartLine).where(CartLine.id == cart_line_id))
    assert line_result.scalar_one_or_none() is None


# ---------------------------------------------------------------------------
# FK ON DELETE RESTRICT
# ---------------------------------------------------------------------------

async def test_restrict_delete_inventory_with_order_line(db_session):
    """Deleting Inventory referenced by an OrderLine raises IntegrityError (RESTRICT)."""
    e = await build_chain(db_session)
    with pytest.raises(IntegrityError):
        await db_session.execute(
            text("DELETE FROM inventory WHERE id = :id"), {"id": str(e.inventory.id)}
        )
        await db_session.flush()
    await db_session.rollback()


async def test_restrict_delete_product_with_order_line(db_session):
    """Deleting a Product referenced by an OrderLine raises IntegrityError (RESTRICT)."""
    e = await build_chain(db_session)
    with pytest.raises(IntegrityError):
        await db_session.execute(
            text("DELETE FROM products WHERE id = :id"), {"id": str(e.product.id)}
        )
        await db_session.flush()
    await db_session.rollback()


async def test_restrict_delete_vendor_with_order_line(db_session):
    """Deleting a Vendor referenced by an OrderLine raises IntegrityError (RESTRICT)."""
    e = await build_chain(db_session)
    with pytest.raises(IntegrityError):
        await db_session.execute(
            text("DELETE FROM vendors WHERE id = :id"), {"id": str(e.vendor.id)}
        )
        await db_session.flush()
    await db_session.rollback()


async def test_restrict_delete_category_with_products(db_session):
    """Deleting a Category that has Products raises IntegrityError (RESTRICT)."""
    e = await build_chain(db_session)
    with pytest.raises(IntegrityError):
        await db_session.execute(
            text("DELETE FROM categories WHERE id = :id"), {"id": str(e.category.id)}
        )
        await db_session.flush()
    await db_session.rollback()


# ---------------------------------------------------------------------------
# FK ON DELETE CASCADE — product/vendor → inventory (no pending orders)
# ---------------------------------------------------------------------------

async def test_cascade_delete_product_without_orders_removes_inventory(db_session):
    """Deleting a Product with no OrderLines removes its Inventory rows (CASCADE)."""
    uid = uuid.uuid4
    cat = Category(id=uid(), name=f"c-{uid()}")
    vendor = Vendor(id=uid(), name=f"v-{uid()}")
    db_session.add_all([cat, vendor])
    await db_session.flush()

    product = Product(id=uid(), category_id=cat.id, name=f"p-{uid()}")
    db_session.add(product)
    await db_session.flush()

    inv = Inventory(
        id=uid(), vendor_id=vendor.id, product_id=product.id,
        price=Decimal("5.00"), stock_quantity=1,
    )
    db_session.add(inv)
    await db_session.flush()
    inv_id = inv.id

    await db_session.execute(
        text("DELETE FROM products WHERE id = :id"), {"id": str(product.id)}
    )
    db_session.expire_all()

    result = await db_session.execute(select(Inventory).where(Inventory.id == inv_id))
    assert result.scalar_one_or_none() is None


async def test_cascade_delete_vendor_without_orders_removes_inventory(db_session):
    """Deleting a Vendor with no OrderLines removes its Inventory rows (CASCADE)."""
    uid = uuid.uuid4
    cat = Category(id=uid(), name=f"c-{uid()}")
    vendor = Vendor(id=uid(), name=f"v-{uid()}")
    db_session.add_all([cat, vendor])
    await db_session.flush()

    product = Product(id=uid(), category_id=cat.id, name=f"p-{uid()}")
    db_session.add(product)
    await db_session.flush()

    inv = Inventory(
        id=uid(), vendor_id=vendor.id, product_id=product.id,
        price=Decimal("5.00"), stock_quantity=1,
    )
    db_session.add(inv)
    await db_session.flush()
    inv_id = inv.id

    await db_session.execute(
        text("DELETE FROM vendors WHERE id = :id"), {"id": str(vendor.id)}
    )
    db_session.expire_all()

    result = await db_session.execute(select(Inventory).where(Inventory.id == inv_id))
    assert result.scalar_one_or_none() is None


# ---------------------------------------------------------------------------
# FK ON DELETE SET NULL — users → orders
# ---------------------------------------------------------------------------

async def test_set_null_delete_user_keeps_orders_with_null_user_id(db_session):
    """Deleting a User sets orders.user_id to NULL; Order rows are retained."""
    e = await build_chain(db_session)
    order_id = e.order.id

    await db_session.execute(
        text("DELETE FROM order_lines WHERE order_id = :id"), {"id": str(e.order.id)}
    )
    await db_session.execute(
        text("DELETE FROM carts WHERE user_id = :id"), {"id": str(e.user.id)}
    )
    await db_session.execute(
        text("DELETE FROM users WHERE id = :id"), {"id": str(e.user.id)}
    )
    db_session.expire_all()

    order = await db_session.get(Order, order_id)
    assert order is not None
    assert order.user_id is None


# ---------------------------------------------------------------------------
# Nullable / Identity assertions
# ---------------------------------------------------------------------------

async def test_product_without_embedding_is_nullable(db_session):
    """Inserting a Product without embedding succeeds; embedding column is NULL."""
    uid = uuid.uuid4
    cat = Category(id=uid(), name=f"c-{uid()}")
    db_session.add(cat)
    await db_session.flush()

    product = Product(id=uid(), category_id=cat.id, name="no-embedding")
    db_session.add(product)
    await db_session.flush()

    result = await db_session.execute(select(Product).where(Product.id == product.id))
    fetched = result.scalar_one()
    assert fetched.embedding is None


async def test_order_number_generated_always_rejects_client_value(db_session):
    """Inserting an Order with a client-supplied order_number is rejected by the DB."""
    uid = uuid.uuid4
    user = User(id=uid(), email=f"u-{uid()}@test.com", password_hash="h")
    db_session.add(user)
    await db_session.flush()

    with pytest.raises((IntegrityError, ProgrammingError)):
        await db_session.execute(
            text(
                "INSERT INTO orders (id, user_id, order_number, created_at) "
                "VALUES (:id, NULL, 42, NOW())"
            ),
            {"id": str(uid())},
        )
        await db_session.flush()
    await db_session.rollback()
