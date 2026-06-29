"""SubCategory SQLAlchemy model (feature 006-vendor-product-management).

Mirrors the Alembic 0004 migration schema. See `models/category.py` for the
String(36)-vs-UUID convention.
"""

import uuid

from sqlalchemy import Column, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from backend.app.db.session import Base


class SubCategory(Base):
    __tablename__ = "subcategories"

    subcategory_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    subcategory_name = Column(String(255), nullable=False)
    parent_category_id = Column(
        UUID(as_uuid=True),
        ForeignKey("categories.category_id", ondelete="CASCADE"),
        nullable=False,
    )
    subcategory_description = Column(String(500), nullable=False)

    category = relationship("Category", back_populates="subcategories")
    products = relationship("Product", back_populates="subcategory")

    __table_args__ = (
        Index("ix_subcategories_parent_category_id", "parent_category_id"),
    )
