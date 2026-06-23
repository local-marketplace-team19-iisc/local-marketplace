"""Endpoint tests for `POST /api/chat` after the feature 008 rewire.

Locked behaviour:
  * Missing Bearer → 401 (no router invocation).
  * Empty text → friendly prompt, no router invocation.
  * Image-only multipart → polite deferral, no router invocation
    (feature 007 FR-6 carries over).
  * Happy text turn → router invoked once; reply + listings + sessionId
    flow through unchanged.
  * Timeout → friendly HTTP 200 reply (NOT 504) so the frontend's apiClient
    does not surface a red toast on a slow router.
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
def vendor_principal(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    principal = {
        "id": "user-v1",
        "email": "v@example.com",
        "user_type": "vendor",
        "vendor_id": "vendor-1",
    }

    def _stub(_db, token):
        if not token:
            raise auth_service.AuthUnauthorizedError("Empty token")
        return principal

    monkeypatch.setattr(auth_service, "get_current_user", _stub)
    return principal


def _stub_router(monkeypatch, result_or_callable):
    if callable(result_or_callable):
        monkeypatch.setattr(router_logic, "route_text", result_or_callable)
    else:
        def _fake(text, role, vendor_id=None, *, forced_intent=None):  # noqa: ARG001
            return result_or_callable

        monkeypatch.setattr(router_logic, "route_text", _fake)


def test_requires_bearer():
    r = client.post("/api/chat", json={"message": "hi"})
    assert r.status_code == 401


def test_empty_text_returns_prompt(vendor_principal):
    r = client.post(
        "/api/chat",
        json={"message": "", "sessionId": "sess_x"},
        headers={"Authorization": "Bearer fake"},
    )
    assert r.status_code == 200
    body = r.json()
    assert "looking for" in body["reply"].lower()
    assert body["listings"] == []
    assert body["sessionId"] == "sess_x"


def test_image_only_returns_polite_deferral(vendor_principal, monkeypatch):
    """Multipart with image but no text → no router call."""
    calls = {"n": 0}

    def _fake(*args, **kwargs):  # noqa: ARG001
        calls["n"] += 1
        return RouterResult(intent="search_products", reply="X", listings=[])

    monkeypatch.setattr(router_logic, "route_text", _fake)
    r = client.post(
        "/api/chat",
        data={"message": "", "sessionId": "sess_img"},
        files={"image": ("p.jpg", b"\xff\xd8fake", "image/jpeg")},
        headers={"Authorization": "Bearer fake"},
    )
    assert r.status_code == 200, r.text
    assert "image" in r.json()["reply"].lower()
    assert calls["n"] == 0


def test_happy_text_turn(vendor_principal, monkeypatch):
    _stub_router(
        monkeypatch,
        RouterResult(
            intent="search_products",
            reply="Found 2 matches.",
            listings=[
                {
                    "id": "p1",
                    "name": "iPhone 15",
                    "price": 57999.0,
                    "vendor": "Apple",
                    "rating": 0.0,
                    "availability": True,
                },
                {
                    "id": "p2",
                    "name": "Samsung S23",
                    "price": 49999.0,
                    "vendor": "Samsung",
                    "rating": 0.0,
                    "availability": True,
                },
            ],
            api_called="GET /api/products",
            api_status=200,
        ),
    )
    r = client.post(
        "/api/chat",
        json={"message": "find a phone", "sessionId": "sess_y"},
        headers={"Authorization": "Bearer fake"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["reply"] == "Found 2 matches."
    assert body["sessionId"] == "sess_y"
    assert len(body["listings"]) == 2
    assert body["listings"][0]["name"] == "iPhone 15"


def test_intent_hint_forwarded_to_router(vendor_principal, monkeypatch):
    """Session 9: the Add Product modal posts {message, intent:'add_product'};
    the chat adapter MUST forward that as `forced_intent` to `route_text` so
    the router skips SBERT classification on a description that otherwise
    would misclassify (e.g. lacks a leading verb)."""
    captured: dict[str, object] = {}

    def _fake(text, role, vendor_id=None, *, forced_intent=None):  # noqa: ARG001
        captured["text"] = text
        captured["forced_intent"] = forced_intent
        return RouterResult(
            intent="add_product",
            reply="Added: Amul butter.",
            listings=[
                {
                    "id": "p99",
                    "name": "Amul butter",
                    "price": 58.0,
                    "vendor": "v",
                    "rating": 0.0,
                    "availability": True,
                }
            ],
            api_called="POST /api/products/from-description",
            api_status=201,
        )

    monkeypatch.setattr(router_logic, "route_text", _fake)
    r = client.post(
        "/api/chat",
        json={
            "message": "Amul butter 100g, \u20b958, 30 in stock, Dairy",
            "intent": "add_product",
        },
        headers={"Authorization": "Bearer fake"},
    )
    assert r.status_code == 200, r.text
    assert captured["forced_intent"] == "add_product"
    assert r.json()["debug"]["intent"] == "add_product"


def test_unknown_intent_hint_silently_dropped(vendor_principal, monkeypatch):
    """Unknown intent values MUST NOT be forwarded — old clients sending
    garbage shouldn't get 422s; SBERT classification kicks in as normal."""
    captured: dict[str, object] = {}

    def _fake(text, role, vendor_id=None, *, forced_intent=None):  # noqa: ARG001
        captured["forced_intent"] = forced_intent
        return RouterResult(intent="search_products", reply="ok", listings=[])

    monkeypatch.setattr(router_logic, "route_text", _fake)
    r = client.post(
        "/api/chat",
        json={"message": "find me iPhone", "intent": "garbage_value"},
        headers={"Authorization": "Bearer fake"},
    )
    assert r.status_code == 200, r.text
    assert captured["forced_intent"] is None


def test_intent_hint_via_multipart(vendor_principal, monkeypatch):
    """Multipart form (voice/image flows) MUST also honour the `intent` form
    field. Without this, the Add Product modal couldn't use the hint when
    the user attaches an image alongside their description."""
    captured: dict[str, object] = {}

    def _fake(text, role, vendor_id=None, *, forced_intent=None):  # noqa: ARG001
        captured["forced_intent"] = forced_intent
        return RouterResult(
            intent="add_product",
            reply="Added.",
            listings=[
                {
                    "id": "p1",
                    "name": "X",
                    "price": 1.0,
                    "vendor": "v",
                    "rating": 0.0,
                    "availability": True,
                }
            ],
        )

    monkeypatch.setattr(router_logic, "route_text", _fake)
    r = client.post(
        "/api/chat",
        data={"message": "Amul butter \u20b958", "intent": "add_product"},
        headers={"Authorization": "Bearer fake"},
    )
    assert r.status_code == 200, r.text
    assert captured["forced_intent"] == "add_product"


def test_timeout_returns_friendly_200(vendor_principal, monkeypatch):
    """A timeout MUST come back as HTTP 200 with a friendly reply."""
    monkeypatch.setattr(
        "backend.app.agent_router.chat_adapter.settings.AGENT_CHAT_TURN_TIMEOUT_S",
        0,
        raising=True,
    )

    import time

    def _slow(*args, **kwargs):  # noqa: ARG001
        time.sleep(1)
        return RouterResult(intent="search_products", reply="x", listings=[])

    monkeypatch.setattr(router_logic, "route_text", _slow)
    r = client.post(
        "/api/chat",
        json={"message": "anything"},
        headers={"Authorization": "Bearer fake"},
    )
    assert r.status_code == 200, r.text
    assert "longer than expected" in r.json()["reply"].lower()
