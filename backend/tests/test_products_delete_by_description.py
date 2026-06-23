"""Service tests: delete-by-description, vendor-scoped (feature 006 FR-8/FR-9)."""

import pytest

from backend.app.services import product_service


def _seed_two(db, vendor_id="vend-1"):
    product_service.create_from_description(db, vendor_id, "Amul Butter 100g ₹58 Dairy")
    product_service.create_from_description(db, vendor_id, "Britannia Bread 400g ₹45 Bakery")


def test_delete_by_description_removes_best_match(catalog_db):
    _seed_two(catalog_db)
    deleted = product_service.delete_by_description(catalog_db, "vend-1", "remove the butter")
    assert "Butter" in deleted.name
    remaining = product_service.list_products(catalog_db, vendor_id="vend-1")
    assert len(remaining) == 1
    assert "Bread" in remaining[0].name


def test_delete_by_description_no_match_raises(catalog_db):
    _seed_two(catalog_db)
    with pytest.raises(product_service.ProductNotFoundError):
        product_service.delete_by_description(catalog_db, "vend-1", "remove the laptop")


def test_delete_by_description_only_targets_own_products(catalog_db):
    # vend-2 owns the butter; vend-1 must not be able to delete it.
    product_service.create_from_description(catalog_db, "vend-2", "Amul Butter 100g ₹58 Dairy")
    with pytest.raises(product_service.ProductNotFoundError):
        product_service.delete_by_description(catalog_db, "vend-1", "remove the butter")
    # vend-2 can.
    deleted = product_service.delete_by_description(catalog_db, "vend-2", "remove the butter")
    assert "Butter" in deleted.name
