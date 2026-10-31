"""Alternatives CLI subcommands (M2-07).

Alternatives record what a customer uses today for one Job — a product, a
service, a workaround, a manual process, or nothing at all. ``nothing`` is a
real row and the most informative one, because it is the evidence for a
new-market bet. Every command works against whichever backend is selected
(local SQLite by default, or a remote MCP server via ``--backend mcp``).
"""

from __future__ import annotations

from enum import Enum
from typing import Any

import typer

from agentic_odi_cli.backend import run_tool
from agentic_odi_cli.render import (
    render_alternative_list,
    render_existing_solution,
    render_saved,
)

alternatives_app = typer.Typer(help="Record what customers use today.")


class KindOption(str, Enum):
    PRODUCT = "product"
    SERVICE = "service"
    WORKAROUND = "workaround"
    MANUAL = "manual"
    NOTHING = "nothing"


JSON_OPTION = typer.Option(False, "--json", help="Emit machine-readable JSON.")


@alternatives_app.command("add")
def add(
    job_id: str = typer.Option(..., help="Job ID the alternative belongs to"),
    name: str = typer.Option(..., help="What the customer calls it"),
    kind: KindOption = typer.Option(..., help="product|service|workaround|manual|nothing"),  # noqa: B008
    notes: str | None = typer.Option(default=None, help="Customer-provided notes"),
    source_kind: str = typer.Option(
        "manual", help="How we learned it: manual|interview|import|customer"
    ),
    json_output: bool = JSON_OPTION,
) -> None:
    """Record an alternative for a Job."""
    result = run_tool(
        "add_alternative",
        {
            "job_id": job_id,
            "name": name,
            "kind": kind.value,
            "notes": notes,
            "source_kind": source_kind,
        },
    )
    typer.echo(render_saved("created", result, as_json=json_output, noun="Alternative"))


@alternatives_app.command("list")
def list_alternatives(
    job_id: str | None = typer.Option(default=None, help="Filter by job ID"),
    json_output: bool = JSON_OPTION,
) -> None:
    """List the alternatives recorded for a Job."""
    args: dict[str, Any] = {}
    if job_id:
        args["job_id"] = job_id
    result = run_tool("list_alternatives", args)
    typer.echo(render_alternative_list(result, as_json=json_output))


@alternatives_app.command("link")
def link(
    outcome_id: str = typer.Argument(...),
    alternative_id: str = typer.Argument(...),
    adequacy: float = typer.Option(..., min=1.0, max=10.0, help="The customer's own rating"),
    usage_n: int | None = typer.Option(default=None, help="How many customers this covers"),
    note: str | None = typer.Option(default=None),
    json_output: bool = JSON_OPTION,
) -> None:
    """Rate one alternative against one outcome with the customer's adequacy."""
    args: dict[str, Any] = {
        "outcome_id": outcome_id,
        "alternative_id": alternative_id,
        "adequacy": adequacy,
    }
    if usage_n is not None:
        args["usage_n"] = usage_n
    if note is not None:
        args["note"] = note
    result = run_tool("link_alternative", args)
    typer.echo(render_saved("linked", result, as_json=json_output, noun="Alternative link"))


@alternatives_app.command("show")
def show(
    outcome_id: str = typer.Argument(...),
    json_output: bool = JSON_OPTION,
) -> None:
    """Show the alternatives recorded for one outcome and its solution state."""
    result = run_tool("get_outcome_alternatives", {"outcome_id": outcome_id})
    verdict = run_tool("get_has_existing_solution", {"outcome_id": outcome_id})
    typer.echo(
        render_alternative_list(
            result,
            as_json=json_output,
            empty="Not yet inventoried — no alternatives recorded for this outcome.",
        )
    )
    if not json_output:
        typer.echo(render_existing_solution(verdict, as_json=False))
