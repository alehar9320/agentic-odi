"""ALH-196 (M2-03.1) — a bulk change is reachable from every surface, spelled the same.

``bulk_update_outcomes`` and ``undo_bulk`` are contract tools before they are commands: the
terminal, the MCP server and the local backend name them identically, and the report shape is
the one core produces. These tests pin the contract surface and the local path through it.
"""

from __future__ import annotations

from typing import Any

import pytest
from agentic_odi_cli.backend import BackendError, LocalBackend
from agentic_odi_core.contract import TOOL_SPECS, ToolEffect, ToolName

BULK_STATEMENT = "Minimize the time to approve an invoice when it arrives"


def test_both_bulk_tools_are_named_with_their_arguments() -> None:
    assert ToolName.BULK_UPDATE_OUTCOMES.value == "bulk_update_outcomes"
    assert ToolName.UNDO_BULK.value == "undo_bulk"
    assert TOOL_SPECS["bulk_update_outcomes"].arguments == (
        "outcome_ids",
        "add_theme_ids",
        "remove_theme_ids",
        "stage",
        "add_tags",
        "dry_run",
    )
    assert TOOL_SPECS["bulk_update_outcomes"].required == ("outcome_ids",)
    assert TOOL_SPECS["undo_bulk"].arguments == ("token",)
    assert TOOL_SPECS["undo_bulk"].required == ("token",)


def test_a_bulk_change_is_a_write_even_when_it_previews() -> None:
    """``dry_run`` is a read-shaped use of a writing tool, not a separate read tool."""
    manifest = LocalBackend()._get_capabilities_manifest({})
    effects = {entry["name"]: entry["effect"] for entry in manifest["tools"]}

    assert effects["bulk_update_outcomes"] == "write"
    assert effects["undo_bulk"] == "write"
    assert TOOL_SPECS["bulk_update_outcomes"].effect is ToolEffect.WRITE
    assert TOOL_SPECS["undo_bulk"].effect is ToolEffect.WRITE


def _seed(backend: LocalBackend) -> dict[str, str]:
    job = backend.service.add_job("Reconcile supplier invoices")
    outcome = backend.service.add_outcome(job.id, BULK_STATEMENT)
    theme = backend.service.add_theme(name="Cash timing", job_id=job.id)
    return {"job_id": job.id, "outcome_id": outcome.id, "theme_id": theme.id}


def test_a_dry_run_through_the_backend_previews_without_writing(tmp_path: Any) -> None:
    backend = LocalBackend(db_path=str(tmp_path / "odi.db"))
    ids = _seed(backend)

    report = backend.call(
        "bulk_update_outcomes",
        {"outcome_ids": [ids["outcome_id"]], "add_theme_ids": [ids["theme_id"]], "dry_run": True},
    )

    assert report["requested"] == 1
    assert report["changed"] == [ids["outcome_id"]]
    assert report["changes"][0]["field"] == "theme_ids"
    assert report["undo_token"] is None
    stored = backend.call("get_outcome", {"outcome_id": ids["outcome_id"]})
    assert stored["theme_ids"] == []


def test_undo_through_the_backend_takes_the_row_back(tmp_path: Any) -> None:
    backend = LocalBackend(db_path=str(tmp_path / "odi.db"))
    ids = _seed(backend)

    report = backend.call(
        "bulk_update_outcomes",
        {"outcome_ids": [ids["outcome_id"]], "add_theme_ids": [ids["theme_id"]]},
    )
    token = report["undo_token"]
    assert token
    assert backend.call("get_outcome", {"outcome_id": ids["outcome_id"]})["theme_ids"] == [
        ids["theme_id"]
    ]

    undone = backend.call("undo_bulk", {"token": token})

    assert undone["changed"] == [ids["outcome_id"]]
    assert backend.call("get_outcome", {"outcome_id": ids["outcome_id"]})["theme_ids"] == []


