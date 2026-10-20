"""Customer Outcomes CLI subcommands.

Customer Outcomes link customer value to business value. Every command works
against whichever backend is selected (local SQLite by default, or a remote MCP
server via ``--backend mcp``).
"""

from __future__ import annotations

import json
from enum import Enum
from typing import Any

import typer

from agentic_odi_cli.backend import run_tool
from agentic_odi_cli.render import (
    render_customer_outcome,
    render_customer_outcome_list,
    render_deleted,
    render_saved,
    render_score,
)

customer_outcomes_app = typer.Typer(help="Manage Customer Outcomes.")


class DirectionOption(str, Enum):
    MINIMIZE = "minimize"
    MAXIMIZE = "maximize"


class CategoryOption(str, Enum):
    REVENUE_GROWTH = "revenue_growth"
    COST_REDUCTION = "cost_reduction"
    RETENTION = "retention"
    RISK_MITIGATION = "risk_mitigation"
    OPERATIONAL_EFFICIENCY = "operational_efficiency"
    COMPLIANCE = "compliance"
    BRAND_REPUTATION = "brand_reputation"
    OTHER = "other"


JSON_OPTION = typer.Option(False, "--json", help="Emit machine-readable JSON.")


def _parse_value_metrics(values: list[str] | None) -> list[dict[str, Any]] | None:
    """Parse repeated ``--value-metric`` JSON objects into value metrics."""
    if not values:
        return None
    metrics: list[dict[str, Any]] = []
    for raw in values:
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise typer.BadParameter("must be valid JSON", param_hint="--value-metric") from exc
        if not isinstance(parsed, dict):
            raise typer.BadParameter("must be a JSON object", param_hint="--value-metric")
        metrics.append(parsed)
    return metrics


@customer_outcomes_app.command("add")
def add(
    job_id: str = typer.Option(..., help="Job ID the outcome belongs to"),
    direction: DirectionOption = typer.Option(..., help="minimize | maximize"),  # noqa: B008
    unit_of_measure: str = typer.Option(..., "--unit"),
    object_of_control: str = typer.Option(..., "--object"),
    statement: str = typer.Option(..., help="Full outcome statement"),
    importance: float = typer.Option(..., min=1.0, max=10.0),
    satisfaction: float = typer.Option(..., min=1.0, max=10.0),
    category: CategoryOption = typer.Option(..., help="Business impact category"),  # noqa: B008
    business_statement: str = typer.Option(..., help="Business value statement"),
    contextual_clarifier: str | None = typer.Option(default=None),
    step_id: str | None = typer.Option(default=None),
    value_metric: list[str] | None = typer.Option(  # noqa: B008
        None, "--value-metric", help="Value metric as a JSON object. Repeatable."
    ),
    json_output: bool = JSON_OPTION,
) -> None:
    """Add a Customer Outcome with customer and business value."""
    customer_value: dict[str, Any] = {
        "direction": direction.value,
        "unit_of_measure": unit_of_measure,
        "object_of_control": object_of_control,
        "statement": statement,
        "importance": importance,
        "satisfaction": satisfaction,
    }
    if contextual_clarifier:
        customer_value["contextual_clarifier"] = contextual_clarifier
    metrics = _parse_value_metrics(value_metric)
    if metrics is not None:
        customer_value["value_metrics"] = metrics
    args: dict[str, Any] = {
        "job_id": job_id,
        "customer_value": customer_value,
        "business_value": {"category": category.value, "statement": business_statement},
    }
    if step_id:
        args["step_id"] = step_id
    result = run_tool("add_customer_outcome", args)
    typer.echo(render_saved("created", result, as_json=json_output))


@customer_outcomes_app.command("get")
def get(
    outcome_id: str = typer.Argument(...),
    json_output: bool = JSON_OPTION,
) -> None:
    """Get a Customer Outcome by ID."""
    result = run_tool("get_customer_outcome", {"outcome_id": outcome_id})
    typer.echo(render_customer_outcome(result, as_json=json_output))


