"""Parametrised tests for `backend.app.agent_router.entities`.

All deterministic — no SBERT. The single SBERT-dependent function
(`extract_category`) is exercised separately by `test_intent_classifier.py`
(slow) and `test_agent_router.py` (mocked) so this file stays fast.
"""

from __future__ import annotations

import pytest

from backend.app.agent_router import entities


# --------------------------------------------------------------------------- #
# extract_price
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "text, expected",
    [
        ("Samsung S24 for ₹45,000", 45000.0),
        ("OnePlus 12 priced ₹40000", 40000.0),
        ("Rs 1000", 1000.0),
        ("Rs. 1,250.50", 1250.5),
        ("INR 999", 999.0),
        ("set the price to 50k", 50000.0),
        ("update to ₹50K", 50000.0),
        ("just a gadget", None),
        # adversarial: model-number digits MUST NOT be parsed as prices
        ("iPhone 15", None),
        ("Samsung S24", None),
        # comma-form without currency still wins because of the comma signal
        ("priced 45,000", 45000.0),
    ],
)
def test_extract_price(text, expected):
    assert entities.extract_price(text) == expected


# --------------------------------------------------------------------------- #
# extract_max_price / extract_min_price
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "text, expected",
    [
        ("Show me iPhone 15 under ₹60,000", 60000.0),
        ("phones below 50k", 50000.0),
        ("less than 1000", 1000.0),
        ("max 500 INR", 500.0),
        ("a laptop", None),  # no modifier → no max
        ("priced ₹40,000", None),  # price without a max-modifier
    ],
)
def test_extract_max_price(text, expected):
    assert entities.extract_max_price(text) == expected


@pytest.mark.parametrize(
    "text, expected",
    [
        ("phones above ₹30,000", 30000.0),
        ("laptops more than 50k", 50000.0),
        ("min 250", 250.0),
        ("a phone under 60k", None),  # "under" is a max keyword, not min
    ],
)
def test_extract_min_price(text, expected):
    assert entities.extract_min_price(text) == expected


# --------------------------------------------------------------------------- #
# extract_product_id
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "text, expected",
    [
        ("Delete product ID 12345", "12345"),
        ("delete product 99", "99"),
        ("remove #abc123", "abc123"),
        ("update item-77-X to ₹500", "item-77-X".replace("item-", "")),  # captured: 77-X
        (
            "Update 33333333-0000-0000-0000-000000000001 to ₹50000",
            "33333333-0000-0000-0000-000000000001",
        ),
        ("show me iPhone", None),
        # 'id the' must not match — heuristic guard against grabbing English glue
        ("delete the milk listing", None),
    ],
)
def test_extract_product_id(text, expected):
    got = entities.extract_product_id(text)
    if expected is None:
        assert got is None, f"expected None, got {got!r}"
    else:
        assert got == expected


# --------------------------------------------------------------------------- #
# extract_keywords
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "text, intent, expected_contains, expected_excludes",
    [
        (
            "Show me iPhone 15 under ₹60,000",
            "search_products",
            ["iphone", "15"],
            ["show", "me", "under", "₹60", "60000", "60,000"],
        ),
        (
            "Find second-hand laptops near me",
            "search_products",
            ["second-hand", "laptops"],
            ["find", "near", "me"],
        ),
        (
            "Add a new Samsung S24 for ₹45,000",
            "add_product",
            ["samsung", "s24"],
            ["add", "new", "for", "45000"],
        ),
        ("Update product 12345 to ₹50,000", "update_product", ["12345"], ["update", "to", "50000"]),
        ("delete the milk listing", "delete_product", ["milk"], ["delete", "the", "listing"]),
    ],
)
def test_extract_keywords(text, intent, expected_contains, expected_excludes):
    out = entities.extract_keywords(text, intent)
    for needle in expected_contains:
        assert needle in out, f"expected {needle!r} in keywords, got {out!r}"
    for needle in expected_excludes:
        assert needle not in out, f"unexpected {needle!r} in keywords, got {out!r}"
