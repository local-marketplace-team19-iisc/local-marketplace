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
    # 008 Session 7: when the vendor doesn't say a stock number we now
    # default to 1 (was 0) so the listing is immediately purchasable in
    # the storefront. Explicit numbers still win — see
    # `test_brand_and_stock` above.
    assert p.stock_quantity == 1


def test_category_and_subcategory_recognition():
    assert parse_description("Amul milk 1L ₹65 Dairy").category_name == "Dairy"
    assert parse_description("Amul milk 1L ₹65").subcategory_name == "Milk"


def test_product_name_strips_structured_tokens():
    p = parse_description("Amul butter 100g ₹58, 30 in stock, Dairy")
    assert "58" not in p.product_name
    assert "stock" not in p.product_name.lower()
    assert "butter" in p.product_name.lower()


# --- chatbot / voice add-product cases ---------------------------------------
# These exercise the patches landed in feature 008 Session 5 so that natural
# vendor utterances (typed and ASR-transcribed) produce a usable price + clean
# product name. The 006 parser owns the contract; 008's SBERT router calls it.


def test_bare_integer_price_no_currency_marker():
    """Voice transcripts often drop ₹/Rs entirely. Bare numbers must work."""
    p = parse_description("Add a new Samsung S24 for 45000")
    assert p.price_inr == Decimal("45000.00")
    assert "samsung s24" in p.product_name.lower()
    assert "add" not in p.product_name.lower()
    assert "for" not in p.product_name.lower()


def test_thousands_comma_is_honoured():
    """`₹45,000` historically parsed as 45.00. It must now parse as 45000.00."""
    assert parse_description("Add iPhone 15 for ₹45,000").price_inr == Decimal(
        "45000.00"
    )
    assert parse_description("Sony WH ₹1,250.50").price_inr == Decimal("1250.50")
    assert parse_description("Bose QC ₹1,00,000").price_inr is not None  # Indian style


def test_priced_at_phrasing():
    """ASR + chat both produce `priced at NNN` / `price: NNN` forms."""
    assert parse_description("iPhone 15 Pro priced at 89999").price_inr == Decimal(
        "89999.00"
    )
    assert parse_description("Add Samsung price 45000 rupees").price_inr == Decimal(
        "45000.00"
    )


def test_sku_and_id_keywords_do_not_become_price():
    """A bare 3+ digit number after `SKU`/`ID`/`model` is an identifier, not a price."""
    assert parse_description("iPhone 15 SKU 12345").price_inr is None
    assert parse_description("Product ID 999 description").price_inr is None
    assert parse_description("iPhone 15 model 12345").price_inr is None
    # but a real price elsewhere in the same string still wins
    assert parse_description(
        "iPhone 15 SKU 12345 priced at ₹89,999"
    ).price_inr == Decimal("89999.00")


def test_add_preamble_is_stripped_from_name():
    """Chatbot vendor adds typically prefix with `Add (a) (new) ...`."""
    assert parse_description("Add Pixel 9 ₹55000").product_name == "Pixel 9"
    assert (
        parse_description("Add a new Samsung S24 for ₹45000").product_name
        == "Samsung S24"
    )
    assert (
        parse_description("Please add the OnePlus 12 Rs 60000").product_name.lower()
        == "oneplus 12"
    )
