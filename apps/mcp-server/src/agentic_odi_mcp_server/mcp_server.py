"""Agentic ODI MCP Server (FastMCP)."""

import argparse
import asyncio
import json
import os
import signal
import sys
from collections.abc import AsyncIterator, Mapping, Sequence
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any

from agentic_odi_core import (
    ODI_ASSISTANT_PROMPT,
    ODI_FRAMEWORK_GUIDELINES,
    TOOL_SPECS,
    ClaimCheckError,
    CustomerOutcomeNotFoundError,
    EvidenceItemType,
    EvidenceNotFoundError,
    InvalidOutcomeStatementError,
    JobNotFoundError,
    JobStage,
    OdiError,
    ODIService,
    OutcomeNotFoundError,
    OutcomeStatementError,
    ProposalStatus,
    Repository,
    ScheduledWorkNotFoundError,
    SignalNotFoundError,
    StepNotFoundError,
    ToolName,
    ValueOutOfRangeError,
    build_repository,
    capability_manifest,
    capability_summary,
    compute_opportunity_score,
    error_envelope,
    evaluate_outcome_statement,
    invalid_strategy_request,
    job_not_found,
    odi_schema,
    scheduled_work_not_found,
)
from agentic_odi_core import (
    customer_outcome_not_found as _cust_not_found,
)
from fastmcp import Context, FastMCP
from pydantic import ValidationError

SERVER_NAME = "Agentic ODI"

#: Declaration surface, never served. The `@mcp.tool` and `@mcp.prompt` functions
#: park here so the tool surface stays one readable list for
#: `website/tools/extract.py` and the contract test, and `create_server()` hands
#: these components to the instance that actually serves them. It holds no store
#: and runs no lifespan.
mcp = FastMCP(SERVER_NAME)


@dataclass
class _Store:
    """One built store: the repository, the service over it, and its close flag."""

    repository: Repository
    service: ODIService
    closed: bool = False

    def close(self) -> None:
        """Flush and close. Safe to call more than once."""
        if self.closed:
            return
        self.closed = True
        try:
            self.repository.commit()
        finally:
            self.repository.close()


_active_store: _Store | None = None


def _store() -> _Store:
    """The store this process built. Only `create_server()` can build one."""
    if _active_store is None:
        raise RuntimeError(
            "no store is built: create_server() builds it, and main() calls it when "
            "the process starts"
        )
    return _active_store


def _service() -> ODIService:
    """The service every tool body talks to."""
    return _store().service


def create_server(repository: Repository | None = None) -> FastMCP:
    """Build the store and return the server that serves it.

    The sidecar already answers "when is the store opened?" this way —
    `agentic_odi_studio_api.create_app(repo=None)` — so the repository arrives from
    the caller, or from `build_repository()`, which is what reads `AGENTIC_ODI_DB`
    and defaults to `~/.agentic-odi/odi.db`. Importing this module does neither.
    """
    global _active_store
    repo = build_repository() if repository is None else repository
    _active_store = _Store(repository=repo, service=ODIService(repo))
    return FastMCP(SERVER_NAME, providers=[mcp.local_provider], lifespan=_lifespan)


def shutdown_store() -> None:
    """Flush and close this process's store; a no-op before one was built."""
    if _active_store is not None:
        _active_store.close()


@asynccontextmanager
async def _lifespan(_server: FastMCP) -> AsyncIterator[None]:
    try:
        yield
    finally:
        shutdown_store()


def _fail(exc: BaseException, sentence: str | None = None) -> str:
    """The one way a tool answers a failure: an envelope and the same sentence.

    ``error_envelope`` chooses the code from the exception's kind, so a client
    branches without reading English. ``sentence`` is where a handler has a
    wording clients already quote back (``Job not found: <id>`` from the shared
    message helpers): it travels verbatim, so adding a code never rewrites the
    prose a text-only client sees.
    """
    human = sentence if sentence is not None else f"Error: {exc}"
    body = human[len("Error:") :].strip() if human.lower().startswith("error:") else human
    return json.dumps({"error": {**error_envelope(exc), "message": body}, "message": human})


