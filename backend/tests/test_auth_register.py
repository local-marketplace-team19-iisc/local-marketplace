import json

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.models.user import User
from backend.app.services.rate_limit import reset_rate_limit_store
from backend.tests.conftest import FakeSession

client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_state():
    """Reset rate limiting and other state before each test."""
    reset_rate_limit_store()
    yield
    reset_rate_limit_store()


class TestRegisterCustomerHappyPath:
    """Happy path: successful customer registration."""

    def test_register_customer_with_valid_data(self):
        payload = {
            "email": "customer@example.com",
            "password": "SecurePass123!",
            "password_confirm": "SecurePass123!",
        }

        response = client.post("/api/auth/register", json=payload)

        assert response.status_code == 201
        data = response.json()
        assert data["user_type"] == "customer"
        assert data["user_id"]
        assert data["access_token"]
        assert data["refresh_token"]
        assert "vendor_id" not in data

    def test_register_multiple_customers_different_emails(self):
        for i in range(3):
            payload = {
                "email": f"customer{i}@example.com",
                "password": "SecurePass123!",
                "password_confirm": "SecurePass123!",
            }
            response = client.post("/api/auth/register", json=payload)
            assert response.status_code == 201


class TestRegisterCustomerValidation:
    """Validation errors in customer registration."""

    def test_register_passwords_dont_match(self):
        payload = {
            "email": "user@example.com",
            "password": "SecurePass123!",
            "password_confirm": "DifferentPass123!",
        }

        response = client.post("/api/auth/register", json=payload)

        assert response.status_code == 400
        assert "do not match" in response.json()["detail"].lower()

    def test_register_password_too_short(self):
        payload = {
            "email": "user@example.com",
            "password": "Short1!",
            "password_confirm": "Short1!",
        }

        response = client.post("/api/auth/register", json=payload)

        assert response.status_code == 400
        assert "8 characters" in response.json()["detail"]

    def test_register_password_no_uppercase(self):
        payload = {
            "email": "user@example.com",
            "password": "securepass123!",
            "password_confirm": "securepass123!",
        }

        response = client.post("/api/auth/register", json=payload)

        assert response.status_code == 400
        assert "uppercase" in response.json()["detail"].lower()

    def test_register_password_no_digit(self):
        payload = {
            "email": "user@example.com",
            "password": "SecurePass!",
            "password_confirm": "SecurePass!",
        }

        response = client.post("/api/auth/register", json=payload)

        assert response.status_code == 400
        assert "digit" in response.json()["detail"].lower()

    def test_register_password_no_special_char(self):
        payload = {
            "email": "user@example.com",
            "password": "SecurePass123",
            "password_confirm": "SecurePass123",
        }

        response = client.post("/api/auth/register", json=payload)

        assert response.status_code == 400
        assert "special character" in response.json()["detail"].lower()

    def test_register_invalid_email(self):
        payload = {
            "email": "not-an-email",
            "password": "SecurePass123!",
            "password_confirm": "SecurePass123!",
        }

        response = client.post("/api/auth/register", json=payload)

        assert response.status_code == 422  # Pydantic validation error


class TestRegisterCustomerDuplicate:
    """Duplicate email registration."""

    def test_register_duplicate_email(self):
        payload = {
            "email": "duplicate@example.com",
            "password": "SecurePass123!",
            "password_confirm": "SecurePass123!",
        }

        # First registration succeeds
        response1 = client.post("/api/auth/register", json=payload)
        assert response1.status_code == 201

        # Second registration with same email fails
        response2 = client.post("/api/auth/register", json=payload)
        assert response2.status_code == 400
        assert "already registered" in response2.json()["detail"].lower()


class TestRegisterVendorHappyPath:
    """Happy path: successful vendor registration."""

    def test_register_vendor_with_valid_data(self):
        payload = {
            "email": "vendor@example.com",
            "password": "SecurePass123!",
            "password_confirm": "SecurePass123!",
            "shop_name": "My Amazing Shop",
            "location": {"lat": 40.7128, "lon": -74.0060},
            "shop_description": "A great place to shop",
        }

        response = client.post("/api/auth/register-vendor", json=payload)

        assert response.status_code == 201
        data = response.json()
        assert data["user_type"] == "vendor"
        assert data["user_id"]
        assert data["vendor_id"]
        assert data["shop_name"] == "My Amazing Shop"
        assert data["access_token"]
        assert data["refresh_token"]

    def test_register_vendor_without_description(self):
        payload = {
            "email": "vendor2@example.com",
            "password": "SecurePass123!",
            "password_confirm": "SecurePass123!",
            "shop_name": "Another Shop",
            "location": {"lat": 51.5074, "lon": -0.1278},
        }

        response = client.post("/api/auth/register-vendor", json=payload)

        assert response.status_code == 201
        assert response.json()["user_type"] == "vendor"


class TestRegisterVendorValidation:
    """Validation errors in vendor registration."""

    def test_register_vendor_invalid_latitude(self):
        payload = {
            "email": "vendor@example.com",
            "password": "SecurePass123!",
            "password_confirm": "SecurePass123!",
            "shop_name": "Shop",
            "location": {"lat": 91, "lon": -74.0060},  # lat > 90
        }

        response = client.post("/api/auth/register-vendor", json=payload)

        assert response.status_code == 400
        assert "location" in response.json()["detail"].lower()

    def test_register_vendor_invalid_longitude(self):
        payload = {
            "email": "vendor@example.com",
            "password": "SecurePass123!",
            "password_confirm": "SecurePass123!",
            "shop_name": "Shop",
            "location": {"lat": 40.7128, "lon": 181},  # lon > 180
        }

        response = client.post("/api/auth/register-vendor", json=payload)

        assert response.status_code == 400
        assert "location" in response.json()["detail"].lower()

    def test_register_vendor_missing_location_field(self):
        payload = {
            "email": "vendor@example.com",
            "password": "SecurePass123!",
            "password_confirm": "SecurePass123!",
            "shop_name": "Shop",
            "location": {"lat": 40.7128},  # missing 'lon'
        }

        response = client.post("/api/auth/register-vendor", json=payload)

        assert response.status_code == 400

    def test_register_vendor_passwords_dont_match(self):
        payload = {
            "email": "vendor@example.com",
            "password": "SecurePass123!",
            "password_confirm": "DifferentPass123!",
            "shop_name": "Shop",
            "location": {"lat": 40.7128, "lon": -74.0060},
        }

        response = client.post("/api/auth/register-vendor", json=payload)

        assert response.status_code == 400
        assert "do not match" in response.json()["detail"].lower()


class TestRegisterRateLimiting:
    """Rate limiting on signup (10 per IP per hour)."""

    def test_signup_rate_limit_blocking(self):
        # Register 10 customers successfully
        for i in range(10):
            payload = {
                "email": f"customer{i}@example.com",
                "password": "SecurePass123!",
                "password_confirm": "SecurePass123!",
            }
            response = client.post("/api/auth/register", json=payload)
            assert response.status_code == 201

        # 11th attempt should be rate limited
        payload = {
            "email": "customer11@example.com",
            "password": "SecurePass123!",
            "password_confirm": "SecurePass123!",
        }
        response = client.post("/api/auth/register", json=payload)
        assert response.status_code == 429
        assert "too many" in response.json()["detail"].lower()
