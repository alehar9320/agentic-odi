"""Coverage: what the research covers, and what it does not.

A PM with six outcomes in Define and none in Conclude is about to decide on
half a job map. This module answers "is there enough research to decide?" as a
read-only report: outcomes per stage, how many are measured, how many evidence
rows stand behind them, and which stages are empty.

Two rules are fixed here because they decide every count:

* An outcome is **measured** when both ``importance`` and ``satisfaction`` are
  set. Those are the two numbers an opportunity score is built from, so an
  outcome missing either cannot be scored and is not yet measured.
* An outcome's stage is the stage of its step (``A7``'s stored field). An
  outcome with no step, or a step with no stage, is counted in an explicit
  ``unassigned`` bucket that cannot be hidden.

Nothing here writes, and nothing recomputes a stage from ``order``.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from agentic_odi_core.models import JOB_STAGE_ORDER, Evidence, JobStage, Outcome, Step


class StageCoverage(BaseModel):
    """One row of the coverage report: a stage and what it holds."""

    stage: JobStage
    outcomes: int = Field(ge=0, description="Outcomes whose step is in this stage")
    measured: int = Field(ge=0, description="Of those, outcomes with both scores set")
    quotes: int = Field(ge=0, description="Evidence rows linked to those outcomes")


class CoverageTotals(BaseModel):
    """The whole-job counts, with the unassigned bucket kept explicit."""

    outcomes: int = Field(ge=0)
    measured: int = Field(ge=0)
    quotes: int = Field(ge=0)
    unassigned_outcomes: int = Field(ge=0)
    unassigned_measured: int = Field(ge=0)
    unassigned_quotes: int = Field(ge=0)


class CoverageReport(BaseModel):
    """A job's coverage: every stage in order, the totals, and the gaps.

    ``gaps`` are the stages with **zero** outcomes. Empty is the finding; a
    stage with one thin outcome is a different problem.
    """

    job_id: str
    per_stage: list[StageCoverage]
    totals: CoverageTotals
    gaps: list[JobStage]


def _is_measured(outcome: Outcome) -> bool:
    """An outcome is measured when both ODI scores are present."""
    return outcome.importance is not None and outcome.satisfaction is not None


def _stage_of_outcome(outcome: Outcome, steps_by_id: dict[str, Step]) -> JobStage | None:
    """The stage an outcome belongs to, or ``None`` when it is unassigned.

    The stage comes from the outcome's step — the field ``A7`` stores — and
    never from recomputing ``order``.
    """
    if outcome.step_id is None:
        return None
    step = steps_by_id.get(outcome.step_id)
    return step.stage if step is not None else None


def build_coverage_report(
    job_id: str,
    steps: list[Step],
    outcomes: list[Outcome],
    evidence: list[Evidence],
) -> CoverageReport:
    """Compose a coverage report from a job's steps, outcomes, and evidence.

    The inputs are the raw reads; the caller supplies them so this stays a pure
    function that writes nothing and can be tested without a store.

    An evidence row is counted once per stage even when it is linked to several
    outcomes in that stage: the count is rows, not links, so a duplicated quote
    cannot inflate the number.
    """
    steps_by_id = {step.id: step for step in steps}

    outcomes_by_stage: dict[JobStage, list[Outcome]] = {stage: [] for stage in JOB_STAGE_ORDER}
    unassigned_outcomes: list[Outcome] = []
    for outcome in outcomes:
        stage = _stage_of_outcome(outcome, steps_by_id)
        if stage is None:
            unassigned_outcomes.append(outcome)
        else:
            outcomes_by_stage[stage].append(outcome)

    evidence_by_stage: dict[JobStage, set[str]] = {stage: set() for stage in JOB_STAGE_ORDER}
    unassigned_evidence: set[str] = set()
    outcome_stage: dict[str, JobStage | None] = {
        outcome.id: _stage_of_outcome(outcome, steps_by_id) for outcome in outcomes
    }
    for row in evidence:
        if row.outcome_id is None:
            # Evidence that names no outcome cannot stand behind a stage's
            # number; counting it here would attribute it to work it is not on.
            continue
        stage = outcome_stage.get(row.outcome_id)
        if stage is None:
            unassigned_evidence.add(row.id)
        else:
            evidence_by_stage[stage].add(row.id)

    per_stage: list[StageCoverage] = []
    for stage in JOB_STAGE_ORDER:
        held = outcomes_by_stage[stage]
        per_stage.append(
            StageCoverage(
                stage=stage,
                outcomes=len(held),
                measured=sum(1 for outcome in held if _is_measured(outcome)),
                quotes=len(evidence_by_stage[stage]),
            )
        )

    totals = CoverageTotals(
        outcomes=sum(row.outcomes for row in per_stage) + len(unassigned_outcomes),
        measured=sum(row.measured for row in per_stage)
        + sum(1 for outcome in unassigned_outcomes if _is_measured(outcome)),
        quotes=sum(row.quotes for row in per_stage) + len(unassigned_evidence),
        unassigned_outcomes=len(unassigned_outcomes),
        unassigned_measured=sum(1 for outcome in unassigned_outcomes if _is_measured(outcome)),
        unassigned_quotes=len(unassigned_evidence),
    )

    return CoverageReport(
        job_id=job_id,
        per_stage=per_stage,
        totals=totals,
        gaps=[row.stage for row in per_stage if row.outcomes == 0],
    )