def _step_not_found(step_id: str | None) -> str:
    return _fail(StepNotFoundError(str(step_id)), f"Error: Step with ID {step_id} not found.")


def _outcome_not_found(outcome_id: str | None) -> str:
    return _fail(
        OutcomeNotFoundError(str(outcome_id)), f"Error: Outcome with ID {outcome_id} not found."
    )


def _evidence_not_found(evidence_id: str, hint: str | None = None) -> str:
    message = f"Error: Evidence with ID {evidence_id} not found."
    if hint:
        message = f"{message} {hint}"
    return _fail(EvidenceNotFoundError(evidence_id, hint), message)


@mcp.prompt
def odi_assistant_prompt() -> str:
    return ODI_ASSISTANT_PROMPT


@mcp.tool
def add_job(name: str, description: str | None = None) -> str:
    job = _service().add_job(name=name, description=description)
    return f"Job created successfully: {job.model_dump_json()}"


@mcp.tool
def get_jobs(limit: int | None = None, offset: int = 0) -> str:
    """List jobs.

    ``limit`` caps how many jobs are returned and ``offset`` skips that many
    first, so a client can walk a long list without re-reading all of it.
    """
    jobs = _service().get_jobs(limit=limit, offset=offset)
    return json.dumps([job.model_dump() for job in jobs])


@mcp.tool
def get_job(job_id: str) -> str:
    job = _service().get_job(job_id)
    if job is None:
        return _fail(JobNotFoundError(job_id), f"Error: Job with ID {job_id} not found.")
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
        step = _service().add_step(
            job_id=job_id,
            name=name,
            order=order,
            stage=stage,
            allow_empty_job_map=allow_empty_job_map,
        )
    except JobNotFoundError:
        return _fail(JobNotFoundError(job_id), job_not_found(job_id))
    except ValueOutOfRangeError as exc:
        return _fail(exc)
    except OdiError as exc:
        return _fail(exc)
    return f"Step created successfully: {step.model_dump_json()}"


@mcp.tool
def get_job_map(job_id: str, limit: int | None = None, offset: int = 0) -> str:
    job = _service().get_job(job_id)
    if job is None:
        return _fail(JobNotFoundError(job_id), f"Error: Job with ID {job_id} not found.")
    steps = _service().get_job_map(job_id, limit=limit, offset=offset)
    return json.dumps([step.model_dump() for step in steps])


@mcp.tool
def add_outcome(
    job_id: str,
    statement: str,
    importance: float | None = None,
    satisfaction: float | None = None,
    step_id: str | None = None,
    claim_check: dict[str, Any] | None = None,
) -> str:
    """Add a desired Outcome to a Job.

    A score needs the questions behind it. Put three questions to the person —
    four when the claim is broad — before any number, and let them answer or skip
    with a reason; never answer your own question and count it.

    When you supply ``importance`` or ``satisfaction`` you must also supply
    ``claim_check`` — the questions you asked and what came back::

        {
          "asked": ["How often does this happen?", "What do you do today?"],
          "answers": ["Weekly", "A spreadsheet"],
          "skips": [{"question": "What does it cost?", "reason": "never measured"}]
        }

    Each skip needs a reason. To record an outcome before you have asked, omit
    both scores: an unscored outcome is legal, a bare number is not.
    """
    if _service().get_job(job_id) is None:
        return _fail(JobNotFoundError(job_id), f"Error: Job with ID {job_id} not found.")
    for score in (importance, satisfaction):
        if score is not None and not (1.0 <= score <= 10.0):
            return _fail(
                ValueOutOfRangeError("importance and satisfaction must be between 1.0 and 10.0")
            )
    scored = importance is not None or satisfaction is not None
    if scored and claim_check is None:
        return _fail(
            ClaimCheckError(
                "add_outcome cannot record a score without a claim_check. "
                "Ask the customer the questions that produce this number, then pass "
                "claim_check with asked/answers/skips (each skip needs a reason). "
                "To record an outcome before asking, omit importance and satisfaction."
            )
        )
    try:
        outcome = _service().add_outcome(
            job_id=job_id,
            statement=statement,
            importance=importance,
            satisfaction=satisfaction,
            step_id=step_id,
            claim_check=claim_check,
        )
    except JobNotFoundError:
        return _fail(JobNotFoundError(job_id), f"Error: Job with ID {job_id} not found.")
    except StepNotFoundError:
        return _step_not_found(step_id)
    except ValueOutOfRangeError as exc:
        return _fail(exc, "Error: importance and satisfaction must be between 1.0 and 10.0")
    except ClaimCheckError as exc:
        return _fail(exc)
    except OutcomeStatementError as exc:
        return _fail(exc)
    return f"Outcome created successfully: {outcome.model_dump_json()}"


