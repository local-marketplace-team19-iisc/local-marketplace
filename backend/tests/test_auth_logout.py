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


class TestLogoutHappyPath:
    """Happy path: successful logout."""

    def test_logout_returns_204(self, login_response):
        payload = {"refresh_token": login_response["refresh_token"]}

        response = client.post("/api/auth/logout", json=payload)

        assert response.status_code == 204
        assert response.content == b""  # No content in response


class TestLogoutTokenRevocation:
    """Logout revokes the refresh token."""

    def test_refresh_fails_after_logout(self, login_response):
        refresh_token = login_response["refresh_token"]

        # Logout
        logout_payload = {"refresh_token": refresh_token}
        response = client.post("/api/auth/logout", json=logout_payload)
        assert response.status_code == 204

        # Try to refresh with revoked token - should fail
        refresh_payload = {"refresh_token": refresh_token}
        response = client.post("/api/auth/refresh", json=refresh_payload)
        assert response.status_code == 401
        assert "revoked" in response.json()["detail"].lower() or "invalid" in response.json()["detail"].lower()


class TestLogoutIdempotent:
    """Logout is idempotent."""

    def test_logout_twice_same_token(self, login_response):
        refresh_token = login_response["refresh_token"]
        payload = {"refresh_token": refresh_token}

        # First logout
        response1 = client.post("/api/auth/logout", json=payload)
        assert response1.status_code == 204

        # Second logout with same token
        response2 = client.post("/api/auth/logout", json=payload)
        assert response2.status_code == 204

    def test_logout_invalid_token_still_succeeds(self):
        """Logout with invalid token should still return 204 (idempotent)."""
        payload = {"refresh_token": "invalid-token"}

        response = client.post("/api/auth/logout", json=payload)

        # Should succeed (idempotent)
        assert response.status_code == 204


class TestLogoutValidation:
    """Input validation."""

    def test_logout_missing_token(self):
        payload = {}

        response = client.post("/api/auth/logout", json=payload)

        assert response.status_code == 422  # Pydantic validation error


class TestLogoutWithMultipleTokens:
    """Logout only affects the specified token."""

    def test_logout_does_not_affect_other_tokens(self, login_response):
        """Logging out with one token shouldn't affect other tokens."""
        # Get first refresh token
        token1 = login_response["refresh_token"]

        # Get second refresh token (new login)
        login_payload = {
            "email": "testuser@example.com",
            "password": "SecurePass123!",
        }
        response = client.post("/api/auth/login", json=login_payload)
        assert response.status_code == 200
        token2 = response.json()["refresh_token"]

        # Logout with first token
        logout_payload = {"refresh_token": token1}
        response = client.post("/api/auth/logout", json=logout_payload)
        assert response.status_code == 204

        # First token should be revoked
        refresh_payload = {"refresh_token": token1}
        response = client.post("/api/auth/refresh", json=refresh_payload)
        assert response.status_code == 401

        # Second token should still work
        refresh_payload = {"refresh_token": token2}
        response = client.post("/api/auth/refresh", json=refresh_payload)
        assert response.status_code == 200


class TestLogoutFlow:
    """Complete logout flow."""

    def test_register_login_logout_flow(self):
        """Complete flow: register, login, logout."""
        # Register
        register_payload = {
            "email": "newuser@example.com",
            "password": "SecurePass123!",
            "password_confirm": "SecurePass123!",
        }
        response = client.post("/api/auth/register", json=register_payload)
        assert response.status_code == 201
        register_data = response.json()

        # Login
        login_payload = {
            "email": "newuser@example.com",
            "password": "SecurePass123!",
        }
        response = client.post("/api/auth/login", json=login_payload)
        assert response.status_code == 200
        login_data = response.json()

        # Logout
        logout_payload = {"refresh_token": login_data["refresh_token"]}
        response = client.post("/api/auth/logout", json=logout_payload)
        assert response.status_code == 204

        # Verify token is revoked
        refresh_payload = {"refresh_token": login_data["refresh_token"]}
        response = client.post("/api/auth/refresh", json=refresh_payload)
        assert response.status_code == 401
