"""Interview CLI subcommands.

An interview records who took part, when, and the job it informs; its quotes
are the verbatim sentences the research is built from. Every command goes
through :func:`cli.backend.run_tool`, so it works against the local SQLite
store or a remote MCP server without a second code path.
"""

from __future__ import annotations

import json
import sys
from typing import Any

import typer

from agentic_odi_cli.backend import BackendError, call_tool, run_tool
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
    render_review_prompt,
    render_review_summary,
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


class _EndOfInput(Exception):
    """Raised when the review loop reaches end-of-input instead of a key."""


def _read_line(label: str, *, quiet: bool = False) -> str:
    """Prompt with ``label`` and read one line, or raise on end-of-input.

    ``quiet`` suppresses the prompt (``--json`` mode emits only the JSON summary
    on stdout, so the prompts would corrupt it). A blank line is an empty
    string; end-of-input is distinct so the loop can treat it as a quit rather
    than a skip.
    """
    if not quiet:
        typer.echo(label, nl=False, err=True)
    raw = sys.stdin.readline()
    if raw == "":
        raise _EndOfInput
    return raw.rstrip("\n")


def _read_score(label: str, provided: float | None, *, quiet: bool = False) -> float:
    """Read a 1–10 score, or return the value the caller already supplied."""
    if provided is not None:
        return provided
    return float(_read_line(f"{label} (1.0-10.0): ", quiet=quiet).strip())


def _proposed_candidates(interview_id: str) -> list[dict[str, Any]]:
    candidates = call_tool("list_candidates", {"interview_id": interview_id, "status": "proposed"})
    return candidates if isinstance(candidates, list) else []


def _quote_index(interview_id: str) -> dict[str, dict[str, Any]]:
    quotes = call_tool("list_quotes", {"interview_id": interview_id})
    if not isinstance(quotes, list):
        return {}
    return {quote["id"]: quote for quote in quotes}


def _accept_one(
    candidate_id: str,
    *,
    importance: float,
    satisfaction: float,
    statement: str | None = None,
) -> str | None:
    """Accept one candidate; return the server's reason on refusal, else None."""
    args: dict[str, Any] = {
        "candidate_id": candidate_id,
        "importance": importance,
        "satisfaction": satisfaction,
    }
    if statement is not None:
        args["statement"] = statement
    try:
        call_tool("accept_candidate", args)
    except BackendError as exc:
        return str(exc)
    return None


@interviews_app.command("review")
def review(
    interview_id: str = typer.Argument(..., help="Interview ID to review"),
    yes: bool = typer.Option(
        False,
        "--yes",
        "-y",
        help="Accept every proposed candidate without prompting (for scripts)",
    ),
    importance: float | None = typer.Option(
        None, help="Importance for --yes acceptance, 1.0 to 10.0"
    ),
    satisfaction: float | None = typer.Option(
        None, help="Satisfaction for --yes acceptance, 1.0 to 10.0"
    ),
    json_output: bool = JSON_OPTION,
) -> None:
    """Work an interview's proposed candidates at the keyboard.

    Keys: ``a`` accept, ``e`` edit-and-accept, ``m`` merge into an accepted
    outcome, ``r`` reject with a reason, ``s`` skip, ``q`` quit. Each prompt
    shows the statement beside the quote it came from. Every decision goes
    through the same service the API uses, so a keypress and a click cannot
    diverge. Skip, quit, and end-of-input preserve every remaining candidate;
    nothing is accepted on ``q``.

    ``--yes`` is explicit human-issued batch consent: it accepts only the
    candidates still ``proposed``, needs ``--importance`` and ``--satisfaction``
    (scores are never invented), and reports the success and failure counts.
    """
    if yes and (importance is None or satisfaction is None):
        typer.secho(
            "Error: --yes needs --importance and --satisfaction; scores are never invented.",
            fg="red",
            err=True,
        )
        raise typer.Exit(code=2)

    proposed = _proposed_candidates(interview_id)
    if not proposed:
        message = f"Nothing to review: no proposed candidates for interview {interview_id}."
        if json_output:
            typer.echo(
                json.dumps(
                    {
                        "interview_id": interview_id,
                        "accepted": 0,
                        "merged": 0,
                        "rejected": 0,
                        "skipped": 0,
                        "failed": 0,
                        "results": [],
                        "message": message,
                    },
                    indent=2,
                    ensure_ascii=False,
                )
            )
        else:
            typer.echo(message)
        return

    quotes = _quote_index(interview_id)
    summary: dict[str, Any] = {
        "interview_id": interview_id,
        "accepted": 0,
        "merged": 0,
        "rejected": 0,
        "skipped": 0,
        "failed": 0,
        "results": [],
    }

    if yes:
        for candidate in proposed:
            candidate_id = candidate["id"]
            reason = _accept_one(
                candidate_id,
                importance=importance,  # type: ignore[arg-type]
                satisfaction=satisfaction,  # type: ignore[arg-type]
            )
            if reason is None:
                summary["accepted"] += 1
                summary["results"].append({"id": candidate_id, "action": "accepted"})
            else:
                summary["failed"] += 1
                summary["results"].append(
                    {"id": candidate_id, "action": "failed", "reason": reason}
                )
        _emit_review(summary, as_json=json_output)
        return

    total = len(proposed)
    quiet = json_output
    for position, candidate in enumerate(proposed, start=1):
        candidate_id = candidate["id"]
        quote = quotes.get(candidate.get("quote_id", ""))
        if not quiet:
            typer.echo(render_review_prompt(position, total, candidate, quote), err=True)
        try:
            action = _review_one(
                candidate,
                importance=importance,
                satisfaction=satisfaction,
                quiet=quiet,
            )
        except _EndOfInput:
            summary["skipped"] += total - position + 1
            break
        if action == "quit":
            summary["skipped"] += total - position + 1
            break
        if action == "accepted":
            summary["accepted"] += 1
        elif action == "merged":
            summary["merged"] += 1
        elif action == "rejected":
            summary["rejected"] += 1
        else:
            summary["skipped"] += 1
        summary["results"].append({"id": candidate_id, "action": action})

    _emit_review(summary, as_json=json_output)