@mcp.tool
def get_outcomes(
    job_id: str,
    step_id: str | None = None,
    limit: int | None = None,
    offset: int = 0,
    sort: str = "opportunity_score",
) -> str:
    job = _service().get_job(job_id)
    if job is None:
        return _fail(JobNotFoundError(job_id), f"Error: Job with ID {job_id} not found.")
    outcomes = _service().get_outcomes(
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
        co = _service().add_customer_outcome(
            job_id=job_id,
            customer_value=customer_value,
            business_value=business_value,
            step_id=step_id,
        )
    except JobNotFoundError:
        return _fail(JobNotFoundError(job_id), f"Error: Job with ID {job_id} not found.")
    except StepNotFoundError:
        return _step_not_found(step_id)
    except ValidationError as e:
        return _fail(e)
    return f"Customer outcome created successfully: {co.model_dump_json()}"


@mcp.tool
def get_customer_outcome(outcome_id: str) -> str:
    try:
        co = _service().get_customer_outcome(outcome_id)
    except CustomerOutcomeNotFoundError:
        return _fail(CustomerOutcomeNotFoundError(outcome_id), _cust_not_found(outcome_id))
    return co.model_dump_json()


@mcp.tool
def list_customer_outcomes(
    job_id: str | None = None, limit: int | None = None, offset: int = 0
) -> str:
    """List customer outcomes, optionally for one job and one page at a time."""
    outcomes = _service().list_customer_outcomes(job_id=job_id, limit=limit, offset=offset)
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
        co = _service().get_customer_outcome(outcome_id)
    except CustomerOutcomeNotFoundError:
        return _fail(CustomerOutcomeNotFoundError(outcome_id), _cust_not_found(outcome_id))
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
        co2 = _service().update_customer_outcome(outcome_id, updates)
    except CustomerOutcomeNotFoundError:
        return _fail(CustomerOutcomeNotFoundError(outcome_id), _cust_not_found(outcome_id))
    except ValidationError as e:
        return _fail(e)
    return f"Customer outcome updated successfully: {co2.model_dump_json()}"


@mcp.tool
def delete_customer_outcome(outcome_id: str) -> str:
    try:
        _service().delete_customer_outcome(outcome_id)
    except CustomerOutcomeNotFoundError:
        return _fail(CustomerOutcomeNotFoundError(outcome_id), _cust_not_found(outcome_id))
    return f"Customer outcome deleted successfully: {outcome_id}"


@mcp.tool
def compute_opportunity(importance: float, satisfaction: float) -> str:
    if not (1.0 <= importance <= 10.0) or not (1.0 <= satisfaction <= 10.0):
        return _fail(
            ValueOutOfRangeError("importance and satisfaction must be between 1.0 and 10.0")
        )
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
    if _store().repository.health():
        return json.dumps({"status": "ok", "store": "accessible"})
    return json.dumps({"status": "degraded", "store": "locked"})


@mcp.tool
def get_step(step_id: str) -> str:
    step = _service().get_step(step_id)
    if step is None:
        return _step_not_found(step_id)
    return step.model_dump_json()


@mcp.tool
def get_outcome(outcome_id: str) -> str:
    outcome = _service().get_outcome(outcome_id)
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
        job = _service().update_job(job_id, updates)
    except JobNotFoundError:
        return _fail(JobNotFoundError(job_id), job_not_found(job_id))
    return f"Job updated successfully: {job.model_dump_json()}"


@mcp.tool
def delete_job(job_id: str) -> str:
    try:
        _service().delete_job(job_id)
    except JobNotFoundError:
        return _fail(JobNotFoundError(job_id), job_not_found(job_id))
    return f"Job deleted successfully: {job_id}"


@mcp.tool
def update_step(step_id: str, name: str | None = None, order: int | None = None) -> str:
    updates: dict = {}
    if name is not None:
        updates["name"] = name
    if order is not None:
        updates["order"] = order
    try:
        step = _service().update_step(step_id, updates)
    except StepNotFoundError:
        return _step_not_found(step_id)
    return f"Step updated successfully: {step.model_dump_json()}"


@mcp.tool
def delete_step(step_id: str) -> str:
    try:
        _service().delete_step(step_id)
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
        updated = _service().update_outcome(outcome_id, updates)
    except OutcomeNotFoundError:
        return _outcome_not_found(outcome_id)
    except OutcomeStatementError as exc:
        return _fail(exc)
    except ValueOutOfRangeError as exc:
        return _fail(exc, "Error: importance and satisfaction must be between 1.0 and 10.0")
    return f"Outcome updated successfully: {updated.model_dump_json()}"


@mcp.tool
def delete_outcome(outcome_id: str) -> str:
    try:
        _service().delete_outcome(outcome_id)
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
        evidence = _service().add_evidence(
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
        return _fail(JobNotFoundError(job_id or ""), job_not_found(job_id or ""))
    except StepNotFoundError:
        return _step_not_found(step_id)
    except OutcomeNotFoundError:
        return _outcome_not_found(outcome_id)
    except (OdiError, ValueError) as exc:
        return _fail(exc)
    await ctx.report_progress(2, 2, "Evidence stored")
    return f"Evidence created successfully: {evidence.model_dump_json()}"


@mcp.tool
def get_evidence(evidence_id: str) -> str:
    evidence = _service().get_evidence(evidence_id)
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
    items = _service().list_evidence(
        job_id=job_id, step_id=step_id, outcome_id=outcome_id, limit=limit, offset=offset
    )
    return json.dumps([item.model_dump() for item in items])


@mcp.tool
def delete_evidence(evidence_id: str) -> str:
    try:
        _service().delete_evidence(evidence_id)
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
        artifact = _service().promote_evidence(
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
        return _fail(JobNotFoundError(job_id or ""), job_not_found(job_id or ""))
    except StepNotFoundError:
        return _step_not_found(None)
    except OutcomeNotFoundError:
        return _outcome_not_found(None)
    except ValueOutOfRangeError as exc:
        return _fail(exc, "Error: importance and satisfaction must be between 1.0 and 10.0")
    except (OdiError, ValueError) as exc:
        return _fail(exc)
    label = "Job" if target == "job" else "Outcome"
    return f"{label} created successfully: {artifact.model_dump_json()}"


@mcp.tool
async def evaluate_outcome(ctx: Context, statement: str, job_id: str | None = None) -> str:
    await ctx.report_progress(0, 2, "Evaluating the statement")
    result = evaluate_outcome_statement(statement)
    if job_id is not None:
        if _service().get_job(job_id) is None:
            return _fail(JobNotFoundError(job_id), job_not_found(job_id))
        result["job_id"] = job_id
        result["existing_outcomes"] = [
            {
                "id": outcome.id,
                "statement": outcome.statement,
                "opportunity_score": outcome.opportunity_score,
            }
            for outcome in _service().get_outcomes(job_id)
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
        work = _service().schedule_work(
            name=name,
            schedule_expression=schedule_expression,
            agent_id=agent_id,
            trigger_type=trigger_type,
            payload=payload,
            job_id=job_id,
        )
    except JobNotFoundError:
        return _fail(JobNotFoundError(job_id or ""), job_not_found(job_id or ""))
    except ValueError as exc:
        return _fail(exc)
    return f"Scheduled work created successfully: {work.model_dump_json()}"


@mcp.tool
def get_scheduled_work(work_id: str) -> str:
    try:
        work = _service().get_scheduled_work(work_id)
    except ScheduledWorkNotFoundError:
        return _fail(ScheduledWorkNotFoundError(work_id), scheduled_work_not_found(work_id))
    return work.model_dump_json()


@mcp.tool
def list_scheduled_work(
    job_id: str | None = None,
    status: str | None = None,
) -> str:
    items = _service().list_scheduled_work(job_id=job_id, status=status)
    return json.dumps([item.model_dump() for item in items])


@mcp.tool
def cancel_scheduled_work(work_id: str) -> str:
    try:
        work = _service().cancel_scheduled_work(work_id)
    except ScheduledWorkNotFoundError:
        return _fail(ScheduledWorkNotFoundError(work_id), scheduled_work_not_found(work_id))
    return f"Scheduled work cancelled successfully: {work.model_dump_json()}"


@mcp.tool
def trigger_scheduled_work(work_id: str) -> str:
    try:
        work = _service().trigger_scheduled_work(work_id)
    except ScheduledWorkNotFoundError:
        return _fail(ScheduledWorkNotFoundError(work_id), scheduled_work_not_found(work_id))
    return f"Scheduled work dispatched: {work.model_dump_json()}"


@mcp.tool
def get_odi_schema() -> str:
    return json.dumps(odi_schema())


@mcp.tool
def list_signals(unread_only: bool = False, limit: int = 50) -> str:
    """List recorded signals, newest first; ``unread_only`` trims to the badge."""
    signals = _service().list_signals(unread_only=unread_only, limit=limit)
    return json.dumps([signal.model_dump(mode="json") for signal in signals])


@mcp.tool
def mark_signal_read(signal_id: str) -> str:
    try:
        signal = _service().mark_signal_read(signal_id)
    except SignalNotFoundError:
        return _fail(
            SignalNotFoundError(signal_id), f"Error: Signal with ID {signal_id} not found."
        )
    return f"Signal marked as read: {signal.model_dump_json()}"


@mcp.tool
def dismiss_signal(signal_id: str) -> str:
    try:
        signal = _service().dismiss_signal(signal_id)
    except SignalNotFoundError:
        return _fail(
            SignalNotFoundError(signal_id), f"Error: Signal with ID {signal_id} not found."
        )
    return f"Signal dismissed: {signal.model_dump_json()}"


@mcp.tool
def segment_market(job_id: str | None = None, people: str | None = None) -> str:
    """Cluster scored outcomes into outcome-based segments (Stage 5).

    Segmentation is by job and job-map step, never by who the customer is:
    ``people`` is a label in the customer's own words when they have supplied
    one, and a group derived from the outcomes alone is marked inferred.
    Re-running updates the same segment rather than adding a second copy.
    """
    try:
        segments = _service().segment_market(job_id=job_id, people=people)
    except JobNotFoundError:
        return _fail(JobNotFoundError(job_id or ""), job_not_found(job_id or ""))
    return json.dumps([segment.model_dump(mode="json") for segment in segments])


@mcp.tool
def get_segments(job_id: str | None = None) -> str:
    """List stored segments, optionally scoped to one job.

    Empty until ``segment_market`` has run: a segment is derived from evidence,
    never typed in.
    """
    segments = _service().list_segments(job_id=job_id)
    return json.dumps([segment.model_dump(mode="json") for segment in segments])


@mcp.tool
def open_study(job_id: str, name: str, wave: int, method_notes: str | None = None) -> str:
    """Open a named study — one pass over a Job at a given wave number.

    A study opens ``planned``. The same ``(job_id, name)`` may not repeat a wave,
    so an accidental re-run is refused while a deliberate later wave is allowed.
    """
    try:
        study = _service().open_study(
            job_id=job_id, name=name, wave=wave, method_notes=method_notes
        )
    except JobNotFoundError:
        return _fail(JobNotFoundError(job_id), job_not_found(job_id))
    except OdiError as exc:
        return _fail(exc)
    return json.dumps(study.model_dump(mode="json"))


@mcp.tool
def list_studies(job_id: str | None = None) -> str:
    """List stored studies, optionally scoped to one job.

    Empty until ``open_study`` has run: a study is opened, never typed in.
    """
    studies = _service().list_studies(job_id=job_id)
    return json.dumps([study.model_dump(mode="json") for study in studies])


@mcp.tool
def get_strategy() -> str:
    """The latest recorded strategy, or ``null`` when Stage 6 has not run."""
    strategy = _service().get_strategy()
    if strategy is None:
        return "null"
    return json.dumps(strategy.model_dump(mode="json"))


@mcp.tool
def propose_strategy(job_id: str | None = None) -> str:
    """Recommend the one innovation path the evidence supports (Stage 6).

    Returns the chosen path with every path it beat and why. When no path has
    evidence behind it this refuses rather than inventing a bet.
    """
    try:
        strategy = _service().propose_strategy(job_id=job_id)
    except JobNotFoundError:
        return _fail(JobNotFoundError(job_id or ""), job_not_found(job_id or ""))
    except OdiError as exc:
        return _fail(exc, f"Error: {invalid_strategy_request(str(exc))}")
    return json.dumps(strategy.model_dump(mode="json"))


@mcp.tool
def propose_outcome(evidence_id: str) -> str:
    """Propose a desired outcome mined from an evidence record (Stage 2).

    The default heuristic strategy (deterministic, offline, no LLM) reads the
    evidence, routes it to a job and step, extracts a candidate ODI-format
    statement, and suggests importance/satisfaction. Nothing is written to the
    ODI store until the proposal is approved via approve_proposal.
    """
    try:
        proposal = _service().propose_outcome_from_evidence(evidence_id)
    except EvidenceNotFoundError:
        return _fail(
            EvidenceNotFoundError(evidence_id), f"Error: evidence {evidence_id} not found."
        )
    except ValidationError as exc:
        return _fail(exc)
    return json.dumps(proposal.model_dump(mode="json"))


@mcp.tool
def list_proposals(status: str | None = None) -> str:
    """List outcome proposals, optionally filtered by status.

    Status values: proposed, approved, rejected, edited. Omit status to list
    all proposals.
    """
    try:
        proposal_status = ProposalStatus(status) if status is not None else None
    except ValueError as exc:
        return _fail(
            exc, f"Error: invalid status '{status}'. Use proposed, approved, rejected, or edited."
        )
    proposals = _service().list_proposals(status=proposal_status)
    return json.dumps([p.model_dump(mode="json") for p in proposals])


@mcp.tool
def approve_proposal(
    proposal_id: str,
    statement: str | None = None,
    importance: float | None = None,
    satisfaction: float | None = None,
) -> str:
    """Approve a proposal and write it as an Outcome through add_outcome.

    If statement is provided, the edited statement is validated before writing.
    Importance/satisfaction default to the proposal's suggested values.
    """
    try:
        outcome = _service().approve_proposal(
            proposal_id, statement=statement, importance=importance, satisfaction=satisfaction
        )
    except ValidationError as exc:
        return _fail(exc)
    except InvalidOutcomeStatementError as exc:
        return _fail(exc)
    return json.dumps(outcome.model_dump(mode="json"))


@mcp.tool
def reject_proposal(proposal_id: str) -> str:
    """Reject a proposal. Nothing is written to the ODI store."""
    try:
        proposal = _service().reject_proposal(proposal_id)
    except ValidationError as exc:
        return _fail(exc)
    return json.dumps(proposal.model_dump(mode="json"))


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


def validate_at_startup(server: FastMCP) -> None:
    """Refuse to serve when the registry disagrees with the contract."""
    errors = validate_tool_specs(tools=asyncio.run(server.list_tools()))
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
    server = create_server()
    validate_at_startup(server)
    setup_graceful_shutdown()
    server.run(transport="http", port=resolve_port(args.port))


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
