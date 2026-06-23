"""Service tests: create-from-description (feature 006 FR-4/FR-5/FR-6)."""

import pytest

from backend.app.catalog.enums import UnitType
from backend.app.services import product_service


def test_create_from_description_persists_and_maps_fields(catalog_db):
    p = product_service.create_from_description(
        catalog_db, "vend-1", "Amul Full Cream Milk 1L, ₹65.50, 30 in stock, Dairy"
    )
    assert p.name == "Amul Full Cream Milk"
    assert p.brand == "Amul"
    assert p.price_inr == 65.5
    assert p.stock == 30
    assert p.unit_type == UnitType.LITER
    assert p.category == "Dairy"
    assert p.vendorId == "vend-1"

    listed = product_service.list_products(catalog_db, vendor_id="vend-1")
    assert len(listed) == 1
    assert listed[0].id == p.id


def test_create_from_description_missing_price_rejected(catalog_db):
    with pytest.raises(product_service.ProductValidationError):
        product_service.create_from_description(catalog_db, "vend-1", "some bread please")


def test_unknown_category_falls_back_to_general(catalog_db):
    p = product_service.create_from_description(catalog_db, "vend-1", "Mystery widget ₹10")
    assert p.category == "General"
