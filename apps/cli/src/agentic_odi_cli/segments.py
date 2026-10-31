"""Segments and strategy from the CLI (D1–D4, ALH-40…ALH-43).

``odi segments add|list|show|delete|suggest|accept|profile`` and
``odi segments strategy`` are argument parsing and transport only: the service
owns membership validation, the deterministic candidate derivation, the profile
counts, and the strategy guardrails, so the CLI and the Studio cannot disagree
about what a valid segment or strategy is.

Nothing here invents a number. A profile with no measured outcome prints
``not measured`` for the ratio, never ``0``; a segment with no members prints a
reason rather than an empty table that reads like a result.
"""

from __future__ import annotations

import json
from typing import Any

import typer

from agentic_odi_cli.backend import run_tool

segments_app = typer.Typer(help="Define segments and record the strategy per segment.")

JSON_OPTION = typer.Option(False, "--json", help="Emit machine-readable JSON.")
JOB_ID_OPTION = typer.Option(..., "--job-id", help="Job the segment belongs to.")
SEGMENT_ID_OPTION = typer.Option(..., "--segment-id", help="Segment to act on.")
NAME_OPTION = typer.Option(..., "--name", help="Human-readable segment name.")
CRITERION_OPTION = typer.Option(..., "--criterion", help="Why the group is coherent.")
OUTCOME_ID_OPTION = typer.Option(
    ..., "--outcome-id", help="A member outcome. Repeat for each member."
)
NOTES_OPTION = typer.Option(None, "--notes", help="Free-form note.")
FINGERPRINT_OPTION = typer.Option(
    ..., "--fingerprint", help="Fingerprint of the suggested candidate to accept."
)
KIND_OPTION = typer.Option(..., "--kind", help="differentiated, disruptive, or new_market.")
RATIONALE_OPTION = typer.Option(..., "--rationale", help="Why this strategy.")
EFFECT_OPTION = typer.Option(..., "--expected-effect", help="What the strategy should change.")
CHOSEN_AT_OPTION = typer.Option(None, "--chosen-at", help="ISO-8601 timestamp of the choice.")


@segments_app.command("add")
def add(
    job_id: str = JOB_ID_OPTION,
    name: str = NAME_OPTION,
    criterion: str = CRITERION_OPTION,
    outcome_id: list[str] = OUTCOME_ID_OPTION,
    notes: str | None = NOTES_OPTION,
    json_output: bool = JSON_OPTION,
) -> None:
    """Create a segment from its member outcomes."""
    args: dict[str, Any] = {
        "job_id": job_id,
        "name": name,
        "criterion": criterion,
        "outcome_ids": list(outcome_id),
    }
    if notes is not None:
        args["notes"] = notes
    segment = run_tool("add_segment", args)
    if json_output:
        typer.echo(json.dumps(segment, indent=2, ensure_ascii=False))
        return
    typer.echo(f"Segment created: {segment['id']}")
    typer.echo(f"  {segment['name']} — {len(segment['outcome_ids'])} member(s)")


@segments_app.command("list")
def list_segments(
    job_id: str | None = typer.Option(None, "--job-id", help="Only segments for this job."),
    json_output: bool = JSON_OPTION,
) -> None:
    """List segments, optionally filtered to one job."""
    args: dict[str, Any] = {}
    if job_id is not None:
        args["job_id"] = job_id
    segments = run_tool("list_segments", args)
    if json_output:
        typer.echo(json.dumps(segments, indent=2, ensure_ascii=False))
        return
    if not segments:
        typer.echo("No segments recorded yet.")
        return
    for segment in segments:
        typer.echo(
            f"{segment['id']}  {segment['origin']:<10}  "
            f"{len(segment['outcome_ids'])} member(s)  {segment['name']}"
        )


@segments_app.command("show")
def show(
    segment_id: str = SEGMENT_ID_OPTION,
    json_output: bool = JSON_OPTION,
) -> None:
    """Show one segment."""
    segment = run_tool("get_segment", {"segment_id": segment_id})
    if json_output:
        typer.echo(json.dumps(segment, indent=2, ensure_ascii=False))
        return
    typer.echo(f"Segment {segment['id']} ({segment['origin']})")
    typer.echo(f"  Name: {segment['name']}")
    typer.echo(f"  Criterion: {segment['criterion']}")
    typer.echo(f"  Members: {', '.join(segment['outcome_ids'])}")
    if segment.get("notes"):
        typer.echo(f"  Notes: {segment['notes']}")


@segments_app.command("delete")
def delete(
    segment_id: str = SEGMENT_ID_OPTION,
    json_output: bool = JSON_OPTION,
) -> None:
    """Delete a segment. Outcomes are never touched."""
    result = run_tool("delete_segment", {"segment_id": segment_id})
    if json_output:
        typer.echo(json.dumps(result, indent=2, ensure_ascii=False))
        return
    typer.echo(f"Segment deleted: {result['deleted']}")


