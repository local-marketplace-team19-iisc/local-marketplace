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
def customer_token():
    """Register and login a customer, return access token."""
    # Register
    register_payload = {
        "email": "customer@example.com",
        "password": "SecurePass123!",
        "password_confirm": "SecurePass123!",
    }
    response = client.post("/api/auth/register", json=register_payload)
    assert response.status_code == 201

    # Login
    login_payload = {
        "email": "customer@example.com",
        "password": "SecurePass123!",
    }
    response = client.post("/api/auth/login", json=login_payload)
    assert response.status_code == 200
    return response.json()["access_token"]


@pytest.fixture
def vendor_token():
    """Register and login a vendor, return access token."""
    # Register
    register_payload = {
        "email": "vendor@example.com",
        "password": "VendorPass123!",
        "password_confirm": "VendorPass123!",
        "shop_name": "Test Shop",
        "location": {"lat": 40.7128, "lon": -74.0060},
        "shop_description": "A test shop",
    }
    response = client.post("/api/auth/register-vendor", json=register_payload)
    assert response.status_code == 201
    response.json()

    # Login
    login_payload = {
        "email": "vendor@example.com",
        "password": "VendorPass123!",
    }
    response = client.post("/api/auth/login", json=login_payload)
    assert response.status_code == 200
    return response.json()["access_token"]


class TestGetMeHappyPath:
    """Happy path: successful GET /me."""

    def test_get_me_customer(self, customer_token):
        headers = {"Authorization": f"Bearer {customer_token}"}

        response = client.get("/api/auth/me", headers=headers)

        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "customer@example.com"
        assert data["user_type"] == "customer"
        assert data["id"]
        assert "vendor_id" not in data or data["vendor_id"] is None

    def test_get_me_vendor(self, vendor_token):
        headers = {"Authorization": f"Bearer {vendor_token}"}

        response = client.get("/api/auth/me", headers=headers)

        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "vendor@example.com"
        assert data["user_type"] == "vendor"
        assert data["id"]
        assert data["vendor_id"]
        assert data["shop_name"] == "Test Shop"
        assert data["shop_description"] == "A test shop"


class TestGetMeCustomerVendorDifference:
    """Verify different user types return correct fields."""

    def test_customer_has_no_vendor_fields(self, customer_token):
        headers = {"Authorization": f"Bearer {customer_token}"}

        response = client.get("/api/auth/me", headers=headers)

        assert response.status_code == 200
        data = response.json()
        assert data["user_type"] == "customer"
        assert data.get("vendor_id") is None
        assert data.get("shop_name") is None

    def test_vendor_has_vendor_fields(self, vendor_token):
        headers = {"Authorization": f"Bearer {vendor_token}"}

        response = client.get("/api/auth/me", headers=headers)

        assert response.status_code == 200
        data = response.json()
        assert data["user_type"] == "vendor"
        assert data["vendor_id"]
        assert data["shop_name"]


class TestGetMeAuthorizationErrors:
    """Missing or invalid authorization."""

    def test_get_me_no_auth_header(self):
        response = client.get("/api/auth/me")

        assert response.status_code == 401
        assert "authorization" in response.json()["detail"].lower()

    def test_get_me_missing_bearer_prefix(self, customer_token):
        headers = {"Authorization": customer_token}  # Missing "Bearer "

        response = client.get("/api/auth/me", headers=headers)

        assert response.status_code == 401
        assert "authorization" in response.json()["detail"].lower()

    def test_get_me_invalid_token(self):
        headers = {"Authorization": "Bearer invalid-token"}

        response = client.get("/api/auth/me", headers=headers)

        assert response.status_code == 401

    def test_get_me_expired_token(self):
        """Using an expired token should fail."""
        headers = {"Authorization": "Bearer header.payload.signature"}

        response = client.get("/api/auth/me", headers=headers)

        assert response.status_code == 401

    def test_get_me_malformed_header(self, customer_token):
        headers = {"Authorization": f"Token {customer_token}"}  # Wrong prefix

        response = client.get("/api/auth/me", headers=headers)

        assert response.status_code == 401


