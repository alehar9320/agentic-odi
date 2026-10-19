"""Backend seam: local SQLite backend and remote MCP backend."""

from __future__ import annotations

import pytest

from cli.backend import (
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


def _add_args(job_id: str = "job-1") -> dict:
    return {
        "job_id": job_id,
        "customer_value": dict(CUSTOMER_VALUE),
        "business_value": dict(BUSINESS_VALUE),
    }


def test_local_backend_round_trips_customer_outcomes(tmp_path):
    backend = LocalBackend(db_path=str(tmp_path / "odi.db"))

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
        "cli.backend._call_mcp",
        lambda tool, args, url, timeout: '[{"id": "a"}]',
    )
    assert backend.call("list_customer_outcomes", {}) == [{"id": "a"}]


def test_mcp_backend_extracts_model_from_success_text(monkeypatch):
    backend = MCPBackend(mcp_url="http://example/mcp")
    monkeypatch.setattr(
        "cli.backend._call_mcp",
        lambda tool, args, url, timeout: 'Customer outcome created successfully: {"id": "a"}',
    )
    assert backend.call("add_customer_outcome", {}) == {"id": "a"}


def test_mcp_backend_treats_not_found_text_as_error(monkeypatch):
    backend = MCPBackend(mcp_url="http://example/mcp")
    monkeypatch.setattr(
        "cli.backend._call_mcp",
        lambda tool, args, url, timeout: "Customer outcome not found: gone",
    )
    with pytest.raises(BackendError, match="Customer outcome not found: gone"):
        backend.call("get_customer_outcome", {"outcome_id": "gone"})


def test_mcp_backend_parses_opportunity_score(monkeypatch):
    backend = MCPBackend(mcp_url="http://example/mcp")
    monkeypatch.setattr(
        "cli.backend._call_mcp",
        lambda tool, args, url, timeout: "Opportunity score: 14.00",
    )
    assert backend.call("compute_opportunity", {"importance": 8, "satisfaction": 2}) == 14.0


def test_mcp_backend_reports_unreachable_server():
    backend = MCPBackend(mcp_url="http://127.0.0.1:9/mcp", timeout=0.5)
    with pytest.raises(BackendError, match="could not reach MCP server"):
        backend.call("get_customer_outcome", {"outcome_id": "x"})
