import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.services.rate_limit import reset_rate_limit_store

client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_state():
    """Reset rate limiting before each test."""
    reset_rate_limit_store()
    yield
    reset_rate_limit_store()


@pytest.fixture
def registered_customer():
    """Create a registered customer for login tests."""
    payload = {
        "email": "testuser@example.com",
        "password": "SecurePass123!",
        "password_confirm": "SecurePass123!",
    }
    response = client.post("/api/auth/register", json=payload)
    assert response.status_code == 201
    return response.json()


@pytest.fixture
def registered_vendor():
    """Create a registered vendor for login tests."""
    payload = {
        "email": "testvendor@example.com",
        "password": "VendorPass123!",
        "password_confirm": "VendorPass123!",
        "shop_name": "Test Shop",
        "location": {"lat": 40.7128, "lon": -74.0060},
    }
    response = client.post("/api/auth/register-vendor", json=payload)
    assert response.status_code == 201
    return response.json()


class TestLoginHappyPath:
    """Happy path: successful login."""

    def test_login_customer_success(self, registered_customer):
        payload = {
            "email": "testuser@example.com",
            "password": "SecurePass123!",
        }

        response = client.post("/api/auth/login", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["user_type"] == "customer"
        assert data["access_token"]
        assert data["refresh_token"]
        assert data["user_id"] == registered_customer["user_id"]

    def test_login_vendor_success(self, registered_vendor):
        payload = {
            "email": "testvendor@example.com",
            "password": "VendorPass123!",
        }

        response = client.post("/api/auth/login", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["user_type"] == "vendor"
        assert data["access_token"]
        assert data["refresh_token"]


class TestLoginInvalidCredentials:
    """Invalid email or password."""

    def test_login_nonexistent_email(self, registered_customer):
        payload = {
            "email": "nonexistent@example.com",
            "password": "SecurePass123!",
        }

        response = client.post("/api/auth/login", json=payload)

        assert response.status_code == 401
        assert "invalid" in response.json()["detail"].lower()

    def test_login_wrong_password(self, registered_customer):
        payload = {
            "email": "testuser@example.com",
            "password": "WrongPassword123!",
        }

        response = client.post("/api/auth/login", json=payload)

        assert response.status_code == 401
        assert "invalid" in response.json()["detail"].lower()

    def test_login_generic_error_message(self, registered_customer):
        """Verify generic error (no user enumeration)."""
        # Test with wrong password
        response1 = client.post(
            "/api/auth/login",
            json={"email": "testuser@example.com", "password": "Wrong123!"},
        )

        # Test with nonexistent email
        response2 = client.post(
            "/api/auth/login",
            json={"email": "noexist@example.com", "password": "SecurePass123!"},
        )

        # Both should return 401 with similar generic message
        assert response1.status_code == 401
        assert response2.status_code == 401
        assert response1.json()["detail"] == response2.json()["detail"]


class TestLoginRateLimiting:
    """Rate limiting on failed login attempts (5 per 15 min)."""

    def test_login_rate_limit_blocking(self, registered_customer):
        # Attempt 5 failed logins
        for _ in range(5):
            response = client.post(
                "/api/auth/login",
                json={"email": "testuser@example.com", "password": "WrongPass123!"},
            )
            assert response.status_code == 401

        # 6th attempt should be rate limited
        response = client.post(
            "/api/auth/login",
            json={"email": "testuser@example.com", "password": "SecurePass123!"},
        )
        assert response.status_code == 429
        assert "too many" in response.json()["detail"].lower()

    def test_login_clear_failed_attempts_on_success(self, registered_customer):
        # Attempt 3 failed logins
        for _ in range(3):
            response = client.post(
                "/api/auth/login",
                json={"email": "testuser@example.com", "password": "WrongPass123!"},
            )
            assert response.status_code == 401

        # Successful login should clear counter
        response = client.post(
            "/api/auth/login",
            json={"email": "testuser@example.com", "password": "SecurePass123!"},
        )
        assert response.status_code == 200

        # Now can attempt more failed logins without immediate rate limit
        for _ in range(3):
            response = client.post(
                "/api/auth/login",
                json={"email": "testuser@example.com", "password": "WrongPass123!"},
            )
            assert response.status_code == 401

        # Should still be allowed (less than 5 since counter was cleared)
        response = client.post(
            "/api/auth/login",
            json={"email": "testuser@example.com", "password": "WrongPass123!"},
        )
        assert response.status_code == 401


class TestLoginValidation:
    """Input validation."""

    def test_login_missing_email(self):
        payload = {
            "password": "SecurePass123!",
        }

        response = client.post("/api/auth/login", json=payload)

        assert response.status_code == 422  # Pydantic validation error

    def test_login_missing_password(self):
        payload = {
            "email": "test@example.com",
        }

        response = client.post("/api/auth/login", json=payload)

        assert response.status_code == 422

    def test_login_invalid_email_format(self):
        payload = {
            "email": "not-an-email",
            "password": "SecurePass123!",
        }

        response = client.post("/api/auth/login", json=payload)

        assert response.status_code == 422


class TestLoginTokenContent:
    """Verify token content and structure."""

    def test_login_access_token_valid_jwt(self, registered_customer):
        response = client.post(
            "/api/auth/login",
            json={"email": "testuser@example.com", "password": "SecurePass123!"},
        )

        assert response.status_code == 200
        data = response.json()
        token = data["access_token"]

        # JWT has 3 parts separated by dots
        assert token.count(".") == 2

    def test_login_refresh_token_valid_jwt(self, registered_customer):
        response = client.post(
            "/api/auth/login",
            json={"email": "testuser@example.com", "password": "SecurePass123!"},
        )

        assert response.status_code == 200
        data = response.json()
        token = data["refresh_token"]

        # JWT has 3 parts separated by dots
        assert token.count(".") == 2

    def test_login_tokens_are_different(self, registered_customer):
        response = client.post(
            "/api/auth/login",
            json={"email": "testuser@example.com", "password": "SecurePass123!"},
        )

        assert response.status_code == 200
        data = response.json()

        # Access and refresh tokens should be different
        assert data["access_token"] != data["refresh_token"]
