import uuid
from datetime import datetime

import pytest


class FakeSession:
    """Stand-in for SQLAlchemy Session for unit tests without real DB."""

    def __init__(self):
        self.added = []
        self.committed = False

    def add(self, instance):
        self.added.append(instance)

    def flush(self):
        pass

    def commit(self):
        self.committed = True

    def refresh(self, instance):
        pass

    def query(self, model):
        return FakeQuery()

    def rollback(self):
        self.added.clear()
        self.committed = False


class FakeQuery:
    """Stand-in for SQLAlchemy Query object."""

    def __init__(self):
        self._filters = []

    def filter(self, *args):
        return self

    def first(self):
        return None


@pytest.fixture
def fake_session():
    """Fixture providing a FakeSession for testing."""
    return FakeSession()


@pytest.fixture
def sample_customer_payload():
    """Sample customer registration payload."""
    return {
        "email": "customer@example.com",
        "password": "SecurePass123!",
    }


@pytest.fixture
def sample_vendor_payload():
    """Sample vendor registration payload."""
    return {
        "email": "vendor@example.com",
        "password": "SecurePass123!",
        "shop_name": "My Amazing Shop",
        "location": (40.7128, -74.0060),  # NYC coordinates
        "shop_description": "A great shop with amazing products",
    }


@pytest.fixture
def sample_user_id():
    """Sample UUID for user ID."""
    return uuid.uuid4()


@pytest.fixture
def sample_timestamp():
    """Sample UTC timestamp."""
    return datetime.utcnow()