@segments_app.command("suggest")
def suggest(
    job_id: str = JOB_ID_OPTION,
    json_output: bool = JSON_OPTION,
) -> None:
    """Propose segment candidates from the scores. Writes nothing."""
    result = run_tool("suggest_segments", {"job_id": job_id})
    if json_output:
        typer.echo(json.dumps(result, indent=2, ensure_ascii=False))
        return
    candidates = result["candidates"]
    if not candidates:
        typer.echo(result.get("reason") or "No candidates.")
        return
    for candidate in candidates:
        typer.echo(
            f"{candidate['fingerprint'][:12]}  {candidate['name']}  "
            f"({candidate['evidence_count']} outcome(s))"
        )
        typer.echo(f"    {candidate['rationale']}")


@segments_app.command("accept")
def accept(
    job_id: str = JOB_ID_OPTION,
    fingerprint: str = FINGERPRINT_OPTION,
    name: str | None = typer.Option(None, "--name", help="Override the candidate's name."),
    criterion: str | None = typer.Option(
        None, "--criterion", help="Override the candidate's criterion."
    ),
    json_output: bool = JSON_OPTION,
) -> None:
    """Accept a suggested candidate into a segment."""
    args: dict[str, Any] = {"job_id": job_id, "fingerprint": fingerprint}
    if name is not None:
        args["name"] = name
    if criterion is not None:
        args["criterion"] = criterion
    segment = run_tool("accept_segment_candidate", args)
    if json_output:
        typer.echo(json.dumps(segment, indent=2, ensure_ascii=False))
        return
    typer.echo(f"Segment accepted: {segment['id']} — {segment['name']}")


@segments_app.command("profile")
def profile(
    segment_id: str = SEGMENT_ID_OPTION,
    json_output: bool = JSON_OPTION,
) -> None:
    """Read a segment's servability: underserved vs overserved, kept separate."""
    result = run_tool("get_segment_profile", {"segment_id": segment_id})
    if json_output:
        typer.echo(json.dumps(result, indent=2, ensure_ascii=False))
        return
    typer.echo(f"Segment {result['segment_id']} — {result['segment_name']}")
    typer.echo(
        f"  Members: {result['total_members']}  "
        f"measured: {result['measured_count']}  "
        f"unscored: {result['unscored_count']}  "
        f"missing: {result['missing_count']}"
    )
    ratio = result["measured_ratio"]
    typer.echo(f"  Measured ratio: {'not measured' if ratio is None else f'{ratio:.2f}'}")
    typer.echo(
        f"  Underserved: {result['underserved_count']}  "
        f"appropriate: {result['appropriate_count']}  "
        f"overserved: {result['overserved_count']}"
    )
    if result["top_underserved"]:
        typer.echo("  Top underserved:")
        for entry in result["top_underserved"]:
            typer.echo(f"    {entry['outcome_id']}  {entry['score']:g}  {entry['statement']}")
    if result["top_overserved"]:
        typer.echo("  Top overserved:")
        for entry in result["top_overserved"]:
            typer.echo(f"    {entry['outcome_id']}  {entry['score']:g}  {entry['statement']}")
    for gap in result["gaps"]:
        typer.echo(f"  Note: {gap}")


@segments_app.command("strategy")
def strategy(
    segment_id: str = SEGMENT_ID_OPTION,
    kind: str = KIND_OPTION,
    rationale: str = RATIONALE_OPTION,
    expected_effect: str = EFFECT_OPTION,
    chosen_at: str | None = CHOSEN_AT_OPTION,
    json_output: bool = JSON_OPTION,
) -> None:
    """Record a strategy for a segment, refusing one its data does not support."""
    args: dict[str, Any] = {
        "segment_id": segment_id,
        "kind": kind,
        "rationale": rationale,
        "expected_effect": expected_effect,
    }
    if chosen_at is not None:
        args["chosen_at"] = chosen_at
    result = run_tool("choose_strategy", args)
    if json_output:
        typer.echo(json.dumps(result, indent=2, ensure_ascii=False))
        return
    typer.echo(f"Strategy recorded: {result['id']} ({result['kind']})")
    typer.echo(f"  Why: {result['rationale']}")
    typer.echo(f"  Expected effect: {result['expected_effect']}")


@segments_app.command("strategies")
def strategies(
    segment_id: str | None = typer.Option(None, "--segment-id", help="Only for this segment."),
    json_output: bool = JSON_OPTION,
) -> None:
    """List recorded strategies, optionally filtered to one segment."""
    args: dict[str, Any] = {}
    if segment_id is not None:
        args["segment_id"] = segment_id
    results = run_tool("list_strategies", args)
    if json_output:
        typer.echo(json.dumps(results, indent=2, ensure_ascii=False))
        return
    if not results:
        typer.echo("No strategies recorded yet.")
        return
    for result in results:
        typer.echo(f"{result['id']}  {result['kind']:<14}  {result['rationale']}")
