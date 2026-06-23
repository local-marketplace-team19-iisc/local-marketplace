import uuid
from datetime import datetime, timedelta

from jose import JWTError as JoseJWTError
from jose import jwt

from backend.app.core.config import settings


class JWTError(Exception):
    """Base error for JWT operations."""


class JWTExpiredError(JWTError):
    pass


class JWTInvalidError(JWTError):
    pass


def create_access_token(user_id: uuid.UUID, user_type: str, expires_delta: timedelta | None = None) -> str:
    """Create JWT access token with user claims.

    Args:
        user_id: UUID of the user
        user_type: 'customer' or 'vendor'
        expires_delta: Custom expiration time (default: JWT_ACCESS_TOKEN_TTL_MINUTES from config)

    Returns:
        Encoded JWT token
    """
    if expires_delta is None:
        expires_delta = timedelta(minutes=settings.JWT_ACCESS_TOKEN_TTL_MINUTES)

    now = datetime.utcnow()
    expire = now + expires_delta

    payload = {
        "sub": str(user_id),
        "user_type": user_type,
        "iat": now,
        "exp": expire,
    }

    encoded_jwt = jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
    return encoded_jwt


def create_refresh_token(user_id: uuid.UUID, expires_delta: timedelta | None = None) -> str:
    """Create JWT refresh token.

    Args:
        user_id: UUID of the user
        expires_delta: Custom expiration time (default: JWT_REFRESH_TOKEN_TTL_DAYS from config)

    Returns:
        Encoded JWT token
    """
    if expires_delta is None:
        expires_delta = timedelta(days=settings.JWT_REFRESH_TOKEN_TTL_DAYS)

    now = datetime.utcnow()
    expire = now + expires_delta

    payload = {
        "sub": str(user_id),
        "type": "refresh",
        "iat": now,
        "exp": expire,
    }

    encoded_jwt = jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
    return encoded_jwt


def verify_token(token: str) -> dict:
    """Verify and decode JWT access token.

    Args:
        token: JWT token string

    Returns:
        Decoded token payload dict with keys: sub, user_type, iat, exp

    Raises:
        JWTExpiredError: Token has expired
        JWTInvalidError: Token is invalid or malformed
    """
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        user_id: str = payload.get("sub")
        user_type: str = payload.get("user_type")

        if user_id is None or user_type is None:
            raise JWTInvalidError("Token missing required claims")

        # Keep user_id as a string: user ids are stored as String(36) (see
        # models/user.py), so the DB lookups compare string-to-string. Returning a
        # uuid.UUID here breaks those lookups (no match on SQLite; type error on PG).
        return {"user_id": user_id, "user_type": user_type, **payload}

    except JoseJWTError as e:
        if "expired" in str(e).lower():
            raise JWTExpiredError("Token has expired") from e
        raise JWTInvalidError(f"Invalid token: {e}") from e


def verify_refresh_token(token: str) -> dict:
    """Verify and decode JWT refresh token.

    Args:
        token: JWT refresh token string

    Returns:
        Decoded token payload dict with keys: sub, type, iat, exp

    Raises:
        JWTExpiredError: Token has expired
        JWTInvalidError: Token is invalid or not a refresh token
    """
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        user_id: str = payload.get("sub")
        token_type: str = payload.get("type")

        if user_id is None or token_type != "refresh":
            raise JWTInvalidError("Not a valid refresh token")

        # See verify_token: keep user_id as a string to match String(36) user ids.
        return {"user_id": user_id, **payload}

    except JoseJWTError as e:
        if "expired" in str(e).lower():
            raise JWTExpiredError("Refresh token has expired") from e
        raise JWTInvalidError(f"Invalid refresh token: {e}") from e
