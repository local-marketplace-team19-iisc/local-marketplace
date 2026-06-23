import uuid
from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from geoalchemy2 import Geography
from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Identity,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import TIMESTAMP

from backend.app.models.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)

    carts: Mapped[List["Cart"]] = relationship(
        back_populates="user", lazy="selectin", cascade="all, delete-orphan"
    )
    orders: Mapped[List["Order"]] = relationship(back_populates="user", lazy="selectin")


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    parent_category_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    products: Mapped[List["Product"]] = relationship(back_populates="category", lazy="selectin")


class Product(Base):
    __tablename__ = "products"

    __table_args__ = (
        Index(
            "ix_products_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    category_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("categories.id", ondelete="RESTRICT"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    embedding = mapped_column(Vector(384), nullable=True)

    category: Mapped["Category"] = relationship(back_populates="products", lazy="selectin")
    inventory: Mapped[List["Inventory"]] = relationship(back_populates="product", lazy="selectin")


class Vendor(Base):
    __tablename__ = "vendors"

    __table_args__ = (
        Index("ix_vendors_location_gist", "location", postgresql_using="gist"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    location = mapped_column(Geography(geometry_type="POINT", srid=4326, spatial_index=False), nullable=True)

    inventory: Mapped[List["Inventory"]] = relationship(back_populates="vendor", lazy="selectin")


class Inventory(Base):
    __tablename__ = "inventory"

    __table_args__ = (
        CheckConstraint("stock_quantity >= 0", name="ck_inventory_stock_nonneg"),
        CheckConstraint("price >= 0", name="ck_inventory_price_nonneg"),
        Index("ix_inventory_price", "price"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    vendor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("vendors.id", ondelete="CASCADE"),
        nullable=False,
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
    )
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    stock_quantity: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")

    vendor: Mapped["Vendor"] = relationship(back_populates="inventory", lazy="selectin")
    product: Mapped["Product"] = relationship(back_populates="inventory", lazy="selectin")
    cart_lines: Mapped[List["CartLine"]] = relationship(back_populates="inventory", lazy="selectin")


class Cart(Base):
    __tablename__ = "carts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    user: Mapped["User"] = relationship(back_populates="carts", lazy="selectin")
    cart_lines: Mapped[List["CartLine"]] = relationship(
        back_populates="cart", lazy="selectin", cascade="all, delete-orphan"
    )


class CartLine(Base):
    __tablename__ = "cart_lines"

    __table_args__ = (
        UniqueConstraint("cart_id", "inventory_id", name="uq_cart_lines_cart_inventory"),
        CheckConstraint("quantity > 0", name="ck_cart_lines_qty_pos"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    cart_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("carts.id", ondelete="CASCADE"),
        nullable=False,
    )
    inventory_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("inventory.id", ondelete="CASCADE"),
        nullable=False,
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")

    cart: Mapped["Cart"] = relationship(back_populates="cart_lines", lazy="selectin")
    inventory: Mapped["Inventory"] = relationship(back_populates="cart_lines", lazy="selectin")


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    order_number: Mapped[int] = mapped_column(
        Integer, Identity(always=True), nullable=False, unique=True
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )

    user: Mapped[Optional["User"]] = relationship(back_populates="orders", lazy="selectin")
    order_lines: Mapped[List["OrderLine"]] = relationship(
        back_populates="order", lazy="selectin", cascade="all, delete-orphan"
    )


class OrderLine(Base):
    __tablename__ = "order_lines"

    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_order_lines_qty_pos"),
        CheckConstraint("purchase_price >= 0", name="ck_order_lines_price_nonneg"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("orders.id", ondelete="CASCADE"),
        nullable=False,
    )
    vendor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("vendors.id", ondelete="RESTRICT"),
        nullable=False,
    )
    inventory_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("inventory.id", ondelete="RESTRICT"),
        nullable=False,
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("products.id", ondelete="RESTRICT"),
        nullable=False,
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    purchase_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)

    order: Mapped["Order"] = relationship(back_populates="order_lines", lazy="selectin")
    vendor: Mapped["Vendor"] = relationship(lazy="selectin")
    inventory: Mapped["Inventory"] = relationship(lazy="selectin")
    product: Mapped["Product"] = relationship(lazy="selectin")
