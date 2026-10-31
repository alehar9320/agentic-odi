"""Desired Outcomes CLI subcommands.

ODI keeps two outcome shapes: the desired Outcome captured against a Job, and
the Customer Outcome that pairs customer value with business value. This module
owns the former; ``customer-outcomes`` owns the latter.
"""

from __future__ import annotations

import csv
import io
import json
from typing import Any

import typer

from agentic_odi_cli import flags
from agentic_odi_cli.backend import run_tool
from agentic_odi_cli.render import (
    render_deleted,
    render_outcome,
    render_outcome_delta,
    render_outcome_list,
    render_saved,
    render_score_history,
)

desired_outcomes_app = typer.Typer(help="Manage desired Outcomes.")

JSON_OPTION = typer.Option(False, "--json", help="Emit machine-readable JSON.")

EXPORT_FIELDS = (
    "id",
    "job_id",
    "step_id",
    "statement",
    "importance",
    "satisfaction",
    "opportunity_score",
)


@desired_outcomes_app.command("add")
def add(
    job_id: str = typer.Option(..., help="Job ID the outcome belongs to"),
    statement: str = typer.Option(..., help="Desired outcome statement"),
    importance: float = typer.Option(..., min=1.0, max=10.0, help="Importance score (1-10)"),
    satisfaction: float = typer.Option(..., min=1.0, max=10.0, help="Satisfaction score (1-10)"),
    step_id: str | None = typer.Option(default=None, help="Optional Step ID"),
    importance_n: int | None = typer.Option(
        default=None, min=1, help="People behind the importance score, when known"
    ),
    satisfaction_n: int | None = typer.Option(
        default=None, min=1, help="People behind the satisfaction score, when known"
    ),
    method: str | None = typer.Option(
        default=None, help="How the score was obtained: estimate (default), survey or import"
    ),
    why: str | None = typer.Option(
        None, "--why", max=500, help="Why the number was given (max 500 characters)"
    ),
    json_output: bool = JSON_OPTION,
) -> None:
    """Add a desired Outcome to a Job."""
    args: dict[str, Any] = {
        "job_id": job_id,
        "statement": statement,
        "importance": importance,
        "satisfaction": satisfaction,
    }
    if step_id is not None:
        args["step_id"] = step_id
    if importance_n is not None:
        args["importance_n"] = importance_n
    if satisfaction_n is not None:
        args["satisfaction_n"] = satisfaction_n
    if method is not None:
        args["score_method"] = method
    if why is not None:
        args["note"] = why
    typer.echo(
        render_saved("created", run_tool("add_outcome", args), as_json=json_output, noun="Outcome")
    )


@desired_outcomes_app.command("list")
def list_outcomes(
    job_id: str = typer.Option(..., help="Job ID to list outcomes for"),
    step_id: str | None = typer.Option(default=None, help="Filter by Step ID"),
    json_output: bool = JSON_OPTION,
) -> None:
    """List desired Outcomes for a Job."""
    args: dict[str, Any] = {"job_id": job_id}
    if step_id is not None:
        args["step_id"] = step_id
    typer.echo(render_outcome_list(run_tool("get_outcomes", args), as_json=json_output))


@desired_outcomes_app.command("export")
def export(
    job_id: str = typer.Option(..., help="Job ID to export outcomes for"),
    step_id: str | None = typer.Option(default=None, help="Filter by Step ID"),
    output_format: str = typer.Option("csv", "--format", help="Output format: csv or json."),
) -> None:
    """Export desired Outcomes to stdout, ready to pipe into another tool."""
    fmt = output_format.lower()
    if fmt not in {"csv", "json"}:
        typer.echo(f"Error: unknown format '{output_format}', expected csv or json", err=True)
        raise typer.Exit(code=1)
    args: dict[str, Any] = {"job_id": job_id}
    if step_id is not None:
        args["step_id"] = step_id
    outcomes = run_tool("get_outcomes", args)
    if not isinstance(outcomes, list):
        typer.echo(str(outcomes))
        return
    if fmt == "json":
        typer.echo(json.dumps(outcomes, indent=2))
        return
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=EXPORT_FIELDS, extrasaction="ignore")
    writer.writeheader()
    for item in outcomes:
        writer.writerow({field: item.get(field, "") for field in EXPORT_FIELDS})
    typer.echo(buffer.getvalue(), nl=False)


@desired_outcomes_app.command("get")
def get(
    outcome_id: str = typer.Argument(..., help="Outcome ID"), json_output: bool = JSON_OPTION
) -> None:
    """Get a desired Outcome by ID."""
    outcome = run_tool("get_outcome", {"outcome_id": outcome_id})
    latest_note = None if json_output else _latest_note(outcome_id)
    typer.echo(render_outcome(outcome, as_json=json_output, latest_note=latest_note))


