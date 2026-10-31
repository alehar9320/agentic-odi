"""Interview CLI subcommands.

An interview records who took part, when, and the job it informs; its quotes
are the verbatim sentences the research is built from. Every command goes
through :func:`cli.backend.run_tool`, so it works against the local SQLite
store or a remote MCP server without a second code path.
"""

from __future__ import annotations

import json
from typing import Any

import typer

from agentic_odi_cli.backend import run_tool
from agentic_odi_cli.render import (
    render_candidate,
    render_candidate_acceptance,
    render_candidate_list,
    render_candidate_merge,
    render_deleted,
    render_duplicate_groups,
    render_interview,
    render_interview_list,
    render_quote_list,
    render_saved,
)

interviews_app = typer.Typer(help="Manage research interviews and their quotes.")

JSON_OPTION = typer.Option(False, "--json", help="Emit machine-readable JSON.")


@interviews_app.command("import")
def import_transcript(
    path: str = typer.Argument(..., help="Transcript file, or - to read stdin"),
    title: str = typer.Option(..., help="Short human-readable title for the interview"),
    participant: str = typer.Option(
        ..., "--participant", help="Free-text participant label (never a real name or email)"
    ),
    job_id: str | None = typer.Option(None, help="The Job this interview informs"),
    role: str | None = typer.Option(None, "--role", help="The participant's role"),
    conducted_at: str | None = typer.Option(None, help="ISO-8601 date/time conducted"),
    fmt: str | None = typer.Option(
        None,
        "--format",
        help="Transcript format: auto, md, txt, vtt, or srt (default: auto)",
    ),
    json_output: bool = JSON_OPTION,
) -> None:
    """Import a transcript from a file (or stdin) as one interview."""
    import sys
    from pathlib import Path

    display = "stdin" if path == "-" else path
    if path == "-":
        text = sys.stdin.read()
        filename = None
    else:
        source = Path(path)
        if not source.is_file():
            typer.echo(f"Transcript file not found: {path}", err=True)
            raise typer.Exit(code=1)
        text = source.read_text(encoding="utf-8")
        filename = source.name

    resolved = None if fmt in (None, "auto") else fmt
    args: dict[str, Any] = {
        "text": text,
        "title": title,
        "participant_label": participant,
        "display_name": display,
    }
    if filename is not None:
        args["filename"] = filename
    if resolved is not None:
        args["format"] = resolved
    if job_id is not None:
        args["job_id"] = job_id
    if role is not None:
        args["participant_role"] = role
    if conducted_at is not None:
        args["conducted_at"] = conducted_at

    result = run_tool("import_transcript", args)

    if json_output:
        typer.echo(json.dumps(result, indent=2, ensure_ascii=False))
        return
    typer.echo(
        f"Imported interview {result['interview']['id']} with {result['quote_count']} quotes."
    )


@interviews_app.command("add")
def add(
    title: str = typer.Option(..., help="Short human-readable title for the interview"),
    participant: str = typer.Option(
        ..., "--participant", help="Free-text participant label (never a real name or email)"
    ),
    job_id: str | None = typer.Option(None, help="The Job this interview informs"),
    role: str | None = typer.Option(None, "--role", help="The participant's role"),
    conducted_at: str | None = typer.Option(None, help="ISO-8601 date/time conducted"),
    notes: str | None = typer.Option(None, help="Researcher notes"),
    json_output: bool = JSON_OPTION,
) -> None:
    """Record a research interview."""
    args: dict[str, Any] = {"title": title, "participant_label": participant}
    if job_id is not None:
        args["job_id"] = job_id
    if role is not None:
        args["participant_role"] = role
    if conducted_at is not None:
        args["conducted_at"] = conducted_at
    if notes is not None:
        args["notes"] = notes
    typer.echo(
        render_saved(
            "created", run_tool("add_interview", args), as_json=json_output, noun="Interview"
        )
    )


@interviews_app.command("list")
def list_interviews(
    job_id: str | None = typer.Option(None, help="Only interviews for this job"),
    json_output: bool = JSON_OPTION,
) -> None:
    """List interviews."""
    args: dict[str, Any] = {}
    if job_id is not None:
        args["job_id"] = job_id
    typer.echo(render_interview_list(run_tool("list_interviews", args), as_json=json_output))


@interviews_app.command("get")
def get(
    interview_id: str = typer.Argument(..., help="Interview ID"),
    json_output: bool = JSON_OPTION,
) -> None:
    """Get an interview by ID."""
    typer.echo(
        render_interview(
            run_tool("get_interview", {"interview_id": interview_id}), as_json=json_output
        )
    )


@interviews_app.command("quotes")
def quotes(
    interview_id: str = typer.Argument(..., help="Interview ID"),
    json_output: bool = JSON_OPTION,
) -> None:
    """List an interview's quotes in ordinal order."""
    typer.echo(
        render_quote_list(
            run_tool("list_quotes", {"interview_id": interview_id}), as_json=json_output
        )
    )


