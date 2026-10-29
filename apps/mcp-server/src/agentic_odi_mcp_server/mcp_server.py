"""Agentic ODI MCP Server (FastMCP)."""

import argparse
import asyncio
import json
import os
import signal
import sys
from collections.abc import AsyncIterator, Mapping, Sequence
from contextlib import asynccontextmanager
from typing import Any

from agentic_odi_core import (
    ODI_ASSISTANT_PROMPT,
    ODI_FRAMEWORK_GUIDELINES,
    TOOL_SPECS,
    CustomerOutcomeNotFoundError,
    EvidenceItemType,
    EvidenceNotFoundError,
    JobNotFoundError,
    JobStage,
    OdiError,
    ODIService,
    OutcomeNotFoundError,
    OutcomeStatementError,
    ScheduledWorkNotFoundError,
    SignalNotFoundError,
    StepNotFoundError,
    ToolName,
    ValueOutOfRangeError,
    build_repository,
    capability_manifest,
    capability_summary,
    compute_opportunity_score,
    evaluate_outcome_statement,
    job_not_found,
    odi_schema,
    scheduled_work_not_found,
)
from agentic_odi_core import (
    customer_outcome_not_found as _cust_not_found,
)
from fastmcp import Context, FastMCP
from pydantic import ValidationError

_repo = build_repository()
service = ODIService(_repo)

_shutdown_complete = False


def shutdown_store() -> None:
    """Flush and close the event store. Safe to call more than once."""
    global _shutdown_complete
    if _shutdown_complete:
        return
    _shutdown_complete = True
    try:
        _repo.commit()
    finally:
        _repo.close()


@asynccontextmanager
async def _lifespan(_server: FastMCP) -> AsyncIterator[None]:
    try:
        yield
    finally:
        shutdown_store()


mcp = FastMCP("Agentic ODI", lifespan=_lifespan)

jobs_db = _repo.jobs
steps_db = _repo.steps
outcomes_db = _repo.outcomes
customer_outcomes_db = _repo.customer_outcomes
evidence_db = _repo.evidence
signals_db = _repo.signals


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
def get_jobs(limit: int | None = None, offset: int = 0) -> str:
    """List jobs.

    ``limit`` caps how many jobs are returned and ``offset`` skips that many
    first, so a client can walk a long list without re-reading all of it.
    """
    jobs = service.get_jobs(limit=limit, offset=offset)
    return json.dumps([job.model_dump() for job in jobs])


@mcp.tool
def get_job(job_id: str) -> str:
    job = service.get_job(job_id)
    if job is None:
        return f"Error: Job with ID {job_id} not found."
    return job.model_dump_json()


@mcp.tool
def add_step(
    job_id: str,
    name: str,
    order: int,
    stage: JobStage | None = None,
    allow_empty_job_map: bool = False,
) -> str:
    try:
        step = service.add_step(
            job_id=job_id,
            name=name,
            order=order,
            stage=stage,
            allow_empty_job_map=allow_empty_job_map,
        )
    except JobNotFoundError:
        return job_not_found(job_id)
    except ValueOutOfRangeError as exc:
        return f"Error: {exc}"
    except OdiError as exc:
        return f"Error: {exc}"
    return f"Step created successfully: {step.model_dump_json()}"


@mcp.tool
def get_job_map(job_id: str, limit: int | None = None, offset: int = 0) -> str:
    job = service.get_job(job_id)
    if job is None:
        return f"Error: Job with ID {job_id} not found."
    steps = service.get_job_map(job_id, limit=limit, offset=offset)
    return json.dumps([step.model_dump() for step in steps])


