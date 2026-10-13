from fastapi.testclient import TestClient

from core.repository import InMemoryRepository
from local_server.app import create_app


def test_health():
    app = create_app(InMemoryRepository())
    client = TestClient(app)
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
