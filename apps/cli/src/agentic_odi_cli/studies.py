"""Studies and the waves inside them (M2-05).

A study is a job measured at one point in time. The frame — the interview
guide, the outcome statements, the themes — carries between waves; the
measurements do not, because a wave starts unmeasured.
"""

from __future__ import annotations

import typer

from agentic_odi_cli.backend import run_tool
from agentic_odi_cli.render import (
    render_study,
    render_study_list,
    render_wave_comparison,
)

studies_app = typer.Typer(help="Studies and the waves inside them.")

JSON_OPTION = typer.Option(False, "--json", help="Emit machine-readable JSON.")


@studies_app.command("open")
def open_study(
    job_id: str = typer.Option(..., "--job", help="The job this study measures"),
    name: str = typer.Option(..., "--name", help="Human label for the study"),
    guide_name: str = typer.Option(None, "--guide-name", help="The interview guide's label"),
    guide_version: str = typer.Option("1", "--guide-version", help="The guide's version"),
    questions: list[str] = typer.Option(  # noqa: B008
        None, "--question", help="An interview question; repeat for each one"
    ),
    statement: list[str] = typer.Option(  # noqa: B008
        None, "--statement", help="An outcome statement in the frame; repeat for each one"
    ),
    theme: list[str] = typer.Option(  # noqa: B008
        None, "--theme", help="A theme in the frame; repeat for each one"
    ),
    json_output: bool = JSON_OPTION,
) -> None:
    """Open wave 1 of a study, with the frame it will measure against."""
    args: dict[str, object] = {"job_id": job_id, "name": name}
    if guide_name is not None:
        args["guide"] = {
            "name": guide_name,
            "version": guide_version,
            "questions": list(questions or []),
        }
    if statement:
        args["outcome_statements"] = list(statement)
    if theme:
        args["themes"] = list(theme)
    typer.echo(render_study(run_tool("open_study", args), as_json=json_output))


@studies_app.command("list")
def list_studies(
    job_id: str = typer.Option(None, "--job", help="Limit to one job"),
    json_output: bool = JSON_OPTION,
) -> None:
    """List the study waves, grouped by lineage and wave number."""
    args: dict[str, object] = {}
    if job_id is not None:
        args["job_id"] = job_id
    typer.echo(render_study_list(run_tool("get_studies", args), as_json=json_output))


@studies_app.command("next")
def next_wave(
    study_id: str = typer.Argument(..., help="The wave to clone the frame from"),
    json_output: bool = JSON_OPTION,
) -> None:
    """Open the next wave: same frame, no measurements carried over."""
    typer.echo(render_study(run_tool("next_wave", {"study_id": study_id}), as_json=json_output))


@studies_app.command("compare")
def compare_waves(
    study_a: str = typer.Argument(..., help="The earlier wave"),
    study_b: str = typer.Argument(..., help="The later wave"),
    json_output: bool = JSON_OPTION,
) -> None:
    """Compare two waves of one job, statement by statement."""
    args = {"study_a": study_a, "study_b": study_b}
    typer.echo(render_wave_comparison(run_tool("compare_waves", args), as_json=json_output))


@studies_app.command("show")
def show_study(
    study_id: str = typer.Argument(..., help="Study wave ID"),
    json_output: bool = JSON_OPTION,
) -> None:
    """Show one wave's frame and status."""
    studies = run_tool("get_studies", {})
    study = next((item for item in studies if item.get("id") == study_id), None)
    if study is None:
        raise typer.BadParameter(f"Study not found: {study_id}")
    typer.echo(render_study(study, as_json=json_output))


__all__ = ["studies_app"]