@mcp.tool
def add_outcome(
    job_id: str,
    statement: str,
    importance: float,
    satisfaction: float,
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
    except OutcomeStatementError as exc:
        return f"Error: {exc}"
    return f"Outcome created successfully: {outcome.model_dump_json()}"


@mcp.tool
def get_outcomes(
    job_id: str,
    step_id: str | None = None,
    limit: int | None = None,
    offset: int = 0,
    sort: str = "opportunity_score",
) -> str:
    job = service.get_job(job_id)
    if job is None:
        return f"Error: Job with ID {job_id} not found."
    outcomes = service.get_outcomes(
        job_id=job_id, step_id=step_id, limit=limit, offset=offset, sort=sort
    )
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
def list_customer_outcomes(
    job_id: str | None = None, limit: int | None = None, offset: int = 0
) -> str:
    """List customer outcomes, optionally for one job and one page at a time."""
    outcomes = service.list_customer_outcomes(job_id=job_id, limit=limit, offset=offset)
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
    return capability_summary()


@mcp.tool
def get_capabilities_manifest() -> str:
    return json.dumps(capability_manifest())


@mcp.tool
def get_health() -> str:
    """Report whether the ODI store can be queried right now."""
    if _repo.health():
        return json.dumps({"status": "ok", "store": "accessible"})
    return json.dumps({"status": "degraded", "store": "locked"})


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
    except OutcomeStatementError as exc:
        return f"Error: {exc}"
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
async def add_evidence(
    ctx: Context,
    source_name: str,
    source_kind: str,
    name: str,
    content: str,
    url: str | None = None,
    item_type: EvidenceItemType = "manual",
    raw: dict[str, Any] | None = None,
    job_id: str | None = None,
    step_id: str | None = None,
    outcome_id: str | None = None,
) -> str:
    await ctx.report_progress(0, 2, "Validating the evidence links")
    try:
        evidence = service.add_evidence(
            source_name=source_name,
            source_kind=source_kind,
            item_type=item_type,
            name=name,
            content=content,
            url=url,
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
    await ctx.report_progress(2, 2, "Evidence stored")
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
    limit: int | None = None,
    offset: int = 0,
) -> str:
    """List evidence for a job, step or outcome, one page at a time."""
    items = service.list_evidence(
        job_id=job_id, step_id=step_id, outcome_id=outcome_id, limit=limit, offset=offset
    )
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
async def evaluate_outcome(ctx: Context, statement: str, job_id: str | None = None) -> str:
    await ctx.report_progress(0, 2, "Evaluating the statement")
    result = evaluate_outcome_statement(statement)
    if job_id is not None:
        if service.get_job(job_id) is None:
            return job_not_found(job_id)
        result["job_id"] = job_id
        result["existing_outcomes"] = [
            {
                "id": outcome.id,
                "statement": outcome.statement,
                "opportunity_score": outcome.opportunity_score,
            }
            for outcome in service.get_outcomes(job_id)
        ]
    await ctx.report_progress(2, 2, "Evaluation complete")
    return json.dumps(result)


@mcp.tool
def schedule_work(
    name: str,
    schedule_expression: str,
    agent_id: str = "default-agent",
    trigger_type: str = "oneshot",
    payload: dict[str, Any] | None = None,
    job_id: str | None = None,
) -> str:
    try:
        work = service.schedule_work(
            name=name,
            schedule_expression=schedule_expression,
            agent_id=agent_id,
            trigger_type=trigger_type,
            payload=payload,
            job_id=job_id,
        )
    except JobNotFoundError:
        return job_not_found(job_id or "")
    except ValueError as exc:
        return f"Error: {exc}"
    return f"Scheduled work created successfully: {work.model_dump_json()}"


@mcp.tool
def get_scheduled_work(work_id: str) -> str:
    try:
        work = service.get_scheduled_work(work_id)
    except ScheduledWorkNotFoundError:
        return scheduled_work_not_found(work_id)
    return work.model_dump_json()


@mcp.tool
def list_scheduled_work(
    job_id: str | None = None,
    status: str | None = None,
) -> str:
    items = service.list_scheduled_work(job_id=job_id, status=status)
    return json.dumps([item.model_dump() for item in items])


@mcp.tool
def cancel_scheduled_work(work_id: str) -> str:
    try:
        work = service.cancel_scheduled_work(work_id)
    except ScheduledWorkNotFoundError:
        return scheduled_work_not_found(work_id)
    return f"Scheduled work cancelled successfully: {work.model_dump_json()}"


@mcp.tool
def trigger_scheduled_work(work_id: str) -> str:
    try:
        work = service.trigger_scheduled_work(work_id)
    except ScheduledWorkNotFoundError:
        return scheduled_work_not_found(work_id)
    return f"Scheduled work dispatched: {work.model_dump_json()}"


@mcp.tool
def get_odi_schema() -> str:
    return json.dumps(odi_schema())


# --- Pillar 4 — Know: did it work -----------------------------------------


@mcp.tool
def record_decision(
    job_id: str,
    chosen_outcome_ids: list[str],
    rationale: str,
    decided_by: str,
    rejected: list[dict[str, Any]] | None = None,
    confidence: str = "medium",
) -> str:
    """Record a decision. A later decision supersedes the previous one."""
    try:
        decision = service.record_decision(
            job_id,
            chosen_outcome_ids,
            rationale,
            decided_by,
            rejected=rejected,
            confidence=confidence,
        )
    except (OdiError, ValueError) as exc:
        return f"Error: {exc}"
    return decision.model_dump_json()


@mcp.tool
def list_decisions(job_id: str) -> str:
    """List a Job's decisions, oldest first. A superseded decision stays readable."""
    try:
        decisions = service.list_decisions(job_id)
    except OdiError as exc:
        return f"Error: {exc}"
    return json.dumps([decision.model_dump(mode="json") for decision in decisions])


@mcp.tool
def record_score_snapshot(
    outcome_id: str,
    method: str | None = None,
    note: str | None = None,
    importance_n: int | None = None,
    satisfaction_n: int | None = None,
) -> str:
    """Capture the outcome's current score as an append-only history entry."""
    try:
        snapshot = service.record_score_snapshot(
            outcome_id,
            method=method,
            note=note,
            importance_n=importance_n,
            satisfaction_n=satisfaction_n,
        )
    except (OdiError, ValueError) as exc:
        return f"Error: {exc}"
    return snapshot.model_dump_json()


@mcp.tool
def outcome_delta(outcome_id: str) -> str:
    """Signed change between an outcome's earlier and latest score snapshots."""
    try:
        return json.dumps(service.outcome_delta(outcome_id))
    except OdiError as exc:
        return f"Error: {exc}"


@mcp.tool
def create_bet(
    decision_id: str,
    outcome_id: str,
    hypothesis: str,
    target: float,
    measure_by: str,
    direction: str = "maximize",
) -> str:
    """Create a bet with a baseline frozen from the outcome's score now."""
    from datetime import date

    try:
        parsed = date.fromisoformat(measure_by)
    except ValueError:
        return f"Error: measure_by must be an ISO date (YYYY-MM-DD), got '{measure_by}'"
    try:
        bet = service.create_bet(
            decision_id,
            outcome_id,
            hypothesis,
            target,
            parsed,
            direction=direction,
        )
    except (OdiError, ValueError) as exc:
        return f"Error: {exc}"
    return bet.model_dump_json()


@mcp.tool
def get_bet(bet_id: str) -> str:
    """Get a single Bet by ID, including its frozen baseline."""
    try:
        bet = service.get_bet(bet_id)
    except OdiError as exc:
        return f"Error: {exc}"
    return bet.model_dump_json()


@mcp.tool
def list_bets(job_id: str | None = None) -> str:
    """List bets ordered by the date you will look."""
    try:
        bets = service.list_bets(job_id)
    except OdiError as exc:
        return f"Error: {exc}"
    return json.dumps([bet.model_dump(mode="json") for bet in bets])


@mcp.tool
def update_bet_status(bet_id: str, status: str) -> str:
    """Move a bet through a legal status transition; refusals name the legal ones."""
    try:
        bet = service.transition_bet(bet_id, status)
    except (OdiError, ValueError) as exc:
        return f"Error: {exc}"
    return bet.model_dump_json()


@mcp.tool
def measure_bet(bet_id: str) -> str:
    """Report met, missed or no_data against the bet's stored baseline."""
    try:
        return json.dumps(service.measure_bet(bet_id))
    except OdiError as exc:
        return f"Error: {exc}"


@mcp.tool
def emit_know_signals(job_id: str | None = None) -> str:
    """Record the "know" signals the store can prove (bets due, superseded decisions, gaps)."""
    try:
        signals = service.emit_know_signals(job_id=job_id)
    except OdiError as exc:
        return f"Error: {exc}"
    return json.dumps([signal.model_dump(mode="json") for signal in signals])


@mcp.tool
def list_signals(unread_only: bool = False, limit: int = 50) -> str:
    """List recorded signals, newest first; ``unread_only`` trims to the badge."""
    signals = service.list_signals(unread_only=unread_only, limit=limit)
    return json.dumps([signal.model_dump(mode="json") for signal in signals])


@mcp.tool
def mark_signal_read(signal_id: str) -> str:
    try:
        signal = service.mark_signal_read(signal_id)
    except SignalNotFoundError:
        return f"Error: Signal with ID {signal_id} not found."
    return f"Signal marked as read: {signal.model_dump_json()}"


@mcp.tool
def dismiss_signal(signal_id: str) -> str:
    try:
        signal = service.dismiss_signal(signal_id)
    except SignalNotFoundError:
        return f"Error: Signal with ID {signal_id} not found."
    return f"Signal dismissed: {signal.model_dump_json()}"


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


def validate_tool_specs(
    specs: Mapping[str, Any] | None = None,
    tools: Sequence[Any] | None = None,
) -> list[str]:
    """Return every mismatch between the contract and the live tool registry.

    ``tools`` is FastMCP's registry; omitting it checks the contract alone.
    """
    specs = TOOL_SPECS if specs is None else specs
    errors: list[str] = []
    enum_names = {member.value for member in ToolName}
    for name in sorted(enum_names - set(specs)):
        errors.append(f"{name}: ToolName member has no TOOL_SPECS entry")
    for name in sorted(set(specs) - enum_names):
        errors.append(f"{name}: TOOL_SPECS entry is not a ToolName member")
    declared = [spec.name for spec in specs.values()]
    for name in sorted({item for item in declared if declared.count(item) > 1}):
        errors.append(f"{name}: duplicate TOOL_SPECS name")
    if tools is None:
        return errors
    by_name: dict[str, Any] = {}
    for tool in tools:
        if tool.name in by_name:
            errors.append(f"{tool.name}: duplicate tool registration")
        by_name[tool.name] = tool
    for name in sorted(set(specs) - set(by_name)):
        errors.append(f"{name}: contract tool has no registered handler")
    for name in sorted(set(by_name) - set(specs)):
        errors.append(f"{name}: registered tool is not in TOOL_SPECS")
    for name in sorted(set(specs) & set(by_name)):
        spec = specs[name]
        tool = by_name[name]
        schema = getattr(tool, "parameters", None) or {}
        arguments = set(schema.get("properties", {}))
        if arguments != set(spec.arguments):
            errors.append(
                f"{name}: contract arguments {sorted(spec.arguments)} do not match "
                f"handler arguments {sorted(arguments)}"
            )
        required = set(schema.get("required", []))
        if required != set(spec.required):
            errors.append(
                f"{name}: contract required {sorted(spec.required)} do not match "
                f"handler required {sorted(required)}"
            )
        handler = getattr(tool, "fn", None)
        if handler is not None and not callable(handler):
            errors.append(f"{name}: registered handler is not callable")
    return errors


def validate_at_startup() -> None:
    """Refuse to serve when the registry disagrees with the contract."""
    errors = validate_tool_specs(tools=asyncio.run(mcp.list_tools()))
    if not errors:
        return
    for error in errors:
        print(f"Error: {error}", file=sys.stderr)
    sys.exit(1)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Run the Agentic ODI MCP server over HTTP.")
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help=f"Port to listen on (default: $AGENTIC_ODI_MCP_PORT or {DEFAULT_PORT}).",
    )
    args = parser.parse_args(argv)
    validate_at_startup()
    setup_graceful_shutdown()
    mcp.run(transport="http", port=resolve_port(args.port))


@mcp.tool
def set_notification_rule(kind: str, threshold: float = 0.0, enabled: bool = True) -> str:
    """Store one interruption rule for a signal kind."""
    try:
        rule = service.set_notification_rule(kind, threshold=threshold, enabled=enabled)
    except (OdiError, ValueError) as exc:
        return f"Error: {exc}"
    return rule.model_dump_json()


@mcp.tool
def list_notification_rules() -> str:
    """List the effective notification rules, including documented defaults."""
    rules = service.list_notification_rules()
    return json.dumps([rule.model_dump(mode="json") for rule in rules])


def setup_graceful_shutdown() -> None:
    """Flush the event store when the process is asked to stop.

    The handler chains to whatever was installed before it, so the server's own
    graceful-shutdown behaviour (drain in-flight requests, then exit) is
    preserved. The store is flushed on the way out either way.
    """

    def _chain(previous: Any) -> Any:
        def _handle(signum: int, frame: Any) -> None:
            shutdown_store()
            if callable(previous):
                previous(signum, frame)

        return _handle

    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, _chain(signal.getsignal(sig)))


if __name__ == "__main__":
    main()
