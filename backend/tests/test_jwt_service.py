import uuid
from datetime import datetime, timedelta

import pytest

from backend.app.services.jwt_service import (
    JWTExpiredError,
    JWTInvalidError,
    create_access_token,
    create_refresh_token,
    verify_refresh_token,
    verify_token,
)


class TestAccessTokenCreation:
    """Tests for JWT access token creation."""

    def test_create_access_token_returns_valid_jwt(self):
        user_id = uuid.uuid4()
        user_type = "customer"

        token = create_access_token(user_id, user_type)

        assert isinstance(token, str)
        assert len(token) > 20
        assert token.count(".") == 2  # JWT has 3 parts separated by dots

    def test_create_access_token_with_custom_expiry(self):
        user_id = uuid.uuid4()
        user_type = "vendor"
        custom_expiry = timedelta(hours=2)

        token = create_access_token(user_id, user_type, expires_delta=custom_expiry)

        assert isinstance(token, str)
        # Verify the token contains the custom expiry
        payload = verify_token(token)
        assert "exp" in payload


class TestAccessTokenVerification:
    """Tests for JWT access token verification."""

    def test_verify_valid_token_returns_payload(self):
        user_id = uuid.uuid4()
        user_type = "customer"
        token = create_access_token(user_id, user_type)

        payload = verify_token(token)

        assert payload["user_id"] == user_id
        assert payload["user_type"] == user_type
        assert "iat" in payload
        assert "exp" in payload

    def test_verify_token_with_wrong_secret_fails(self, monkeypatch):
        user_id = uuid.uuid4()
        user_type = "customer"
        token = create_access_token(user_id, user_type)

        # Simulate wrong secret by monkeypatching settings
        from backend.app import core
        original_secret = core.config.settings.JWT_SECRET
        monkeypatch.setattr(core.config.settings, "JWT_SECRET", "different-secret")

        with pytest.raises(JWTInvalidError):
            verify_token(token)

        # Restore original secret
        monkeypatch.setattr(core.config.settings, "JWT_SECRET", original_secret)

    def test_verify_token_with_missing_claims_fails(self):
        from jose import jwt

        from backend.app.core.config import settings

        # Create token without user_type claim
        payload = {
            "sub": str(uuid.uuid4()),
            "iat": datetime.utcnow(),
            "exp": datetime.utcnow() + timedelta(hours=1),
        }
        bad_token = jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)

        with pytest.raises(JWTInvalidError):
            verify_token(bad_token)


class TestRefreshTokenCreation:
    """Tests for JWT refresh token creation."""

    def test_create_refresh_token_returns_valid_jwt(self):
        user_id = uuid.uuid4()

        token = create_refresh_token(user_id)

        assert isinstance(token, str)
        assert len(token) > 20
        assert token.count(".") == 2

    def test_create_refresh_token_with_custom_expiry(self):
        user_id = uuid.uuid4()
        custom_expiry = timedelta(days=14)

        token = create_refresh_token(user_id, expires_delta=custom_expiry)

        assert isinstance(token, str)
        payload = verify_refresh_token(token)
        assert "exp" in payload


class TestRefreshTokenVerification:
    """Tests for JWT refresh token verification."""

    def test_verify_valid_refresh_token_returns_payload(self):
        user_id = uuid.uuid4()
        token = create_refresh_token(user_id)

        payload = verify_refresh_token(token)

        assert payload["user_id"] == user_id
        assert payload["type"] == "refresh"
        assert "iat" in payload
        assert "exp" in payload

    def test_verify_refresh_token_rejects_access_token(self):
        user_id = uuid.uuid4()
        access_token = create_access_token(user_id, "customer")

        with pytest.raises(JWTInvalidError):
            verify_refresh_token(access_token)

    def test_verify_expired_token_raises_error(self):
        user_id = uuid.uuid4()
        from datetime import datetime

        from jose import jwt

        from backend.app.core.config import settings

        # Create an already-expired token
        past_time = datetime.utcnow() - timedelta(hours=1)
        payload = {
            "sub": str(user_id),
            "type": "refresh",
            "iat": past_time,
            "exp": past_time,  # Already expired
        }
        expired_token = jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)

        with pytest.raises(JWTExpiredError):
            verify_refresh_token(expired_token)


class TestTokenRoundTrip:
    """Integration tests for token creation and verification."""

    def test_access_token_roundtrip(self):
        user_id = uuid.uuid4()
        user_type = "vendor"

        token = create_access_token(user_id, user_type)
        payload = verify_token(token)

        assert payload["user_id"] == user_id
        assert payload["user_type"] == user_type

    def test_refresh_token_roundtrip(self):
        user_id = uuid.uuid4()

        token = create_refresh_token(user_id)
        payload = verify_refresh_token(token)

        assert payload["user_id"] == user_id
        assert payload["type"] == "refresh"
