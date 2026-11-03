"""Backend seam: local SQLite backend and remote MCP backend."""

from __future__ import annotations

import pytest
import typer
from agentic_odi_cli import backend as backend_module
from agentic_odi_cli.backend import (
    AutoBackend,
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


def test_get_backend_selects_auto(tmp_path):
    backend = get_backend(backend="auto", db_path=str(tmp_path / "odi.db"))
    assert isinstance(backend, AutoBackend)


def test_auto_backend_stays_local_when_the_mcp_server_is_down(tmp_path, monkeypatch, capsys):
    backend = AutoBackend(db_path=str(tmp_path / "odi.db"))

    def unreachable(*_args):
        raise BackendError("could not reach MCP server")

    monkeypatch.setattr(backend._mcp, "call", unreachable)

    job = backend.call("add_job", {"name": "Local job"})

    assert job["name"] == "Local job"
    assert "using the MCP server" not in capsys.readouterr().err


def test_auto_backend_falls_back_to_mcp_and_notices_once(tmp_path, monkeypatch, capsys):
    backend = AutoBackend(db_path=str(tmp_path / "odi.db"))

    def stuck(*_args):
        raise BackendError("local store is locked")

    monkeypatch.setattr(backend._local, "call", stuck)
    monkeypatch.setattr(
        backend._mcp,
        "call",
        lambda _tool, _args: {"name": "Remote job"},
    )

    first = backend.call("add_job", {"name": "Remote job"})
    second = backend.call("add_job", {"name": "Remote job"})

    assert first["name"] == "Remote job"
    assert second["name"] == "Remote job"
    assert capsys.readouterr().err.count("Local store unavailable") == 1


def test_get_backend_rejects_unknown_backend():
    with pytest.raises(BackendError, match="unknown backend: warp"):
        get_backend(backend="warp")


def test_backend_error_carries_suggestion():
    err = BackendError("boom", "restart the sidecar")
    assert err.suggestion == "restart the sidecar"
    assert str(err) == "boom"


def test_backend_error_suggestion_defaults_to_none():
    assert BackendError("boom").suggestion is None
    assert str(BackendError("boom")) == "boom"


def test_parse_remote_threads_suggestion(monkeypatch):
    from agentic_odi_core.remote import StudioError, StudioErrorCode

    monkeypatch.setattr(
        "agentic_odi_core.remote.parse_tool_result",
        lambda text: StudioError(
            code=StudioErrorCode.MCP_UNREACHABLE,
            message="Could not reach the MCP server.",
            suggestion="Start the MCP server with `python -m agentic_odi_mcp_server`.",
            retryable=True,
        ),
    )

    with pytest.raises(BackendError) as exc_info:
        backend_module._parse_remote("get_jobs", "Error: anything")

    assert (
        exc_info.value.suggestion == "Start the MCP server with `python -m agentic_odi_mcp_server`."
    )


def test_run_tool_prints_suggestion_as_a_hint(monkeypatch, capsys):
    class _FailingBackend:
        def call(self, tool_name, args):
            raise BackendError(
                "sidecar is down", "Start the studio sidecar with `python scripts/dev.py`."
            )

    monkeypatch.setattr(backend_module, "require_backend", lambda: _FailingBackend())

    with pytest.raises(typer.Exit) as exc_info:
        backend_module.run_tool("get_jobs", {})
    assert exc_info.value.exit_code == 1

    captured = capsys.readouterr()
    assert "Error: sidecar is down" in captured.err
    assert "Hint: Start the studio sidecar" in captured.err


def test_mcp_timeout_reads_env(monkeypatch):
    monkeypatch.setenv("AGENTIC_ODI_MCP_TIMEOUT", "5.5")
    assert mcp_timeout() == 5.5
    monkeypatch.setenv("AGENTIC_ODI_MCP_TIMEOUT", "nonsense")
    assert mcp_timeout() == 30.0


def test_mcp_calls_bound_the_client_with_the_configured_timeout(monkeypatch):
    created = {}

    class _FakeResult:
        content = [type("_Block", (), {"text": "[]"})()]

    class _FakeClient:
        def __init__(self, url, **kwargs):
            created["url"] = url
            created["kwargs"] = kwargs

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc_info):
            return False

        async def call_tool(self, tool, args):
            return _FakeResult()

    monkeypatch.setattr("fastmcp.Client", _FakeClient)

    backend_module._call_mcp("get_jobs", {}, "http://example/mcp", 12.0)

    assert created["kwargs"] == {"timeout": 12.0, "init_timeout": 12.0}


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


def test_mcp_backend_reports_unreachable_server(monkeypatch):
    """An unreachable server must surface as a clear BackendError.

    The transport is stubbed: dialing a real port makes this test depend on
    whether the host refuses or silently drops the connection, which decided
    between the connection-failure and timeout messages on different runners.
    """

    class _UnreachableClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            raise ConnectionError("connection refused")

        async def __aexit__(self, *exc):
            return False

    monkeypatch.setattr("fastmcp.Client", _UnreachableClient)

    backend = MCPBackend(mcp_url="http://127.0.0.1:9/mcp", timeout=0.5)
    with pytest.raises(BackendError, match="could not reach MCP server"):
        backend.call("get_customer_outcome", {"outcome_id": "x"})


