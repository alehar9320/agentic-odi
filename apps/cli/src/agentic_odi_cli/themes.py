"""Themes: a named two-level tree over the desired-outcome library (M2-01).

A theme is a folder, not a new kind of outcome: outcomes keep their scores and
gain memberships. Two levels at most, scoped to one job, or workspace-wide when
no job is given.
"""

from __future__ import annotations

import typer

from agentic_odi_cli.backend import run_tool
from agentic_odi_cli.render import (
    render_outcome_list,
    render_theme,
    render_theme_deleted,
    render_theme_list,
)

themes_app = typer.Typer(help="Group desired outcomes into a named theme tree.")

JSON_OPTION = typer.Option(False, "--json", help="Emit machine-readable JSON.")
OUTCOME_OPTION = typer.Option(..., "--outcome", help="Outcome ID; repeat for several outcomes")


@themes_app.command("add")
def add_theme(
    name: str = typer.Option(..., "--name", help="What this group of outcomes is about"),
    job_id: str = typer.Option(
        None, "--job", help="Job this theme organizes; omit for a workspace theme"
    ),
    parent_id: str = typer.Option(None, "--parent", help="Parent theme ID (two levels at most)"),
    description: str = typer.Option(None, "--description", help="Longer note on the grouping"),
    ordinal: int = typer.Option(0, "--ordinal", help="Display order among siblings"),
    json_output: bool = JSON_OPTION,
) -> None:
    """Name a group of related desired outcomes."""
    args: dict[str, object] = {"name": name, "ordinal": ordinal}
    if job_id is not None:
        args["job_id"] = job_id
    if parent_id is not None:
        args["parent_id"] = parent_id
    if description is not None:
        args["description"] = description
    typer.echo(render_theme(run_tool("add_theme", args), as_json=json_output))


@themes_app.command("list")
def list_themes(
    job_id: str = typer.Option(
        None, "--job", help="Limit to one job (workspace themes always show)"
    ),
    json_output: bool = JSON_OPTION,
) -> None:
    """List the theme tree."""
    args: dict[str, object] = {}
    if job_id is not None:
        args["job_id"] = job_id
    typer.echo(render_theme_list(run_tool("list_themes", args), as_json=json_output))


@themes_app.command("rename")
def rename_theme(
    theme_id: str = typer.Argument(..., help="Theme ID"),
    name: str = typer.Option(None, "--name", help="New name"),
    description: str = typer.Option(None, "--description", help="New description"),
    ordinal: int = typer.Option(None, "--ordinal", help="New display order"),
    parent_id: str = typer.Option(None, "--parent", help="Move under this parent theme"),
    json_output: bool = JSON_OPTION,
) -> None:
    """Rename, reword, reorder, or move a theme. Omitted options stay unchanged."""
    args: dict[str, object] = {"theme_id": theme_id}
    if name is not None:
        args["name"] = name
    if description is not None:
        args["description"] = description
    if ordinal is not None:
        args["ordinal"] = ordinal
    if parent_id is not None:
        args["parent_id"] = parent_id
    typer.echo(render_theme(run_tool("rename_theme", args), as_json=json_output))


@themes_app.command("delete")
def delete_theme(
    theme_id: str = typer.Argument(..., help="Theme ID"),
    json_output: bool = JSON_OPTION,
) -> None:
    """Delete a theme; children move up and outcomes keep their other memberships."""
    result = run_tool("delete_theme", {"theme_id": theme_id})
    typer.echo(render_theme_deleted(result, as_json=json_output))


@themes_app.command("assign")
def assign_theme(
    theme_id: str = typer.Option(..., "--theme", help="Theme ID"),
    outcome_ids: list[str] = OUTCOME_OPTION,
    json_output: bool = JSON_OPTION,
) -> None:
    """File outcomes under a theme; all of them or none."""
    result = run_tool("assign_theme", {"outcome_ids": list(outcome_ids), "theme_id": theme_id})
    typer.echo(render_outcome_list(result, as_json=json_output))


@themes_app.command("unassign")
def unassign_theme(
    theme_id: str = typer.Option(..., "--theme", help="Theme ID"),
    outcome_ids: list[str] = OUTCOME_OPTION,
    json_output: bool = JSON_OPTION,
) -> None:
    """Remove a theme from outcomes; their other memberships stay."""
    result = run_tool("unassign_theme", {"outcome_ids": list(outcome_ids), "theme_id": theme_id})
    typer.echo(render_outcome_list(result, as_json=json_output))
