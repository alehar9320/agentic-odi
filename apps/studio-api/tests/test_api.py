from agentic_odi_core.repository import InMemoryRepository
from agentic_odi_studio_api.app import create_app
from fastapi.testclient import TestClient


def test_health():
    app = create_app(InMemoryRepository())
    client = TestClient(app)
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
