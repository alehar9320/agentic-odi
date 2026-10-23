"""Agentic ODI MCP Server (FastMCP)."""

import argparse
import json
import os
from typing import Any

from agentic_odi_core import (
    CAPABILITIES,
    ODI_ASSISTANT_PROMPT,
    ODI_FRAMEWORK_GUIDELINES,
    CustomerOutcomeNotFoundError,
    EvidenceItemType,
    EvidenceNotFoundError,
    JobNotFoundError,
    OdiError,
    ODIService,
    OutcomeNotFoundError,
    StepNotFoundError,
    ValueOutOfRangeError,
    build_repository,
    compute_opportunity_score,
    evaluate_outcome_statement,
    job_not_found,
    odi_schema,
)
from agentic_odi_core import (
    customer_outcome_not_found as _cust_not_found,
)
from fastmcp import FastMCP
from pydantic import ValidationError

mcp = FastMCP("Agentic ODI")

_repo = build_repository()
service = ODIService(_repo)

jobs_db = _repo.jobs
steps_db = _repo.steps
outcomes_db = _repo.outcomes
customer_outcomes_db = _repo.customer_outcomes
evidence_db = _repo.evidence


def _step_not_found(step_id: str | None) -> str:
    return f"Error: Step with ID {step_id} not found."


def _outcome_not_found(outcome_id: str | None) -> str:
    return f"Error: Outcome with ID {outcome_id} not found."


def _evidence_not_found(evidence_id: str, hint: str | None = None) -> str:
    message = f"Error: Evidence with ID {evidence_id} not found."
    if hint:
        message = f"{message} {hint}"
    return message


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
    if job is None:
        return f"Error: Job with ID {job_id} not found."
    return job.model_dump_json()


@mcp.tool
def add_step(job_id: str, name: str, order: int) -> str:
    try:
        step = service.add_step(job_id=job_id, name=name, order=order)
    except JobNotFoundError:
        return job_not_found(job_id)
    return f"Step created successfully: {step.model_dump_json()}"


@mcp.tool
def get_job_map(job_id: str) -> str:
    job = service.get_job(job_id)
    if job is None:
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
    try:
        outcome = service.add_outcome(
            job_id=job_id,
            statement=statement,
            importance=importance,
            satisfaction=satisfaction,
            step_id=step_id,
        )
    except JobNotFoundError:
        return f"Error: Job with ID {job_id} not found."
    except StepNotFoundError:
        return _step_not_found(step_id)
    except ValueOutOfRangeError:
        return "Error: importance and satisfaction must be between 1.0 and 10.0"
    return f"Outcome created successfully: {outcome.model_dump_json()}"


@mcp.tool
def get_outcomes(job_id: str, step_id: str | None = None) -> str:
    job = service.get_job(job_id)
    if job is None:
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
    try:
        co = service.add_customer_outcome(
            job_id=job_id,
            customer_value=customer_value,
            business_value=business_value,
            step_id=step_id,
        )
    except JobNotFoundError:
        return f"Error: Job with ID {job_id} not found."
    except StepNotFoundError:
        return _step_not_found(step_id)
    except ValidationError as e:
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
    value_metrics: list[dict] | None = None,
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
    if value_metrics is not None:
        cv_d["value_metrics"] = value_metrics
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
    except CustomerOutcomeNotFoundError:
        return _cust_not_found(outcome_id)
    except ValidationError as e:
        return f"Error: {e}"
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
    if not (1.0 <= importance <= 10.0) or not (1.0 <= satisfaction <= 10.0):
        return "Error: importance and satisfaction must be between 1.0 and 10.0"
    score = compute_opportunity_score(importance, satisfaction)
    return f"Opportunity score: {score:.2f}"


@mcp.tool
def get_odi_framework_guidelines() -> str:
    return ODI_FRAMEWORK_GUIDELINES


@mcp.tool
def get_capabilities() -> str:
    return CAPABILITIES


@mcp.tool
def get_step(step_id: str) -> str:
    step = service.get_step(step_id)
    if step is None:
        return _step_not_found(step_id)
    return step.model_dump_json()


@mcp.tool
def get_outcome(outcome_id: str) -> str:
    outcome = service.get_outcome(outcome_id)
    if outcome is None:
        return _outcome_not_found(outcome_id)
    return outcome.model_dump_json()


@mcp.tool
def update_job(job_id: str, name: str | None = None, description: str | None = None) -> str:
    updates: dict = {}
    if name is not None:
        updates["name"] = name
    if description is not None:
        updates["description"] = description
    try:
        job = service.update_job(job_id, updates)
    except JobNotFoundError:
        return job_not_found(job_id)
    return f"Job updated successfully: {job.model_dump_json()}"


@mcp.tool
def delete_job(job_id: str) -> str:
    try:
        service.delete_job(job_id)
    except JobNotFoundError:
        return job_not_found(job_id)
    return f"Job deleted successfully: {job_id}"


@mcp.tool
def update_step(step_id: str, name: str | None = None, order: int | None = None) -> str:
    updates: dict = {}
    if name is not None:
        updates["name"] = name
    if order is not None:
        updates["order"] = order
    try:
        step = service.update_step(step_id, updates)
    except StepNotFoundError:
        return _step_not_found(step_id)
    return f"Step updated successfully: {step.model_dump_json()}"


@mcp.tool
def delete_step(step_id: str) -> str:
    try:
        service.delete_step(step_id)
    except StepNotFoundError:
        return _step_not_found(step_id)
    return f"Step deleted successfully: {step_id}"


