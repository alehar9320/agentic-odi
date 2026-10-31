"""CLI commands for managing scheduled cloud agent work tasks."""

from __future__ import annotations

import json
from typing import Any

import typer

from agentic_odi_cli.backend import run_tool
from agentic_odi_cli.render import render_scheduled_work_list

schedule_app = typer.Typer(
    name="schedule",
    help="Schedule and manage background cloud agent work tasks.",
    no_args_is_help=True,
)


@schedule_app.command(name="create")
def create_cmd(
    name: str = typer.Option(..., "--name", "-n", help="Name or label for the scheduled task"),
    expression: str = typer.Option(
        ...,
        "--expression",
        "-e",
        help=(
            "ISO-8601 timestamp, relative delay (+1h, +90m, +2d), or cron "
            "(0 9 * * 1-5). The expression decides one-shot vs recurring."
        ),
    ),
    agent_id: str = typer.Option(
        "default-agent", "--agent-id", "-a", help="Agent ID assigned to run the work"
    ),
    trigger_type: str = typer.Option(
        "oneshot",
        "--trigger-type",
        "-t",
        help="Compatibility hint; the parsed expression decides the real trigger type.",
    ),
    job_id: str | None = typer.Option(None, "--job-id", "-j", help="Associated ODI Job ID"),
    payload: str | None = typer.Option(
        None, "--payload", "-p", help="JSON string payload/parameters for the task"
    ),
) -> None:
    """Schedule a new task for cloud agent execution."""
    parsed_payload: dict[str, Any] = {}
    if payload:
        try:
            parsed_payload = json.loads(payload)
        except json.JSONDecodeError as exc:
            typer.secho(f"Error: Invalid JSON payload: {exc}", fg="red", err=True)
            raise typer.Exit(code=1) from exc

    result = run_tool(
        "schedule_work",
        {
            "name": name,
            "schedule_expression": expression,
            "agent_id": agent_id,
            "trigger_type": trigger_type,
            "job_id": job_id,
            "payload": parsed_payload,
        },
    )
    typer.secho(f"Scheduled work created successfully with ID: {result.get('id')}", fg="green")


@schedule_app.command(name="list")
def list_cmd(
    job_id: str | None = typer.Option(
        None, "--job-id", "-j", help="Filter by associated ODI Job ID"
    ),
    status: str | None = typer.Option(
        None, "--status", "-s", help="Filter by status (scheduled, completed, cancelled, etc.)"
    ),
    as_json: bool = typer.Option(False, "--json", help="Output raw JSON array"),
) -> None:
    """List scheduled cloud work tasks."""
    args: dict[str, Any] = {}
    if job_id:
        args["job_id"] = job_id
    if status:
        args["status"] = status

    items = run_tool("list_scheduled_work", args)
    typer.echo(render_scheduled_work_list(items, as_json=as_json))


@schedule_app.command(name="show")
def show_cmd(
    work_id: str = typer.Argument(..., help="The ID of the scheduled work task"),
) -> None:
    """Show details for a specific scheduled task."""
    result = run_tool("get_scheduled_work", {"work_id": work_id})
    typer.echo(json.dumps(result, indent=2))


@schedule_app.command(name="cancel")
def cancel_cmd(
    work_id: str = typer.Argument(..., help="The ID of the scheduled work task to cancel"),
) -> None:
    """Cancel a scheduled cloud task."""
    result = run_tool("cancel_scheduled_work", {"work_id": work_id})
    typer.secho(
        f"Cancelled scheduled task '{result.get('name')}' ({result.get('id')})", fg="yellow"
    )


@schedule_app.command(name="trigger")
def trigger_cmd(
    work_id: str = typer.Argument(
        ..., help="The ID of the scheduled work task to trigger immediately"
    ),
) -> None:
    """Queue a scheduled task for the orchestrator to dispatch."""
    result = run_tool("trigger_scheduled_work", {"work_id": work_id})
    typer.secho(
        f"Queued task '{result.get('name')}' for the orchestrator: {result.get('result_summary')}",
        fg="green",
    )
