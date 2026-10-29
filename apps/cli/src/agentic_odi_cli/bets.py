"""Track bets from the CLI (E1.2, ALH-159).

``odi bets add|list|show|advance`` is argument parsing and transport only: the
service owns validation, baseline capture and the legal transitions, so the CLI
and the Studio cannot disagree about what a valid bet is. The baseline is
captured at creation and never recomputed here.
"""

from __future__ import annotations

import json
from typing import Any

import typer

from agentic_odi_cli.backend import run_tool

bets_app = typer.Typer(help="Record, list and advance bets.")

JSON_OPTION = typer.Option(False, "--json", help="Emit machine-readable JSON.")
DECISION_ID_OPTION = typer.Option(..., "--decision-id", help="Decision the bet belongs to")
OUTCOME_ID_OPTION = typer.Option(..., "--outcome-id", help="Outcome the bet targets")
HYPOTHESIS_OPTION = typer.Option(..., "--hypothesis", help="What we expect to happen")
TARGET_OPTION = typer.Option(..., "--target", help="The number we intend to reach")
MEASURE_BY_OPTION = typer.Option(..., "--measure-by", help="ISO-8601 date we will look")
BASELINE_OPTION = typer.Option(
    None, "--baseline", help="The starting measurement. Defaults to the outcome's score now."
)


@bets_app.command("add")
def add(
    decision_id: str = DECISION_ID_OPTION,
    outcome_id: str = OUTCOME_ID_OPTION,
    hypothesis: str = HYPOTHESIS_OPTION,
    target: float = TARGET_OPTION,
    measure_by: str = MEASURE_BY_OPTION,
    baseline: float | None = BASELINE_OPTION,
    json_output: bool = JSON_OPTION,
) -> None:
    """Record a bet, capturing its baseline at creation."""
    args: dict[str, Any] = {
        "decision_id": decision_id,
        "outcome_id": outcome_id,
        "hypothesis": hypothesis,
        "target": target,
        "measure_by": measure_by,
    }
    if baseline is not None:
        args["baseline"] = baseline

    bet = run_tool("record_bet", args)
    if json_output:
        typer.echo(json.dumps(bet, indent=2, ensure_ascii=False))
        return
    typer.echo(f"Bet recorded: {bet.get('id')}")
    typer.echo(f"  Baseline: {bet.get('baseline')} → Target: {bet.get('target')}")
    typer.echo(f"  Measure by: {bet.get('measure_by')}")


@bets_app.command("list")
def list_bets(
    job_id: str = typer.Option(None, "--job-id", help="Only bets for this job."),
    decision_id: str = typer.Option(None, "--decision-id", help="Only bets for this decision."),
    json_output: bool = JSON_OPTION,
) -> None:
    """List bets, optionally filtered to one job or one decision."""
    args: dict[str, Any] = {}
    if job_id is not None:
        args["job_id"] = job_id
    if decision_id is not None:
        args["decision_id"] = decision_id

    bets = run_tool("list_bets", args)
    if json_output:
        typer.echo(json.dumps(bets, indent=2, ensure_ascii=False))
        return
    if not bets:
        typer.echo("No bets recorded yet.")
        return
    for bet in bets:
        typer.echo(
            f"{bet['id']}  {bet['status']:<9}  baseline {bet['baseline']} → "
            f"{bet['target']}  by {bet['measure_by']}  {bet['hypothesis']}"
        )


@bets_app.command("show")
def show(
    bet_id: str = typer.Option(..., "--bet-id", help="Bet to show."),
    json_output: bool = JSON_OPTION,
) -> None:
    """Show one bet."""
    bet = run_tool("get_bet", {"bet_id": bet_id})
    if json_output:
        typer.echo(json.dumps(bet, indent=2, ensure_ascii=False))
        return
    typer.echo(f"Bet {bet['id']} ({bet['status']})")
    typer.echo(f"  Hypothesis: {bet['hypothesis']}")
    typer.echo(f"  Baseline: {bet['baseline']} → Target: {bet['target']}")
    typer.echo(f"  Measure by: {bet['measure_by']}")
    if bet.get("measured_at"):
        typer.echo(f"  Measured at: {bet['measured_at']}")


@bets_app.command("advance")
def advance(
    bet_id: str = typer.Option(..., "--bet-id", help="Bet to advance."),
    status: str = typer.Option(..., "--status", help="planned, running, measured, or abandoned"),
    at: str | None = typer.Option(None, "--at", help="ISO-8601 timestamp of the transition."),
    json_output: bool = JSON_OPTION,
) -> None:
    """Move a bet to a new status, refusing an illegal transition."""
    args: dict[str, Any] = {"bet_id": bet_id, "status": status}
    if at is not None:
        args["at"] = at

    bet = run_tool("advance_bet", args)
    if json_output:
        typer.echo(json.dumps(bet, indent=2, ensure_ascii=False))
        return
    typer.echo(f"Bet {bet['id']} is now {bet['status']}")
