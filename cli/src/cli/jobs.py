"""Jobs-to-be-Done CLI subcommands.

Every command goes through :func:`cli.backend.run_tool`, so it works against
the local SQLite store or a remote MCP server without a second code path.
"""

from __future__ import annotations

from typing import Any

import typer

from cli.backend import run_tool
from cli.render import render_deleted, render_job, render_job_list, render_saved

jobs_app = typer.Typer(help="Manage Jobs-to-be-Done.")

JSON_OPTION = typer.Option(False, "--json", help="Emit machine-readable JSON.")


@jobs_app.command("add")
def add(
    name: str = typer.Option(..., help="Job name"),
    description: str | None = typer.Option(default=None, help="Job description"),
    json_output: bool = JSON_OPTION,
) -> None:
    """Add a new Job."""
    args: dict[str, Any] = {"name": name}
    if description is not None:
        args["description"] = description
    typer.echo(render_saved("created", run_tool("add_job", args), as_json=json_output, noun="Job"))


@jobs_app.command("list")
def list_jobs(json_output: bool = JSON_OPTION) -> None:
    """List all Jobs."""
    typer.echo(render_job_list(run_tool("get_jobs", {}), as_json=json_output))


@jobs_app.command("get")
def get(job_id: str = typer.Argument(..., help="Job ID"), json_output: bool = JSON_OPTION) -> None:
    """Get a Job by ID."""
    typer.echo(render_job(run_tool("get_job", {"job_id": job_id}), as_json=json_output))


@jobs_app.command("update")
def update(
    job_id: str = typer.Argument(..., help="Job ID"),
    name: str | None = typer.Option(default=None, help="New job name"),
    description: str | None = typer.Option(default=None, help="New job description"),
    json_output: bool = JSON_OPTION,
) -> None:
    """Update an existing Job."""
    args: dict[str, Any] = {"job_id": job_id}
    if name is not None:
        args["name"] = name
    if description is not None:
        args["description"] = description
    typer.echo(
        render_saved("updated", run_tool("update_job", args), as_json=json_output, noun="Job")
    )


@jobs_app.command("delete")
def delete(
    job_id: str = typer.Argument(..., help="Job ID"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation"),
    json_output: bool = JSON_OPTION,
) -> None:
    """Delete a Job and every Step and Outcome attached to it."""
    if not yes:
        confirm = typer.confirm(f"Delete job {job_id}?")
        if not confirm:
            raise typer.Exit()
    typer.echo(
        render_deleted(run_tool("delete_job", {"job_id": job_id}), as_json=json_output, noun="job")
    )
