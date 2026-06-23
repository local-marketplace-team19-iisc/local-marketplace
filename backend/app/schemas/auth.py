from typing import Optional

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    """Customer registration request."""

    email: EmailStr
    password: str = Field(..., min_length=8)
    password_confirm: Optional[str] = None
    full_name: Optional[str] = None
    account_type: Optional[str] = None

    class Config:
        extra = "allow"


class RegisterVendorRequest(BaseModel):
    """Vendor registration request."""

    email: EmailStr
    password: str = Field(..., min_length=8)
    password_confirm: str
    shop_name: str = Field(..., min_length=1, max_length=255)
    location: dict = Field(
        ...,
        description="Coordinates as {lat, lon}",
        json_schema_extra={"example": {"lat": 40.7128, "lon": -74.0060}},
    )
    shop_description: Optional[str] = Field(None, max_length=1000)


class LoginRequest(BaseModel):
    """Login request."""

    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    """Refresh token request."""

    refresh_token: str


class AuthResponse(BaseModel):
    """Response after successful auth (register, login, refresh)."""

    access_token: str
    refresh_token: str
    user_id: str
    user_type: str  # 'customer' or 'vendor'
    email: Optional[str] = None
    vendor_id: Optional[str] = None
    shop_name: Optional[str] = None


class UserMeResponse(BaseModel):
    """Response from GET /me endpoint."""

    id: str
    email: str
    user_type: str  # 'customer' or 'vendor'
    vendor_id: Optional[str] = None
    shop_name: Optional[str] = None
    shop_description: Optional[str] = None
    shop_location: Optional[dict] = None
