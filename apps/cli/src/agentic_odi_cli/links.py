"""Links CLI subcommands.

Typed links between ODI entities (jobs, steps, outcomes, evidence, etc.).
"""

from __future__ import annotations

from enum import Enum
from typing import Any

import typer

from agentic_odi_cli.backend import run_tool
from agentic_odi_cli.render import render_deleted, render_link_list, render_saved

links_app = typer.Typer(help="Manage typed links between ODI entities.")

JSON_OPTION = typer.Option(False, "--json", help="Emit machine-readable JSON.")


class RelationshipType(str, Enum):
    REFERENCES = "references"
    SERVES = "serves"
    BLOCKED_BY = "blocked_by"
    BLOCKING = "blocking"
    DUPLICATES = "duplicates"
    RELATES_TO = "relates_to"
    IMPLEMENTS = "implements"
    VALIDATES = "validates"
    EVIDENCE_FOR = "evidence_for"
    OUTCOME_OF = "outcome_of"
    EXTERNAL_JIRA = "external_jira"
    EXTERNAL_LINEAR = "external_linear"
    EXTERNAL_JPD = "external_jpd"
    EXTERNAL_GITHUB = "external_github"
    EXTERNAL_NOTION = "external_notion"


def _fail(message: str) -> None:
    typer.secho(f"Error: {message}", fg="red", err=True)
    raise typer.Exit(1)


@links_app.command("add")
def add(
    source_type: str = typer.Option(..., "--source-type", help="Type of the source entity"),
    source_id: str = typer.Option(..., "--source-id", help="ID of the source entity"),
    target_type: str = typer.Option(..., "--target-type", help="Type of the target entity"),
    target_id: str = typer.Option(..., "--target-id", help="ID of the target entity"),
    relationship_type: RelationshipType = typer.Option(  # noqa: B008
        ..., "--relationship-type", help="Relationship between source and target"
    ),
    external_system: str | None = typer.Option(
        None, "--external-system", help="External system that originated the link"
    ),
    external_id: str | None = typer.Option(
        None, "--external-id", help="External ID in the origin system"
    ),
    preview: str | None = typer.Option(
        None, "--preview", help="Cached preview of the target entity as JSON string"
    ),
    json_output: bool = JSON_OPTION,
) -> None:
    """Create a typed link between two entities."""
    import json

    args: dict[str, Any] = {
        "source_type": source_type,
        "source_id": source_id,
        "target_type": target_type,
        "target_id": target_id,
        "relationship_type": relationship_type.value,
    }
    if external_system is not None:
        args["external_system"] = external_system
    if external_id is not None:
        args["external_id"] = external_id
    if preview is not None:
        try:
            args["preview"] = json.loads(preview)
        except json.JSONDecodeError as exc:
            _fail(f"Invalid JSON for --preview: {exc}")

    result = run_tool("links_add", args)
    typer.echo(render_saved("created", result, as_json=json_output, noun="Link"))


@links_app.command("list")
def list_links(
    source_type: str | None = typer.Option(
        None, "--source-type", help="Filter by source entity type"
    ),
    source_id: str | None = typer.Option(None, "--source-id", help="Filter by source entity ID"),
    target_type: str | None = typer.Option(
        None, "--target-type", help="Filter by target entity type"
    ),
    target_id: str | None = typer.Option(None, "--target-id", help="Filter by target entity ID"),
    relationship_type: str | None = typer.Option(
        None, "--relationship-type", help="Filter by relationship type"
    ),
    limit: int | None = typer.Option(None, "--limit", help="Maximum number of links to return"),
    offset: int = typer.Option(0, "--offset", help="Number of links to skip"),
    json_output: bool = JSON_OPTION,
) -> None:
    """List links, optionally filtered by source, target, or relationship type."""
    args: dict[str, Any] = {}
    if source_type is not None:
        args["source_type"] = source_type
    if source_id is not None:
        args["source_id"] = source_id
    if target_type is not None:
        args["target_type"] = target_type
    if target_id is not None:
        args["target_id"] = target_id
    if relationship_type is not None:
        args["relationship_type"] = relationship_type
    if limit is not None:
        args["limit"] = limit
    if offset != 0:
        args["offset"] = offset

    typer.echo(render_link_list(run_tool("links_list", args), as_json=json_output))


@links_app.command("remove")
def remove(
    link_id: str = typer.Argument(..., help="Link ID to remove"),
    json_output: bool = JSON_OPTION,
) -> None:
    """Remove a link by ID."""
    result = run_tool("links_remove", {"link_id": link_id})
    if not result:
        typer.secho(f"Error: No link with id {link_id!r}", fg="red", err=True)
        raise typer.Exit(1)
    typer.echo(render_deleted(link_id, as_json=json_output, noun="link"))