def test_local_backend_job_step_outcome_crud(tmp_path):
    backend = LocalBackend(db_path=str(tmp_path / "odi.db"))
    job_id = backend.call("add_job", {"name": "Job", "description": "d"})["id"]

    assert backend.call("get_jobs", {})[0]["name"] == "Job"
    assert backend.call("get_job", {"job_id": job_id})["name"] == "Job"
    assert backend.call("update_job", {"job_id": job_id, "name": "Job 2"})["name"] == "Job 2"

    # An outcome must exist before steps can be added.
    backend.call(
        "add_outcome",
        {
            "job_id": job_id,
            "statement": "Minimize the time it takes to deploy when releasing",
            "importance": 8.0,
            "satisfaction": 4.0,
        },
    )
    step_id = backend.call("add_step", {"job_id": job_id, "name": "S", "order": 1})["id"]
    assert [step["name"] for step in backend.call("get_job_map", {"job_id": job_id})] == ["S"]
    assert backend.call("update_step", {"step_id": step_id, "name": "S2"})["name"] == "S2"
    assert backend.call("get_step", {"step_id": step_id})["order"] == 1

    outcome_id = backend.call(
        "add_outcome",
        {
            "job_id": job_id,
            "statement": "Minimize the time to ship a release when the build is green",
            "importance": 8.0,
            "satisfaction": 4.0,
        },
    )["id"]
    assert (
        backend.call("get_outcomes", {"job_id": job_id})[0]["statement"]
        == "Minimize the time it takes to deploy when releasing"
    )
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
    job_id = backend.call("add_job", {"name": "Job"})["id"]

    with pytest.raises(BackendError, match="between 1.0 and 10.0"):
        backend.call(
            "add_outcome",
            {
                "job_id": job_id,
                "statement": "Minimize the time to ship a release when the build is green",
                "importance": 99.0,
                "satisfaction": 5.0,
            },
        )


def test_local_backend_update_customer_outcome_folds_value_metrics(tmp_path):
    backend = LocalBackend(db_path=str(tmp_path / "odi.db"))
    job_id = backend.call("add_job", {"name": "Job"})["id"]
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


@pytest.mark.parametrize(
    ("text", "expected_message"),
    [
        ("Error: Job with ID X not found.", "Job with ID X not found."),
        (
            "Error: importance and satisfaction must be between 1.0 and 10.0",
            "importance and satisfaction must be between 1.0 and 10.0",
        ),
    ],
)
def test_parse_remote_raises_backend_error_for_error_text(text, expected_message):
    with pytest.raises(BackendError) as exc_info:
        backend_module._parse_remote("get_jobs", text)

    assert exc_info.value.args[0] == expected_message


def test_parse_remote_returns_payload_for_success_text():
    assert backend_module._parse_remote("get_jobs", "[]") == []


def test_parse_remote_uses_the_shared_parser(monkeypatch):
    from agentic_odi_core import remote
    from agentic_odi_core.remote import StudioError, StudioErrorCode

    seen: list[str] = []

    def _spy(text: str):
        seen.append(text)
        return StudioError(code=StudioErrorCode.NOT_FOUND, message="nope")

    monkeypatch.setattr(remote, "parse_tool_result", _spy)

    with pytest.raises(BackendError, match="nope"):
        backend_module._parse_remote("get_jobs", "Error: Job with ID X not found.")

    assert seen == ["Error: Job with ID X not found."]


def test_evaluate_outcome_job_error_surfaces_as_a_backend_error():
    from agentic_odi_cli.backend import _parse_remote

    with pytest.raises(BackendError, match="Job not found: missing"):
        _parse_remote("evaluate_outcome", "Job not found: missing")


def _seed_evidence(backend: LocalBackend) -> tuple[dict, dict]:
    job = backend.call("add_job", {"name": "Secret rotation", "description": "Rotate credentials"})
    evidence = backend.call(
        "add_evidence",
        {
            "source_name": "gong",
            "source_kind": "mcp",
            "name": "Q3 call",
            "content": ("It takes too long to rotate production secrets before the next deploy."),
            "job_id": job["id"],
        },
    )
    return job, evidence


def test_local_backend_proposal_round_trip(tmp_path):
    backend = LocalBackend(db_path=str(tmp_path / "odi.db"))
    job, evidence = _seed_evidence(backend)

    proposal = backend.call("propose_outcome", {"evidence_id": evidence["id"]})
    assert proposal["status"] == "proposed"
    assert proposal["job_id"] == job["id"]
    assert proposal["statement"].startswith("Minimize")

    assert [p["id"] for p in backend.call("list_proposals", {"status": "proposed"})] == [
        proposal["id"]
    ]
    assert backend.call("list_proposals", {"status": "approved"}) == []

    outcome = backend.call("approve_proposal", {"proposal_id": proposal["id"]})
    assert outcome["job_id"] == job["id"]
    assert outcome["statement"] == proposal["statement"]
    assert backend.call("list_proposals", {"status": "proposed"}) == []


def test_local_backend_rejects_a_proposal_without_writing(tmp_path):
    backend = LocalBackend(db_path=str(tmp_path / "odi.db"))
    _job, evidence = _seed_evidence(backend)
    proposal = backend.call("propose_outcome", {"evidence_id": evidence["id"]})

    rejected = backend.call("reject_proposal", {"proposal_id": proposal["id"]})
    assert rejected["status"] == "rejected"
    assert backend.call("get_outcomes", {"job_id": _job["id"]}) == []


def test_local_backend_rejects_an_unknown_proposal_status(tmp_path):
    backend = LocalBackend(db_path=str(tmp_path / "odi.db"))

    with pytest.raises(BackendError, match="Invalid proposal status"):
        backend.call("list_proposals", {"status": "pending"})
