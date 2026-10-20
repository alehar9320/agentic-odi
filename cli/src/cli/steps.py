"""Job-map Steps CLI subcommands."""

from __future__ import annotations

from typing import Any

import typer

from cli.backend import run_tool
from cli.render import render_deleted, render_saved, render_step, render_step_list

steps_app = typer.Typer(help="Manage Job-map Steps.")

JSON_OPTION = typer.Option(False, "--json", help="Emit machine-readable JSON.")


@steps_app.command("add")
def add(
    job_id: str = typer.Option(..., help="Job ID the step belongs to"),
    name: str = typer.Option(..., help="Step name"),
    order: int = typer.Option(..., help="Step order"),
    json_output: bool = JSON_OPTION,
) -> None:
    """Add a Step to a Job."""
    args: dict[str, Any] = {"job_id": job_id, "name": name, "order": order}
    typer.echo(
        render_saved("created", run_tool("add_step", args), as_json=json_output, noun="Step")
    )


@steps_app.command("list")
def list_steps(
    job_id: str = typer.Option(..., help="Job ID to list steps for"),
    json_output: bool = JSON_OPTION,
) -> None:
    """List the ordered Step map for a Job."""
    typer.echo(render_step_list(run_tool("get_job_map", {"job_id": job_id}), as_json=json_output))


@steps_app.command("get")
def get(
    step_id: str = typer.Argument(..., help="Step ID"), json_output: bool = JSON_OPTION
) -> None:
    """Get a Step by ID."""
    typer.echo(render_step(run_tool("get_step", {"step_id": step_id}), as_json=json_output))


@steps_app.command("update")
def update(
    step_id: str = typer.Argument(..., help="Step ID"),
    name: str | None = typer.Option(default=None, help="New step name"),
    order: int | None = typer.Option(default=None, help="New step order"),
    json_output: bool = JSON_OPTION,
) -> None:
    """Update an existing Step."""
    args: dict[str, Any] = {"step_id": step_id}
    if name is not None:
        args["name"] = name
    if order is not None:
        args["order"] = order
    typer.echo(
        render_saved("updated", run_tool("update_step", args), as_json=json_output, noun="Step")
    )


@steps_app.command("delete")
def delete(
    step_id: str = typer.Argument(..., help="Step ID"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation"),
    json_output: bool = JSON_OPTION,
) -> None:
    """Delete a Step and the Outcomes attached to it."""
    if not yes:
        confirm = typer.confirm(f"Delete step {step_id}?")
        if not confirm:
            raise typer.Exit()
    typer.echo(
        render_deleted(
            run_tool("delete_step", {"step_id": step_id}), as_json=json_output, noun="step"
        )
    )
