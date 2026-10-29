"""Backend seam: local SQLite backend and remote MCP backend."""

from __future__ import annotations

import pytest
from agentic_odi_cli.backend import (
    BackendConfig,
    BackendError,
    LocalBackend,
    MCPBackend,
    get_backend,
    mcp_timeout,
    resolve_backend,
)

CUSTOMER_VALUE = {
    "direction": "minimize",
    "unit_of_measure": "time",
    "object_of_control": "to resolve setup errors",
    "statement": "Minimize the time to resolve setup errors",
    "importance": 8.8,
    "satisfaction": 3.2,
}
BUSINESS_VALUE = {"category": "cost_reduction", "statement": "Saves engineering hours"}


def _seed_job(backend: LocalBackend, job_id: str = "job-1") -> None:
    """Customer Outcomes validate their parent Job, so seed one first."""
    from agentic_odi_core import Job

    backend.service.repo.add_job(Job(id=job_id, name="Onboard customers"))


def _add_args(job_id: str = "job-1") -> dict:
    return {
        "job_id": job_id,
        "customer_value": dict(CUSTOMER_VALUE),
        "business_value": dict(BUSINESS_VALUE),
    }


def test_local_backend_round_trips_customer_outcomes(tmp_path):
    backend = LocalBackend(db_path=str(tmp_path / "odi.db"))
    _seed_job(backend)

    created = backend.call("add_customer_outcome", _add_args())
    outcome_id = created["id"]

    fetched = backend.call("get_customer_outcome", {"outcome_id": outcome_id})
    assert fetched["id"] == outcome_id
    assert fetched["customer_value"]["importance"] == 8.8

    listed = backend.call("list_customer_outcomes", {"job_id": "job-1"})
    assert [item["id"] for item in listed] == [outcome_id]

    deleted = backend.call("delete_customer_outcome", {"outcome_id": outcome_id})
    assert deleted == outcome_id
    assert backend.call("list_customer_outcomes", {}) == []


def test_local_update_changes_nested_business_and_customer_value(tmp_path):
    backend = LocalBackend(db_path=str(tmp_path / "odi.db"))
    _seed_job(backend)
    outcome_id = backend.call("add_customer_outcome", _add_args())["id"]

    updated = backend.call(
        "update_customer_outcome",
        {
            "outcome_id": outcome_id,
            "importance": 9.5,
            "business_statement": "Reduces churn",
        },
    )

    assert updated["customer_value"]["importance"] == 9.5
    assert updated["business_value"]["statement"] == "Reduces churn"
    assert updated["business_value"]["category"] == "cost_reduction"


def test_local_get_missing_raises_backend_error(tmp_path):
    backend = LocalBackend(db_path=str(tmp_path / "odi.db"))

    with pytest.raises(BackendError, match="Customer outcome not found: nope"):
        backend.call("get_customer_outcome", {"outcome_id": "nope"})


def test_local_backend_defers_database_creation_until_first_call(tmp_path):
    db_path = tmp_path / "odi.db"
    backend = LocalBackend(db_path=str(db_path))

    assert not db_path.exists()
    backend.call("compute_opportunity", {"importance": 8, "satisfaction": 2})
    assert not db_path.exists(), "score must not open the store"


def test_local_compute_opportunity(tmp_path):
    backend = LocalBackend(db_path=str(tmp_path / "odi.db"))
    assert backend.call("compute_opportunity", {"importance": 8, "satisfaction": 2}) == 14.0


def test_resolve_backend_selects_local_by_default(tmp_path):
    backend = resolve_backend(BackendConfig(backend="local", db_path=str(tmp_path / "odi.db")))
    assert isinstance(backend, LocalBackend)


def test_get_backend_rejects_unknown_backend():
    with pytest.raises(BackendError, match="unknown backend: warp"):
        get_backend(backend="warp")


def test_mcp_timeout_reads_env(monkeypatch):
    monkeypatch.setenv("AGENTIC_ODI_MCP_TIMEOUT", "5.5")
    assert mcp_timeout() == 5.5
    monkeypatch.setenv("AGENTIC_ODI_MCP_TIMEOUT", "nonsense")
    assert mcp_timeout() == 30.0


def test_mcp_backend_parses_list_payload(monkeypatch):
    backend = MCPBackend(mcp_url="http://example/mcp")
    monkeypatch.setattr(
        "agentic_odi_cli.backend._call_mcp",
        lambda tool, args, url, timeout: '[{"id": "a"}]',
    )
    assert backend.call("list_customer_outcomes", {}) == [{"id": "a"}]


def test_mcp_backend_extracts_model_from_success_text(monkeypatch):
    backend = MCPBackend(mcp_url="http://example/mcp")
    monkeypatch.setattr(
        "agentic_odi_cli.backend._call_mcp",
        lambda tool, args, url, timeout: 'Customer outcome created successfully: {"id": "a"}',
    )
    assert backend.call("add_customer_outcome", {}) == {"id": "a"}


def test_mcp_backend_treats_not_found_text_as_error(monkeypatch):
    backend = MCPBackend(mcp_url="http://example/mcp")
    monkeypatch.setattr(
        "agentic_odi_cli.backend._call_mcp",
        lambda tool, args, url, timeout: "Customer outcome not found: gone",
    )
    with pytest.raises(BackendError, match="Customer outcome not found: gone"):
        backend.call("get_customer_outcome", {"outcome_id": "gone"})


