"""Outcome-based market segments (Stage 5).

A segment is a group of people plus the functional job they are trying to do,
derived from scored outcomes on a job map. Demographics are never an input: if
it is not visible in an outcome, it is not in a segment.
"""

from __future__ import annotations

import typer

from agentic_odi_cli.backend import run_tool
from agentic_odi_cli.render import render_segment, render_segment_list

segments_app = typer.Typer(help="Segments derived from outcomes, never from demographics.")

JSON_OPTION = typer.Option(False, "--json", help="Emit machine-readable JSON.")


@segments_app.command("list")
def list_segments(
    job_id: str = typer.Option(None, "--job", help="Limit to one job"),
    json_output: bool = JSON_OPTION,
) -> None:
    """List stored segments with each verdict and its confidence."""
    args: dict[str, object] = {}
    if job_id is not None:
        args["job_id"] = job_id
    typer.echo(render_segment_list(run_tool("get_segments", args), as_json=json_output))


@segments_app.command("show")
def show_segment(
    segment_id: str = typer.Argument(..., help="Segment ID"),
    job_id: str = typer.Option(None, "--job", help="Narrow the search to one job"),
    json_output: bool = JSON_OPTION,
) -> None:
    """Show one segment: its people, its evidence, and why it got its verdict."""
    args: dict[str, object] = {}
    if job_id is not None:
        args["job_id"] = job_id
    segments = run_tool("get_segments", args)
    segment = next((item for item in segments if item.get("id") == segment_id), None)
    if segment is None:
        raise typer.BadParameter(f"Segment not found: {segment_id}")
    typer.echo(render_segment(segment, as_json=json_output))


@segments_app.command("run")
def run_segmentation(
    job_id: str = typer.Option(None, "--job", help="Segment one job instead of every job"),
    people: str = typer.Option(
        None, "--people", help="The group in their own words, when they have said them"
    ),
    json_output: bool = JSON_OPTION,
) -> None:
    """Cluster scored outcomes into segments and store what the clustering found."""
    args: dict[str, object] = {}
    if job_id is not None:
        args["job_id"] = job_id
    if people is not None:
        args["people"] = people
    typer.echo(render_segment_list(run_tool("segment_market", args), as_json=json_output))
