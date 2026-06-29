"""Category SQLAlchemy model (feature 006-vendor-product-management).

Mirrors the Alembic 0004 migration schema. Per architecture decision D2 of
feature 006, ORM models declare `String(36)` ids while the migration emits
PostgreSQL `UUID` — the same convention `users` and `vendors` follow. This
keeps the in-memory SQLite test path (`catalog_db` fixture) working without
needing dialect-specific column types.
"""

import uuid

from sqlalchemy import Column, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from backend.app.db.session import Base


class Category(Base):
    __tablename__ = "categories"

    category_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    category_name = Column(String(255), nullable=False, unique=True)
    parent_category_id = Column(
        UUID(as_uuid=True),
        ForeignKey("categories.category_id"),
        nullable=True,
    )

    subcategories = relationship(
        "SubCategory",
        back_populates="category",
        cascade="all, delete-orphan",
    )
