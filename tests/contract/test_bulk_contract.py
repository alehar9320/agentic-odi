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
