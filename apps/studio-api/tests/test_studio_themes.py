"""ALH-65 (M2-01) — themes through the sidecar: the same records under both backends.

`GET /api/themes` is a read: themes are opened by the agent through the
``add_theme`` tool, never typed into the canvas.
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


def test_local_themes_are_empty_until_the_agent_opens_one() -> None:
    client = _client()
    assert client.get("/api/themes").json() == []

    job = _service(client).add_job("Reconcile supplier invoices")
    theme = _service(client).add_theme(name="Cash timing", job_id=job.id)
    child = _service(client).add_theme(name="Payment windows", job_id=job.id, parent_id=theme.id)

    themes = client.get("/api/themes").json()
    assert [entry["id"] for entry in themes] == [theme.id, child.id]
    assert themes[1]["parent_id"] == theme.id


def test_local_themes_filter_by_job_and_keep_workspace_themes() -> None:
    client = _client()
    service = _service(client)
    job = service.add_job("Reconcile supplier invoices")
    other = service.add_job("Onboard a new supplier")
    service.add_theme(name="Cash timing", job_id=job.id)
    service.add_theme(name="Not yours", job_id=other.id)
    service.add_theme(name="Compliance", job_id=None)

    listed = client.get(f"/api/themes?job_id={job.id}").json()
    assert [entry["name"] for entry in listed] == ["Cash timing", "Compliance"]
    assert [entry["name"] for entry in client.get("/api/themes?job_id=nope").json()] == [
        "Compliance"
    ]


def test_mcp_backend_uses_the_contract_tool(monkeypatch) -> None:
    calls: list[tuple[str, dict]] = []

    async def _call(mcp_url: str, tool: str, arguments: dict) -> str:
        calls.append((tool, arguments))
        return json.dumps([{"id": "th-1", "name": "Cash timing"}])

    monkeypatch.setattr(router_module, "call_mcp_tool", _call)
    client = _client(backend="mcp")

    assert client.get("/api/themes?job_id=j-1&mcp_url=http://mcp").json() == [
        {"id": "th-1", "name": "Cash timing"}
    ]
    assert calls == [("list_themes", {"job_id": "j-1"})]


def test_mcp_backend_requires_mcp_url_with_the_existing_400_shape() -> None:
    client = _client(backend="mcp")
    assert client.get("/api/themes").status_code == 400
