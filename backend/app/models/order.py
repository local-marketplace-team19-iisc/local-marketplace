"""Order SQLAlchemy model (V1 — customer checkout).

Minimal, deterministic order placement per master SPEC §2 ("pricing, ordering,
and inventory stay deterministic"). One Order row per checkout call; a single
order may span multiple vendors (SPEC §3 — "one unique order number"). Line
items live in `OrderItem`.

Schema conventions match the rest of the codebase:
* `String(36)` ids so the same model is portable to SQLite for local dev/test
  (architecture decisions D-001-3, D-006-2).
* `NUMERIC(12, 2)` for ₹ amounts so we never lose precision (SPEC §2 — 2 dp).
* `created_at` defaults are ORM-side; we don't add migration noise for V1
  because local dev bootstraps via `Base.metadata.create_all` (Postgres prod
  will get a proper Alembic migration when the Orders feature graduates).
"""

import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Index, Numeric, String
from sqlalchemy.orm import relationship

from backend.app.db.session import Base


class Order(Base):
    __tablename__ = "orders"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    order_number = Column(String(32), nullable=False, unique=True)
    customer_id = Column(
        String(36),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    total_inr = Column(Numeric(12, 2), nullable=False)
    status = Column(String(20), nullable=False, server_default="placed")
    placed_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    items = relationship(
        "OrderItem",
        back_populates="order",
        cascade="all, delete-orphan",
        lazy="joined",
    )

    __table_args__ = (
        Index("ix_orders_customer_id", "customer_id"),
        Index("ix_orders_placed_at", "placed_at"),
    )
