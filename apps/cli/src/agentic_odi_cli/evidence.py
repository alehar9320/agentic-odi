"""Evidence CLI subcommands.

Evidence is captured research that supports a Job, Step, or desired Outcome.
Records usually arrive from connectors, but they can also be entered by hand and
later promoted into ODI artifacts.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

import typer

from agentic_odi_cli.backend import run_tool
from agentic_odi_cli.render import (
    render_deleted,
    render_evidence,
    render_evidence_list,
    render_saved,
)

evidence_app = typer.Typer(help="Manage evidence captured from connectors.")

JSON_OPTION = typer.Option(False, "--json", help="Emit machine-readable JSON.")


class PromoteTarget(str, Enum):
    JOB = "job"
    OUTCOME = "outcome"


@evidence_app.command("add")
def add(
    source_name: str = typer.Option(..., help="Where the record came from"),
    name: str = typer.Option(..., help="Short label for the record"),
    content: str = typer.Option(..., help="Normalized text content"),
    url: str | None = typer.Option(default=None, help="External link to evidence in source system"),
    source_kind: str = typer.Option("manual", help="Connector kind or 'manual'"),
    item_type: str = typer.Option(
        "manual", help="catalog | resource | tool_result | manual | note"
    ),
    job_id: str | None = typer.Option(default=None),
    step_id: str | None = typer.Option(default=None),
    outcome_id: str | None = typer.Option(default=None),
    json_output: bool = JSON_OPTION,
) -> None:
    """Add a research record as evidence."""
    args: dict[str, Any] = {
        "source_name": source_name,
        "source_kind": source_kind,
        "item_type": item_type,
        "name": name,
        "content": content,
    }
    if url is not None:
        args["url"] = url
    if job_id is not None:
        args["job_id"] = job_id
    if step_id is not None:
        args["step_id"] = step_id
    if outcome_id is not None:
        args["outcome_id"] = outcome_id
    typer.echo(
        render_saved(
            "created", run_tool("add_evidence", args), as_json=json_output, noun="Evidence"
        )
    )


@evidence_app.command("list")
def list_evidence(
    job_id: str | None = typer.Option(default=None, help="Filter by Job ID"),
    step_id: str | None = typer.Option(default=None, help="Filter by Step ID"),
    outcome_id: str | None = typer.Option(default=None, help="Filter by Outcome ID"),
    json_output: bool = JSON_OPTION,
) -> None:
    """List captured evidence."""
    args: dict[str, Any] = {}
    if job_id is not None:
        args["job_id"] = job_id
    if step_id is not None:
        args["step_id"] = step_id
    if outcome_id is not None:
        args["outcome_id"] = outcome_id
    typer.echo(render_evidence_list(run_tool("list_evidence", args), as_json=json_output))


@evidence_app.command("get")
def get(
    evidence_id: str = typer.Argument(..., help="Evidence ID"), json_output: bool = JSON_OPTION
) -> None:
    """Get one evidence record by ID."""
    typer.echo(
        render_evidence(run_tool("get_evidence", {"evidence_id": evidence_id}), as_json=json_output)
    )


@evidence_app.command("delete")
def delete(
    evidence_id: str = typer.Argument(..., help="Evidence ID"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation"),
    json_output: bool = JSON_OPTION,
) -> None:
    """Delete an evidence record."""
    if not yes:
        confirm = typer.confirm(f"Delete evidence {evidence_id}?")
        if not confirm:
            raise typer.Exit()
    typer.echo(
        render_deleted(
            run_tool("delete_evidence", {"evidence_id": evidence_id}),
            as_json=json_output,
            noun="evidence",
        )
    )


@evidence_app.command("promote")
def promote(
    evidence_id: str = typer.Argument(..., help="Evidence ID"),
    to: PromoteTarget = typer.Option(..., "--to", help="Create a job or outcome"),  # noqa: B008
    job_id: str | None = typer.Option(default=None, help="Job for an outcome"),
    statement: str | None = typer.Option(default=None, help="Outcome statement override"),
    name: str | None = typer.Option(default=None, help="Job name override"),
    importance: float | None = typer.Option(default=None, min=1.0, max=10.0),
    satisfaction: float | None = typer.Option(default=None, min=1.0, max=10.0),
    json_output: bool = JSON_OPTION,
) -> None:
    """Turn an evidence record into a Job or desired Outcome."""
    args: dict[str, Any] = {"evidence_id": evidence_id, "target": to.value}
    if job_id is not None:
        args["job_id"] = job_id
    if statement is not None:
        args["statement"] = statement
    if name is not None:
        args["name"] = name
    if importance is not None:
        args["importance"] = importance
    if satisfaction is not None:
        args["satisfaction"] = satisfaction
    noun = "Job" if to is PromoteTarget.JOB else "Outcome"
    typer.echo(
        render_saved("created", run_tool("promote_evidence", args), as_json=json_output, noun=noun)
    )
