"""Desired Outcomes CLI subcommands.

ODI keeps two outcome shapes: the desired Outcome captured against a Job, and
the Customer Outcome that pairs customer value with business value. This module
owns the former; ``customer-outcomes`` owns the latter.
"""

from __future__ import annotations

import json
from typing import Any

import typer

from agentic_odi_cli.backend import run_tool
from agentic_odi_cli.render import render_deleted, render_outcome, render_outcome_list, render_saved

desired_outcomes_app = typer.Typer(help="Manage desired Outcomes.")

JSON_OPTION = typer.Option(False, "--json", help="Emit machine-readable JSON.")


@desired_outcomes_app.command("add")
def add(
    job_id: str = typer.Option(..., help="Job ID the outcome belongs to"),
    statement: str = typer.Option(..., help="Desired outcome statement"),
    importance: float | None = typer.Option(default=None, min=1.0, max=10.0),
    satisfaction: float | None = typer.Option(default=None, min=1.0, max=10.0),
    step_id: str | None = typer.Option(default=None, help="Optional Step ID"),
    json_output: bool = JSON_OPTION,
) -> None:
    """Add a desired Outcome to a Job."""
    args: dict[str, Any] = {"job_id": job_id, "statement": statement}
    if importance is not None:
        args["importance"] = importance
    if satisfaction is not None:
        args["satisfaction"] = satisfaction
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


@desired_outcomes_app.command("evaluate")
def evaluate(
    statement: str = typer.Argument(..., help="Outcome statement to validate"),
    job_id: str | None = typer.Option(None, help="Optional Job ID to check existing outcomes"),
    json_output: bool = JSON_OPTION,
) -> None:
    """Evaluate an outcome statement against canonical ODI guidelines."""
    args: dict[str, Any] = {"statement": statement}
    if job_id is not None:
        args["job_id"] = job_id
    res = run_tool("evaluate_outcome", args)
    if json_output:
        typer.echo(json.dumps(res, indent=2))
        return

    is_valid = res.get("valid", False)
    verdict = "VALID" if is_valid else "INVALID"
    typer.secho(f"Verdict: {verdict}", fg="green" if is_valid else "red", bold=True)
    if res.get("issues"):
        typer.echo("\nIssues:")
        for issue in res["issues"]:
            typer.echo(f"  - {issue}")
    if res.get("suggestions"):
        typer.echo("\nSuggestions:")
        for sugg in res["suggestions"]:
            typer.echo(f"  - {sugg}")
