"""Desired Outcomes CLI subcommands.

ODI keeps two outcome shapes: the desired Outcome captured against a Job, and
the Customer Outcome that pairs customer value with business value. This module
owns the former; ``customer-outcomes`` owns the latter.
"""

from __future__ import annotations

import json
from typing import Any

import typer

from agentic_odi_cli import flags
from agentic_odi_cli.backend import run_tool
from agentic_odi_cli.render import render_deleted, render_outcome, render_outcome_list, render_saved

desired_outcomes_app = typer.Typer(help="Manage desired Outcomes.")

JSON_OPTION = typer.Option(False, "--json", help="Emit machine-readable JSON.")


@desired_outcomes_app.command("add")
def add(
    job_id: str = typer.Option(..., help="Job ID the outcome belongs to"),
    statement: str = typer.Option(..., help="Desired outcome statement"),
    importance: float = typer.Option(..., min=1.0, max=10.0, help="Importance score (1-10)"),
    satisfaction: float = typer.Option(..., min=1.0, max=10.0, help="Satisfaction score (1-10)"),
    step_id: str | None = typer.Option(default=None, help="Optional Step ID"),
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


@desired_outcomes_app.command("get")
def get(
    outcome_id: str = typer.Argument(..., help="Outcome ID"), json_output: bool = JSON_OPTION
) -> None:
    """Get a desired Outcome by ID."""
    typer.echo(
        render_outcome(run_tool("get_outcome", {"outcome_id": outcome_id}), as_json=json_output)
    )


@desired_outcomes_app.command("update")
def update(
    outcome_id: str = typer.Argument(..., help="Outcome ID"),
    statement: str | None = typer.Option(default=None, help="New statement"),
    importance: float | None = typer.Option(default=None, min=1.0, max=10.0),
    satisfaction: float | None = typer.Option(default=None, min=1.0, max=10.0),
    step_id: str | None = typer.Option(default=None, help="Move to a Step"),
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
    typer.echo(
        render_saved(
            "updated", run_tool("update_outcome", args), as_json=json_output, noun="Outcome"
        )
    )


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
