"""Agentic ODI MCP Server (FastMCP)."""

import argparse
import asyncio
import json
import os
import signal
import sys
from collections.abc import AsyncIterator, Mapping, Sequence
from contextlib import asynccontextmanager
from datetime import date
from typing import Any

from agentic_odi_core import (
    ODI_ASSISTANT_PROMPT,
    ODI_FRAMEWORK_GUIDELINES,
    TOOL_SPECS,
    BetNotFoundError,
    CustomerOutcomeNotFoundError,
    DecisionNotFoundError,
    EvidenceItemType,
    EvidenceNotFoundError,
    JobNotFoundError,
    JobStage,
    MemoDecisionNotFoundError,
    OdiError,
    ODIService,
    OutcomeNotFoundError,
    OutcomeStatementError,
    Rejection,
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
from agentic_odi_core import (
    outcome_delta as outcome_delta_read,
)
from agentic_odi_core import (
    render_memo as render_memo_text,
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


def _bet_not_found(bet_id: str | None) -> str:
    return f"Error: Bet with ID {bet_id} not found."


def _segment_not_found(segment_id: str | None) -> str:
    return f"Error: Segment with ID {segment_id} not found."


def _strategy_not_found(strategy_id: str | None) -> str:
    return f"Error: Strategy with ID {strategy_id} not found."


def _first_line(text: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped
    return ""


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
    importance_n: int | None = None,
    satisfaction_n: int | None = None,
    score_method: str = "estimate",
) -> str:
    try:
        outcome = service.add_outcome(
            job_id=job_id,
            statement=statement,
            importance=importance,
            satisfaction=satisfaction,
            step_id=step_id,
            importance_n=importance_n,
            satisfaction_n=satisfaction_n,
            score_method=score_method,  # type: ignore[arg-type]
        )
    except JobNotFoundError:
        return f"Error: Job with ID {job_id} not found."
    except StepNotFoundError:
        return _step_not_found(step_id)
    except ValueOutOfRangeError:
        return "Error: importance and satisfaction must be between 1.0 and 10.0"
    except OutcomeStatementError as exc:
        return f"Error: {exc}"
    except ValidationError as exc:
        return f"Error: {_first_line(str(exc))}"
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
    importance_n: int | None = None,
    satisfaction_n: int | None = None,
    score_method: str | None = None,
    at: str | None = None,
    note: str | None = None,
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
    if importance_n is not None:
        updates["importance_n"] = importance_n
    if satisfaction_n is not None:
        updates["satisfaction_n"] = satisfaction_n
    if score_method is not None:
        updates["score_method"] = score_method
    try:
        updated = service.update_outcome(outcome_id, updates, at=at, note=note)
    except OutcomeNotFoundError:
        return _outcome_not_found(outcome_id)
    except OutcomeStatementError as exc:
        return f"Error: {exc}"
    except ValueOutOfRangeError:
        return "Error: importance and satisfaction must be between 1.0 and 10.0"
    except ValidationError as exc:
        return f"Error: {_first_line(str(exc))}"
    return f"Outcome updated successfully: {updated.model_dump_json()}"


@mcp.tool
def set_outcome_value(
    outcome_id: str,
    estimate: float | None,
    unit: str | None = None,
    basis: str = "estimate",
    n: int | None = None,
    source: str | None = None,
) -> str:
    """Record what an opportunity is worth, with its basis (W1/ALH-64).

    Pass ``estimate=None`` to clear a value. A ``market`` or ``pilot`` basis
    requires a ``source``. The estimate is a judgement the caller supplies; it is
    never derived from the opportunity score.
    """
    try:
        updated = service.set_outcome_value(
            outcome_id,
            estimate,
            unit=unit,  # type: ignore[arg-type]
            basis=basis,  # type: ignore[arg-type]
            n=n,
            source=source,
        )
    except OutcomeNotFoundError:
        return _outcome_not_found(outcome_id)
    except (OdiError, ValueError) as exc:
        return f"Error: {_first_line(str(exc))}"
    return f"Outcome value updated successfully: {updated.model_dump_json()}"


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
def compare_outcomes(outcome_ids: list[str]) -> str:
    """Align two or three outcomes on the same axes.

    One row per metric, one column per outcome, in the given order. A metric
    nobody measured renders the literal "not measured"; a real recorded 0 stays
    0. The tool never declares a winner.
    """
    try:
        comparison = service.compare_outcomes(outcome_ids)
    except OutcomeNotFoundError as exc:
        return _outcome_not_found(exc.outcome_id)
    except (OdiError, ValueError) as exc:
        return f"Error: {exc}"
    return json.dumps(
        {
            "columns": list(comparison.columns),
            "statements": list(comparison.statements),
            "rows": [
                {"metric": row.metric, "label": row.label, "cells": list(row.cells)}
                for row in comparison.rows
            ],
        }
    )


@mcp.tool
def get_roadmap(job_id: str, horizon: int = 4, today: str | None = None) -> str:
    """Derive a job's outcome roadmap from its recorded decisions.

    One entry per chosen outcome, grouped by the quarter its decision was made.
    An outcome with no decision is excluded and counted, with its reason. A
    baseline nobody measured renders "not measured", never 0. ``today`` is
    optional so a caller can pin the window; when omitted the current UTC date
    is used.
    """
    pinned: date | None = None
    if today:
        try:
            pinned = date.fromisoformat(today)
        except ValueError:
            return f"Error: today must be an ISO-8601 date, got {today!r}"
    try:
        roadmap = service.build_roadmap(job_id, horizon=horizon, today=pinned)
    except JobNotFoundError:
        return job_not_found(job_id)
    except (OdiError, ValueError) as exc:
        return f"Error: {exc}"
    return json.dumps(
        {
            "entries": [
                {
                    "period": entry.period,
                    "outcome_id": entry.outcome_id,
                    "statement": entry.statement,
                    "decision_id": entry.decision_id,
                    "baseline": entry.baseline,
                    "target": entry.target,
                }
                for entry in roadmap.entries
            ],
            "undecided_count": roadmap.undecided_count,
            "horizon_excluded_count": roadmap.horizon_excluded_count,
            "superseded_excluded_count": roadmap.superseded_excluded_count,
            "horizon": roadmap.horizon,
            "exclusion_note": roadmap.exclusion_note(),
        }
    )


@mcp.tool
async def record_decision(
    ctx: Context,
    job_id: str,
    chosen_outcome_ids: list[str],
    rationale: str,
    decided_by: str,
    decided_at: str,
    rejected: list[dict[str, Any]] | None = None,
    confidence: str = "medium",
    supersedes: str | None = None,
) -> str:
    await ctx.report_progress(0, 2, "Recording the decision")
    rejections: list[Rejection] = []
    for item in rejected or []:
        if not isinstance(item, dict) or "outcome_id" not in item:
            return "Error: each rejected option needs an outcome_id and a reason"
        rejections.append(
            Rejection(outcome_id=str(item["outcome_id"]), reason=str(item.get("reason", "")))
        )
    try:
        decision = service.record_decision(
            job_id=job_id,
            chosen_outcome_ids=chosen_outcome_ids,
            rationale=rationale,
            decided_by=decided_by,
            decided_at=decided_at,
            rejected=rejections,
            confidence=confidence,
            supersedes=supersedes,
        )
    except JobNotFoundError:
        return job_not_found(job_id)
    except OutcomeNotFoundError as exc:
        return _outcome_not_found(exc.outcome_id)
    except DecisionNotFoundError:
        return f"Error: decision not found: {supersedes}"
    except (OdiError, ValueError) as exc:
        return f"Error: {exc}"
    await ctx.report_progress(2, 2, "Decision recorded")
    return f"Decision recorded successfully: {decision.model_dump_json()}"


@mcp.tool
def get_decision(decision_id: str) -> str:
    decision = service.get_decision(decision_id)
    if decision is None:
        return f"Error: decision not found: {decision_id}"
    return decision.model_dump_json()


@mcp.tool
def list_decisions(job_id: str, limit: int | None = None, offset: int = 0) -> str:
    if service.get_job(job_id) is None:
        return job_not_found(job_id)
    decisions = service.list_decisions(job_id, limit=limit, offset=offset)
    return json.dumps([d.model_dump(mode="json") for d in decisions])


@mcp.tool
def review_decision(decision_id: str, today: str) -> str:
    """Re-examine a past decision against today's numbers."""
    try:
        parsed_today = date.fromisoformat(today)
    except ValueError:
        return "Error: today must be an ISO-8601 date"
    try:
        review = service.review_decision(decision_id, today=parsed_today)
    except DecisionNotFoundError:
        return f"Error: decision not found: {decision_id}"
    payload = {
        "decision_id": review.decision_id,
        "job_id": review.job_id,
        "decided_at": review.decided_at,
        "days_elapsed": review.days_elapsed,
        "stale": review.stale,
        "summary": review.summary(),
        "outcomes": [
            {
                "outcome_id": o.outcome_id,
                "statement": o.statement,
                "state": o.state,
                "satisfaction_change": o.satisfaction_change,
                "importance_change": o.importance_change,
                "opportunity_change": o.opportunity_change,
            }
            for o in review.outcomes
        ],
    }
    return json.dumps(payload)


@mcp.tool
def render_memo(decision_id: str) -> str:
    """Assemble the decision memo from what is already recorded."""
    try:
        memo = service.build_memo(decision_id)
    except MemoDecisionNotFoundError:
        return f"Error: decision not found: {decision_id}"
    return render_memo_text(memo)


@mcp.tool
def get_outcome_history(outcome_id: str) -> str:
    if service.get_outcome(outcome_id) is None:
        return _outcome_not_found(outcome_id)
    snapshots = service.list_score_snapshots(outcome_id)
    return json.dumps([s.model_dump(mode="json") for s in snapshots])


@mcp.tool
def get_outcome_delta(outcome_id: str, since: str | None = None) -> str:
    if service.get_outcome(outcome_id) is None:
        return _outcome_not_found(outcome_id)
    delta = outcome_delta_read(service.list_score_snapshots(), outcome_id, since=since)
    if delta is None:
        return json.dumps(None)
    return json.dumps(
        {
            "importance": delta.importance,
            "satisfaction": delta.satisfaction,
            "opportunity": delta.opportunity,
            "direction": delta.direction,
        }
    )


@mcp.tool
def record_bet(
    decision_id: str,
    outcome_id: str,
    hypothesis: str,
    target: float,
    measure_by: str,
    baseline: float | None = None,
) -> str:
    try:
        bet = service.record_bet(
            decision_id,
            outcome_id,
            hypothesis,
            target,
            measure_by,
            baseline=baseline,
        )
    except DecisionNotFoundError:
        return f"Error: decision not found: {decision_id}"
    except OutcomeNotFoundError:
        return _outcome_not_found(outcome_id)
    except (OdiError, ValueError) as exc:
        return f"Error: {exc}"
    return f"Bet recorded successfully: {bet.model_dump_json()}"


@mcp.tool
def get_bet(bet_id: str) -> str:
    bet = service.get_bet(bet_id)
    if bet is None:
        return _bet_not_found(bet_id)
    return bet.model_dump_json()


@mcp.tool
def list_bets(
    job_id: str | None = None,
    decision_id: str | None = None,
    limit: int | None = None,
    offset: int = 0,
) -> str:
    bets = service.list_bets(job_id, decision_id, limit=limit, offset=offset)
    return json.dumps([b.model_dump(mode="json") for b in bets])


@mcp.tool
def advance_bet(bet_id: str, status: str, at: str | None = None) -> str:
    try:
        bet = service.advance_bet(bet_id, status, at=at)
    except BetNotFoundError:
        return _bet_not_found(bet_id)
    except (OdiError, ValueError) as exc:
        return f"Error: {exc}"
    return f"Bet advanced successfully: {bet.model_dump_json()}"


@mcp.tool
def add_segment(
    job_id: str,
    name: str,
    criterion: str,
    outcome_ids: list[str],
    notes: str | None = None,
    origin: str = "manual",
) -> str:
    try:
        segment = service.add_segment(
            job_id=job_id,
            name=name,
            criterion=criterion,
            outcome_ids=outcome_ids,
            notes=notes,
            origin=origin,
        )
    except JobNotFoundError:
        return job_not_found(job_id)
    except OutcomeNotFoundError as exc:
        return _outcome_not_found(exc.outcome_id)
    except (OdiError, ValueError) as exc:
        return f"Error: {exc}"
    return f"Segment created successfully: {segment.model_dump_json()}"


@mcp.tool
def get_segment(segment_id: str) -> str:
    segment = service.get_segment(segment_id)
    if segment is None:
        return _segment_not_found(segment_id)
    return segment.model_dump_json()


@mcp.tool
def list_segments(
    job_id: str | None = None,
    limit: int | None = None,
    offset: int = 0,
) -> str:
    segments = service.list_segments(job_id, limit=limit, offset=offset)
    return json.dumps([s.model_dump(mode="json") for s in segments])


@mcp.tool
def delete_segment(segment_id: str) -> str:
    from agentic_odi_core import SegmentNotFoundError

    try:
        service.delete_segment(segment_id)
    except SegmentNotFoundError:
        return _segment_not_found(segment_id)
    return f"Segment deleted: {segment_id}"


@mcp.tool
def suggest_segments(job_id: str) -> str:
    try:
        result = service.suggest_segments(job_id)
    except JobNotFoundError:
        return job_not_found(job_id)
    return json.dumps(
        {
            "candidates": [
                {
                    "name": c.name,
                    "members": list(c.members),
                    "rationale": c.rationale,
                    "evidence_count": c.evidence_count,
                    "segment": c.segment,
                    "decile": c.decile,
                    "fingerprint": c.fingerprint,
                }
                for c in result.candidates
            ],
            "reason": result.reason,
        }
    )


@mcp.tool
def accept_segment_candidate(
    job_id: str,
    fingerprint: str,
    name: str | None = None,
    criterion: str | None = None,
) -> str:
    try:
        segment = service.accept_segment_candidate(
            job_id=job_id,
            fingerprint=fingerprint,
            name=name,
            criterion=criterion,
        )
    except JobNotFoundError:
        return job_not_found(job_id)
    except (OdiError, ValueError) as exc:
        return f"Error: {exc}"
    return f"Segment accepted: {segment.model_dump_json()}"


@mcp.tool
def get_segment_profile(segment_id: str) -> str:
    from agentic_odi_core import SegmentNotFoundError

    try:
        profile = service.segment_profile(segment_id)
    except SegmentNotFoundError:
        return _segment_not_found(segment_id)
    return json.dumps(
        {
            "segment_id": profile.segment_id,
            "segment_name": profile.segment_name,
            "total_members": profile.total_members,
            "measured_count": profile.measured_count,
            "unscored_count": profile.unscored_count,
            "missing_count": profile.missing_count,
            "underserved_count": profile.underserved_count,
            "appropriate_count": profile.appropriate_count,
            "overserved_count": profile.overserved_count,
            "top_underserved": [
                {
                    "outcome_id": e.outcome_id,
                    "statement": e.statement,
                    "score": e.score,
                    "band": e.band,
                }
                for e in profile.top_underserved
            ],
            "top_overserved": [
                {
                    "outcome_id": e.outcome_id,
                    "statement": e.statement,
                    "score": e.score,
                    "band": e.band,
                }
                for e in profile.top_overserved
            ],
            "measured_ratio": profile.measured_ratio,
            "gaps": list(profile.gaps),
        }
    )


@mcp.tool
def choose_strategy(
    segment_id: str,
    kind: str,
    rationale: str,
    expected_effect: str,
    chosen_at: str | None = None,
) -> str:
    from agentic_odi_core import SegmentNotFoundError

    try:
        strategy = service.choose_strategy(
            segment_id=segment_id,
            kind=kind,
            rationale=rationale,
            expected_effect=expected_effect,
            chosen_at=chosen_at,
        )
    except SegmentNotFoundError:
        return _segment_not_found(segment_id)
    except (OdiError, ValueError) as exc:
        return f"Error: {exc}"
    return f"Strategy recorded: {strategy.model_dump_json()}"


@mcp.tool
def get_strategy(strategy_id: str) -> str:
    strategy = service.get_strategy(strategy_id)
    if strategy is None:
        return _strategy_not_found(strategy_id)
    return strategy.model_dump_json()


@mcp.tool
def list_strategies(
    segment_id: str | None = None,
    limit: int | None = None,
    offset: int = 0,
) -> str:
    strategies = service.list_strategies(segment_id, limit=limit, offset=offset)
    return json.dumps([s.model_dump(mode="json") for s in strategies])


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
