from __future__ import annotations

import pytest
from agentic_odi_connectors.models import HealthStatus
from agentic_odi_core import InMemoryRepository
from agentic_odi_studio_api.app import create_app
from agentic_odi_studio_api.studio import connectors as connectors_module
from agentic_odi_studio_api.studio.connectors import ConnectorService
from fastapi.testclient import TestClient


def _app(tmp_path) -> TestClient:
    service = ConnectorService(tmp_path / "connectors.json")
    return TestClient(create_app(InMemoryRepository(), connectors=service))


def _stub_healthy():
    class _Stub:
        async def health(self) -> HealthStatus:
            return HealthStatus(ok=True, message="ok", details={})

    return _Stub()


def test_catalog_returns_presets(tmp_path) -> None:
    client = _app(tmp_path)

    response = client.get("/api/connectors/catalog")

    assert response.status_code == 200
    data = response.json()
    ids = {item["id"] for item in data}
    assert {"notion", "posthog"} <= ids
    assert all("is_recommended" in item for item in data)


def test_list_connectors_empty_by_default(tmp_path) -> None:
    response = _app(tmp_path).get("/api/connectors")

    assert response.status_code == 200
    assert response.json() == []


def test_add_from_preset_persists(tmp_path) -> None:
    client = _app(tmp_path)

    response = client.post("/api/connectors", json={"preset": "notion"})

    assert response.status_code == 200
    assert response.json() == {"ok": True, "name": "notion"}
    assert client.get("/api/connectors").json()[0]["name"] == "notion"


def test_add_custom_url(tmp_path) -> None:
    client = _app(tmp_path)

    response = client.post(
        "/api/connectors", json={"name": "gong", "url": "http://localhost:9000/mcp"}
    )

    assert response.status_code == 200
    assert response.json() == {"ok": True, "name": "gong"}


@pytest.mark.parametrize("body", [{}, {"name": "gong"}])
def test_add_requires_preset_or_url(tmp_path, body: dict) -> None:
    response = _app(tmp_path).post("/api/connectors", json=body)

    assert response.status_code == 400


def test_add_unknown_preset_is_400(tmp_path) -> None:
    response = _app(tmp_path).post("/api/connectors", json={"preset": "nope"})

    assert response.status_code == 400


def test_add_duplicate_is_409(tmp_path) -> None:
    client = _app(tmp_path)
    client.post("/api/connectors", json={"preset": "notion"})

    response = client.post("/api/connectors", json={"preset": "notion"})

    assert response.status_code == 409


def test_delete_removes_connector(tmp_path) -> None:
    client = _app(tmp_path)
    client.post("/api/connectors", json={"preset": "notion"})

    response = client.delete("/api/connectors/notion")

    assert response.status_code == 200
    assert response.json() == {"ok": True, "name": "notion"}
    assert client.get("/api/connectors").json() == []


def test_delete_missing_is_404(tmp_path) -> None:
    response = _app(tmp_path).delete("/api/connectors/missing")

    assert response.status_code == 404


def test_health_ok(monkeypatch, tmp_path) -> None:
    client = _app(tmp_path)
    client.post("/api/connectors", json={"preset": "gong"})
    monkeypatch.setattr(connectors_module, "build_connector", lambda config: _stub_healthy())

    response = client.post("/api/connectors/gong/health")

    assert response.status_code == 200
    assert response.json()["ok"] is True


def test_health_missing_is_404(tmp_path) -> None:
    response = _app(tmp_path).post("/api/connectors/missing/health")

    assert response.status_code == 404


def test_health_failure_returns_unhealthy(monkeypatch, tmp_path) -> None:
    client = _app(tmp_path)
    client.post("/api/connectors", json={"preset": "gong"})

    class _Bad:
        async def health(self) -> HealthStatus:
            raise RuntimeError("boom")

    monkeypatch.setattr(connectors_module, "build_connector", lambda config: _Bad())

    response = client.post("/api/connectors/gong/health")

    assert response.status_code == 200
    assert response.json()["ok"] is False
    assert "boom" in response.json()["message"]


def test_unknown_route_is_404(tmp_path) -> None:
    response = _app(tmp_path).get("/api/not-a-thing")

    assert response.status_code == 404


def test_error_bodies_use_the_studio_shape(tmp_path) -> None:
    client = _app(tmp_path)
    client.post("/api/connectors", json={"preset": "notion"})

    duplicate = client.post("/api/connectors", json={"preset": "notion"})
    assert duplicate.status_code == 409
    body = duplicate.json()
    assert set(body) == {"error"}
    assert body["error"]["code"] == "conflict"
    assert body["error"]["suggestion"]

    missing = client.delete("/api/connectors/missing")
    assert missing.status_code == 404
    body = missing.json()
    assert body["error"]["code"] == "not_found"
    assert body["error"]["suggestion"]

    bad = client.post("/api/connectors", json={"preset": "nope"})
    assert bad.status_code == 400
    body = bad.json()
    assert body["error"]["code"] == "validation"
    assert body["error"]["suggestion"]
