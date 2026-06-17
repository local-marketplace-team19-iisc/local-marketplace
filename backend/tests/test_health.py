from fastapi.testclient import TestClient

from backend.app.main import app

client = TestClient(app)


def test_health_returns_ok():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "OK"}


def test_no_route_other_than_health():
    # SPEC §7: auto-docs are disabled, so these must not exist.
    for path in ("/docs", "/redoc", "/openapi.json"):
        assert client.get(path).status_code == 404
