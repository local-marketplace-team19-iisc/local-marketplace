"""Endpoint tests for `POST /api/agent/route` (spec FR-6).

These tests:
  * Stub `auth_service.get_current_user` so we don't need a real DB / JWT.
  * Stub `route.route_text` so we don't load the real SBERT model.
The combination keeps each test under ~200 ms while still exercising the
adapter's request adaptation, auth gating, and response projection.
"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from backend.app.agent_router import route as router_logic
from backend.app.agent_router.route import RouterResult
from backend.app.main import app
from backend.app.services import auth_service


client = TestClient(app)


@pytest.fixture
def customer_principal(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    principal = {"id": "user-1", "email": "c@example.com", "user_type": "customer"}

    def _stub(_db, token):
        if not token:
            raise auth_service.AuthUnauthorizedError("Empty token")
        return principal

    # `_auth.py` does a lazy `from backend.app.services import auth_service`
    # inside `_principal_from_token`, so patching the symbol on the module
    # object catches the call at runtime regardless of import order.
    monkeypatch.setattr(auth_service, "get_current_user", _stub)
    return principal


def _stub_router(monkeypatch, result: RouterResult):
    def _fake(text, role, vendor_id=None, *, forced_intent=None):  # noqa: ARG001
        return result

    monkeypatch.setattr(router_logic, "route_text", _fake)


def test_requires_bearer():
    r = client.post("/api/agent/route", json={"text": "hello"})
    assert r.status_code == 401


def test_search_happy_path(customer_principal, monkeypatch):
    _stub_router(
        monkeypatch,
        RouterResult(
            intent="search_products",
            entities={"keywords": "iphone", "max_price": 60000.0},
            reply="Found 1 match.",
            listings=[
                {
                    "id": "p1",
                    "name": "iPhone 15",
                    "price": 57999.0,
                    "vendor": "Apple",
                    "rating": 0.0,
                    "availability": True,
                }
            ],
            api_called="GET /api/products",
            api_status=200,
        ),
    )
    r = client.post(
        "/api/agent/route",
        json={"text": "show me iPhone under ₹60,000"},
        headers={"Authorization": "Bearer fake"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["intent"] == "search_products"
    assert body["api_called"] == "GET /api/products"
    assert body["entities"]["max_price"] == 60000.0
    assert body["listings"][0]["name"] == "iPhone 15"


def test_empty_text_rejected(customer_principal):
    r = client.post(
        "/api/agent/route",
        json={"text": ""},
        headers={"Authorization": "Bearer fake"},
    )
    assert r.status_code == 422  # pydantic min_length=1


def test_unknown_intent_returns_200_with_no_api_call(customer_principal, monkeypatch):
    _stub_router(
        monkeypatch,
        RouterResult(
            intent="unknown",
            reply="I can help you search...",
            api_called=None,
            api_status=200,
        ),
    )
    r = client.post(
        "/api/agent/route",
        json={"text": "what's the weather"},
        headers={"Authorization": "Bearer fake"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["intent"] == "unknown"
    assert body["api_called"] is None
