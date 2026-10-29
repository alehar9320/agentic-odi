from agentic_odi_core.repository import InMemoryRepository
from agentic_odi_studio_api.app import create_app
from fastapi.testclient import TestClient


def test_health():
    app = create_app(InMemoryRepository())
    client = TestClient(app)
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_openapi_contract_describes_the_api_routes():
    client = TestClient(create_app(InMemoryRepository()))

    response = client.get("/api/openapi.json")

    assert response.status_code == 200
    paths = response.json()["paths"]
    assert len(paths) >= 3
    assert "/api/canvas" in paths
    assert "/api/config" in paths
