"""Studies — a named pass over a job, and the waves inside it (ALH-69, M2-05).

Nothing in the product distinguished research done in March from research done in
September. A study is the container that makes "the market last quarter" and "the
market this quarter" comparable; opening the same study again is a new wave, not a
second copy of the first.
"""

from __future__ import annotations

import typer

from agentic_odi_cli.backend import run_tool
from agentic_odi_cli.render import render_study, render_study_list

studies_app = typer.Typer(help="A study is one named pass over a job; each pass is a wave.")

JSON_OPTION = typer.Option(False, "--json", help="Emit machine-readable JSON.")


@studies_app.command("open")
def open_study(
    job_id: str = typer.Option(..., "--job", help="The job this study is a pass over"),
    name: str = typer.Option(..., "--name", help="The pass in the researcher's own words"),
    wave: int = typer.Option(..., "--wave", help="Pass number, from 1; a later wave is a re-run"),
    method_notes: str = typer.Option(
        None, "--method-notes", help="How the pass was run, when it is known"
    ),
    json_output: bool = JSON_OPTION,
) -> None:
    """Open a study pass over a job. Refuses to repeat a wave under the same name."""
    args: dict[str, object] = {"job_id": job_id, "name": name, "wave": wave}
    if method_notes is not None:
        args["method_notes"] = method_notes
    typer.echo(render_study(run_tool("open_study", args), as_json=json_output))


@studies_app.command("list")
def list_studies(
    job_id: str = typer.Option(None, "--job", help="Limit to one job"),
    json_output: bool = JSON_OPTION,
) -> None:
    """List the studies opened so far."""
    args: dict[str, object] = {}
    if job_id is not None:
        args["job_id"] = job_id
    typer.echo(render_study_list(run_tool("list_studies", args), as_json=json_output))
