import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.services.rate_limit import reset_rate_limit_store

client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_state():
    """Reset state before each test."""
    reset_rate_limit_store()
    yield
    reset_rate_limit_store()


@pytest.fixture
def login_response():
    """Login a user and return the response."""
    # Register
    register_payload = {
        "email": "testuser@example.com",
        "password": "SecurePass123!",
        "password_confirm": "SecurePass123!",
    }
    response = client.post("/api/auth/register", json=register_payload)
    assert response.status_code == 201

    # Login
    login_payload = {
        "email": "testuser@example.com",
        "password": "SecurePass123!",
    }
    response = client.post("/api/auth/login", json=login_payload)
    assert response.status_code == 200
    return response.json()


class TestRefreshHappyPath:
    """Happy path: successful token refresh."""

    def test_refresh_returns_new_tokens(self, login_response):
        old_refresh_token = login_response["refresh_token"]
        old_access_token = login_response["access_token"]

        payload = {"refresh_token": old_refresh_token}
        response = client.post("/api/auth/refresh", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["access_token"]
        assert data["refresh_token"]
        assert data["user_id"] == login_response["user_id"]
        assert data["user_type"] == login_response["user_type"]

        # Tokens should be different from old ones
        assert data["access_token"] != old_access_token
        assert data["refresh_token"] != old_refresh_token

    def test_refresh_tokens_are_valid_jwt(self, login_response):
        payload = {"refresh_token": login_response["refresh_token"]}
        response = client.post("/api/auth/refresh", json=payload)

        assert response.status_code == 200
        data = response.json()

        # Both new tokens should be valid JWTs
        assert data["access_token"].count(".") == 2
        assert data["refresh_token"].count(".") == 2


class TestRefreshTokenRotation:
    """Token rotation: old refresh token is invalidated."""

    def test_old_refresh_token_rejected_after_rotation(self, login_response):
        old_refresh_token = login_response["refresh_token"]

        # First refresh succeeds
        payload = {"refresh_token": old_refresh_token}
        response1 = client.post("/api/auth/refresh", json=payload)
        assert response1.status_code == 200
        new_refresh_token = response1.json()["refresh_token"]

        # Attempt to use old token again - should fail
        payload = {"refresh_token": old_refresh_token}
        response2 = client.post("/api/auth/refresh", json=payload)
        assert response2.status_code == 401
        assert "revoked" in response2.json()["detail"].lower() or "invalid" in response2.json()["detail"].lower()

        # New token should work
        payload = {"refresh_token": new_refresh_token}
        response3 = client.post("/api/auth/refresh", json=payload)
        assert response3.status_code == 200


class TestRefreshInvalidToken:
    """Invalid or malformed refresh tokens."""

    def test_refresh_invalid_token_format(self):
        payload = {"refresh_token": "not-a-valid-jwt"}

        response = client.post("/api/auth/refresh", json=payload)

        assert response.status_code == 401
        assert "invalid" in response.json()["detail"].lower()

    def test_refresh_malformed_jwt(self):
        payload = {"refresh_token": "header.payload"}  # Missing signature

        response = client.post("/api/auth/refresh", json=payload)

        assert response.status_code == 401

    def test_refresh_empty_token(self):
        payload = {"refresh_token": ""}

        response = client.post("/api/auth/refresh", json=payload)

        assert response.status_code == 401

    def test_refresh_with_access_token(self, login_response):
        """Using access token instead of refresh token should fail."""
        payload = {"refresh_token": login_response["access_token"]}

        response = client.post("/api/auth/refresh", json=payload)

        assert response.status_code == 401
        assert "invalid" in response.json()["detail"].lower()


class TestRefreshValidation:
    """Input validation."""

    def test_refresh_missing_token(self):
        payload = {}

        response = client.post("/api/auth/refresh", json=payload)

        assert response.status_code == 422  # Pydantic validation error


class TestRefreshChaining:
    """Multiple refreshes in sequence."""

    def test_multiple_refreshes_chain(self, login_response):
        """Test refreshing multiple times in sequence."""
        current_token = login_response["refresh_token"]

        # Refresh 3 times
        for i in range(3):
            payload = {"refresh_token": current_token}
            response = client.post("/api/auth/refresh", json=payload)

            assert response.status_code == 200
            data = response.json()
            assert data["refresh_token"]

            # Get new token for next iteration
            current_token = data["refresh_token"]

    def test_old_tokens_invalid_after_chain(self, login_response):
        """Verify all old tokens are invalid after chain of refreshes."""
        tokens = [login_response["refresh_token"]]

        # Refresh 3 times
        for _ in range(3):
            payload = {"refresh_token": tokens[-1]}
            response = client.post("/api/auth/refresh", json=payload)
            assert response.status_code == 200
            tokens.append(response.json()["refresh_token"])

        # All old tokens (except the current one) should be rejected
        for old_token in tokens[:-1]:
            payload = {"refresh_token": old_token}
            response = client.post("/api/auth/refresh", json=payload)
            assert response.status_code == 401

        # Current token should work
        payload = {"refresh_token": tokens[-1]}
        response = client.post("/api/auth/refresh", json=payload)
        assert response.status_code == 200


class TestRefreshTokenContent:
    """Verify token claims and user info."""

    def test_refresh_user_id_preserved(self, login_response):
        """User ID should be the same in new tokens."""
        original_user_id = login_response["user_id"]

        payload = {"refresh_token": login_response["refresh_token"]}
        response = client.post("/api/auth/refresh", json=payload)

        assert response.status_code == 200
        assert response.json()["user_id"] == original_user_id

    def test_refresh_user_type_preserved(self, login_response):
        """User type should be the same in new tokens."""
        original_user_type = login_response["user_type"]

        payload = {"refresh_token": login_response["refresh_token"]}
        response = client.post("/api/auth/refresh", json=payload)

        assert response.status_code == 200
        assert response.json()["user_type"] == original_user_type