@interviews_app.command("delete")
def delete(
    interview_id: str = typer.Argument(..., help="Interview ID"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation"),
    json_output: bool = JSON_OPTION,
) -> None:
    """Delete an interview and the quotes it recorded."""
    if not yes:
        confirm = typer.confirm(f"Delete interview {interview_id} and its quotes?")
        if not confirm:
            raise typer.Exit()
    typer.echo(
        render_deleted(
            run_tool("delete_interview", {"interview_id": interview_id}),
            as_json=json_output,
            noun="interview",
        )
    )


@interviews_app.command("extract")
def extract(
    quote_id: str = typer.Argument(..., help="Quote ID to propose candidates from"),
    stage_hint: str | None = typer.Option(None, help="Optional job-stage hint for the extractor"),
    json_output: bool = JSON_OPTION,
) -> None:
    """Propose outcome candidates from one quote.

    Valid proposals are stored ``proposed``; a proposal that fails the ODI
    statement check is stored ``rejected`` with the validator's reason. No
    Outcome is created — a person accepts a candidate later.
    """
    args: dict[str, Any] = {"quote_id": quote_id}
    if stage_hint is not None:
        args["stage_hint"] = stage_hint
    candidates = run_tool("extract_candidates", args)
    typer.echo(render_candidate_list(candidates, as_json=json_output))


candidates_app = typer.Typer(help="Review outcome candidates proposed from quotes.")


@candidates_app.command("list")
def list_candidates(
    interview_id: str | None = typer.Option(None, help="Only candidates for this interview"),
    status: str | None = typer.Option(None, help="Only candidates with this status"),
    limit: int | None = typer.Option(None, help="Maximum candidates to return"),
    offset: int = typer.Option(0, help="Skip this many candidates first"),
    json_output: bool = JSON_OPTION,
) -> None:
    """List outcome candidates."""
    args: dict[str, Any] = {"offset": offset}
    if interview_id is not None:
        args["interview_id"] = interview_id
    if status is not None:
        args["status"] = status
    if limit is not None:
        args["limit"] = limit
    typer.echo(render_candidate_list(run_tool("list_candidates", args), as_json=json_output))


@candidates_app.command("get")
def get_candidate(
    candidate_id: str = typer.Argument(..., help="Outcome candidate ID"),
    json_output: bool = JSON_OPTION,
) -> None:
    """Get an outcome candidate by ID."""
    typer.echo(
        render_candidate(
            run_tool("get_candidate", {"candidate_id": candidate_id}), as_json=json_output
        )
    )


@candidates_app.command("delete")
def delete_candidate(
    candidate_id: str = typer.Argument(..., help="Outcome candidate ID"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation"),
    json_output: bool = JSON_OPTION,
) -> None:
    """Delete an outcome candidate."""
    if not yes:
        confirm = typer.confirm(f"Delete outcome candidate {candidate_id}?")
        if not confirm:
            raise typer.Exit()
    typer.echo(
        render_deleted(
            run_tool("delete_candidate", {"candidate_id": candidate_id}),
            as_json=json_output,
            noun="outcome candidate",
        )
    )


@candidates_app.command("accept")
def accept_candidate(
    candidate_id: str = typer.Argument(..., help="Outcome candidate ID"),
    importance: float = typer.Option(..., help="Importance score, 1.0 to 10.0"),
    satisfaction: float = typer.Option(..., help="Current satisfaction, 1.0 to 10.0"),
    statement: str | None = typer.Option(None, help="Edit the statement before accepting"),
    step_id: str | None = typer.Option(None, help="Job-map Step the new outcome belongs to"),
    json_output: bool = JSON_OPTION,
) -> None:
    """Accept a candidate into exactly one outcome, with its quote as evidence.

    The statement is validated before anything is written; accepting twice
    returns the first outcome, so a retry never duplicates it.
    """
    args: dict[str, Any] = {
        "candidate_id": candidate_id,
        "importance": importance,
        "satisfaction": satisfaction,
    }
    if statement is not None:
        args["statement"] = statement
    if step_id is not None:
        args["step_id"] = step_id
    typer.echo(render_candidate_acceptance(run_tool("accept_candidate", args), as_json=json_output))


@candidates_app.command("reject")
def reject_candidate(
    candidate_id: str = typer.Argument(..., help="Outcome candidate ID"),
    reason: str = typer.Option(..., help="Why the candidate is rejected (required)"),
    json_output: bool = JSON_OPTION,
) -> None:
    """Reject a candidate, keeping it and the reason beside its quote."""
    typer.echo(
        render_candidate(
            run_tool("reject_candidate", {"candidate_id": candidate_id, "reason": reason}),
            as_json=json_output,
        )
    )


@candidates_app.command("duplicates")
def duplicates(
    interview_id: str | None = typer.Option(None, help="Only candidates for this interview"),
    threshold: float | None = typer.Option(
        None, help="Similarity threshold, 0 to 1 (default: 0.82)"
    ),
    json_output: bool = JSON_OPTION,
) -> None:
    """Suggest groups of candidates that look like the same need. Read-only.

    Nothing is written and nothing is merged: a person chooses which candidate
    becomes the outcome target, then merges the rest into it.
    """
    args: dict[str, Any] = {}
    if interview_id is not None:
        args["interview_id"] = interview_id
    if threshold is not None:
        args["threshold"] = threshold
    typer.echo(
        render_duplicate_groups(run_tool("suggest_duplicate_candidates", args), as_json=json_output)
    )


@candidates_app.command("merge")
def merge_candidates(
    target_id: str = typer.Argument(..., help="Outcome ID to merge evidence into"),
    merged_ids: list[str] = typer.Argument(  # noqa: B008
        ..., help="Proposed candidate IDs to absorb"
    ),
    json_output: bool = JSON_OPTION,
) -> None:
    """Merge proposed candidates' evidence into one accepted outcome.

    The target is an accepted outcome; each source candidate's verbatim quote is
    added as evidence on it and the candidate is marked ``merged``. No second
    outcome is created and the sources and quotes are retained.
    """
    typer.echo(
        render_candidate_merge(
            run_tool("merge_candidates", {"target_id": target_id, "merged_ids": merged_ids}),
            as_json=json_output,
        )
    )
