"""OrderItem SQLAlchemy model (V1 — one row per cart line).

Stores **snapshots** of product_name, brand, and unit_price_inr at the time
the order was placed. This keeps order history stable even if a vendor
later edits or deletes the underlying product (a real-world MVP need).
The `product_id` / `vendor_id` foreign keys use `ondelete="SET NULL"` for
the same reason — we don't want a vendor's product-cleanup to break a
customer's past invoice.
"""

import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from backend.app.db.session import Base


class OrderItem(Base):
    __tablename__ = "order_items"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id = Column(
        UUID(as_uuid=True),
        ForeignKey("orders.id", ondelete="CASCADE"),
        nullable=False,
    )
    product_id = Column(
        UUID(as_uuid=True),
        ForeignKey("products.product_id", ondelete="SET NULL"),
        nullable=True,
    )
    vendor_id = Column(
        UUID(as_uuid=True),
        ForeignKey("vendors.id", ondelete="SET NULL"),
        nullable=True,
    )

    product_name_snapshot = Column(String(255), nullable=False)
    brand_snapshot = Column(String(255), nullable=False)
    vendor_name_snapshot = Column(String(255), nullable=False)

    unit_price_inr = Column(Numeric(12, 2), nullable=False)
    qty = Column(Integer, nullable=False)
    line_total_inr = Column(Numeric(12, 2), nullable=False)

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    order = relationship("Order", back_populates="items")

    __table_args__ = (
        Index("ix_order_items_order_id", "order_id"),
        Index("ix_order_items_vendor_id", "vendor_id"),
    )