@customer_outcomes_app.command("list")
def list_outcomes(
    job_id: str | None = typer.Option(default=None, help="Filter by job ID"),
    json_output: bool = JSON_OPTION,
) -> None:
    """List Customer Outcomes."""
    args: dict[str, Any] = {}
    if job_id:
        args["job_id"] = job_id
    result = run_tool("list_customer_outcomes", args)
    typer.echo(render_customer_outcome_list(result, as_json=json_output))


@customer_outcomes_app.command("update")
def update(
    outcome_id: str = typer.Argument(...),
    importance: float | None = typer.Option(default=None, min=1.0, max=10.0),
    satisfaction: float | None = typer.Option(default=None, min=1.0, max=10.0),
    direction: DirectionOption | None = typer.Option(default=None),  # noqa: B008
    unit_of_measure: str | None = typer.Option(default=None, help="Unit of measure"),
    object_of_control: str | None = typer.Option(default=None, help="Object of control"),
    contextual_clarifier: str | None = typer.Option(default=None),
    statement: str | None = typer.Option(default=None),
    category: CategoryOption | None = typer.Option(default=None),  # noqa: B008
    business_statement: str | None = typer.Option(default=None),
    detail: str | None = typer.Option(default=None),
    estimated_annual_value: float | None = typer.Option(default=None),
    confidence: float | None = typer.Option(default=None),
    step_id: str | None = typer.Option(default=None),
    value_metric: list[str] | None = typer.Option(  # noqa: B008
        None, "--value-metric", help="Replace value metrics with these JSON objects."
    ),
    json_output: bool = JSON_OPTION,
) -> None:
    """Update a Customer Outcome."""
    args: dict[str, Any] = {"outcome_id": outcome_id}
    if step_id is not None:
        args["step_id"] = step_id
    if importance is not None:
        args["importance"] = importance
    if satisfaction is not None:
        args["satisfaction"] = satisfaction
    if direction is not None:
        args["direction"] = direction.value
    if unit_of_measure is not None:
        args["unit_of_measure"] = unit_of_measure
    if object_of_control is not None:
        args["object_of_control"] = object_of_control
    if contextual_clarifier is not None:
        args["contextual_clarifier"] = contextual_clarifier
    if statement is not None:
        args["statement"] = statement
    if category is not None:
        args["category"] = category.value
    if business_statement is not None:
        args["business_statement"] = business_statement
    if detail is not None:
        args["detail"] = detail
    if estimated_annual_value is not None:
        args["estimated_annual_value"] = estimated_annual_value
    if confidence is not None:
        args["confidence"] = confidence
    metrics = _parse_value_metrics(value_metric)
    if metrics is not None:
        args["value_metrics"] = metrics
    result = run_tool("update_customer_outcome", args)
    typer.echo(render_saved("updated", result, as_json=json_output))


@customer_outcomes_app.command("delete")
def delete(
    outcome_id: str = typer.Argument(...),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation"),
    json_output: bool = JSON_OPTION,
) -> None:
    """Delete a Customer Outcome."""
    if not yes:
        confirm = typer.confirm(f"Delete customer outcome {outcome_id}?")
        if not confirm:
            raise typer.Exit()
    result = run_tool("delete_customer_outcome", {"outcome_id": outcome_id})
    typer.echo(render_deleted(result, as_json=json_output))


def score(
    importance: float = typer.Argument(..., min=1.0, max=10.0),
    satisfaction: float = typer.Argument(..., min=1.0, max=10.0),
    json_output: bool = JSON_OPTION,
) -> None:
    """Compute an ODI Opportunity Score."""
    result = run_tool(
        "compute_opportunity",
        {"importance": importance, "satisfaction": satisfaction},
    )
    typer.echo(render_score(importance, satisfaction, result, as_json=json_output))


customer_outcomes_app.command(name="score")(score)
