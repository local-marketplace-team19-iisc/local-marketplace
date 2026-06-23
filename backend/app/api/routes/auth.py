from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from backend.app.db.session import SessionLocal
from backend.app.schemas.auth import (
    AuthResponse,
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    RegisterVendorRequest,
    UserMeResponse,
)
from backend.app.services import auth_service, rate_limit

router = APIRouter()


def get_db() -> Session:
    """Dependency: get database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_client_ip(request: Request) -> str:
    """Extract client IP from request."""
    if request.client:
        return request.client.host
    return "unknown"


@router.post("/register", status_code=201, response_model=AuthResponse)
def register_customer(
    request_data: RegisterRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """Register a new customer.

    Validation:
    - Email must be valid and unique
    - Password must be 8+ chars with uppercase, digit, special char
    - Passwords must match
    - Rate limited: 10 signups per IP per hour
    """
    try:
        # Validate passwords match (if password_confirm is provided)
        if request_data.password_confirm and request_data.password != request_data.password_confirm:
            raise HTTPException(status_code=400, detail="Passwords do not match")

        # Check signup rate limit
        client_ip = get_client_ip(request)
        allowed, reason = rate_limit.check_signup_rate_limit(client_ip)
        if not allowed:
            raise HTTPException(status_code=429, detail=reason)

        # Register customer
        result = auth_service.register_customer(db, request_data.email, request_data.password)
        rate_limit.record_signup(client_ip)

        return AuthResponse(
            access_token=result["access_token"],
            refresh_token=result["refresh_token"],
            user_id=result["user_id"],
            user_type=result["user_type"],
            email=result.get("email"),
        )
    except auth_service.AuthValidationError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)}") from e


@router.post("/register-vendor", status_code=201, response_model=AuthResponse)
def register_vendor(
    request_data: RegisterVendorRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> AuthResponse:
    """Register a new vendor with shop details.

    Validation:
    - Email must be valid and unique
    - Password must be 8+ chars with uppercase, digit, special char
    - Passwords must match
    - Location must be valid coordinates (lat ±90, lon ±180)
    - Rate limited: 10 signups per IP per hour
    """
    # Validate passwords match
    if request_data.password != request_data.password_confirm:
        raise HTTPException(status_code=400, detail="Passwords do not match")

    # Extract location coordinates
    try:
        lat = request_data.location.get("lat")
        lon = request_data.location.get("lon")
        if lat is None or lon is None:
            raise ValueError("Location must have 'lat' and 'lon' keys")
        location = (float(lat), float(lon))
    except (ValueError, TypeError) as e:
        raise HTTPException(status_code=400, detail=f"Invalid location format: {e}") from e

    # Check signup rate limit
    client_ip = get_client_ip(request)
    allowed, reason = rate_limit.check_signup_rate_limit(client_ip)
    if not allowed:
        raise HTTPException(status_code=429, detail=reason)

    # Register vendor
    try:
        result = auth_service.register_vendor(
            db,
            request_data.email,
            request_data.password,
            request_data.shop_name,
            location,
            request_data.shop_description,
        )
        rate_limit.record_signup(client_ip)

        return AuthResponse(
            access_token=result["access_token"],
            refresh_token=result["refresh_token"],
            user_id=result["user_id"],
            user_type=result["user_type"],
            email=result.get("email"),
            vendor_id=result.get("vendor_id"),
            shop_name=result.get("shop_name"),
        )
    except auth_service.AuthValidationError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/login", status_code=200, response_model=AuthResponse)
def login(
    request_data: LoginRequest,
    db: Session = Depends(get_db),
) -> AuthResponse:
    """Authenticate user with email and password.

    Returns:
    - access_token: JWT token (valid for 1 hour)
    - refresh_token: JWT refresh token (valid for 7 days)
    - user_id: UUID of authenticated user
    - user_type: 'customer' or 'vendor'

    Rate limited: 5 failed attempts per email per 15 minutes
    """
    try:
        result = auth_service.login(db, request_data.email, request_data.password)

        return AuthResponse(
            access_token=result["access_token"],
            refresh_token=result["refresh_token"],
            user_id=result["user_id"],
            user_type=result["user_type"],
            email=result.get("email"),
            vendor_id=result.get("vendor_id"),
            shop_name=result.get("shop_name"),
        )
    except auth_service.AuthUnauthorizedError as e:
        raise HTTPException(status_code=401, detail=str(e)) from e
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)}") from e


@router.post("/refresh", status_code=200, response_model=AuthResponse)
def refresh_token(
    request_data: RefreshRequest,
    db: Session = Depends(get_db),
) -> AuthResponse:
    """Get new access token using valid refresh token.

    Refresh token is rotated on each call (old token revoked).

    Returns:
    - access_token: New JWT access token
    - refresh_token: New JWT refresh token (old one revoked)
    - user_id: UUID of user
    - user_type: 'customer' or 'vendor'
    """
    try:
        result = auth_service.refresh_access_token(db, request_data.refresh_token)

        return AuthResponse(
            access_token=result["access_token"],
            refresh_token=result["refresh_token"],
            user_id=result["user_id"],
            user_type=result["user_type"],
            email=result.get("email"),
        )
    except auth_service.AuthUnauthorizedError as e:
        raise HTTPException(status_code=401, detail=str(e)) from e


@router.post("/logout", status_code=204)
def logout(
    request_data: RefreshRequest,
    db: Session = Depends(get_db),
) -> None:
    """Revoke refresh token and logout user.

    Idempotent: calling multiple times with same token succeeds.
    """
    from backend.app.services.jwt_service import verify_refresh_token

    try:
        # Verify refresh token to get user_id
        payload = verify_refresh_token(request_data.refresh_token)
        user_id = payload["user_id"]
        auth_service.logout(db, user_id, request_data.refresh_token)
    except Exception:
        # Logout is best-effort and idempotent
        # Return 204 even if token is invalid (already logged out)
        pass


@router.get("/me", status_code=200, response_model=UserMeResponse)
def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
) -> UserMeResponse:
    """Get current authenticated user's profile.

    Returns user info including vendor details if the user is a vendor.

    Authorization: Requires valid JWT access token in Authorization header
    (Authorization: Bearer <token>)
    """
    # Extract JWT from Authorization header
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid authorization header")

    access_token = auth_header[7:]  # Remove "Bearer " prefix

    try:
        user_data = auth_service.get_current_user(db, access_token)

        return UserMeResponse(
            id=user_data["id"],
            email=user_data["email"],
            user_type=user_data["user_type"],
            vendor_id=user_data.get("vendor_id"),
            shop_name=user_data.get("shop_name"),
            shop_description=user_data.get("shop_description"),
            shop_location=user_data.get("shop_location"),
        )
    except auth_service.AuthUnauthorizedError as e:
        raise HTTPException(status_code=401, detail=str(e)) from e
