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


# --------------------------------------------------------------------------- #
# Feature 006 — vendor product management
# --------------------------------------------------------------------------- #
@pytest.fixture
def catalog_db():
    """In-memory SQLite session seeded with the catalog taxonomy + two vendors.

    Runtime is PostgreSQL, but the 006 ORM uses only portable column types
    (String/Numeric/DateTime/Enum), so the product service can be exercised on
    SQLite for fast, isolated tests.
    """
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from backend.app import models  # noqa: F401  registers all tables
    from backend.app.catalog import seed_data
    from backend.app.db.session import Base
    from backend.app.models.category import Category
    from backend.app.models.subcategory import SubCategory
    from backend.app.models.vendor import Vendor

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()

    for row in seed_data.iter_categories():
        db.add(Category(**row))
    for row in seed_data.iter_subcategories():
        db.add(SubCategory(**row))
    for vid, uid_, name in (("vend-1", "user-1", "Shop One"), ("vend-2", "user-2", "Shop Two")):
        db.add(
            Vendor(id=vid, user_id=uid_, shop_name=name, shop_location_lat=0.0, shop_location_lon=0.0)
        )
    db.commit()

    yield db
    db.close()
