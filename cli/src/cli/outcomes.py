"""Customer Outcomes CLI subcommands."""

from __future__ import annotations

import asyncio
import os
from enum import StrEnum
from typing import Any

import typer
from fastmcp import Client

MCP_URL_DEFAULT = os.getenv("AGENTIC_ODI_MCP_URL", "http://localhost:8000/mcp")

outcomes_app = typer.Typer(help="Manage Customer Outcome entities.")


class DirectionOption(StrEnum):
    MINIMIZE = "minimize"
    MAXIMIZE = "maximize"


class CategoryOption(StrEnum):
    REVENUE_GROWTH = "revenue_growth"
    COST_REDUCTION = "cost_reduction"
    RETENTION = "retention"
    RISK_MITIGATION = "risk_mitigation"
    OPERATIONAL_EFFICIENCY = "operational_efficiency"
    COMPLIANCE = "compliance"
    BRAND_REPUTATION = "brand_reputation"
    OTHER = "other"


def _call_mcp(tool: str, args: dict[str, Any], mcp_url: str = MCP_URL_DEFAULT) -> str:
    async def _run() -> str:
        async with Client(mcp_url) as client:
            result = await client.call_tool(tool, args)
            return result.content[0].text  # type: ignore[index]

    try:
        return asyncio.run(_run())
    except Exception as exc:  # noqa: BLE001
        typer.echo(f"Error: could not reach MCP server at {mcp_url}: {exc}", err=True)
        raise typer.Exit(code=1) from exc


@outcomes_app.command("add")
def add(
    job_id: str = typer.Option(..., help="Job ID the outcome belongs to"),
    direction: DirectionOption = typer.Option(..., help="minimize | maximize"),
    unit_of_measure: str = typer.Option(..., "--unit"),
    object_of_control: str = typer.Option(..., "--object"),
    statement: str = typer.Option(..., help="Full outcome statement"),
    importance: float = typer.Option(..., min=1.0, max=10.0),
    satisfaction: float = typer.Option(..., min=1.0, max=10.0),
    category: CategoryOption = typer.Option(..., help="Business impact category"),
    business_statement: str = typer.Option(..., help="Business value statement"),
    contextual_clarifier: str | None = typer.Option(default=None),
    step_id: str | None = typer.Option(default=None),
    mcp_url: str = typer.Option(default=MCP_URL_DEFAULT, help="MCP server URL"),
) -> None:
    """Add a Customer Outcome with customer and business value."""
    customer_value = {
        "direction": direction.value,
        "unit_of_measure": unit_of_measure,
        "object_of_control": object_of_control,
        "statement": statement,
        "importance": importance,
        "satisfaction": satisfaction,
    }
    if contextual_clarifier:
        customer_value["contextual_clarifier"] = contextual_clarifier
    business_value = {
        "category": category.value,
        "statement": business_statement,
    }
    args: dict[str, Any] = {
        "job_id": job_id,
        "customer_value": customer_value,
        "business_value": business_value,
    }
    if step_id:
        args["step_id"] = step_id
    from cli.backend import get_backend; typer.echo(get_backend("mcp", mcp_url=mcp_url).call("add_customer_outcome", args))


@outcomes_app.command("get")
def get(
    outcome_id: str = typer.Argument(...),
    mcp_url: str = typer.Option(default=MCP_URL_DEFAULT, help="MCP server URL"),
) -> None:
    """Get a Customer Outcome by ID."""
    from cli.backend import get_backend; typer.echo(get_backend("mcp", mcp_url=mcp_url).call("get_customer_outcome", {"outcome_id": outcome_id}))


@outcomes_app.command("list")
def list_outcomes(
    job_id: str | None = typer.Option(default=None, help="Filter by job ID"),
    mcp_url: str = typer.Option(default=MCP_URL_DEFAULT, help="MCP server URL"),
) -> None:
    """List Customer Outcomes."""
    args: dict[str, Any] = {}
    if job_id:
        args["job_id"] = job_id
    from cli.backend import get_backend; typer.echo(get_backend("mcp", mcp_url=mcp_url).call("list_customer_outcomes", args))


@outcomes_app.command("update")
def update(
    outcome_id: str = typer.Argument(...),
    importance: float | None = typer.Option(default=None, min=1.0, max=10.0),
    satisfaction: float | None = typer.Option(default=None, min=1.0, max=10.0),
    direction: DirectionOption | None = typer.Option(default=None),
    unit_of_measure: str | None = typer.Option(default=None, help="Unit of measure"),
    object_of_control: str | None = typer.Option(default=None, help="Object of control"),
    contextual_clarifier: str | None = typer.Option(default=None),
    statement: str | None = typer.Option(default=None),
    category: CategoryOption | None = typer.Option(default=None),
    business_statement: str | None = typer.Option(default=None),
    detail: str | None = typer.Option(default=None),
    estimated_annual_value: float | None = typer.Option(default=None),
    confidence: float | None = typer.Option(default=None),
    step_id: str | None = typer.Option(default=None),
    mcp_url: str = typer.Option(default=MCP_URL_DEFAULT, help="MCP server URL"),
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
    from cli.backend import get_backend; typer.echo(get_backend("mcp", mcp_url=mcp_url).call("update_customer_outcome", args))


@outcomes_app.command("delete")
def delete(
    outcome_id: str = typer.Argument(...),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation"),
    mcp_url: str = typer.Option(default=MCP_URL_DEFAULT, help="MCP server URL"),
) -> None:
    """Delete a Customer Outcome."""
    if not yes:
        confirm = typer.confirm(f"Delete customer outcome {outcome_id}?")
        if not confirm:
            raise typer.Exit()
    from cli.backend import get_backend; typer.echo(get_backend("mcp", mcp_url=mcp_url).call("delete_customer_outcome", {"outcome_id": outcome_id}))


@outcomes_app.command("score")
def score(
    importance: float = typer.Argument(..., min=1.0, max=10.0),
    satisfaction: float = typer.Argument(..., min=1.0, max=10.0),
    mcp_url: str = typer.Option(default=MCP_URL_DEFAULT, help="MCP server URL"),
) -> None:
    """Compute ODI Opportunity Score."""
    typer.echo(
        _call_mcp(
            "compute_opportunity",
            {"importance": importance, "satisfaction": satisfaction},
            mcp_url,
        )
    )