def test_a_contradictory_theme_is_refused_with_the_contract_error_text(tmp_path: Any) -> None:
    backend = LocalBackend(db_path=str(tmp_path / "odi.db"))
    ids = _seed(backend)

    with pytest.raises(BackendError) as excinfo:
        backend.call(
            "bulk_update_outcomes",
            {
                "outcome_ids": [ids["outcome_id"]],
                "add_theme_ids": [ids["theme_id"]],
                "remove_theme_ids": [ids["theme_id"]],
            },
        )

    assert "both added and removed" in str(excinfo.value)


def test_the_studio_preview_and_the_cli_preview_answer_the_same_table(tmp_path: Any) -> None:
    """ALH-197: the landscape shows the terminal's arithmetic, not a copy of it.

    One fixture, two surfaces, one report — and neither of them wrote anything.
    """
    from agentic_odi_studio_api.app import create_app
    from fastapi.testclient import TestClient

    backend = LocalBackend(db_path=str(tmp_path / "odi.db"))
    service = backend.service
    invoices = service.add_job("Reconcile supplier invoices")
    on_hold = service.add_outcome(
        invoices.id, "Minimize the time to approve an invoice when it arrives"
    )
    #: A job map needs an outcome first — the steps are named after what they deliver.
    service.add_step(invoices.id, "Locate", order=1, stage="locate")
    theme = service.add_theme(name="Cash timing", job_id=invoices.id)
    vendors = service.add_job("Onboard vendors")  # a job map with no Locate step
    stranded = service.add_outcome(
        vendors.id, "Minimize the time to classify a chargeback when a customer disputes it"
    )
    body = {
        "outcome_ids": [on_hold.id, stranded.id, "o-gone"],
        "add_theme_ids": [theme.id],
        "stage": "locate",
        "add_tags": ["reviewed"],
    }
    events_before = len(service.repo.store.get_stream())

    cli = backend.call("bulk_update_outcomes", {**body, "dry_run": True})
    studio = TestClient(create_app(service.repo, backend="local")).post(
        "/api/outcomes/bulk", json={**body, "dry_run": True}
    )

    assert studio.status_code == 200
    assert studio.json() == cli
    assert cli["requested"] == 3
    assert cli["changed"] == [on_hold.id]
    #: One reason per row, the first problem the service met: the theme is scoped to the
    #: invoices job, so a vendor outcome cannot join it before the stage is even asked about.
    assert [row["id"] for row in cli["skipped"]] == [stranded.id, "o-gone"]
    assert "organizes job" in cli["skipped"][0]["reason"]
    assert cli["skipped"][1]["reason"] == "outcome not found"
    assert len(cli["changes"]) == 3
    assert cli["undo_token"] is None
    #: A preview is a read: not one row moved, not one event appended, nothing to undo.
    assert len(service.repo.store.get_stream()) == events_before
    assert service.repo.get_outcome(on_hold.id).theme_ids == []
    assert service.repo.bulk_operations == {}


def test_a_run_applied_by_one_surface_is_taken_back_by_the_other(tmp_path: Any) -> None:
    """The undo token is a store fact, so any surface holding it can use it."""
    from agentic_odi_studio_api.app import create_app
    from fastapi.testclient import TestClient

    backend = LocalBackend(db_path=str(tmp_path / "odi.db"))
    service = backend.service
    job = service.add_job("Reconcile supplier invoices")
    outcome = service.add_outcome(job.id, "Minimize the time to approve an invoice when it arrives")
    theme = service.add_theme(name="Cash timing", job_id=job.id)
    client = TestClient(create_app(service.repo, backend="local"))

    applied = client.post(
        "/api/outcomes/bulk", json={"outcome_ids": [outcome.id], "add_theme_ids": [theme.id]}
    ).json()
    undone = backend.call("undo_bulk", {"token": applied["undo_token"]})

    assert undone["changed"] == [outcome.id]
    assert service.repo.get_outcome(outcome.id).theme_ids == []
