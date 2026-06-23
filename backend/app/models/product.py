import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import relationship

from backend.app.catalog.enums import UnitType
from backend.app.db.session import Base


class Product(Base):
    __tablename__ = "products"

    product_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    subcategory_id = Column(
        String(36),
        ForeignKey("subcategories.subcategory_id"),
        nullable=False,
        index=True,
    )
    product_name = Column(String(255), nullable=False)
    brand = Column(String(255), nullable=False, default="Generic")
    description = Column(Text, nullable=False)
    unit_type = Column(Enum(UnitType), nullable=False)
    unit_value = Column(Numeric(10, 3), nullable=False)
    price_inr = Column(Numeric(10, 2), nullable=False)
    vendor_id = Column(
        String(36),
        ForeignKey("vendors.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    stock_quantity = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    subcategory = relationship("SubCategory", back_populates="products")
    vendor = relationship("Vendor")
