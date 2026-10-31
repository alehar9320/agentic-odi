"""Signal inbox CLI subcommands.

Signals are the record of things that actually happened in the store — a job
added, an outcome re-scored, evidence promoted. They are emitted by writes,
never invented, so an empty feed genuinely means a quiet workspace.
"""

from __future__ import annotations

import typer

from agentic_odi_cli.backend import run_tool
from agentic_odi_cli.render import render_saved, render_signal_list

signals_app = typer.Typer(help="Read the signal inbox — real changes worth attention.")

JSON_OPTION = typer.Option(False, "--json", help="Emit machine-readable JSON.")


@signals_app.command("list")
def list_signals(
    unread_only: bool = typer.Option(False, "--unread", help="Only signals nobody has read"),
    limit: int = typer.Option(50, "--limit", min=1, help="How many signals to fetch"),
    job_id: str | None = typer.Option(None, "--job-id", help="Limit to one Job"),
    json_output: bool = JSON_OPTION,
) -> None:
    """List signals, newest first; ``--job-id`` scopes the feed to one Job."""
    args: dict[str, object] = {"unread_only": unread_only, "limit": limit}
    if job_id is not None:
        args["job_id"] = job_id
    typer.echo(render_signal_list(run_tool("list_signals", args), as_json=json_output))


@signals_app.command("unread")
def unread(json_output: bool = JSON_OPTION) -> None:
    """List only the signals nobody has read yet."""
    typer.echo(
        render_signal_list(
            run_tool("list_signals", {"unread_only": True, "limit": 50}), as_json=json_output
        )
    )


@signals_app.command("read")
def read(
    signal_id: str = typer.Argument(..., help="Signal ID"),
    json_output: bool = JSON_OPTION,
) -> None:
    """Mark a signal as read."""
    typer.echo(
        render_saved(
            "read",
            run_tool("mark_signal_read", {"signal_id": signal_id}),
            as_json=json_output,
            noun="Signal",
        )
    )


@signals_app.command("dismiss")
def dismiss(
    signal_id: str = typer.Argument(..., help="Signal ID"),
    json_output: bool = JSON_OPTION,
) -> None:
    """Dismiss a signal so it leaves the feed."""
    typer.echo(
        render_saved(
            "dismissed",
            run_tool("dismiss_signal", {"signal_id": signal_id}),
            as_json=json_output,
            noun="Signal",
        )
    )
