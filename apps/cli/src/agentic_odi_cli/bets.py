"""Bets and recorded decisions: the Pillar 4 tracking surface.

A decision names what was chosen and what was rejected; a bet turns a chosen
outcome into a dated expectation with a baseline frozen at creation. Both read
back exactly what was stored, so a later score can never rewrite the start.
"""

from __future__ import annotations

from datetime import date
from typing import Annotated, Any

import typer

from agentic_odi_cli.backend import run_tool
from agentic_odi_cli.render import (
    render_bet,
    render_bet_list,
    render_decision_list,
    render_disproof_report,
    render_measurement,
    render_saved,
)

bets_app = typer.Typer(help="Track bets: dated expectations with a frozen baseline.")
decisions_app = typer.Typer(help="Record and read decisions.")

JSON_OPTION = typer.Option(False, "--json", help="Emit machine-readable JSON.")


@bets_app.command("add")
def add(
    decision_id: str = typer.Option(..., help="Decision the bet follows from"),
    outcome_id: str = typer.Option(..., help="Outcome the bet targets"),
    hypothesis: str = typer.Option(..., help="What you expect to happen"),
    target: float = typer.Option(..., help="Value the metric must reach to be met"),
    measure_by: str = typer.Option(..., help="Day you will look (YYYY-MM-DD)"),
    direction: str = typer.Option("maximize", help="maximize or minimize"),
    json_output: bool = JSON_OPTION,
) -> None:
    """Create a bet with a baseline frozen from the outcome's score now."""
    try:
        date.fromisoformat(measure_by)
    except ValueError as exc:
        raise typer.BadParameter("measure_by must be an ISO date (YYYY-MM-DD)") from exc
    args: dict[str, Any] = {
        "decision_id": decision_id,
        "outcome_id": outcome_id,
        "hypothesis": hypothesis,
        "target": target,
        "measure_by": measure_by,
        "direction": direction,
    }
    typer.echo(
        render_saved("created", run_tool("create_bet", args), as_json=json_output, noun="Bet")
    )


@bets_app.command("list")
def list_bets(
    job_id: str | None = typer.Option(None, help="Limit to one Job"),
    json_output: bool = JSON_OPTION,
) -> None:
    """List bets ordered by the day you will look, marking overdue ones."""
    args: dict[str, Any] = {}
    if job_id is not None:
        args["job_id"] = job_id
    bets = run_tool("list_bets", args)
    typer.echo(render_bet_list(bets, today=date.today().isoformat(), as_json=json_output))


@bets_app.command("show")
def show(
    bet_id: str = typer.Argument(..., help="Bet ID"),
    json_output: bool = JSON_OPTION,
) -> None:
    """Show a bet, including the baseline stored when it was created."""
    typer.echo(render_bet(run_tool("get_bet", {"bet_id": bet_id}), as_json=json_output))


@bets_app.command("measure")
def measure(
    bet_id: str = typer.Argument(..., help="Bet ID"),
    json_output: bool = JSON_OPTION,
) -> None:
    """Report met, missed or no_data against the bet's stored baseline."""
    typer.echo(render_measurement(run_tool("measure_bet", {"bet_id": bet_id}), as_json=json_output))


@bets_app.command("status")
def status(
    bet_id: str = typer.Argument(..., help="Bet ID"),
    new_status: str = typer.Argument(..., help="planned, running, measured or abandoned"),
    json_output: bool = JSON_OPTION,
) -> None:
    """Move a bet through a legal status transition."""
    result = run_tool("update_bet_status", {"bet_id": bet_id, "status": new_status})
    typer.echo(render_saved("updated", result, as_json=json_output, noun="Bet"))


@bets_app.command("disprove")
def disprove(
    bet_id: str = typer.Argument(..., help="Bet ID"),
    metric: str = typer.Option(..., help="opportunity, importance or satisfaction"),
    op: str = typer.Option(..., "--op", help="below, above, at_or_below or at_or_above"),
    threshold: float = typer.Option(..., help="Value the metric is compared against"),
    by: str = typer.Option(..., "--by", help="Day by which this must be judged (YYYY-MM-DD)"),
    rationale: str = typer.Option(..., help="Why this would disprove the bet"),
    index: int | None = typer.Option(None, help="Replace the condition at this index"),
    json_output: bool = JSON_OPTION,
) -> None:
    """Commit a typed disproof condition before the bet runs."""
    try:
        date.fromisoformat(by)
    except ValueError as exc:
        raise typer.BadParameter("--by must be an ISO date (YYYY-MM-DD)") from exc
    args: dict[str, Any] = {
        "bet_id": bet_id,
        "metric": metric,
        "operator": op,
        "threshold": threshold,
        "by_date": by,
        "rationale": rationale,
    }
    if index is not None:
        args["index"] = index
    typer.echo(
        render_saved("committed", run_tool("add_disproof", args), as_json=json_output, noun="Bet")
    )


@bets_app.command("verdict")
def verdict(
    bet_id: str = typer.Argument(..., help="Bet ID"),
    json_output: bool = JSON_OPTION,
) -> None:
    """Judge each committed disproof condition: disproved, holding or no_data."""
    result = run_tool("evaluate_disproof", {"bet_id": bet_id})
    typer.echo(render_disproof_report(result, as_json=json_output))


@decisions_app.command("record")
def record(
    job_id: str = typer.Option(..., help="Job the decision belongs to"),
    rationale: str = typer.Option(..., help="Why this choice was made"),
    by: str = typer.Option(..., "--by", help="Who decided"),
    outcome: Annotated[
        list[str] | None,
        typer.Option("--outcome", help="Chosen outcome ID (repeatable)"),
    ] = None,
    reject: Annotated[
        list[str] | None,
        typer.Option("--reject", help="Rejected outcome as 'id:reason' (repeatable)"),
    ] = None,
    confidence: str = typer.Option("medium", help="low, medium or high"),
    json_output: bool = JSON_OPTION,
) -> None:
    """Record a decision; a later decision supersedes this one."""
    if not outcome:
        raise typer.BadParameter("at least one --outcome is required")
    rejected = []
    for item in reject or []:
        outcome_id, _, reason = item.partition(":")
        if not reason.strip():
            raise typer.BadParameter(f"--reject needs 'id:reason', got '{item}'")
        rejected.append({"outcome_id": outcome_id.strip(), "reason": reason.strip()})
    args: dict[str, Any] = {
        "job_id": job_id,
        "chosen_outcome_ids": outcome,
        "rationale": rationale,
        "decided_by": by,
        "confidence": confidence,
    }
    if rejected:
        args["rejected"] = rejected
    typer.echo(
        render_saved(
            "recorded", run_tool("record_decision", args), as_json=json_output, noun="Decision"
        )
    )


@decisions_app.command("list")
def list_decisions(
    job_id: str = typer.Argument(..., help="Job ID"),
    json_output: bool = JSON_OPTION,
) -> None:
    """List a Job's decisions, oldest first; superseded ones stay visible."""
    decisions = run_tool("list_decisions", {"job_id": job_id})
    typer.echo(render_decision_list(decisions, as_json=json_output))
