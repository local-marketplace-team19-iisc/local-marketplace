"""Tests for the customer tools (baseline scope)."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from backend.agent.tools import REGISTRY, _store
from backend.agent.tools.base import ToolContext


@pytest.fixture(autouse=True)
def _reset_store():
    _store.reset_store()
    yield
    _store.reset_store()


def _customer_ctx():
    cfg = SimpleNamespace(retrieval=SimpleNamespace(return_top_k=5))
    return ToolContext(
        session_id="sess_test", user_id="c_demo",
        role="customer", config=cfg,
    )


def _vendor_ctx(user_id: str = "v_demo"):
    return ToolContext(
        session_id="sess_v", user_id=user_id,
        role="vendor", config=type("Cfg", (), {})(),
    )


def _draft(**overrides):
    base = dict(
        name="Sona Masuri Rice 10kg", category="Grocery > Rice",
        price=580, quantity=10, unit="kg", confidence=0.9,
    )
    base.update(overrides)
    return base


async def _seed():
    await REGISTRY["add_product"].run(_draft(), _vendor_ctx("v_a"))
    await REGISTRY["add_product"].run(
        _draft(name="IR-20 Rice 10kg", price=540), _vendor_ctx("v_a"),
    )
    await REGISTRY["add_product"].run(
        _draft(name="Sugar 5kg", category="Grocery > Sugar",
               price=300, quantity=5), _vendor_ctx("v_b"),
    )


# --------------------------------------------------------------------------- #
# search_products
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_search_returns_keyword_matches_sorted_by_score_then_distance():
    await _seed()
    res = await REGISTRY["search_products"].run(
        {"text": "rice 10kg", "radius_km": 25.0},
        _customer_ctx(),
    )
    assert res.ok, res.error
    names = [r["name"] for r in res.data["results"]]
    assert names == ["Sona Masuri Rice 10kg", "IR-20 Rice 10kg"]
    for r in res.data["results"]:
        assert r["distance_km"] == 0.0


@pytest.mark.asyncio
async def test_search_returns_empty_on_nonmatching_query():
    await _seed()
    res = await REGISTRY["search_products"].run(
        {"text": "laptop"}, _customer_ctx(),
    )
    assert res.ok
    assert res.data["results"] == []


@pytest.mark.asyncio
async def test_search_respects_max_price_filter():
    await _seed()
    res = await REGISTRY["search_products"].run(
        {"text": "rice 10kg", "max_price": 550, "radius_km": 25.0},
        _customer_ctx(),
    )
    assert res.ok
    names = [r["name"] for r in res.data["results"]]
    assert names == ["IR-20 Rice 10kg"]


@pytest.mark.asyncio
async def test_search_respects_unit_filter():
    await _seed()
    res = await REGISTRY["search_products"].run(
        {"text": "rice", "unit": "g"}, _customer_ctx(),
    )
    assert res.ok
    assert res.data["results"] == []


@pytest.mark.asyncio
async def test_search_radius_excludes_far_stores():
    await _seed()
    # Move v_b's store far north (~150 km from Bangalore centroid).
    store_b = next(s for s in _store._STORES.values() if s.vendor_id == "v_b")
    _store.put_store(store_b.model_copy(update={"lat": 14.5, "lng": 77.5946}))

    res = await REGISTRY["search_products"].run(
        {"text": "sugar 5kg", "radius_km": 5.0}, _customer_ctx(),
    )
    assert res.ok
    assert res.data["results"] == []


# --------------------------------------------------------------------------- #
# get_store
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_get_store_returns_existing_store():
    await _seed()
    any_product = next(_store.iter_products())
    res = await REGISTRY["get_store"].run(
        {"store_id": any_product.store_id}, _customer_ctx(),
    )
    assert res.ok, res.error
    assert res.data["store_id"] == any_product.store_id


@pytest.mark.asyncio
async def test_get_store_returns_error_on_unknown():
    await _seed()
    res = await REGISTRY["get_store"].run(
        {"store_id": "st_999"}, _customer_ctx(),
    )
    assert res.ok is False
    assert "ValueError" in (res.error or "")
