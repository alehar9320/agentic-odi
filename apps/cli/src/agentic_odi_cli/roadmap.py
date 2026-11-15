"""Render a job's outcome roadmap from the CLI (C7.2, ALH-160).

``odi roadmap`` is transport only: it asks the backend for the derived roadmap
and hands the result to the shared ``render_roadmap``, so the CLI and the Studio
cannot disagree about a period or an exclusion. It never regroups, recomputes a
quarter, or fetches an entry separately.

A baseline or target nobody measured prints ``not measured`` — never ``0``.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

import typer

from agentic_odi_cli.backend import run_tool

roadmap_app = typer.Typer(help="Render a job's outcome roadmap.")

JOB_ID_OPTION = typer.Option(..., "--job-id", help="Job to derive the roadmap for.")
HORIZON_OPTION = typer.Option(4, "--horizon", help="How many quarters the view spans.")
TODAY_OPTION = typer.Option(
    None, "--today", help="ISO-8601 date to pin the window. Defaults to today in UTC."
)
JSON_OPTION = typer.Option(False, "--json", help="Emit machine-readable JSON.")


def _to_roadmap(payload: dict[str, Any]) -> Any:
    """Rebuild the derived view from the transport payload.

    The renderer consumes a :class:`Roadmap`; this is the only shaping the CLI
    does, and it copies every field rather than recomputing one. The core import
    is deferred so ``--help`` does not pull in the domain layer.
    """
    from agentic_odi_core.roadmap import Roadmap, RoadmapEntry

    return Roadmap(
        entries=tuple(
            RoadmapEntry(
                period=entry["period"],
                outcome_id=entry["outcome_id"],
                statement=entry["statement"],
                decision_id=entry["decision_id"],
                baseline=entry.get("baseline"),
                target=entry.get("target"),
            )
            for entry in payload.get("entries") or []
        ),
        undecided_count=payload.get("undecided_count", 0),
        horizon_excluded_count=payload.get("horizon_excluded_count", 0),
        superseded_excluded_count=payload.get("superseded_excluded_count", 0),
        horizon=payload.get("horizon", 4),
    )


@roadmap_app.command("show")
def show(
    job_id: str = JOB_ID_OPTION,
    horizon: int = HORIZON_OPTION,
    today: str | None = TODAY_OPTION,
    json_output: bool = JSON_OPTION,
) -> None:
    """Derive and render the roadmap from the job's recorded decisions."""
    if horizon < 1:
        typer.echo("Error: horizon must be at least 1 quarter", err=True)
        raise typer.Exit(code=1)

    args: dict[str, Any] = {
        "job_id": job_id,
        "horizon": horizon,
        "today": today or datetime.now(timezone.utc).date().isoformat(),
    }
    payload = run_tool("get_roadmap", args)

    if json_output:
        typer.echo(json.dumps(payload, indent=2, ensure_ascii=False))
        return

    from agentic_odi_core.roadmap import render_roadmap

    typer.echo(render_roadmap(_to_roadmap(payload)), nl=False)
