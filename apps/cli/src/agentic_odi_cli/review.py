"""Review a decision from the CLI (C8, ALH-39).

``odi review show`` is transport only: it asks the backend for the review and
hands the result to the shared ``render_review``, so the CLI, the Studio API and
the MCP tool cannot disagree about a state or a change. It never recomputes a
delta, and a missing measurement stays ``no evidence`` rather than ``no change``.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from typing import Any

import typer

from agentic_odi_cli.backend import run_tool

review_app = typer.Typer(help="Re-examine a past decision against today's numbers.")

DECISION_ID_OPTION = typer.Option(..., "--decision-id", help="Decision to review.")
TODAY_OPTION = typer.Option(
    None, "--today", help="ISO-8601 date to compare against. Defaults to today in UTC."
)
JSON_OPTION = typer.Option(False, "--json", help="Emit machine-readable JSON.")


def _to_review(payload: dict[str, Any]) -> Any:
    """Rebuild the review from the transport payload.

    The renderer consumes a :class:`DecisionReview`; this copies every field
    rather than recomputing one. The core import is deferred so ``--help`` does
    not pull in the domain layer.
    """
    from agentic_odi_core.review import DecisionReview, OutcomeReview

    return DecisionReview(
        decision_id=payload["decision_id"],
        job_id=payload["job_id"],
        decided_at=payload["decided_at"],
        days_elapsed=payload["days_elapsed"],
        outcomes=tuple(
            OutcomeReview(
                outcome_id=outcome["outcome_id"],
                statement=outcome.get("statement"),
                state=outcome["state"],
                satisfaction_change=outcome.get("satisfaction_change"),
                importance_change=outcome.get("importance_change"),
                opportunity_change=outcome.get("opportunity_change"),
            )
            for outcome in payload.get("outcomes") or []
        ),
    )


@review_app.command("show")
def show(
    decision_id: str = DECISION_ID_OPTION,
    today: str | None = TODAY_OPTION,
    json_output: bool = JSON_OPTION,
) -> None:
    """Compare a decision's chosen outcomes against today's numbers."""
    if today is not None:
        try:
            date.fromisoformat(today)
        except ValueError as exc:
            typer.echo("Error: today must be an ISO-8601 date", err=True)
            raise typer.Exit(code=1) from exc

    args: dict[str, Any] = {
        "decision_id": decision_id,
        "today": today or datetime.now(timezone.utc).date().isoformat(),
    }
    payload = run_tool("review_decision", args)

    if json_output:
        typer.echo(json.dumps(payload, indent=2, ensure_ascii=False))
        return

    from agentic_odi_core.review import render_review

    typer.echo(render_review(_to_review(payload)), nl=False)
