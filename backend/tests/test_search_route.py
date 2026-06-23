"""Endpoint tests for `GET /api/search?q=…` (spec FR-8).

Anonymous-friendly: a bearer is *optional*. The adapter forces
intent=search_products on every call (no SBERT round-trip).
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.app.agent_router import route as router_logic
from backend.app.agent_router.route import RouterResult
from backend.app.main import app


client = TestClient(app)


def _stub_router(monkeypatch, result: RouterResult):
    captured: dict = {}

    def _fake(text, role, vendor_id=None, *, forced_intent=None):
        captured["text"] = text
        captured["role"] = role
        captured["vendor_id"] = vendor_id
        captured["forced_intent"] = forced_intent
        return result

    monkeypatch.setattr(router_logic, "route_text", _fake)
    return captured


def test_search_anonymous_ok(monkeypatch):
    """No Bearer → still works (anonymous browse)."""
    cap = _stub_router(
        monkeypatch,
        RouterResult(
            intent="search_products",
            entities={"keywords": "iphone", "max_price": 60000.0},
            reply="Found 1 match.",
            listings=[{"id": "p1", "name": "iPhone 15", "price": 57999.0, "vendor": "Apple", "rating": 0.0, "availability": True}],
            api_called="GET /api/products",
        ),
    )
    r = client.get("/api/search", params={"q": "iphone under ₹60000"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["products"][0]["name"] == "iPhone 15"
    assert body["meta"]["max_price"] == 60000.0
    assert cap["forced_intent"] == "search_products"
    assert cap["role"] == "unknown"


def test_search_empty_q_returns_empty(monkeypatch):
    monkeypatch.setattr(
        router_logic, "route_text", lambda *a, **k: pytest.fail("router should not be called for empty q")
    )
    r = client.get("/api/search", params={"q": ""})
    assert r.status_code == 200
    body = r.json()
    assert body["products"] == []
    assert body["meta"]["empty_query"] is True


def test_search_no_q_param_returns_empty():
    r = client.get("/api/search")
    assert r.status_code == 200
    assert r.json()["products"] == []