class TestGetMeTokenTypes:
    """Verify only access tokens work, not refresh tokens."""

    def test_get_me_with_refresh_token(self):
        """Using refresh token instead of access token should fail."""
        # Register and login
        register_payload = {
            "email": "test@example.com",
            "password": "SecurePass123!",
            "password_confirm": "SecurePass123!",
        }
        response = client.post("/api/auth/register", json=register_payload)
        assert response.status_code == 201
        refresh_token = response.json()["refresh_token"]

        # Try to use refresh token for /me
        headers = {"Authorization": f"Bearer {refresh_token}"}
        response = client.get("/api/auth/me", headers=headers)

        assert response.status_code == 401


class TestGetMeConsistency:
    """Data consistency across multiple requests."""

    def test_get_me_returns_consistent_data(self, customer_token):
        """Multiple requests should return same user data."""
        headers = {"Authorization": f"Bearer {customer_token}"}

        # First request
        response1 = client.get("/api/auth/me", headers=headers)
        assert response1.status_code == 200
        data1 = response1.json()

        # Second request
        response2 = client.get("/api/auth/me", headers=headers)
        assert response2.status_code == 200
        data2 = response2.json()

        # Should be identical
        assert data1["email"] == data2["email"]
        assert data1["user_type"] == data2["user_type"]
        assert data1["id"] == data2["id"]


class TestGetMeWithRefreshedToken:
    """Verify /me works with refreshed access token."""

    def test_get_me_after_refresh(self, customer_token):
        """After refreshing token, GET /me should work with new token."""
        # First, get initial user data
        headers = {"Authorization": f"Bearer {customer_token}"}
        response = client.get("/api/auth/me", headers=headers)
        assert response.status_code == 200
        response.json()["id"]

        # Need to refresh (but we need the refresh token from login)
        # Register and login fresh for this test
        register_payload = {
            "email": "refresh_test@example.com",
            "password": "SecurePass123!",
            "password_confirm": "SecurePass123!",
        }
        response = client.post("/api/auth/register", json=register_payload)
        assert response.status_code == 201
        login_data = response.json()

        # Get new access token
        refresh_payload = {"refresh_token": login_data["refresh_token"]}
        response = client.post("/api/auth/refresh", json=refresh_payload)
        assert response.status_code == 200
        new_access_token = response.json()["access_token"]

        # Use new token for /me
        headers = {"Authorization": f"Bearer {new_access_token}"}
        response = client.get("/api/auth/me", headers=headers)
        assert response.status_code == 200
        assert response.json()["email"] == "refresh_test@example.com"


class TestGetMeVendorDetails:
    """Vendor-specific details in GET /me."""

    def test_vendor_location_returned(self, vendor_token):
        headers = {"Authorization": f"Bearer {vendor_token}"}

        response = client.get("/api/auth/me", headers=headers)

        assert response.status_code == 200
        data = response.json()
        assert "shop_location" in data
        # Location is returned as PostGIS geometry object

    def test_vendor_without_description(self):
        """Vendor without description should still return other fields."""
        # Register vendor without description
        register_payload = {
            "email": "nodesc@example.com",
            "password": "VendorPass123!",
            "password_confirm": "VendorPass123!",
            "shop_name": "No Description Shop",
            "location": {"lat": 51.5074, "lon": -0.1278},
        }
        response = client.post("/api/auth/register-vendor", json=register_payload)
        assert response.status_code == 201
        access_token = response.json()["access_token"]

        # Get user info
        headers = {"Authorization": f"Bearer {access_token}"}
        response = client.get("/api/auth/me", headers=headers)

        assert response.status_code == 200
        data = response.json()
        assert data["shop_name"] == "No Description Shop"
        assert data["shop_description"] is None or data["shop_description"] == ""
