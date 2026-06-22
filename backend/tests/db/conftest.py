import os
import uuid
from decimal import Decimal
from types import SimpleNamespace

import asyncpg
import pytest_asyncio
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.app.models.base import Base
from backend.app.models.models import (  # noqa: F401 — registers models on Base.metadata
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

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://marketplace:marketplace@localhost:5432/marketplace_test",
)


def _parse_dsn(url: str) -> dict:
    raw = url.replace("postgresql+asyncpg://", "")
    creds, rest = raw.split("@", 1)
    host_port, dbname = rest.split("/", 1)
    host, port_str = host_port.rsplit(":", 1)
    user, password = creds.split(":", 1)
    return {
        "host": host,
        "port": int(port_str),
        "user": user,
        "password": password,
        "database": dbname,
    }


@pytest_asyncio.fixture
async def db_session():
    params = _parse_dsn(TEST_DATABASE_URL)
    dbname = params["database"]

    # Create test DB if missing (must not be inside a transaction)
    sys_conn = await asyncpg.connect(
        host=params["host"],
        port=params["port"],
        user=params["user"],
        password=params["password"],
        database=params["user"],  # connect to user's own default DB
    )
    try:
        exists = await sys_conn.fetchval(
            "SELECT 1 FROM pg_database WHERE datname = $1", dbname
        )
        if not exists:
            await sys_conn.execute(f'CREATE DATABASE "{dbname}"')
    finally:
        await sys_conn.close()

    # Ensure extensions in the test DB
    ext_conn = await asyncpg.connect(**params)
    try:
        await ext_conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
        await ext_conn.execute("CREATE EXTENSION IF NOT EXISTS postgis")
    finally:
        await ext_conn.close()

    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session
        await session.rollback()

    await engine.dispose()


async def build_chain(session: AsyncSession) -> SimpleNamespace:
    """Insert one of each entity type and flush (no commit). Returns all entities."""
    uid = uuid.uuid4

    category = Category(id=uid(), name=f"cat-{uid()}", description="test")
    user = User(id=uid(), email=f"u-{uid()}@test.com", password_hash="hashed")
    vendor = Vendor(id=uid(), name=f"vendor-{uid()}")
    session.add_all([category, user, vendor])
    await session.flush()

    product = Product(id=uid(), category_id=category.id, name=f"prod-{uid()}")
    session.add(product)
    await session.flush()

    inventory = Inventory(
        id=uid(),
        vendor_id=vendor.id,
        product_id=product.id,
        price=Decimal("9.99"),
        stock_quantity=10,
    )
    cart = Cart(id=uid(), user_id=user.id)
    session.add_all([inventory, cart])
    await session.flush()

    cart_line = CartLine(id=uid(), cart_id=cart.id, inventory_id=inventory.id, quantity=1)
    order = Order(id=uid(), user_id=user.id)
    session.add_all([cart_line, order])
    await session.flush()

    order_line = OrderLine(
        id=uid(),
        order_id=order.id,
        vendor_id=vendor.id,
        inventory_id=inventory.id,
        product_id=product.id,
        quantity=1,
        purchase_price=Decimal("9.99"),
    )
    session.add(order_line)
    await session.flush()

    return SimpleNamespace(
        category=category,
        user=user,
        vendor=vendor,
        product=product,
        inventory=inventory,
        cart=cart,
        cart_line=cart_line,
        order=order,
        order_line=order_line,
    )
