from __future__ import annotations

import pytest
from agentic_odi_core.repository import InMemoryRepository
from agentic_odi_integrations_openhands.models import (
    AgentRun,
    AgentRunStatus,
    AgentTarget,
    OrchestratorSettings,
)
from agentic_odi_integrations_openhands.service import OrchestratorService
from agentic_odi_integrations_openhands.store import OrchestratorStore
from agentic_odi_studio_api.app import create_app
from fastapi.testclient import TestClient


@pytest.fixture
def service(tmp_path) -> OrchestratorService:
    target = AgentTarget(
        alias="cloud",
        base_url="https://cloud.test",
        api_key="test-key",
        repository="acme/repo",
    )
    settings = OrchestratorSettings(
        targets=[target],
        default_target="cloud",
        heartbeat_path=str(tmp_path / "heartbeat.json"),
    )
    return OrchestratorService(
        store=OrchestratorStore(tmp_path / "orch.db"),
        settings=settings,
        workspace_root=str(tmp_path),
    )


@pytest.fixture
def client(service: OrchestratorService) -> TestClient:
    return TestClient(create_app(InMemoryRepository(), orchestrator=service))


def _add(client: TestClient, **overrides) -> dict:
    payload = {"title": "Fix the README", "prompt": "Correct the install command."}
    payload.update(overrides)
    response = client.post("/api/work-items", json=payload)
    assert response.status_code == 200, response.text
    return response.json()


def test_add_list_and_get_work(client: TestClient):
    added = _add(client, work_key="manual:readme")
    work = added["work_item"]
    assert added["created"] is True
    assert work["status"] == "queued"
    assert work["target_alias"] == "cloud"
    assert work["repository"] == "acme/repo"

    listed = client.get("/api/work-items").json()["work_items"]
    assert [item["work_item"]["id"] for item in listed] == [work["id"]]
    assert listed[0]["latest_run"] is None

    detail = client.get(f"/api/work-items/{work['id']}").json()
    assert detail["work_item"]["id"] == work["id"]
    assert detail["latest_run"] is None


def test_duplicate_work_key_returns_the_existing_item(client: TestClient):
    first = _add(client, work_key="manual:readme")
    second = _add(client, work_key="manual:readme")

    assert first["created"] is True
    assert second["created"] is False
    assert second["work_item"]["id"] == first["work_item"]["id"]


def test_unknown_target_is_a_validation_error(client: TestClient):
    response = client.post(
        "/api/work-items",
        json={"title": "x", "prompt": "y", "target": "missing"},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation"


def test_cancel_then_retry(client: TestClient):
    work = _add(client)["work_item"]

    cancelled = client.post(f"/api/work-items/{work['id']}/cancel")
    assert cancelled.status_code == 200
    assert cancelled.json()["work_item"]["status"] == "cancelled"

    conflict = client.post(f"/api/work-items/{work['id']}/cancel")
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "conflict"

    retried = client.post(f"/api/work-items/{work['id']}/retry")
    assert retried.status_code == 200
    assert retried.json()["work_item"]["status"] == "queued"


def test_missing_work_is_a_not_found_error(client: TestClient):
    response = client.get("/api/work-items/nope")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_status_counts_and_targets_are_safe(client: TestClient):
    _add(client)

    status = client.get("/api/orchestrator/status").json()["status"]
    assert status["queued"] == 1
    assert status["daemon_running"] is False
    assert status["targets"] == ["cloud"]

    targets = client.get("/api/agent-targets").json()["targets"]
    assert targets[0]["alias"] == "cloud"
    assert targets[0]["api_key"] is None
    assert targets[0]["has_literal_key"] is True


def test_agent_runs_never_expose_the_session_key(client: TestClient, service: OrchestratorService):
    work = _add(client)["work_item"]
    service.store.add_run(
        AgentRun(
            work_item_id=work["id"],
            status=AgentRunStatus.RUNNING,
            conversation_id="conv-1",
            session_api_key="super-secret",
        )
    )

    runs = client.get("/api/agent-runs", params={"work_id": work["id"]}).json()["runs"]

    assert len(runs) == 1
    assert runs[0]["conversation_id"] == "conv-1"
    assert "session_api_key" not in runs[0]
    assert "super-secret" not in str(runs)


def test_unknown_status_filter_returns_no_items(client: TestClient):
    _add(client)

    response = client.get("/api/work-items", params={"status": "nonsense"})

    assert response.status_code == 200
    assert response.json()["work_items"] == []


def test_detail_includes_the_latest_run(client: TestClient, service: OrchestratorService):
    work = _add(client)["work_item"]
    service.store.add_run(
        AgentRun(
            work_item_id=work["id"],
            status=AgentRunStatus.RUNNING,
            conversation_url="https://cloud.test/conversations/conv-1",
            cost_usd=0.5,
        )
    )

    detail = client.get(f"/api/work-items/{work['id']}").json()

    assert detail["latest_run"]["status"] == "running"
    assert detail["latest_run"]["cost_usd"] == 0.5


def test_lazy_orchestrator_reads_the_environment(tmp_path, monkeypatch):
    config = tmp_path / "openhands.json"
    config.write_text(
        '{"default_target": "cloud", "targets": '
        '[{"alias": "cloud", "base_url": "https://cloud.test"}]}'
    )
    monkeypatch.setenv("AGENTIC_ODI_OPENHANDS_CONFIG", str(config))
    monkeypatch.setenv("AGENTIC_ODI_ORCHESTRATOR_DB", str(tmp_path / "orch.db"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("OPENHANDS_API_KEY", "test-key")

    lazy = TestClient(create_app(InMemoryRepository()))

    targets = lazy.get("/api/agent-targets").json()["targets"]
    assert [target["alias"] for target in targets] == ["cloud"]
    assert targets[0]["has_env_key"] is True


class _BrokenOrchestrator:
    def __init__(self, error: Exception) -> None:
        self.error = error

    def __getattr__(self, _name):
        def _raise(*_args, **_kwargs):
            raise self.error

        return _raise


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("get", "/api/work-items"),
        ("post", "/api/work-items/missing/retry"),
        ("get", "/api/agent-targets"),
        ("get", "/api/agent-runs"),
        ("get", "/api/orchestrator/status"),
    ],
)
def test_orchestrator_failures_become_typed_errors(method: str, path: str):
    from agentic_odi_integrations_openhands.service import OrchestratorError

    broken = _BrokenOrchestrator(OrchestratorError("the store is unavailable"))
    client = TestClient(create_app(InMemoryRepository(), orchestrator=broken))

    response = getattr(client, method)(path)

    assert response.status_code == 500
    assert response.json()["error"]["code"] == "internal"
    assert "the store is unavailable" in response.json()["error"]["message"]


def test_unexpected_failures_are_still_rendered_as_internal_errors():
    broken = _BrokenOrchestrator(RuntimeError("boom"))
    client = TestClient(create_app(InMemoryRepository(), orchestrator=broken))

    response = client.get("/api/orchestrator/status")

    assert response.status_code == 500
    assert response.json()["error"]["code"] == "internal"
    assert "boom" in response.json()["error"]["message"]
