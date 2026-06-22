"""Unit tests for the catalog domain models (feature 005-catalog).

Covers the acceptance criteria in specs/005-catalog/spec.md §3, including the
pricing rules (FR-16..FR-18). Referential FK *existence* (-> an existing
Category/SubCategory) is a persistence-layer concern and is out of scope here;
these tests assert presence, type, and value rules.
"""

from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError

from backend.app.catalog.enums import UnitType
from backend.app.catalog.models import Category, Product, SubCategory


def _valid_product_kwargs(**overrides) -> dict:
    kwargs = dict(
        subcategory_id=uuid4(),
        product_name="Amul Full Cream Milk",
        brand="Amul",
        description="Full cream milk",
        unit_type=UnitType.LITER,
        unit_value=Decimal("1"),
        price_inr=Decimal("65.50"),
    )
    kwargs.update(overrides)
    return kwargs


# --- Category (FR-1, FR-2) ---

def test_category_with_null_parent_is_accepted():
    cat = Category(category_name="Dairy")
    assert cat.parent_category_id is None


def test_category_with_non_null_parent_is_rejected():
    with pytest.raises(ValidationError):
        Category(category_name="Dairy", parent_category_id=uuid4())


def test_category_blank_name_is_rejected():
    with pytest.raises(ValidationError):
        Category(category_name="   ")


# --- SubCategory (FR-3, FR-4) ---

def test_subcategory_references_one_category():
    parent = uuid4()
    sub = SubCategory(
        subcategory_name="Milk",
        parent_category_id=parent,
        subcategory_description="Milk products",
    )
    assert sub.parent_category_id == parent


def test_subcategory_without_parent_is_rejected():
    with pytest.raises(ValidationError):
        SubCategory(subcategory_name="Milk", subcategory_description="Milk products")


# --- Product assignment + units (FR-6, FR-7, FR-8) ---

def test_product_requires_subcategory_id():
    kwargs = _valid_product_kwargs()
    del kwargs["subcategory_id"]
    with pytest.raises(ValidationError):
        Product(**kwargs)


def test_product_invalid_unit_type_rejected():
    with pytest.raises(ValidationError):
        Product(**_valid_product_kwargs(unit_type="TONNE"))


@pytest.mark.parametrize("value", [Decimal("0"), Decimal("-1")])
def test_product_non_positive_unit_value_rejected(value):
    with pytest.raises(ValidationError):
        Product(**_valid_product_kwargs(unit_value=value))


# --- Brand (FR-9) ---

def test_product_without_brand_is_rejected():
    kwargs = _valid_product_kwargs()
    del kwargs["brand"]
    with pytest.raises(ValidationError):
        Product(**kwargs)


def test_product_with_generic_brand_is_accepted():
    p = Product(**_valid_product_kwargs(brand="Generic"))
    assert p.brand == "Generic"


# --- Pricing (FR-16, FR-17, FR-18) ---

@pytest.mark.parametrize("value", ["10.00", "65.50", "999.99"])
def test_price_inr_valid_values_accepted(value):
    p = Product(**_valid_product_kwargs(price_inr=Decimal(value)))
    assert p.price_inr == Decimal(value)


@pytest.mark.parametrize("value", ["10", "10.1", "0.00", "-5.00"])
def test_price_inr_invalid_values_rejected(value):
    with pytest.raises(ValidationError):
        Product(**_valid_product_kwargs(price_inr=Decimal(value)))


def test_price_inr_is_mandatory():
    kwargs = _valid_product_kwargs()
    del kwargs["price_inr"]
    with pytest.raises(ValidationError):
        Product(**kwargs)


def test_price_inr_float_is_rejected():
    # FR-18: floats can't represent exact 2-dp money; a Decimal/str is required.
    with pytest.raises(ValidationError):
        Product(**_valid_product_kwargs(price_inr=10.0))


def test_currency_is_not_configurable():
    # FR-17: there is no currency field and INR is fixed; extra fields are forbidden.
    with pytest.raises(ValidationError):
        Product(**_valid_product_kwargs(currency="USD"))


# --- Hierarchy, duplicates, determinism (§3) ---

def test_full_hierarchy_can_be_represented():
    # "Dairy -> Milk -> Amul Full Cream Milk (LITER, 1)" end-to-end.
    cat = Category(category_name="Dairy")
    sub = SubCategory(
        subcategory_name="Milk",
        parent_category_id=cat.category_id,
        subcategory_description="Milk products",
    )
    prod = Product(
        **_valid_product_kwargs(
            subcategory_id=sub.subcategory_id,
            unit_type=UnitType.LITER,
            unit_value=Decimal("1"),
            price_inr=Decimal("65.50"),
        )
    )
    assert sub.parent_category_id == cat.category_id
    assert prod.subcategory_id == sub.subcategory_id


def test_duplicate_product_definitions_both_accepted():
    # FR-15: no catalog-level uniqueness; identical definitions get distinct ids.
    kwargs = _valid_product_kwargs()
    p1 = Product(**kwargs)
    p2 = Product(**kwargs)
    assert p1.product_id != p2.product_id