def test_mcp_backend_parses_opportunity_score(monkeypatch):
    backend = MCPBackend(mcp_url="http://example/mcp")
    monkeypatch.setattr(
        "agentic_odi_cli.backend._call_mcp",
        lambda tool, args, url, timeout: "Opportunity score: 14.00",
    )
    assert backend.call("compute_opportunity", {"importance": 8, "satisfaction": 2}) == 14.0


def test_mcp_backend_reports_unreachable_server():
    backend = MCPBackend(mcp_url="http://127.0.0.1:9/mcp", timeout=0.5)
    with pytest.raises(BackendError, match="could not reach MCP server"):
        backend.call("get_customer_outcome", {"outcome_id": "x"})


def test_local_backend_job_step_outcome_crud(tmp_path):
    backend = LocalBackend(db_path=str(tmp_path / "odi.db"))
    job_id = backend.call("add_job", {"name": "J", "description": "d"})["id"]

    assert backend.call("get_jobs", {})[0]["name"] == "J"
    assert backend.call("get_job", {"job_id": job_id})["name"] == "J"
    assert backend.call("update_job", {"job_id": job_id, "name": "J2"})["name"] == "J2"

    step_id = backend.call("add_step", {"job_id": job_id, "name": "S", "order": 1})["id"]
    assert [step["name"] for step in backend.call("get_job_map", {"job_id": job_id})] == ["S"]
    assert backend.call("update_step", {"step_id": step_id, "name": "S2"})["name"] == "S2"
    assert backend.call("get_step", {"step_id": step_id})["order"] == 1

    outcome_id = backend.call(
        "add_outcome",
        {"job_id": job_id, "statement": "Min x", "importance": 8.0, "satisfaction": 4.0},
    )["id"]
    assert backend.call("get_outcomes", {"job_id": job_id})[0]["statement"] == "Min x"
    updated = backend.call("update_outcome", {"outcome_id": outcome_id, "importance": 9.0})
    assert updated["importance"] == 9.0
    assert backend.call("get_outcome", {"outcome_id": outcome_id})["opportunity_score"] == 14.0

    assert backend.call("delete_step", {"step_id": step_id}) == step_id
    assert backend.call("delete_outcome", {"outcome_id": outcome_id}) == outcome_id
    assert backend.call("delete_job", {"job_id": job_id}) == job_id
    assert backend.call("get_jobs", {}) == []


def test_local_backend_not_found_raises_backend_error(tmp_path):
    backend = LocalBackend(db_path=str(tmp_path / "odi.db"))

    with pytest.raises(BackendError, match="Job not found: missing"):
        backend.call("get_job", {"job_id": "missing"})
    with pytest.raises(BackendError, match="Job not found: missing"):
        backend.call("get_job_map", {"job_id": "missing"})
    with pytest.raises(BackendError, match="Step not found: missing"):
        backend.call("get_step", {"step_id": "missing"})
    with pytest.raises(BackendError, match="Outcome not found: missing"):
        backend.call("get_outcome", {"outcome_id": "missing"})


def test_local_backend_rejects_out_of_range_scores(tmp_path):
    backend = LocalBackend(db_path=str(tmp_path / "odi.db"))
    job_id = backend.call("add_job", {"name": "J"})["id"]

    with pytest.raises(BackendError, match="between 1.0 and 10.0"):
        backend.call("add_outcome", {"job_id": job_id, "statement": "S", "importance": 99.0})


def test_local_backend_update_customer_outcome_folds_value_metrics(tmp_path):
    backend = LocalBackend(db_path=str(tmp_path / "odi.db"))
    job_id = backend.call("add_job", {"name": "J"})["id"]
    outcome_id = backend.call(
        "add_customer_outcome",
        {
            "job_id": job_id,
            "customer_value": dict(CUSTOMER_VALUE),
            "business_value": dict(BUSINESS_VALUE),
        },
    )["id"]

    updated = backend.call(
        "update_customer_outcome",
        {
            "outcome_id": outcome_id,
            "importance": 7.0,
            "value_metrics": [
                {
                    "name": "m2",
                    "direction": "maximize",
                    "unit_of_measure": "s",
                    "importance": 9.0,
                    "satisfaction": 3.0,
                }
            ],
        },
    )

    assert updated["customer_value"]["importance"] == 7.0
    assert updated["customer_value"]["value_metrics"][0]["name"] == "m2"


def test_mcp_backend_parses_job_and_step_payloads(monkeypatch):
    backend = MCPBackend(mcp_url="http://example/mcp")
    monkeypatch.setattr(
        "agentic_odi_cli.backend._call_mcp",
        lambda tool, args, url, timeout: '[{"id": "job-1"}]',
    )
    assert backend.call("get_jobs", {}) == [{"id": "job-1"}]
    assert backend.call("get_job_map", {"job_id": "job-1"}) == [{"id": "job-1"}]

    monkeypatch.setattr(
        "agentic_odi_cli.backend._call_mcp",
        lambda tool, args, url, timeout: "Job deleted successfully: job-1",
    )
    assert backend.call("delete_job", {"job_id": "job-1"}) == "job-1"
