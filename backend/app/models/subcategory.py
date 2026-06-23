import uuid

from sqlalchemy import Column, ForeignKey, String
from sqlalchemy.orm import relationship

from backend.app.db.session import Base


class SubCategory(Base):
    __tablename__ = "subcategories"

    subcategory_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    subcategory_name = Column(String(255), nullable=False)
    parent_category_id = Column(
        String(36),
        ForeignKey("categories.category_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    subcategory_description = Column(String(500), nullable=False)

    category = relationship("Category", back_populates="subcategories")
    products = relationship("Product", back_populates="subcategory")
