import uuid
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, String
from sqlalchemy.orm import relationship

from backend.app.db.session import Base


class Vendor(Base):
    __tablename__ = "vendors"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True)
    shop_name = Column(String(255), nullable=False)
    shop_location_lat = Column(Float, nullable=False)
    shop_location_lon = Column(Float, nullable=False)
    shop_description = Column(String(1000), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    user = relationship("User", back_populates="vendor")
