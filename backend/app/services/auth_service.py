import uuid
from datetime import datetime

from sqlalchemy.orm import Session

from backend.app.models.refresh_token import RefreshToken
from backend.app.models.user import User, UserRole
from backend.app.models.vendor import Vendor
from backend.app.security.password import hash_password, validate_password_strength, verify_password
from backend.app.services.jwt_service import create_access_token, create_refresh_token, verify_refresh_token
from backend.app.services.rate_limit import (
    check_login_rate_limit,
    clear_failed_login,
    record_failed_login,
)


class AuthError(Exception):
    """Base error for auth operations."""


class AuthValidationError(AuthError):
    pass


class AuthNotFoundError(AuthError):
    pass


class AuthUnauthorizedError(AuthError):
    pass


def register_customer(db: Session, email: str, password: str) -> dict:
    """Register a new customer user and return JWT tokens.

    Args:
        db: Database session
        email: User email (must be unique)
        password: Plain text password

    Returns:
        {user_id, email, user_type, access_token, refresh_token}

    Raises:
        AuthValidationError: Invalid email/password or email already registered
    """
    import hashlib
    from datetime import timedelta

    from backend.app.core.config import settings

    # Validate password strength
    is_valid, reason = validate_password_strength(password)
    if not is_valid:
        raise AuthValidationError(reason)

    # Check if email already exists
    existing_user = db.query(User).filter(User.email == email.lower()).first()
    if existing_user:
        raise AuthValidationError("Email already registered")

    # Create user
    user = User(
        email=email.lower(),
        password_hash=hash_password(password),
        role=UserRole.customer.value,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    # Generate tokens
    access_token = create_access_token(user.id, user.role)
    refresh_token = create_refresh_token(user.id)
    token_hash = hashlib.sha256(refresh_token.encode()).hexdigest()

    # Store refresh token hash in DB
    refresh_token_record = RefreshToken(
        user_id=user.id,
        token_hash=token_hash,
        expires_at=datetime.utcnow() + timedelta(days=settings.JWT_REFRESH_TOKEN_TTL_DAYS),
    )
    db.add(refresh_token_record)
    db.commit()

    return {
        "user_id": str(user.id),
        "email": user.email,
        "user_type": user.role,
        "access_token": access_token,
        "refresh_token": refresh_token,
    }


def register_vendor(
    db: Session,
    email: str,
    password: str,
    shop_name: str,
    location: tuple[float, float],
    shop_description: str | None = None,
) -> dict:
    """Register a new vendor user with shop details and return JWT tokens.

    Args:
        db: Database session
        email: User email (must be unique)
        password: Plain text password
        shop_name: Vendor shop name
        location: Tuple of (latitude, longitude)
        shop_description: Optional shop description

    Returns:
        {user_id, vendor_id, email, user_type, shop_name, access_token, refresh_token}

    Raises:
        AuthValidationError: Invalid data, duplicate email, or invalid location
    """
    import hashlib
    from datetime import timedelta

    from backend.app.core.config import settings

    # Validate password strength
    is_valid, reason = validate_password_strength(password)
    if not is_valid:
        raise AuthValidationError(reason)

    # Validate location coordinates
    lat, lon = location
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise AuthValidationError("Invalid location coordinates. Latitude must be between -90 and 90, longitude between -180 and 180.")

    # Check if email already exists
    existing_user = db.query(User).filter(User.email == email.lower()).first()
    if existing_user:
        raise AuthValidationError("Email already registered")

    # Create user and vendor in transaction
    try:
        user = User(
            email=email.lower(),
            password_hash=hash_password(password),
            role=UserRole.vendor.value,
        )
        db.add(user)
        db.flush()  # Get user.id without committing

        vendor = Vendor(
            user_id=user.id,
            shop_name=shop_name,
            shop_location_lat=lat,
            shop_location_lon=lon,
            shop_description=shop_description,
            is_active=True,
        )
        db.add(vendor)
        db.commit()
        db.refresh(user)
        db.refresh(vendor)

    except Exception as e:
        db.rollback()
        raise AuthValidationError(f"Failed to create vendor account: {str(e)}") from e

    # Generate tokens
    access_token = create_access_token(user.id, user.role)
    refresh_token = create_refresh_token(user.id)
    token_hash = hashlib.sha256(refresh_token.encode()).hexdigest()

    # Store refresh token hash in DB
    refresh_token_record = RefreshToken(
        user_id=user.id,
        token_hash=token_hash,
        expires_at=datetime.utcnow() + timedelta(days=settings.JWT_REFRESH_TOKEN_TTL_DAYS),
    )
    db.add(refresh_token_record)
    db.commit()

    return {
        "user_id": str(user.id),
        "vendor_id": str(vendor.id),
        "email": user.email,
        "user_type": user.role,
        "shop_name": vendor.shop_name,
        "access_token": access_token,
        "refresh_token": refresh_token,
    }


def login(db: Session, email: str, password: str) -> dict:
    """Authenticate user with email and password.

    Args:
        db: Database session
        email: User email
        password: Plain text password

    Returns:
        {user_id, user_type, access_token, refresh_token}

    Raises:
        AuthUnauthorizedError: Invalid email or password
    """
    # Check rate limit
    allowed, reason = check_login_rate_limit(email)
    if not allowed:
        raise AuthUnauthorizedError(reason)

    # Find user
    user = db.query(User).filter(User.email == email.lower()).first()

    # Verify password (generic error for security)
    if not user or not verify_password(password, user.password_hash or ""):
        record_failed_login(email)
        raise AuthUnauthorizedError("Invalid email or password")

    # Clear failed attempts on successful login
    clear_failed_login(email)

    vendor = None
    if user.role == UserRole.vendor.value:
        vendor = db.query(Vendor).filter(Vendor.user_id == user.id).first()

    # Generate tokens
    access_token = create_access_token(user.id, user.role)
    refresh_token = create_refresh_token(user.id)

    # Store refresh token hash in DB
    import hashlib
    token_hash = hashlib.sha256(refresh_token.encode()).hexdigest()

    from datetime import timedelta
    from backend.app.core.config import settings

    refresh_token_record = RefreshToken(
        user_id=user.id,
        token_hash=token_hash,
        expires_at=datetime.utcnow() + timedelta(days=settings.JWT_REFRESH_TOKEN_TTL_DAYS),
    )
    db.add(refresh_token_record)
    db.commit()

    return {
        "user_id": str(user.id),
        "user_type": user.role,
        "email": user.email,
        "vendor_id": str(vendor.id) if vendor else None,
        "shop_name": vendor.shop_name if vendor else None,
        "access_token": access_token,
        "refresh_token": refresh_token,
    }


def refresh_access_token(db: Session, refresh_token: str) -> dict:
    """Issue new access token using valid refresh token.

    Refresh token is rotated on each call (old token invalidated).

    Args:
        db: Database session
        refresh_token: JWT refresh token string

    Returns:
        {access_token, refresh_token, user_id, user_type}

    Raises:
        AuthUnauthorizedError: Invalid or expired refresh token
    """
    import hashlib
    from datetime import timedelta

    from backend.app.core.config import settings

    # Verify refresh token JWT
    try:
        payload = verify_refresh_token(refresh_token)
    except Exception as e:
        raise AuthUnauthorizedError(f"Invalid refresh token: {str(e)}") from e

    user_id = str(payload["user_id"])
    token_hash = hashlib.sha256(refresh_token.encode()).hexdigest()

    # Find and validate refresh token in DB
    token_record = db.query(RefreshToken).filter(
        RefreshToken.user_id == user_id,
        RefreshToken.token_hash == token_hash,
    ).first()

    if not token_record:
        raise AuthUnauthorizedError("Refresh token not found or revoked")

    if token_record.revoked_at is not None:
        raise AuthUnauthorizedError("Refresh token has been revoked")

    if datetime.utcnow() > token_record.expires_at:
        raise AuthUnauthorizedError("Refresh token has expired")

    # Get user to determine user_type
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise AuthUnauthorizedError("User not found")

    # Invalidate old refresh token
    token_record.revoked_at = datetime.utcnow()
    db.commit()

    # Issue new tokens
    new_access_token = create_access_token(user.id, user.role)
    new_refresh_token = create_refresh_token(user.id)
    new_token_hash = hashlib.sha256(new_refresh_token.encode()).hexdigest()

    new_token_record = RefreshToken(
        user_id=user.id,
        token_hash=new_token_hash,
        expires_at=datetime.utcnow() + timedelta(days=settings.JWT_REFRESH_TOKEN_TTL_DAYS),
    )
    db.add(new_token_record)
    db.commit()

    return {
        "user_id": str(user.id),
        "user_type": user.role,
        "email": user.email,
        "access_token": new_access_token,
        "refresh_token": new_refresh_token,
    }


def logout(db: Session, user_id: uuid.UUID, refresh_token: str) -> bool:
    """Revoke refresh token on logout.

    Args:
        db: Database session
        user_id: User ID
        refresh_token: JWT refresh token string

    Returns:
        True if logout successful (idempotent)
    """
    import hashlib

    token_hash = hashlib.sha256(refresh_token.encode()).hexdigest()

    # Find and revoke token
    token_record = db.query(RefreshToken).filter(
        RefreshToken.user_id == str(user_id),
        RefreshToken.token_hash == token_hash,
    ).first()

    if token_record and token_record.revoked_at is None:
        token_record.revoked_at = datetime.utcnow()
        db.commit()

    return True


def get_current_user(db: Session, access_token: str) -> dict:
    """Get current user info from access token.

    Args:
        db: Database session
        access_token: JWT access token string

    Returns:
        {id, email, user_type, vendor_id, shop_name, shop_location} (vendor fields if applicable)

    Raises:
        AuthUnauthorizedError: Invalid or expired token
    """
    from backend.app.services.jwt_service import verify_token

    try:
        payload = verify_token(access_token)
    except Exception as e:
        raise AuthUnauthorizedError(f"Invalid token: {str(e)}") from e

    user_id = str(payload["user_id"])
    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise AuthUnauthorizedError("User not found")

    result = {
        "id": str(user.id),
        "email": user.email,
        "user_type": user.role,
    }

    # Add vendor details if vendor
    if user.role == UserRole.vendor.value:
        vendor = db.query(Vendor).filter(Vendor.user_id == user_id).first()
        if vendor:
            result["vendor_id"] = str(vendor.id)
            result["shop_name"] = vendor.shop_name
            result["shop_description"] = vendor.shop_description
            result["shop_location"] = {
                "lat": vendor.shop_location_lat,
                "lon": vendor.shop_location_lon,
            }

    return result
