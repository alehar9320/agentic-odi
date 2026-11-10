"""``odi top`` and ``odi coverage``: the evidence-aware ranking from a terminal (B4.2).

Both read the same ranking payload the landscape uses, so the terminal and the
SPA cannot disagree. ``top`` defaults to measured outcomes only and names the
thin and unscored counts it excluded; ``coverage`` reports how much of a job's
outcome set is measured, thin or unscored.
"""

from __future__ import annotations

import json
from typing import Any

import typer

from agentic_odi_cli.backend import run_tool

JSON_OPTION = typer.Option(False, "--json", help="Emit machine-readable JSON.")


def _band_label(entry: dict[str, Any]) -> str:
    low = entry.get("opportunity_low")
    high = entry.get("opportunity_high")
    method = entry.get("score_method") or "estimate"
    if low is None or high is None:
        return "no band"
    if low == high:
        return "no band" if method == "estimate" else "±0 (n=1)"
    return f"[{low:.1f}–{high:.1f}]"


def _sample_label(entry: dict[str, Any]) -> str:
    importance_n = entry.get("importance_n")
    satisfaction_n = entry.get("satisfaction_n")
    method = entry.get("score_method") or "estimate"
    if method == "estimate" or (importance_n is None and satisfaction_n is None):
        return "est."
    if importance_n == satisfaction_n:
        return f"n={importance_n} ({method})"
    return f"n={importance_n or '?'}/{satisfaction_n or '?'} ({method})"


def top(
    job_id: str | None = typer.Option(None, "--job", help="Job to rank; all jobs when omitted"),
    limit: int = typer.Option(10, "--limit", min=1, help="Maximum rows per section"),
    include_thin: bool = typer.Option(
        False, "--include-thin", help="Add the thin section (unscored stays counted, not listed)"
    ),
    json_output: bool = JSON_OPTION,
) -> None:
    """List a Job's measured outcomes, highest band low end first."""
    job_ids = [job_id] if job_id else [job["id"] for job in run_tool("get_jobs", {})]
    sections: dict[str, list[dict[str, Any]]] = {"measured": [], "thin": [], "none": []}
    for current in job_ids:
        ranking = run_tool("rank_outcomes", {"job_id": current})
        for name, entries in ranking["sections"].items():
            sections[name].extend(entries)

    measured = sections["measured"][:limit]
    thin = sections["thin"][:limit] if include_thin else []
    if json_output:
        typer.echo(
            json.dumps(
                {
                    "measured": measured,
                    "thin": thin,
                    "excluded": {
                        "thin": len(sections["thin"]),
                        "none": len(sections["none"]),
                    },
                },
                indent=2,
                sort_keys=True,
            )
        )
        return

    if not measured and not thin:
        typer.echo("No measured outcomes yet; every outcome is thin or unscored.")
    for entry in measured:
        typer.echo(
            f"  {entry['id']}  {entry['opportunity_score']}  {_band_label(entry)}  "
            f"{_sample_label(entry)}  {entry['statement']}"
        )
    for entry in thin:
        typer.echo(
            f"  [thin] {entry['id']}  {entry['opportunity_score']}  {_band_label(entry)}  "
            f"{_sample_label(entry)}  {entry['statement']}"
        )
    # The M2-14 advisory is a footer line, not a filter: a below-threshold score
    # still renders and still ranks, it just says how thin its sample is.
    for entry in measured + thin:
        advisory = entry.get("advisory")
        if advisory:
            typer.echo(f"  note: {advisory['message']}")
    if not include_thin and sections["thin"]:
        typer.echo(f"  ({len(sections['thin'])} thin outcome(s) not shown; pass --include-thin)")
    if sections["none"]:
        typer.echo(f"  ({len(sections['none'])} unscored/estimate outcome(s) not ranked)")


def coverage(
    job_id: str | None = typer.Option(None, "--job", help="Job to report; all jobs when omitted"),
    json_output: bool = JSON_OPTION,
) -> None:
    """Report how many of a Job's outcomes are measured, thin or unscored."""
    job_ids = [job_id] if job_id else [job["id"] for job in run_tool("get_jobs", {})]
    totals = {"measured": 0, "thin": 0, "none": 0, "total": 0}
    for current in job_ids:
        counts = run_tool("rank_outcomes", {"job_id": current})["counts"]
        for key in totals:
            totals[key] += counts[key]
    if json_output:
        typer.echo(json.dumps(totals, indent=2, sort_keys=True))
        return
    typer.echo(
        f"Coverage: {totals['measured']} measured, {totals['thin']} thin, "
        f"{totals['none']} unscored of {totals['total']} outcome(s)."
    )


def register(app: typer.Typer) -> None:
    """Register ``odi top`` and ``odi coverage`` as root commands."""
    app.command("top")(top)
    app.command("coverage")(coverage)
