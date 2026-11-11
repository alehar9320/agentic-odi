"""Candidate review CLI subcommands.

The ``candidates`` group is the keyboard surface over the review state machine:
extract proposals from a quote, then accept, edit, merge or reject them. Nothing
here writes to ``outcomes`` except ``accept`` (and ``accept --statement`` to edit
first), because a candidate is a proposal and a person accepts it.
"""

from __future__ import annotations

import json
from typing import Any

import typer

from agentic_odi_cli.backend import run_tool

candidates_app = typer.Typer(help="Review proposed outcomes extracted from quotes.")

JSON_OPTION = typer.Option(False, "--json", help="Emit machine-readable JSON.")


def _render_candidate(candidate: Any, *, as_json: bool) -> str:
    if as_json:
        return json.dumps(candidate, indent=2)
    if not isinstance(candidate, dict):
        return str(candidate)
    lines = [
        f"id:         {candidate.get('id')}",
        f"status:     {candidate.get('status')}",
        f"statement:  {candidate.get('statement')}",
        f"confidence: {candidate.get('confidence')}",
    ]
    if candidate.get("rationale"):
        lines.append(f"rationale:  {candidate.get('rationale')}")
    if candidate.get("outcome_id"):
        lines.append(f"outcome_id: {candidate.get('outcome_id')}")
    if candidate.get("rejection_reason"):
        lines.append(f"reason:     {candidate.get('rejection_reason')}")
    return "\n".join(lines)


def _render_candidate_list(candidates: Any, *, as_json: bool) -> str:
    if as_json:
        return json.dumps(candidates, indent=2)
    items = candidates if isinstance(candidates, list) else []
    if not items:
        return "No candidates yet."
    rows = [
        f"- [{item.get('status')}] {item.get('statement')}  ({item.get('id')})" for item in items
    ]
    return "\n".join(rows)


@candidates_app.command("extract")
def extract(
    quote_id: str = typer.Option(..., help="The id of the source quote."),
    quote: str = typer.Option(..., help="The quote text to extract from."),
    job_id: str = typer.Option(..., help="Job ID the candidates would become outcomes of."),
    job_name: str | None = typer.Option(None, help="Optional job name for the extractor."),
    stage_hint: str | None = typer.Option(None, help="Optional job-map stage hint."),
    json_output: bool = JSON_OPTION,
) -> None:
    """Propose outcomes from one quote. Proposes only; nothing is accepted."""
    args: dict[str, Any] = {"quote_id": quote_id, "quote": quote, "job_id": job_id}
    if job_name is not None:
        args["job_name"] = job_name
    if stage_hint is not None:
        args["stage_hint"] = stage_hint
    typer.echo(_render_candidate_list(run_tool("extract_candidates", args), as_json=json_output))


@candidates_app.command("list")
def list_candidates(
    quote_id: str | None = typer.Option(None, help="Only candidates from this quote."),
    job_id: str | None = typer.Option(None, help="Only candidates for this job."),
    status: str | None = typer.Option(
        None, help="Only candidates in this status (proposed|accepted|rejected|merged)."
    ),
    limit: int | None = typer.Option(None, help="Maximum number to return."),
    offset: int = typer.Option(0, help="Number to skip."),
    json_output: bool = JSON_OPTION,
) -> None:
    """List proposed outcomes."""
    args: dict[str, Any] = {"offset": offset}
    if quote_id is not None:
        args["quote_id"] = quote_id
    if job_id is not None:
        args["job_id"] = job_id
    if status is not None:
        args["status"] = status
    if limit is not None:
        args["limit"] = limit
    typer.echo(_render_candidate_list(run_tool("list_candidates", args), as_json=json_output))


@candidates_app.command("show")
def show(
    candidate_id: str = typer.Argument(..., help="Candidate ID"),
    json_output: bool = JSON_OPTION,
) -> None:
    """Show a single candidate."""
    typer.echo(
        _render_candidate(
            run_tool("get_candidate", {"candidate_id": candidate_id}), as_json=json_output
        )
    )


@candidates_app.command("accept")
def accept(
    candidate_id: str = typer.Argument(..., help="Candidate ID"),
    importance: float = typer.Option(..., min=1.0, max=10.0, help="Importance score (1-10)"),
    satisfaction: float = typer.Option(..., min=1.0, max=10.0, help="Satisfaction score (1-10)"),
    statement: str | None = typer.Option(None, help="An edited statement to accept instead."),
    step_id: str | None = typer.Option(None, help="Optional Step ID to attach the outcome to."),
    json_output: bool = JSON_OPTION,
) -> None:
    """Accept a candidate, creating exactly one Outcome."""
    args: dict[str, Any] = {
        "candidate_id": candidate_id,
        "importance": importance,
        "satisfaction": satisfaction,
    }
    if statement is not None:
        args["statement"] = statement
    if step_id is not None:
        args["step_id"] = step_id
    outcome = run_tool("accept_candidate", args)
    if json_output:
        typer.echo(json.dumps(outcome, indent=2))
    else:
        typer.echo(
            f"Outcome created: {outcome.get('id') if isinstance(outcome, dict) else outcome}"
        )


@candidates_app.command("reject")
def reject(
    candidate_id: str = typer.Argument(..., help="Candidate ID"),
    reason: str = typer.Option(..., help="Why the candidate is rejected (required)."),
    json_output: bool = JSON_OPTION,
) -> None:
    """Reject a candidate. The reason is required and kept."""
    candidate = run_tool("reject_candidate", {"candidate_id": candidate_id, "reason": reason})
    typer.echo(_render_candidate(candidate, as_json=json_output))


@candidates_app.command("merge")
def merge(
    candidate_id: str = typer.Argument(..., help="Candidate ID"),
    merged_into: str = typer.Option(..., help="The existing Outcome ID to fold into."),
    json_output: bool = JSON_OPTION,
) -> None:
    """Fold a candidate into an existing Outcome. Creates no outcome."""
    candidate = run_tool(
        "merge_candidate", {"candidate_id": candidate_id, "merged_into": merged_into}
    )
    typer.echo(_render_candidate(candidate, as_json=json_output))


__all__ = ["candidates_app"]
