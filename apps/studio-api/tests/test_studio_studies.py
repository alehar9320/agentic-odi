"""Studies through the sidecar: the same records under both backends.

`GET /api/studies` is empty until a study has been opened — the route never
invents a pass over the job. It mirrors the segments surface: a read-only
collection scoped by job, served from the local service or forwarded to the
contract's ``list_studies`` tool when the app runs against MCP.
"""

from __future__ import annotations

import json

from agentic_odi_core import InMemoryRepository
from agentic_odi_studio_api.app import create_app
from agentic_odi_studio_api.studio import router as router_module
from fastapi.testclient import TestClient


def _client(backend: str = "local") -> TestClient:
    return TestClient(create_app(InMemoryRepository(), backend=backend))


def _service(client: TestClient):
    return client.app.state.service  # type: ignore[attr-defined]


def _seed_job_with_study(client: TestClient) -> str:
    service = _service(client)
    job = service.add_job("Rotate a leaked secret")
    service.open_study(job.id, "Q3 sweep", wave=1)
    return job.id


def test_local_studies_are_empty_until_one_is_opened() -> None:
    client = _client()
    service = _service(client)
    job = service.add_job("Rotate a leaked secret")

    assert client.get("/api/studies").json() == []
    assert client.get(f"/api/studies?job_id={job.id}").json() == []

    study = service.open_study(job.id, "Q3 sweep", wave=1)

    studies = client.get("/api/studies").json()
    assert len(studies) == 1
    assert studies[0]["id"] == study.id
    assert studies[0]["status"] == "planned"
    assert studies[0]["wave"] == 1


def test_local_studies_filter_by_job() -> None:
    client = _client()
    job_id = _seed_job_with_study(client)

    assert len(client.get(f"/api/studies?job_id={job_id}").json()) == 1
    assert client.get("/api/studies?job_id=nope").json() == []


def test_mcp_backend_forwards_to_list_studies(monkeypatch) -> None:
    calls: list[tuple[str, dict]] = []

    async def _call(mcp_url: str, tool: str, arguments: dict) -> str:
        calls.append((tool, arguments))
        return json.dumps([{"id": "st-1", "status": "planned", "wave": 1}])

    monkeypatch.setattr(router_module, "call_mcp_tool", _call)
    client = _client(backend="mcp")

    assert client.get("/api/studies?job_id=j-1&mcp_url=http://mcp").json() == [
        {"id": "st-1", "status": "planned", "wave": 1}
    ]
    assert calls == [("list_studies", {"job_id": "j-1"})]


def test_mcp_backend_requires_mcp_url_with_the_existing_400_shape() -> None:
    client = _client(backend="mcp")
    assert client.get("/api/studies").status_code == 400
