"""The scoring pass: walk unscored outcomes at the keyboard (A9 · ALH-22).

``odi score`` shows one outcome at a time with its current score and the
customer's sentence in view, and takes a 1–10 importance, then a 1–10
satisfaction. Every write goes through the same ``update_outcome`` tool the API
uses, so a keypress and a click cannot diverge. ``u`` undoes the last write by
replaying the previous pair through that same tool, which is how a truly
unscored outcome (no prior pair, not a zero) is restored.
"""

from __future__ import annotations

import json
from typing import Any

import typer

from agentic_odi_cli import flags
from agentic_odi_cli.backend import BackendError, call_tool
from agentic_odi_cli.prompt import EndOfInput, read_line, warn
from agentic_odi_cli.render import render_score_prompt, render_score_summary

JSON_OPTION = typer.Option(False, "--json", help="Emit machine-readable JSON.")

_PROMPT = "importance 1-10, s=skip, u=undo, q=quit › "
_SAT_PROMPT = "satisfaction 1-10, s=skip, u=undo, q=quit › "


def _working_set(job: str | None) -> list[dict[str, Any]]:
    """Every outcome in scope, ranked the way the landscape shows them.

    With ``--job`` only that job's outcomes; otherwise every outcome across
    every job. The order comes from :func:`rank_outcomes` (highest opportunity
    first, unscored last) so the pass follows the same ranking the map and the
    landscape use rather than a second ordering.
    """
    if job is not None:
        if not isinstance(call_tool("get_job", {"job_id": job}), dict):
            raise BackendError(f"Job with ID {job} not found.")
        outcomes = call_tool("get_outcomes", {"job_id": job})
        return list(outcomes) if isinstance(outcomes, list) else []
    jobs = call_tool("get_jobs", {})
    collected: list[dict[str, Any]] = []
    for item in jobs if isinstance(jobs, list) else []:
        rows = call_tool("get_outcomes", {"job_id": item["id"]})
        if isinstance(rows, list):
            collected.extend(rows)
    return collected