def _latest_note(outcome_id: str) -> str | None:
    """The reason recorded with the most recent accepted score change.

    Read from the snapshot history rather than the Outcome record: a note is
    metadata on a score change, not a field. The most recent snapshot's note is
    returned when present; an outcome with no history, or a latest change with
    no reason, yields ``None`` so the detail line is omitted rather than faked.
    """
    snapshots = run_tool("get_outcome_history", {"outcome_id": outcome_id})
    if not isinstance(snapshots, list) or not snapshots:
        return None
    note = snapshots[-1].get("note")
    return note or None


@desired_outcomes_app.command("update")
def update(
    outcome_id: str = typer.Argument(..., help="Outcome ID"),
    statement: str | None = typer.Option(default=None, help="New statement"),
    importance: float | None = typer.Option(default=None, min=1.0, max=10.0),
    satisfaction: float | None = typer.Option(default=None, min=1.0, max=10.0),
    step_id: str | None = typer.Option(default=None, help="Move to a Step"),
    importance_n: int | None = typer.Option(default=None, min=1, help="People behind importance"),
    satisfaction_n: int | None = typer.Option(
        default=None, min=1, help="People behind satisfaction"
    ),
    method: str | None = typer.Option(
        default=None, help="How the score was obtained: estimate, survey or import"
    ),
    why: str | None = typer.Option(
        None, "--why", max=500, help="Why the number was given (max 500 characters)"
    ),
    json_output: bool = JSON_OPTION,
) -> None:
    """Update a desired Outcome."""
    args: dict[str, Any] = {"outcome_id": outcome_id}
    if statement is not None:
        args["statement"] = statement
    if importance is not None:
        args["importance"] = importance
    if satisfaction is not None:
        args["satisfaction"] = satisfaction
    if step_id is not None:
        args["step_id"] = step_id
    if importance_n is not None:
        args["importance_n"] = importance_n
    if satisfaction_n is not None:
        args["satisfaction_n"] = satisfaction_n
    if method is not None:
        args["score_method"] = method
    if why is not None:
        args["note"] = why
    typer.echo(
        render_saved(
            "updated", run_tool("update_outcome", args), as_json=json_output, noun="Outcome"
        )
    )


@desired_outcomes_app.command("history")
def history(
    outcome_id: str = typer.Argument(..., help="Outcome ID"),
    since: str | None = typer.Option(
        None, "--since", help="Baseline timestamp; the last snapshot at or before it"
    ),
    why: bool = typer.Option(
        False, "--why", help="Show the signed change from the baseline, not just the states"
    ),
    json_output: bool = JSON_OPTION,
) -> None:
    """Show an Outcome's accepted score snapshots, oldest first."""
    snapshots = run_tool("get_outcome_history", {"outcome_id": outcome_id})
    typer.echo(render_score_history(snapshots, as_json=json_output))
    if not why:
        return
    args: dict[str, Any] = {"outcome_id": outcome_id}
    if since is not None:
        args["since"] = since
    delta = run_tool("get_outcome_delta", args)
    if json_output:
        typer.echo(json.dumps(delta, indent=2, sort_keys=True))
        return
    typer.echo(render_outcome_delta(delta))


@desired_outcomes_app.command("evaluate")
def evaluate(
    statement: str = typer.Argument(..., help="Outcome statement to check"),
    job_id: str | None = typer.Option(default=None, help="Job to compare against"),
    json_output: bool = JSON_OPTION,
) -> None:
    """Evaluate an outcome statement against ODI format rules."""
    args: dict[str, Any] = {"statement": statement}
    if job_id is not None:
        args["job_id"] = job_id
    result = run_tool("evaluate_outcome", args)
    if json_output:
        typer.echo(result if isinstance(result, str) else json.dumps(result))
        return
    parsed = json.loads(result) if isinstance(result, str) else result
    verdict = "passes" if parsed.get("valid") else "needs work"
    typer.echo(f"{verdict}: {statement}")
    for problem in parsed.get("issues", []):
        typer.echo(f"  - {problem}")
    if flags.is_enabled("advanced_metrics"):
        for suggestion in parsed.get("suggestions", []):
            typer.echo(f"  Suggestion: {suggestion}")


@desired_outcomes_app.command("delete")
def delete(
    outcome_id: str = typer.Argument(..., help="Outcome ID"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation"),
    json_output: bool = JSON_OPTION,
) -> None:
    """Delete a desired Outcome."""
    if not yes:
        confirm = typer.confirm(f"Delete outcome {outcome_id}?")
        if not confirm:
            raise typer.Exit()
    typer.echo(
        render_deleted(
            run_tool("delete_outcome", {"outcome_id": outcome_id}),
            as_json=json_output,
            noun="outcome",
        )
    )
