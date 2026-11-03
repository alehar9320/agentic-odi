"""ALH-222 (M2-04.1) — ``POST /api/outcomes/import``.

The route is an adapter: whatever the shared loop reports *is* the body, so the
Studio renders a calculation it did not make. What is pinned here is what only the
HTTP door can pin — that a bad row is a 200 with a reason while a bad *request* is
a 404 or a 422, and that the MCP branch drives the five existing outcome tools
rather than a new import-shaped one. The rules of the loop itself live in
``packages/core/tests/test_outcome_import.py``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agentic_odi_core import (
    ClaimCheck,
    InMemoryRepository,
    JobStage,
    ODIService,
    ServiceImportTarget,
    import_outcomes,
    manual_claim_check,
    parse_outcome_table,
)
from agentic_odi_core.remote import StudioError, StudioErrorCode
from agentic_odi_studio_api.app import create_app
from agentic_odi_studio_api.studio import router as router_module
from agentic_odi_studio_api.studio.errors import StudioHTTPError
from fastapi.testclient import TestClient

#: One fixture, both doors: the CLI test reads these same bytes.
FIXTURE = (
    Path(__file__).resolve().parents[3]
    / "packages"
    / "core"
    / "tests"
    / "fixtures"
    / "outcomes_mixed_40.csv"
)

#: The fixture's three unreadable lines, refused before any write.
REFUSED_LINES = [9, 18, 27]


def _seeded_service(backend: str = "local") -> tuple[TestClient, ODIService, str]:
    repo = InMemoryRepository()
    service = ODIService(repo)
    job = service.add_job("Reconcile supplier invoices")
    service.add_step(
        job.id, "Execute the reconciliation", 5, stage=JobStage.EXECUTE, allow_empty_job_map=True
    )
    service.add_theme("Onboarding", job_id=job.id)
    service.add_theme("Urgent", job_id=job.id)
    service.add_theme("Urgent")
    client = TestClient(create_app(repo, backend=backend))
    return client, service, job.id


def _upload(client: TestClient, job_id: str, **fields: Any):
    return client.post(
        "/api/outcomes/import",
        files={"file": ("outcomes.csv", FIXTURE.read_bytes(), "text/csv")},
        data={"job_id": job_id, **fields},
    )


def _upload_text(client: TestClient, job_id: str, body: str):
    return client.post(
        "/api/outcomes/import",
        files={"file": ("notes.csv", body.encode("utf-8"), "text/csv")},
        data={"job_id": job_id},
    )


def _refused_lines(body: dict[str, Any]) -> list[int]:
    return [entry["line"] for entry in body["refused"]]


def _install_mcp(
    monkeypatch,
    service: ODIService,
    *,
    refuse: Any = None,
    abort_at: int | None = None,
) -> list[tuple[str, dict[str, Any]]]:
    """Drive the route's MCP branch over the real tools, without the wire.

    Every tool the branch names is answered from a live ``ODIService``, so a test
    can assert both the arguments the loop sent and the rows the store holds.
    """
    calls: list[tuple[str, dict[str, Any]]] = []
    writes = 0

    async def _call(mcp_url: str, tool: str, arguments: dict[str, Any]) -> str:
        nonlocal writes
        calls.append((tool, arguments))
        if tool == "get_job":
            job = service.get_job(arguments["job_id"])
            if job is None:
                return json.dumps({"error": {"message": "Job not found"}})
            return job.model_dump_json()
        if tool == "list_themes":
            themes = service.list_themes(arguments["job_id"])
            return json.dumps([theme.model_dump(mode="json") for theme in themes])
        if tool == "get_job_map":
            steps = service.get_job_map(arguments["job_id"])
            return json.dumps([step.model_dump(mode="json") for step in steps])
        if tool == "get_outcomes":
            outcomes = service.get_outcomes(arguments["job_id"])
            return json.dumps([outcome.model_dump(mode="json") for outcome in outcomes])
        if tool == "add_outcome":
            writes += 1
            if abort_at is not None and writes == abort_at:
                raise StudioHTTPError(
                    StudioError(code=StudioErrorCode.MCP_UNREACHABLE, message="server down")
                )
            if refuse is not None and refuse(arguments["statement"]):
                raise StudioHTTPError(
                    StudioError(
                        code=StudioErrorCode.MCP_TOOL_FAILED, message="row refused upstream"
                    )
                )
            claim_check = arguments.get("claim_check")
            outcome = service.add_outcome(
                arguments["job_id"],
                arguments["statement"],
                arguments.get("importance"),
                arguments.get("satisfaction"),
                step_id=arguments.get("step_id"),
                claim_check=None if claim_check is None else ClaimCheck.model_validate(claim_check),
            )
            return f"Outcome created successfully: {outcome.model_dump_json()}"
        if tool == "assign_theme":
            outcomes = service.assign_theme(arguments["outcome_ids"], arguments["theme_id"])
            return json.dumps([outcome.model_dump(mode="json") for outcome in outcomes])
        raise AssertionError(f"the import drove an unexpected tool: {tool}")

    monkeypatch.setattr(router_module, "call_mcp_tool", _call)
    return calls


# --- the local backend --------------------------------------------------------


def test_a_dry_run_reports_the_run_and_writes_nothing() -> None:
    client, service, job_id = _seeded_service()

    response = _upload(client, job_id, dry_run="true")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["dry_run"] is True
    assert body["job_id"] == job_id
    assert len(body["created"]) == 37
    assert all(entry["outcome_id"] is None for entry in body["created"])
    assert _refused_lines(body) == REFUSED_LINES
    assert service.get_outcomes(job_id) == []


def test_the_upload_writes_the_rows_the_preview_promised() -> None:
    client, service, job_id = _seeded_service()

    body = _upload(client, job_id).json()

    assert body["dry_run"] is False
    assert all(entry["outcome_id"] for entry in body["created"])
    assert len(service.get_outcomes(job_id)) == 37
    assert body["aborted"] is None
    assert body["warnings"] == []


def test_a_refused_row_is_a_two_hundred_with_a_reason() -> None:
    client, _, job_id = _seeded_service()

    body = _upload(client, job_id).json()

    reasons = {entry["line"]: entry["reason"] for entry in body["refused"]}
    assert "must be between 1.0 and 10.0" in reasons[9]
    assert "Unknown stage: collect" in reasons[27]
    assert reasons[18].startswith("Outcome statement does not match the ODI format")
    written = [entry["statement"] for entry in body["created"]]
    assert not any(entry["statement"] in written for entry in body["refused"])


def test_the_theme_notes_come_back_as_data_the_board_can_show() -> None:
    client, _, job_id = _seeded_service()

    body = _upload(client, job_id, dry_run="true").json()

    assert body["unmatched_themes"] == [{"name": "Retention", "lines": [8, 10, 11]}]
    assert [entry["name"] for entry in body["ambiguous_themes"]] == ["Urgent"]


def test_an_unparseable_file_is_one_refusal_at_line_one() -> None:
    client, service, job_id = _seeded_service()

    response = _upload_text(client, job_id, "notes,importance\nchurn,1\n")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["created"] == []
    assert _refused_lines(body) == [1]
    assert "statement" in body["refused"][0]["reason"]
    assert service.get_outcomes(job_id) == []


def test_an_unknown_job_is_a_404_and_writes_nothing() -> None:
    client, service, _ = _seeded_service()

    response = _upload(client, "nope")

    assert response.status_code == 404, response.text
    assert response.json()["error"]["code"] == "not_found"
    assert "nope" in response.text
    assert service.get_outcomes("nope") == []


def test_a_missing_file_is_a_422() -> None:
    client, _, job_id = _seeded_service()

    response = client.post("/api/outcomes/import", data={"job_id": job_id})

    assert response.status_code == 422, response.text


def test_a_scored_row_is_written_with_the_by_hand_claim_check() -> None:
    client, service, job_id = _seeded_service()

    _upload(client, job_id)

    scored = [outcome for outcome in service.get_outcomes(job_id) if outcome.importance is not None]
    assert scored
    assert all(outcome.claim_check == manual_claim_check() for outcome in scored)


# --- the MCP branch -----------------------------------------------------------


def test_the_mcp_branch_drives_the_existing_tools(monkeypatch) -> None:
    client, service, job_id = _seeded_service(backend="mcp")
    calls = _install_mcp(monkeypatch, service)

    body = _upload(client, job_id, mcp_url="http://mcp").json()

    assert sorted({tool for tool, _ in calls}) == [
        "add_outcome",
        "assign_theme",
        "get_job",
        "get_job_map",
        "get_outcomes",
        "list_themes",
    ]
    assert len(body["created"]) == 37
    assert len(service.get_outcomes(job_id)) == 37
    filings = [arguments for tool, arguments in calls if tool == "assign_theme"]
    onboarding = [theme for theme in service.list_themes(job_id) if theme.name == "Onboarding"]
    assert filings == [{"outcome_ids": filings[0]["outcome_ids"], "theme_id": onboarding[0].id}]
    assert len(filings[0]["outcome_ids"]) == 6
    written = [arguments for tool, arguments in calls if tool == "add_outcome"]
    scored = [item for item in written if item.get("importance") is not None]
    assert scored
    assert all(
        item["claim_check"] == manual_claim_check().model_dump(mode="json") for item in scored
    )
    assert all("claim_check" not in item for item in written if item not in scored)


def test_a_tool_refusal_is_a_row_refusal_and_the_run_continues(monkeypatch) -> None:
    client, service, job_id = _seeded_service(backend="mcp")
    _install_mcp(
        monkeypatch,
        service,
        refuse=lambda statement: statement.startswith("Minimize the time to approve"),
    )

    body = _upload(client, job_id, mcp_url="http://mcp").json()

    assert len(body["created"]) == 36
    refused = [entry for entry in body["refused"] if entry["reason"] == "row refused upstream"]
    assert len(refused) == 1
    assert _refused_lines(body) == [9, 18, refused[0]["line"], 27]
    assert len(service.get_outcomes(job_id)) == 36


def test_an_unreachable_server_aborts_the_run_and_keeps_what_it_wrote(monkeypatch) -> None:
    client, service, job_id = _seeded_service(backend="mcp")
    _install_mcp(monkeypatch, service, abort_at=20)

    body = _upload(client, job_id, mcp_url="http://mcp").json()

    assert len(body["created"]) == 19
    assert body["aborted"]["line"] == 23
    assert _refused_lines(body) == [9, 18]
    assert max(entry["line"] for entry in body["created"]) == 22
    assert len(service.get_outcomes(job_id)) == 19


def test_an_unknown_job_over_mcp_is_a_404_not_a_report(monkeypatch) -> None:
    client, service, _ = _seeded_service(backend="mcp")
    calls = _install_mcp(monkeypatch, service)

    response = _upload(client, "nope", mcp_url="http://mcp")

    assert response.status_code == 404, response.text
    assert [tool for tool, _ in calls] == ["get_job"]


# --- the two doors ------------------------------------------------------------


def test_the_cli_and_the_upload_report_the_same_run() -> None:
    """The criterion the design exists to satisfy: one loop, two handles.

    The terminal runs the import over the service and prints what comes back; the
    Studio runs the same call behind this route and shows the JSON it comes back
    in. A sentence the route invented, a refusal it reordered, a theme note lost on
    the way out of HTTP — each goes red here as a whole-report difference, because
    that is exactly what a person comparing the two screens would see.
    """
    client, service, job_id = _seeded_service()
    preview = import_outcomes(
        parse_outcome_table(FIXTURE.read_bytes()),
        ServiceImportTarget(service),
        job_id=job_id,
        dry_run=True,
    ).as_dict()

    body = _upload(client, job_id, dry_run="true").json()

    assert body == preview