@mcp.tool
def update_outcome(
    outcome_id: str,
    statement: str | None = None,
    importance: float | None = None,
    satisfaction: float | None = None,
    step_id: str | None = None,
) -> str:
    updates: dict = {}
    if statement is not None:
        updates["statement"] = statement
    if importance is not None:
        updates["importance"] = importance
    if satisfaction is not None:
        updates["satisfaction"] = satisfaction
    if step_id is not None:
        updates["step_id"] = step_id
    try:
        updated = service.update_outcome(outcome_id, updates)
    except OutcomeNotFoundError:
        return _outcome_not_found(outcome_id)
    except ValueOutOfRangeError:
        return "Error: importance and satisfaction must be between 1.0 and 10.0"
    return f"Outcome updated successfully: {updated.model_dump_json()}"


@mcp.tool
def delete_outcome(outcome_id: str) -> str:
    try:
        service.delete_outcome(outcome_id)
    except OutcomeNotFoundError:
        return _outcome_not_found(outcome_id)
    return f"Outcome deleted successfully: {outcome_id}"


@mcp.tool
def add_evidence(
    source_name: str,
    source_kind: str,
    name: str,
    content: str,
    item_type: EvidenceItemType = "manual",
    raw: dict[str, Any] | None = None,
    job_id: str | None = None,
    step_id: str | None = None,
    outcome_id: str | None = None,
) -> str:
    try:
        evidence = service.add_evidence(
            source_name=source_name,
            source_kind=source_kind,
            item_type=item_type,
            name=name,
            content=content,
            raw=raw,
            job_id=job_id,
            step_id=step_id,
            outcome_id=outcome_id,
        )
    except JobNotFoundError:
        return job_not_found(job_id or "")
    except StepNotFoundError:
        return _step_not_found(step_id)
    except OutcomeNotFoundError:
        return _outcome_not_found(outcome_id)
    except (OdiError, ValueError) as exc:
        return f"Error: {exc}"
    return f"Evidence created successfully: {evidence.model_dump_json()}"


@mcp.tool
def get_evidence(evidence_id: str) -> str:
    evidence = service.get_evidence(evidence_id)
    if evidence is None:
        return _evidence_not_found(
            evidence_id,
            "List the stored records with list_evidence() to find a valid id.",
        )
    return evidence.model_dump_json()


@mcp.tool
def list_evidence(
    job_id: str | None = None,
    step_id: str | None = None,
    outcome_id: str | None = None,
) -> str:
    items = service.list_evidence(job_id=job_id, step_id=step_id, outcome_id=outcome_id)
    return json.dumps([item.model_dump() for item in items])


@mcp.tool
def delete_evidence(evidence_id: str) -> str:
    try:
        service.delete_evidence(evidence_id)
    except EvidenceNotFoundError as exc:
        return _evidence_not_found(evidence_id, exc.hint)
    return f"Evidence deleted successfully: {evidence_id}"


@mcp.tool
def promote_evidence(
    evidence_id: str,
    target: str,
    job_id: str | None = None,
    statement: str | None = None,
    name: str | None = None,
    importance: float | None = None,
    satisfaction: float | None = None,
) -> str:
    try:
        artifact = service.promote_evidence(
            evidence_id,
            target,
            job_id=job_id,
            statement=statement,
            name=name,
            importance=importance,
            satisfaction=satisfaction,
        )
    except EvidenceNotFoundError as exc:
        return _evidence_not_found(evidence_id, exc.hint)
    except JobNotFoundError:
        return job_not_found(job_id or "")
    except StepNotFoundError:
        return _step_not_found(None)
    except OutcomeNotFoundError:
        return _outcome_not_found(None)
    except ValueOutOfRangeError:
        return "Error: importance and satisfaction must be between 1.0 and 10.0"
    except (OdiError, ValueError) as exc:
        return f"Error: {exc}"
    label = "Job" if target == "job" else "Outcome"
    return f"{label} created successfully: {artifact.model_dump_json()}"


@mcp.tool
def evaluate_outcome(statement: str, job_id: str | None = None) -> str:
    result = evaluate_outcome_statement(statement)
    if job_id is not None:
        if service.get_job(job_id) is None:
            return json.dumps({**result, "job_id": job_id, "error": job_not_found(job_id)})
        result["job_id"] = job_id
        result["existing_outcomes"] = [
            {
                "id": outcome.id,
                "statement": outcome.statement,
                "opportunity_score": outcome.opportunity_score,
            }
            for outcome in service.get_outcomes(job_id)
        ]
    return json.dumps(result)


@mcp.tool
def get_odi_schema() -> str:
    return json.dumps(odi_schema())


DEFAULT_PORT = 8000


def resolve_port(cli_port: int | None = None) -> int:
    """Return the HTTP port for the server: flag, then env var, then default."""
    if cli_port is not None:
        return cli_port
    raw = os.environ.get("AGENTIC_ODI_MCP_PORT")
    if raw is None or not raw.strip():
        return DEFAULT_PORT
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError(f"AGENTIC_ODI_MCP_PORT must be an integer, got {raw!r}") from exc


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Run the Agentic ODI MCP server over HTTP.")
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help=f"Port to listen on (default: $AGENTIC_ODI_MCP_PORT or {DEFAULT_PORT}).",
    )
    args = parser.parse_args(argv)
    mcp.run(transport="http", port=resolve_port(args.port))


if __name__ == "__main__":
    main()
