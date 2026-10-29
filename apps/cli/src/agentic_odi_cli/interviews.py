"""Interview CLI subcommands.

An interview records who took part, when, and the job it informs; its quotes
are the verbatim sentences the research is built from. Every command goes
through :func:`cli.backend.run_tool`, so it works against the local SQLite
store or a remote MCP server without a second code path.
"""

from __future__ import annotations

from typing import Any

import typer

from agentic_odi_cli.backend import run_tool
from agentic_odi_cli.render import (
    render_deleted,
    render_interview,
    render_interview_list,
    render_quote_list,
    render_saved,
)

interviews_app = typer.Typer(help="Manage research interviews and their quotes.")

JSON_OPTION = typer.Option(False, "--json", help="Emit machine-readable JSON.")


@interviews_app.command("add")
def add(
    title: str = typer.Option(..., help="Short human-readable title for the interview"),
    participant: str = typer.Option(
        ..., "--participant", help="Free-text participant label (never a real name or email)"
    ),
    job_id: str | None = typer.Option(None, help="The Job this interview informs"),
    role: str | None = typer.Option(None, "--role", help="The participant's role"),
    conducted_at: str | None = typer.Option(None, help="ISO-8601 date/time conducted"),
    notes: str | None = typer.Option(None, help="Researcher notes"),
    json_output: bool = JSON_OPTION,
) -> None:
    """Record a research interview."""
    args: dict[str, Any] = {"title": title, "participant_label": participant}
    if job_id is not None:
        args["job_id"] = job_id
    if role is not None:
        args["participant_role"] = role
    if conducted_at is not None:
        args["conducted_at"] = conducted_at
    if notes is not None:
        args["notes"] = notes
    typer.echo(
        render_saved(
            "created", run_tool("add_interview", args), as_json=json_output, noun="Interview"
        )
    )


@interviews_app.command("list")
def list_interviews(
    job_id: str | None = typer.Option(None, help="Only interviews for this job"),
    json_output: bool = JSON_OPTION,
) -> None:
    """List interviews."""
    args: dict[str, Any] = {}
    if job_id is not None:
        args["job_id"] = job_id
    typer.echo(render_interview_list(run_tool("list_interviews", args), as_json=json_output))


@interviews_app.command("get")
def get(
    interview_id: str = typer.Argument(..., help="Interview ID"),
    json_output: bool = JSON_OPTION,
) -> None:
    """Get an interview by ID."""
    typer.echo(
        render_interview(
            run_tool("get_interview", {"interview_id": interview_id}), as_json=json_output
        )
    )


@interviews_app.command("quotes")
def quotes(
    interview_id: str = typer.Argument(..., help="Interview ID"),
    json_output: bool = JSON_OPTION,
) -> None:
    """List an interview's quotes in ordinal order."""
    typer.echo(
        render_quote_list(
            run_tool("list_quotes", {"interview_id": interview_id}), as_json=json_output
        )
    )


@interviews_app.command("delete")
def delete(
    interview_id: str = typer.Argument(..., help="Interview ID"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation"),
    json_output: bool = JSON_OPTION,
) -> None:
    """Delete an interview and the quotes it recorded."""
    if not yes:
        confirm = typer.confirm(f"Delete interview {interview_id} and its quotes?")
        if not confirm:
            raise typer.Exit()
    typer.echo(
        render_deleted(
            run_tool("delete_interview", {"interview_id": interview_id}),
            as_json=json_output,
            noun="interview",
        )
    )
