"""Record a decision from the CLI (C6.2, ALH-158).

``odi decide`` is argument parsing and transport only: it shapes the flags into
the ``record_decision`` tool call and prints what the service returns. The
service owns validation and supersession, so the CLI and the Studio API cannot
disagree about what a valid decision is.

Rejection reasons are repeated ``--reject OUTCOME_ID=REASON`` flags rather than
a comma-separated string, so an outcome id and a reason that contain punctuation
cannot be confused for each other.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

import typer

from agentic_odi_cli.backend import run_tool

decide_app = typer.Typer(help="Record a decision with its rejected options.")

JSON_OPTION = typer.Option(False, "--json", help="Emit machine-readable JSON.")
JOB_ID_OPTION = typer.Option(..., "--job-id", help="Job the decision belongs to")
CHOOSE_OPTION = typer.Option(..., "--choose", help="Outcome ID to choose (repeatable)")
RATIONALE_OPTION = typer.Option(..., "--rationale", help="Why this choice was made")
DECIDED_BY_OPTION = typer.Option(..., "--decided-by", help="Who recorded the decision")
REJECT_OPTION = typer.Option(
    None, "--reject", help="Rejected option as OUTCOME_ID=REASON (repeatable)"
)
CONFIDENCE_OPTION = typer.Option("medium", "--confidence", help="low, medium, or high")
DECIDED_AT_OPTION = typer.Option(
    None, "--decided-at", help="ISO-8601 timestamp. Defaults to now in UTC."
)
SUPERSEDES_OPTION = typer.Option(None, "--supersedes", help="Decision ID this one replaces")
DECISION_ID_OPTION = typer.Option(..., "--decision-id", help="Decision to assemble a memo for")


def parse_rejection(raw: str) -> dict[str, str]:
    """Split ``OUTCOME_ID=REASON`` into its parts.

    A missing separator or an empty outcome id is a usage error, not a decision
    with a silent empty reason.
    """
    outcome_id, separator, reason = raw.partition("=")
    outcome_id = outcome_id.strip()
    if not separator or not outcome_id:
        raise ValueError(f"expected OUTCOME_ID=REASON, got {raw!r}")
    return {"outcome_id": outcome_id, "reason": reason.strip()}


@decide_app.command("record")
def record(
    job_id: str = JOB_ID_OPTION,
    choose: list[str] = CHOOSE_OPTION,
    rationale: str = RATIONALE_OPTION,
    decided_by: str = DECIDED_BY_OPTION,
    reject: list[str] = REJECT_OPTION,
    confidence: str = CONFIDENCE_OPTION,
    decided_at: str | None = DECIDED_AT_OPTION,
    supersedes: str | None = SUPERSEDES_OPTION,
    json_output: bool = JSON_OPTION,
) -> None:
    """Record a decision, naming the options it rejected and why."""
    try:
        rejected = [parse_rejection(item) for item in reject or []]
    except ValueError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    args: dict[str, Any] = {
        "job_id": job_id,
        "chosen_outcome_ids": list(choose),
        "rationale": rationale,
        "decided_by": decided_by,
        "decided_at": decided_at or datetime.now(timezone.utc).isoformat(),
        "confidence": confidence,
    }
    if rejected:
        args["rejected"] = rejected
    if supersedes is not None:
        args["supersedes"] = supersedes

    decision = run_tool("record_decision", args)
    if json_output:
        typer.echo(json.dumps(decision, indent=2, ensure_ascii=False))
        return
    typer.echo(f"Decision recorded: {decision.get('id')}")
    chosen = decision.get("chosen_outcome_ids") or []
    typer.echo(f"  Chose: {', '.join(chosen)}")
    if decision.get("superseded_by"):
        typer.echo(f"  This decision was already superseded by {decision['superseded_by']}")
    predecessor = supersedes
    if predecessor:
        typer.echo(f"  Supersedes: {predecessor}")


@decide_app.command("memo")
def memo(
    decision_id: str = DECISION_ID_OPTION,
    json_output: bool = JSON_OPTION,
) -> None:
    """Assemble the decision memo from what is already recorded."""
    payload = run_tool("render_memo", {"decision_id": decision_id})
    if json_output:
        typer.echo(json.dumps(payload, indent=2, ensure_ascii=False))
        return
    markdown = payload["markdown"] if isinstance(payload, dict) else payload
    typer.echo(markdown, nl=False)
