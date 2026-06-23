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
    """Vendor registration request.

    `location` is optional in V1 — the registration form no longer asks the
    vendor for lat/lon coordinates because we don't yet ship a
    location-based search or distance feature for customers. The backend
    persists a placeholder `(0, 0)` when the field is omitted, leaving the
    underlying NOT-NULL `shop_location_lat`/`shop_location_lon` columns
    intact (no migration required). If we add a real "find vendors near
    me" feature later, we'll re-introduce a proper geocoding step rather
    than asking users to type raw coordinates.
    """

    email: EmailStr
    password: str = Field(..., min_length=8)
    password_confirm: str
    shop_name: str = Field(..., min_length=1, max_length=255)
    location: Optional[dict] = Field(
        None,
        description="Optional shop coordinates as {lat, lon}",
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
