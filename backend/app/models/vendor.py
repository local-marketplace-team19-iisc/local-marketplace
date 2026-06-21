import uuid
from datetime import datetime

from geoalchemy2 import Geometry
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from backend.app.db.session import Base


class Vendor(Base):
    __tablename__ = "vendors"
    __table_args__ = (
        # plan.md decision: duplicate shop names are allowed (different locations);
        # only the (shop_name, shop_location) pair must be unique.
        UniqueConstraint("shop_name", "shop_location", name="uq_vendors_shop_name_location"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True)
    shop_name = Column(String(255), nullable=False)
    shop_location = Column(Geometry(geometry_type="POINT", srid=4326), nullable=False)
    shop_description = Column(String(1000), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    user = relationship("User", back_populates="vendor")
