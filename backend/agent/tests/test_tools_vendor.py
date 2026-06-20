"""Tests for the vendor tools (baseline scope).

We exercise tools *through the registry* (`REGISTRY[name].run(args, ctx)`)
because the `@tool(...)` decorator replaces the function symbol with a
`Tool` instance — calling it directly would TypeError.
"""
from __future__ import annotations

import pytest

from backend.agent.tools import REGISTRY, _store
from backend.agent.tools.base import ToolContext
from backend.agent.tools.nlp_tools import is_affirmative, is_negative


@pytest.fixture(autouse=True)
def _reset_store():
    _store.reset_store()
    yield
    _store.reset_store()


def _ctx(user_id: str = "v_demo"):
    return ToolContext(
        session_id="sess_test",
        user_id=user_id,
        role="vendor",
        config=type("Cfg", (), {})(),  # tools used here don't read cfg
    )


def _draft(**overrides):
    base = dict(
        name="Sona Masuri Rice", category="Grocery",
        price=58.0, quantity=10, unit="kg",
        confidence=0.9,
    )
    base.update(overrides)
    return base


# --------------------------------------------------------------------------- #
# add_product (registry round-trip)
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_add_product_persists_to_store_and_mints_id():
    res = await REGISTRY["add_product"].run(_draft(), _ctx())
    assert res.ok is True, res.error
    assert res.data is not None
    assert res.data["product_id"] == "p_1"
    assert res.data["store_id"] == "st_1"
    assert res.data["name"] == "Sona Masuri Rice"
    assert _store.snapshot() == {"products": 1, "stores": 1}


@pytest.mark.asyncio
async def test_add_product_reuses_same_store_for_same_vendor():
    r1 = await REGISTRY["add_product"].run(_draft(), _ctx("v_a"))
    r2 = await REGISTRY["add_product"].run(_draft(name="Item 2"), _ctx("v_a"))
    assert r1.ok and r2.ok
    assert r1.data["store_id"] == r2.data["store_id"]
    assert r1.data["product_id"] != r2.data["product_id"]
    assert _store.snapshot() == {"products": 2, "stores": 1}


@pytest.mark.asyncio
async def test_add_product_isolates_stores_per_vendor():
    await REGISTRY["add_product"].run(_draft(), _ctx("v_a"))
    await REGISTRY["add_product"].run(_draft(), _ctx("v_b"))
    assert _store.snapshot() == {"products": 2, "stores": 2}


@pytest.mark.asyncio
async def test_add_product_rejects_bad_args():
    bad = _draft(price=-5)  # ProductDraft enforces price >= 0
    res = await REGISTRY["add_product"].run(bad, _ctx())
    assert res.ok is False
    assert res.error and "input_validation_failed" in res.error


# --------------------------------------------------------------------------- #
# get_my_catalog
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_get_my_catalog_returns_only_callers_products():
    await REGISTRY["add_product"].run(_draft(name="Rice"), _ctx("v_a"))
    await REGISTRY["add_product"].run(_draft(name="Atta"), _ctx("v_a"))
    await REGISTRY["add_product"].run(_draft(name="Sugar"), _ctx("v_b"))

    out_a = await REGISTRY["get_my_catalog"].run({}, _ctx("v_a"))
    out_b = await REGISTRY["get_my_catalog"].run({}, _ctx("v_b"))
    assert out_a.ok and out_b.ok
    assert out_a.data["total"] == 2
    assert {p["name"] for p in out_a.data["products"]} == {"Rice", "Atta"}
    assert out_b.data["total"] == 1
    assert out_b.data["products"][0]["name"] == "Sugar"


# --------------------------------------------------------------------------- #
# extract_product_fields (regex backstop)
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_extract_product_fields_parses_qty_unit_price():
    res = await REGISTRY["extract_product_fields"].run(
        {"free_text": "Add 10 kg Sona Masuri rice ₹58 per kg"},
        _ctx(),
    )
    assert res.ok, res.error
    d = res.data
    assert d["quantity"] == 10.0
    assert d["unit"] == "kg"
    assert d["price"] == 58.0
    assert d["needs_clarification"] == []
    assert "10 kg" not in d["name"]
    assert "₹58" not in d["name"]


@pytest.mark.asyncio
async def test_extract_product_fields_flags_missing_fields():
    res = await REGISTRY["extract_product_fields"].run(
        {"free_text": "Some unstructured note"},
        _ctx(),
    )
    assert res.ok, res.error
    d = res.data
    assert "price" in d["needs_clarification"]
    assert "quantity_and_unit" in d["needs_clarification"]
    assert d["confidence"] < 0.6


# --------------------------------------------------------------------------- #
# is_affirmative / is_negative (helper, not a registered tool)
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("text,expected", [
    ("yes", True),
    ("YES", True),
    ("yes!", True),
    ("y", True),
    ("yep", True),
    ("ok", True),
    ("ok confirm", True),
    ("confirm.", True),
    ("no", False),
    ("nope", False),
    ("cancel", False),
    ("maybe", False),
    ("", False),
    ("   ", False),
    ("sure why not", True),
])
def test_is_affirmative(text, expected):
    assert is_affirmative(text) is expected


@pytest.mark.parametrize("text,expected", [
    ("no", True), ("n", True), ("nope", True), ("cancel", True),
    ("yes", False), ("", False), ("maybe", False),
])
def test_is_negative(text, expected):
    assert is_negative(text) is expected