def _warn(message: str, *, quiet: bool) -> None:
    """Show a refusal to the person, unless ``--json`` must keep stdout clean."""
    if not quiet:
        typer.secho(message, fg="red", err=True)


def _review_one(
    candidate: dict[str, Any],
    *,
    importance: float | None,
    satisfaction: float | None,
    quiet: bool = False,
) -> str:
    """Prompt for one candidate's decision until it is made or the person quits.

    A refused decision shows the server's reason and re-prompts, so a blank
    reject reason or an invalid edit stays for correction rather than silently
    dropping the candidate.
    """
    candidate_id = candidate["id"]
    while True:
        key = (
            _read_line("a=accept  e=edit  m=merge  r=reject  s=skip  q=quit › ", quiet=quiet)
            .strip()
            .lower()
        )
        if key == "":
            key = "s"
        if key in {"q", "quit"}:
            return "quit"
        if key in {"s", "skip"}:
            return "skipped"
        if key in {"a", "accept"}:
            if _do_accept(candidate_id, importance, satisfaction, statement=None, quiet=quiet):
                return "accepted"
            continue
        if key in {"e", "edit"}:
            edited = _read_line("new statement: ", quiet=quiet).strip()
            if not edited:
                _warn("Error: a statement must not be blank.", quiet=quiet)
                continue
            if _do_accept(candidate_id, importance, satisfaction, statement=edited, quiet=quiet):
                return "accepted"
            continue
        if key in {"r", "reject"}:
            reason = _read_line("reason: ", quiet=quiet).strip()
            try:
                call_tool("reject_candidate", {"candidate_id": candidate_id, "reason": reason})
            except BackendError as exc:
                _warn(f"Error: {exc}", quiet=quiet)
                continue
            return "rejected"
        if key in {"m", "merge"}:
            target = _read_line("merge into outcome id: ", quiet=quiet).strip()
            if not target:
                _warn("Error: a merge needs an explicit target outcome.", quiet=quiet)
                continue
            try:
                call_tool("merge_candidates", {"target_id": target, "merged_ids": [candidate_id]})
            except BackendError as exc:
                _warn(f"Error: {exc}", quiet=quiet)
                continue
            return "merged"
        _warn(f"Unknown key: {key!r}. Use a, e, m, r, s, or q.", quiet=quiet)


def _do_accept(
    candidate_id: str,
    importance: float | None,
    satisfaction: float | None,
    *,
    statement: str | None,
    quiet: bool = False,
) -> bool:
    """Accept one candidate, showing the server's reason and returning success."""
    try:
        imp = _read_score("importance", importance, quiet=quiet)
        sat = _read_score("satisfaction", satisfaction, quiet=quiet)
    except ValueError:
        _warn("Error: scores must be numbers between 1.0 and 10.0.", quiet=quiet)
        return False
    reason = _accept_one(candidate_id, importance=imp, satisfaction=sat, statement=statement)
    if reason is not None:
        _warn(f"Error: {reason}", quiet=quiet)
        return False
    return True


def _emit_review(summary: dict[str, Any], *, as_json: bool) -> None:
    if as_json:
        typer.echo(json.dumps(summary, indent=2, ensure_ascii=False))
    else:
        typer.echo(render_review_summary(summary))
