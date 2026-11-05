"""The next step — what the user said they would do before coming back (ALH-146, M0-14).

The product has always known what the user wants and never what they intend to
do about it, so a return visit starts from scratch. A step is stored rather than
kept in the terminal's memory, because asking about a promise that vanished on a
cache clear is worse than not asking. One step is outstanding at a time: saying a
new one supersedes the old, and answering one turns what happened into evidence.
"""

from __future__ import annotations

import typer

from agentic_odi_cli.backend import run_tool
from agentic_odi_cli.render import render_evidence, render_next_step, render_next_step_list

next_step_app = typer.Typer(help="Remember the one thing meant for next, and ask about it.")

JSON_OPTION = typer.Option(False, "--json", help="Emit machine-readable JSON.")


@next_step_app.command("set")
def set_next_step(
    text: str = typer.Argument(..., help="One line, in the user's own words"),
    outcome_id: str = typer.Option(None, "--outcome", help="The outcome this step is about"),
    json_output: bool = JSON_OPTION,
) -> None:
    """Say what happens next. A step already outstanding is superseded, not deleted."""
    args: dict[str, object] = {"text": text}
    if outcome_id is not None:
        args["outcome_id"] = outcome_id
    typer.echo(render_next_step(run_tool("set_next_step", args), as_json=json_output))


@next_step_app.command("show")
def show_next_step(json_output: bool = JSON_OPTION) -> None:
    """The step still outstanding — the one a returning session asks about."""
    typer.echo(render_next_step(run_tool("get_next_step", {}), as_json=json_output))


@next_step_app.command("list")
def list_next_steps(json_output: bool = JSON_OPTION) -> None:
    """Every step recorded, outstanding and closed."""
    typer.echo(render_next_step_list(run_tool("list_next_steps", {}), as_json=json_output))


@next_step_app.command("resolve")
def resolve_next_step(
    step_id: str = typer.Argument(..., help="The step being answered"),
    resolution: str = typer.Argument(..., help="What actually happened"),
    json_output: bool = JSON_OPTION,
) -> None:
    """Answer the step. What happened is research, so it joins the evidence library."""
    typer.echo(
        render_evidence(
            run_tool("resolve_next_step", {"step_id": step_id, "resolution": resolution}),
            as_json=json_output,
        )
    )
