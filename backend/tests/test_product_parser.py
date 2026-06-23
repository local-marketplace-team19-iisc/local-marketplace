"""Unit tests for the deterministic description parser (feature 006 FR-4)."""

from decimal import Decimal

from backend.app.catalog.enums import UnitType
from backend.app.catalog.parser import parse_description


def test_price_variants():
    assert parse_description("milk ₹65.50").price_inr == Decimal("65.50")
    assert parse_description("milk Rs 65").price_inr == Decimal("65.00")
    assert parse_description("milk 65 rupees").price_inr == Decimal("65.00")
    assert parse_description("price: 99.99 widget").price_inr == Decimal("99.99")


def test_missing_price_is_none():
    assert parse_description("just some milk").price_inr is None


def test_units():
    assert parse_description("milk 1L ₹65").unit_type == UnitType.LITER
    assert parse_description("rice 5kg ₹545").unit_type == UnitType.KILOGRAM
    assert parse_description("butter 100g ₹58").unit_value == Decimal("100")
    assert parse_description("eggs 1 dozen ₹70").unit_type == UnitType.DOZEN


def test_brand_and_stock():
    p = parse_description("Amul butter 100g ₹58, 30 in stock")
    assert p.brand == "Amul"
    assert p.stock_quantity == 30


def test_default_brand_unit_stock():
    p = parse_description("local honey ₹120")
    assert p.brand == "Generic"
    assert p.unit_type == UnitType.PIECE
    assert p.unit_value == Decimal("1")
    assert p.stock_quantity == 0


def test_category_and_subcategory_recognition():
    assert parse_description("Amul milk 1L ₹65 Dairy").category_name == "Dairy"
    assert parse_description("Amul milk 1L ₹65").subcategory_name == "Milk"


def test_product_name_strips_structured_tokens():
    p = parse_description("Amul butter 100g ₹58, 30 in stock, Dairy")
    assert "58" not in p.product_name
    assert "stock" not in p.product_name.lower()
    assert "butter" in p.product_name.lower()
