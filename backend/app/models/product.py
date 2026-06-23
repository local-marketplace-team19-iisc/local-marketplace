"""Product SQLAlchemy model (feature 006-vendor-product-management).

Mirrors the Alembic 0004 migration schema. The `unit_type` column is stored as
a string (with allowed values matching the `UnitType` enum) rather than a
Postgres ENUM, so the same model is portable to SQLite for local dev/test.
See `models/category.py` for the String(36)-vs-UUID convention.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from backend.app.db.session import Base


class Product(Base):
    __tablename__ = "products"

    product_id = Column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    subcategory_id = Column(
        String(36),
        ForeignKey("subcategories.subcategory_id"),
        nullable=False,
    )
    product_name = Column(String(255), nullable=False)
    brand = Column(String(255), nullable=False, server_default="Generic")
    description = Column(Text, nullable=False)
    unit_type = Column(String(20), nullable=False)
    unit_value = Column(Numeric(10, 3), nullable=False)
    price_inr = Column(Numeric(10, 2), nullable=False)
    vendor_id = Column(
        String(36),
        ForeignKey("vendors.id", ondelete="CASCADE"),
        nullable=False,
    )
    stock_quantity = Column(Integer, nullable=False, server_default="0")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    subcategory = relationship("SubCategory", back_populates="products")
    vendor = relationship("Vendor")

    __table_args__ = (
        Index("ix_products_vendor_id", "vendor_id"),
        Index("ix_products_subcategory_id", "subcategory_id"),
    )
