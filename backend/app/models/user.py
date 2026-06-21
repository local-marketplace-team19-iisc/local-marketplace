import enum
import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, String
from sqlalchemy.orm import relationship

from backend.app.db.session import Base


class UserRole(str, enum.Enum):
    customer = "customer"
    vendor = "vendor"


class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String(255), unique=True, nullable=True, index=True)
    password_hash = Column(String(255), nullable=True)
    phone = Column(String(15), unique=True, nullable=True, index=True)
    role = Column(String(50), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    vendor = relationship("Vendor", back_populates="user", uselist=False, cascade="all, delete-orphan")
    otps = relationship("Otp", back_populates="user", cascade="all, delete-orphan")
    refresh_tokens = relationship("RefreshToken", back_populates="user", cascade="all, delete-orphan")
