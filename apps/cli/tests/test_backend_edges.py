"""Edge-case tests for backend validation, parsing, and MCP failures."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest
import typer
from agentic_odi_cli import backend

CUSTOMER_VALUE = {
    "direction": "minimize",
    "unit_of_measure": "time",
    "object_of_control": "to resolve setup errors",
    "statement": "Minimize the time to resolve setup errors",
    "importance": 8.8,
    "satisfaction": 3.2,
}
BUSINESS_VALUE = {"category": "cost_reduction", "statement": "Saves engineering hours"}


def _backend(tmp_path) -> backend.LocalBackend:
    return backend.LocalBackend(db_path=str(tmp_path / "odi.db"))


def _seed_job(instance: backend.LocalBackend, job_id: str = "job-1") -> None:
    """Customer Outcomes validate their parent Job, so seed one first."""
    from agentic_odi_core import Job

    instance.service.repo.add_job(Job(id=job_id, name="Onboard customers"))


def _add(instance: backend.LocalBackend) -> str:
    _seed_job(instance)
    created = instance.call(
        "add_customer_outcome",
        {
            "job_id": "job-1",
            "customer_value": dict(CUSTOMER_VALUE),
            "business_value": dict(BUSINESS_VALUE),
        },
    )
    return created["id"]


def _add_args() -> dict:
    return {
        "job_id": "job-1",
        "customer_value": dict(CUSTOMER_VALUE),
        "business_value": dict(BUSINESS_VALUE),
    }


def test_validation_message_handles_plain_exceptions() -> None:
    assert backend._validation_message(RuntimeError("boom")) == "Invalid customer outcome: boom"


def test_validation_message_handles_empty_error_lists() -> None:
    class _Empty(Exception):
        def errors(self):
            return []

    error = _Empty()

    assert backend._validation_message(error) == str(error)


def test_validation_message_uses_the_first_pydantic_error() -> None:
    class _One(Exception):
        def errors(self):
            return [{"msg": "bad value"}]

    assert backend._validation_message(_One()) == "Invalid customer outcome: bad value"


def test_unknown_tool_raises_not_implemented(tmp_path) -> None:
    with pytest.raises(NotImplementedError, match="Unknown tool: nope"):
        _backend(tmp_path).call("nope", {})


def test_add_rejects_invalid_customer_values(tmp_path) -> None:
    instance = _backend(tmp_path)
    _seed_job(instance)
    args = _add_args()
    args["customer_value"] = {**CUSTOMER_VALUE, "direction": "sideways"}

    with pytest.raises(backend.BackendError, match="Invalid customer outcome:"):
        instance.call("add_customer_outcome", args)


def test_add_maps_value_range_errors_to_backend_errors(tmp_path) -> None:
    instance = _backend(tmp_path)

    class _Rejecting:
        def add_customer_outcome(self, **kwargs):
            from agentic_odi_core import ValueOutOfRangeError

            raise ValueOutOfRangeError()

    instance._service = _Rejecting()  # type: ignore[assignment]

    with pytest.raises(backend.BackendError, match="between 1.0 and 10.0"):
        instance.call("add_customer_outcome", _add_args())


def test_update_missing_outcome_raises_backend_error(tmp_path) -> None:
    with pytest.raises(backend.BackendError, match="Customer outcome not found: nope"):
        _backend(tmp_path).call("update_customer_outcome", {"outcome_id": "nope"})


def test_update_applies_step_id_and_all_value_fields(tmp_path) -> None:
    instance = _backend(tmp_path)
    outcome_id = _add(instance)

    updated = instance.call(
        "update_customer_outcome",
        {
            "outcome_id": outcome_id,
            "step_id": "step-1",
            "direction": "maximize",
            "unit_of_measure": "hours",
            "object_of_control": "throughput",
            "contextual_clarifier": "during onboarding",
            "statement": "Maximize onboarding throughput",
            "importance": 9.0,
            "satisfaction": 2.0,
            "category": "retention",
            "business_statement": "Keeps customers",
            "detail": "Expansion revenue",
            "estimated_annual_value": 120000.0,
            "confidence": 0.8,
        },
    )

    assert updated["step_id"] == "step-1"
    assert updated["customer_value"]["direction"] == "maximize"
    assert updated["customer_value"]["unit_of_measure"] == "hours"
    assert updated["customer_value"]["object_of_control"] == "throughput"
    assert updated["customer_value"]["contextual_clarifier"] == "during onboarding"
    assert updated["customer_value"]["statement"] == "Maximize onboarding throughput"
    assert updated["customer_value"]["importance"] == 9.0
    assert updated["customer_value"]["satisfaction"] == 2.0
    assert updated["business_value"]["category"] == "retention"
    assert updated["business_value"]["statement"] == "Keeps customers"
    assert updated["business_value"]["detail"] == "Expansion revenue"
    assert updated["business_value"]["estimated_annual_value"] == 120000.0
    assert updated["business_value"]["confidence"] == 0.8


def test_update_rejects_out_of_range_scores(tmp_path) -> None:
    instance = _backend(tmp_path)
    outcome_id = _add(instance)

    with pytest.raises(backend.BackendError, match="Invalid customer outcome:"):
        instance.call(
            "update_customer_outcome",
            {"outcome_id": outcome_id, "importance": 99.0},
        )


def test_delete_missing_outcome_raises_backend_error(tmp_path) -> None:
    with pytest.raises(backend.BackendError, match="Customer outcome not found: nope"):
        _backend(tmp_path).call("delete_customer_outcome", {"outcome_id": "nope"})


def test_compute_opportunity_rejects_out_of_range_scores(tmp_path) -> None:
    with pytest.raises(backend.BackendError, match="between 1.0 and 10.0"):
        _backend(tmp_path).call("compute_opportunity", {"importance": 11, "satisfaction": 5})


def test_parse_remote_delete_returns_the_id() -> None:
    assert (
        backend._parse_remote("delete_customer_outcome", "Deleted customer outcome: co-1") == "co-1"
    )


def test_extract_json_returns_plain_text_without_a_payload() -> None:
    assert backend._extract_json("no json here") == "no json here"


def test_extract_json_returns_text_for_malformed_payloads() -> None:
    assert backend._extract_json("{not valid json") == "{not valid json"


def test_extract_float_rejects_unparseable_scores() -> None:
    with pytest.raises(backend.BackendError, match="Opportunity score: nope"):
        backend._extract_float("Opportunity score: nope")


def test_resolve_backend_warns_when_db_is_ignored(capsys) -> None:
    resolved = backend.resolve_backend(backend.BackendConfig(backend="mcp", db_path="ignored.db"))

    assert isinstance(resolved, backend.MCPBackend)
    assert "--db is ignored" in capsys.readouterr().err


def test_run_tool_strips_the_server_error_prefix(monkeypatch, capsys) -> None:
    class _Failing:
        def call(self, tool_name, args):
            raise backend.BackendError("Error: server said no")

    monkeypatch.setattr(backend, "require_backend", lambda: _Failing())

    with pytest.raises(typer.Exit) as exc_info:
        backend.run_tool("get_customer_outcome", {})

    assert exc_info.value.exit_code == 1
    assert "Error: server said no" in capsys.readouterr().err


class _Client:
    payload = "ok"
    error: Exception | None = None

    def __init__(self, url: str) -> None:
        self.url = url

    async def __aenter__(self) -> _Client:
        return self

    async def __aexit__(self, *exc) -> bool:
        return False

    async def call_tool(self, tool: str, args: dict):
        if self.error is not None:
            raise self.error
        return SimpleNamespace(content=[SimpleNamespace(text=self.payload)])


def test_call_mcp_returns_tool_text(monkeypatch) -> None:
    _Client.error = None
    monkeypatch.setattr("fastmcp.Client", _Client)

    assert backend._call_mcp("get_jobs", {}, "http://mcp", 1.0) == "ok"


def test_call_mcp_wraps_connection_failures(monkeypatch) -> None:
    _Client.error = RuntimeError("boom")
    monkeypatch.setattr("fastmcp.Client", _Client)

    with pytest.raises(backend.BackendError, match="could not reach MCP server"):
        backend._call_mcp("get_jobs", {}, "http://mcp", 1.0)


def test_call_mcp_reports_timeouts(monkeypatch) -> None:
    class _Slow(_Client):
        async def call_tool(self, tool: str, args: dict):
            await asyncio.sleep(0.05)
            return SimpleNamespace(content=[SimpleNamespace(text="late")])

    monkeypatch.setattr("fastmcp.Client", _Slow)

    with pytest.raises(backend.BackendError, match="timed out after 0s"):
        backend._call_mcp("get_jobs", {}, "http://mcp", 0.001)
