"""The innovation strategy the segments imply (Stage 6).

The recommendation carries the paths it beat: a strategy without its rejections
is a conclusion, not a recommendation.
"""

from __future__ import annotations

import typer

from agentic_odi_cli.backend import run_tool
from agentic_odi_cli.render import render_strategy

strategy_app = typer.Typer(help="The innovation strategy your segments imply.")

JSON_OPTION = typer.Option(False, "--json", help="Emit machine-readable JSON.")


@strategy_app.command("show")
def show(json_output: bool = JSON_OPTION) -> None:
    """Show the recorded strategy, or say that none exists."""
    typer.echo(render_strategy(run_tool("get_strategy", {}), as_json=json_output))


@strategy_app.command("propose")
def propose(
    job_id: str = typer.Option(None, "--job", help="Scope the bet to one job's segments"),
    json_output: bool = JSON_OPTION,
) -> None:
    """Ask which of the three paths the evidence supports, and why not the others."""
    args: dict[str, object] = {}
    if job_id is not None:
        args["job_id"] = job_id
    typer.echo(render_strategy(run_tool("propose_strategy", args), as_json=json_output))