def _ranked(outcomes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    from agentic_odi_core import Outcome
    from agentic_odi_core.repository import rank_outcomes

    models = [Outcome.model_validate(row) for row in outcomes]
    return [model.model_dump() for model in rank_outcomes(models)]


def _customer_sentence(outcome_id: str) -> str | None:
    """The verbatim quote behind an outcome, or ``None`` when none was captured."""
    evidence = call_tool("list_evidence", {"outcome_id": outcome_id})
    for item in evidence if isinstance(evidence, list) else []:
        content = str(item.get("content", "")).strip()
        if content:
            return content
    return None


def _parse_score(key: str) -> float:
    """A 1–10 score, or a refusal. Never invents a zero or a default."""
    value = float(key)
    if not (1.0 <= value <= 10.0):
        raise ValueError("must be between 1.0 and 10.0")
    return value


def _write(outcome_id: str, importance: float | None, satisfaction: float | None) -> str | None:
    """Write one outcome's pair through ``update_outcome``; return a refusal, else None."""
    try:
        call_tool(
            "update_outcome",
            {"outcome_id": outcome_id, "importance": importance, "satisfaction": satisfaction},
        )
    except BackendError as exc:
        return str(exc)
    return None


def _prompt_pair(quiet: bool) -> tuple[str, float | None, float | None]:
    """Read importance then satisfaction for one outcome.

    Returns ``("quit", None, None)``, ``("skip", None, None)``, ``("undo", None,
    None)``, or ``("scored", importance, satisfaction)``. A value outside 1–10
    is refused for this prompt only and re-prompted, so one bad entry cannot
    abort the pass.
    """
    importance: float | None = None
    for prompt, label in ((_PROMPT, "importance"), (_SAT_PROMPT, "satisfaction")):
        while True:
            key = read_line(prompt, quiet=quiet).strip().lower()
            if key in {"q", "quit"}:
                return "quit", None, None
            if key in {"s", "skip", ""}:
                return "skip", None, None
            if key in {"u", "undo"}:
                return "undo", None, None
            try:
                value = _parse_score(key)
            except ValueError:
                warn(f"Error: {label} must be a number between 1.0 and 10.0.", quiet=quiet)
                continue
            if label == "importance":
                importance = value
            else:
                return "scored", importance, value
            break
    return "skip", None, None


def score_pass(
    job: str | None = typer.Option(None, "--job", help="Only outcomes of this Job"),
    unscored: bool = typer.Option(False, "--unscored", help="Only outcomes with no score yet"),
    limit: int | None = typer.Option(None, "--limit", help="Score at most this many outcomes"),
    json_output: bool = JSON_OPTION,
) -> None:
    """Score many outcomes in one keyboard pass.

    Keys: a number ``1-10`` for importance, then another for satisfaction;
    ``s`` skip, ``u`` undo the last write, ``q`` quit. Skip, quit, and
    end-of-input make no further writes. Progress shows ``3/20`` and a summary
    closes the pass. Every write goes through the same ``update_outcome`` the
    API uses, and a refused write is reported, never counted as a success.
    """
    try:
        outcomes = _working_set(job)
    except BackendError as exc:
        typer.secho(f"Error: {exc}", fg="red", err=True)
        raise typer.Exit(code=1) from exc

    if unscored:
        outcomes = [
            row
            for row in outcomes
            if row.get("importance") is None or row.get("satisfaction") is None
        ]
    outcomes = _ranked(outcomes)
    if limit is not None:
        outcomes = outcomes[:limit]

    if not outcomes:
        message = "Nothing to score: no outcomes match."
        if json_output:
            typer.echo(json.dumps(_empty_summary(message), indent=2, ensure_ascii=False))
        else:
            typer.echo(message)
        return

    total = len(outcomes)
    quiet = json_output
    summary: dict[str, Any] = {
        "scored": 0,
        "skipped": 0,
        "failed": 0,
        "undone": 0,
        "total": total,
        "results": [],
    }
    applied: list[tuple[int, str, float | None, float | None]] = []
    index = 0
    while index < total:
        outcome = outcomes[index]
        outcome_id = outcome["id"]
        if not quiet:
            typer.echo(
                render_score_prompt(index + 1, total, outcome, _customer_sentence(outcome_id)),
                err=True,
            )
        try:
            action, importance, satisfaction = _prompt_pair(quiet)
        except EndOfInput:
            summary["skipped"] += total - index
            break
        if action == "quit":
            summary["skipped"] += total - index
            break
        if action == "skip":
            summary["skipped"] += 1
            summary["results"].append({"outcome_id": outcome_id, "action": "skipped"})
            index += 1
            continue
        if action == "undo":
            if not applied:
                warn("Error: nothing to undo.", quiet=quiet)
                continue
            back_index, back_id, prev_importance, prev_satisfaction = applied.pop()
            refusal = _write(back_id, prev_importance, prev_satisfaction)
            if refusal is not None:
                warn(f"Error: {refusal}", quiet=quiet)
                applied.append((back_index, back_id, prev_importance, prev_satisfaction))
                continue
            summary["undone"] += 1
            summary["results"].append({"outcome_id": back_id, "action": "undone"})
            index = back_index
            continue
        refusal = _write(outcome_id, importance, satisfaction)
        if refusal is not None:
            summary["failed"] += 1
            summary["results"].append(
                {"outcome_id": outcome_id, "action": "failed", "error": refusal}
            )
            warn(f"Error: {refusal}", quiet=quiet)
            continue
        applied.append((index, outcome_id, outcome.get("importance"), outcome.get("satisfaction")))
        summary["scored"] += 1
        summary["results"].append(
            {
                "outcome_id": outcome_id,
                "action": "scored",
                "importance": importance,
                "satisfaction": satisfaction,
            }
        )
        index += 1

    _emit_summary(summary, as_json=json_output)


def _empty_summary(message: str) -> dict[str, Any]:
    return {
        "scored": 0,
        "skipped": 0,
        "failed": 0,
        "undone": 0,
        "total": 0,
        "results": [],
        "message": message,
    }


def _emit_summary(summary: dict[str, Any], *, as_json: bool) -> None:
    if as_json:
        typer.echo(json.dumps(summary, indent=2, ensure_ascii=False))
        return
    typer.echo(render_score_summary(summary))
    if flags.is_enabled("developer_mode"):
        for row in summary["results"]:
            typer.echo(f"  {row['outcome_id']}  {row['action']}", err=True)
