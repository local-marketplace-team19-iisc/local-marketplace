import uuid

from sqlalchemy import Column, String
from sqlalchemy.orm import relationship

from backend.app.db.session import Base


class Category(Base):
    __tablename__ = "categories"

    category_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    category_name = Column(String(255), unique=True, nullable=False)
    parent_category_id = Column(String(36), nullable=True)

    subcategories = relationship(
        "SubCategory",
        back_populates="category",
        cascade="all, delete-orphan",
    )
