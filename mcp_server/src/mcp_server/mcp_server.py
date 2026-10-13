"""Agentic ODI MCP Server (FastMCP)."""

import json
import uuid
from typing import Any

from fastmcp import FastMCP

from core import (
    CAPABILITIES,
    BusinessImpactCategory,
    CustomerOutcomeNotFoundError,
    JobNotFoundError,
    ODIService,
    ODI_ASSISTANT_PROMPT,
    ODI_FRAMEWORK_GUIDELINES,
    ValueOutOfRangeError,
    compute_opportunity_score,
)
from core import (
    customer_outcome_not_found as _cust_not_found,
)
from core import (
    job_not_found as _job_not_found,
)
from core.repository import InMemoryRepository

mcp = FastMCP("Agentic ODI")

_repo = InMemoryRepository()
service = ODIService(_repo)

jobs_db = _repo.jobs
steps_db = _repo.steps
outcomes_db = _repo.outcomes
customer_outcomes_db = _repo.customer_outcomes


@mcp.prompt
def odi_assistant_prompt() -> str:
    return ODI_ASSISTANT_PROMPT


@mcp.tool
def add_job(name: str, description: str | None = None) -> str:
    job = service.add_job(name=name, description=description)
    return f"Job created successfully: {job.model_dump_json()}"


@mcp.tool
def get_jobs() -> str:
    jobs = service.get_jobs()
    return json.dumps([job.model_dump() for job in jobs])


@mcp.tool
def get_job(job_id: str) -> str:
    job = service.get_job(job_id)
    if not job:
        return f"Error: Job with ID {job_id} not found."
    return job.model_dump_json()


@mcp.tool
def add_step(job_id: str, name: str, order: int) -> str:
    step = service.add_step(job_id=job_id, name=name, order=order)
    return f"Step created successfully: {step.model_dump_json()}"


@mcp.tool
def get_job_map(job_id: str) -> str:
    job = service.get_job(job_id)
    if not job:
        return f"Error: Job with ID {job_id} not found."
    steps = service.get_job_map(job_id)
    return json.dumps([step.model_dump() for step in steps])


@mcp.tool
def add_outcome(
    job_id: str,
    statement: str,
    importance: float | None = None,
    satisfaction: float | None = None,
    step_id: str | None = None,
) -> str:
    job = service.get_job(job_id)
    if not job:
        return f"Error: Job with ID {job_id} not found."
    try:
        outcome = service.add_outcome(
            job_id=job_id,
            statement=statement,
            importance=importance,
            satisfaction=satisfaction,
            step_id=step_id,
        )
    except ValueOutOfRangeError:
        return "Error: importance and satisfaction must be between 1.0 and 10.0"
    return f"Outcome created successfully: {outcome.model_dump_json()}"


@mcp.tool
def get_outcomes(job_id: str, step_id: str | None = None) -> str:
    job = service.get_job(job_id)
    if not job:
        return f"Error: Job with ID {job_id} not found."
    outcomes = service.get_outcomes(job_id=job_id, step_id=step_id)
    return json.dumps([outcome.model_dump() for outcome in outcomes])


@mcp.tool
def add_customer_outcome(
    job_id: str,
    customer_value: dict[str, Any],
    business_value: dict[str, Any],
    step_id: str | None = None,
) -> str:
    job = service.get_job(job_id)
    if not job:
        return f"Error: Job with ID {job_id} not found."
    try:
        co = service.add_customer_outcome(
            job_id=job_id,
            customer_value=customer_value,
            business_value=business_value,
            step_id=step_id,
        )
    except Exception as e:
        return f"Error: {e}"
    return f"Customer outcome created successfully: {co.model_dump_json()}"


@mcp.tool
def get_customer_outcome(outcome_id: str) -> str:
    try:
        co = service.get_customer_outcome(outcome_id)
    except CustomerOutcomeNotFoundError:
        return _cust_not_found(outcome_id)
    return co.model_dump_json()


@mcp.tool
def list_customer_outcomes(job_id: str | None = None) -> str:
    outcomes = service.list_customer_outcomes(job_id=job_id)
    return json.dumps([o.model_dump() for o in outcomes])


@mcp.tool
def update_customer_outcome(
    outcome_id: str,
    direction: str | None = None,
    unit_of_measure: str | None = None,
    object_of_control: str | None = None,
    contextual_clarifier: str | None = None,
    statement: str | None = None,
    importance: float | None = None,
    satisfaction: float | None = None,
    category: str | None = None,
    business_statement: str | None = None,
    detail: str | None = None,
    estimated_annual_value: float | None = None,
    confidence: float | None = None,
    step_id: str | None = None,
) -> str:
    try:
        co = service.get_customer_outcome(outcome_id)
    except CustomerOutcomeNotFoundError:
        return _cust_not_found(outcome_id)
    updates: dict[str, Any] = {}
    cv_d = co.customer_value.model_dump()
    if direction is not None:
        cv_d["direction"] = direction
    if unit_of_measure is not None:
        cv_d["unit_of_measure"] = unit_of_measure
    if object_of_control is not None:
        cv_d["object_of_control"] = object_of_control
    if contextual_clarifier is not None:
        cv_d["contextual_clarifier"] = contextual_clarifier
    if statement is not None:
        cv_d["statement"] = statement
    if importance is not None:
        cv_d["importance"] = importance
    if satisfaction is not None:
        cv_d["satisfaction"] = satisfaction
    updates["customer_value"] = cv_d
    bv_d = co.business_value.model_dump()
    if category is not None:
        bv_d["category"] = category
    if business_statement is not None:
        bv_d["statement"] = business_statement
    if detail is not None:
        bv_d["detail"] = detail
    if estimated_annual_value is not None:
        bv_d["estimated_annual_value"] = estimated_annual_value
    if confidence is not None:
        bv_d["confidence"] = confidence
    updates["business_value"] = bv_d
    if step_id is not None:
        updates["step_id"] = step_id
    try:
        co2 = service.update_customer_outcome(outcome_id, updates)
    except Exception:
        return _cust_not_found(outcome_id)
    return f"Customer outcome updated successfully: {co2.model_dump_json()}"


@mcp.tool
def delete_customer_outcome(outcome_id: str) -> str:
    try:
        service.delete_customer_outcome(outcome_id)
    except CustomerOutcomeNotFoundError:
        return _cust_not_found(outcome_id)
    return f"Customer outcome deleted successfully: {outcome_id}"


@mcp.tool
def compute_opportunity(importance: float, satisfaction: float) -> str:
    try:
        if not (1.0 <= importance <= 10.0) or not (1.0 <= satisfaction <= 10.0):
            return "Error: importance and satisfaction must be between 1.0 and 10.0"
        score = compute_opportunity_score(importance, satisfaction)
    except Exception as e:
        return f"Error: {e}"
    return f"Opportunity score: {score:.2f}"


@mcp.tool
def get_odi_framework_guidelines() -> str:
    return ODI_FRAMEWORK_GUIDELINES


@mcp.tool
def get_capabilities() -> str:
    return CAPABILITIES


def main() -> None:
    mcp.run(transport="http", port=8000)


if __name__ == "__main__":
    main()


@mcp.tool
def greet(name: str) -> str:
    return f"Hello, {name}!"
