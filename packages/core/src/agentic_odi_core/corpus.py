"""A deterministic, typed study corpus for measurement and demos.

This is the one fixture builder: it produces a whole study — jobs, the eight
Universal Job Map steps per job, scored outcomes, and the evidence that backs
them — from a single size argument. Every value is derived from its index, so
two runs on two machines produce byte-identical records and a cold-open number
is comparable between them. Nothing here reads the clock or a random source.

The default shape is the reference study the cold-open budget is measured
against: 1,500 outcomes over 30 jobs, each with a complete eight-step job map
and one customer quote per outcome.

The generated records are fixtures, not research. Every evidence row carries
``source_kind="corpus"`` so a surface can label it and no reader mistakes it
for connector output.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from agentic_odi_core.models import (
    JOB_STAGE_INDEX,
    JOB_STAGE_ORDER,
    Evidence,
    Job,
    Outcome,
    Step,
    compute_opportunity_score,
)

#: The reference study size the cold-open budget is stated against.
REFERENCE_OUTCOMES = 1_500
#: Jobs in the reference study; each gets a full eight-step job map.
REFERENCE_JOBS = 30
#: Evidence rows per outcome. One quote behind each outcome.
EVIDENCE_PER_OUTCOME = 1
#: The connector kind every corpus evidence row declares.
CORPUS_SOURCE_KIND = "corpus"

_STAGE_VERBS = (
    "Define",
    "Locate",
    "Prepare",
    "Confirm",
    "Execute",
    "Monitor",
    "Modify",
    "Conclude",
)


@dataclass(frozen=True)
class Corpus:
    """A complete, typed study: the four records a canvas renders."""

    jobs: list[Job]
    steps: list[Step]
    outcomes: list[Outcome]
    evidence: list[Evidence]

    def counts(self) -> dict[str, int]:
        return {
            "jobs": len(self.jobs),
            "steps": len(self.steps),
            "outcomes": len(self.outcomes),
            "evidence": len(self.evidence),
        }

    def digest(self) -> str:
        """sha256 over every record in a fixed field order.

        Two runs of :func:`build_corpus` with the same arguments must produce
        the same digest; the determinism test compares exactly this.
        """
        payload = {
            "jobs": [job.model_dump() for job in self.jobs],
            "steps": [step.model_dump() for step in self.steps],
            "outcomes": [outcome.model_dump() for outcome in self.outcomes],
            "evidence": [record.model_dump() for record in self.evidence],
        }
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _job_id(index: int) -> str:
    return f"JOB-{index:04d}"


def _step_id(job_index: int, step_index: int) -> str:
    return f"STP-{job_index:04d}-{step_index}"


def _outcome_id(index: int) -> str:
    return f"OUT-{index:05d}"


def _evidence_id(index: int) -> str:
    return f"EVD-{index:05d}"


def build_corpus(
    outcomes: int = REFERENCE_OUTCOMES,
    jobs: int = REFERENCE_JOBS,
) -> Corpus:
    """Build the reference study deterministically.

    ``outcomes`` outcomes are spread round-robin across ``jobs`` jobs and the
    eight steps of each job map. Importance and satisfaction cycle through
    fixed integer patterns so the opportunity scores span served, appropriately
    served, and underserved, without a random source.
    """
    if outcomes < 1:
        raise ValueError("a corpus needs at least one outcome")
    if jobs < 1:
        raise ValueError("a corpus needs at least one job")
    if jobs > outcomes:
        raise ValueError("a corpus cannot have more jobs than outcomes")

    job_records = [
        Job(id=_job_id(j), name=f"Study job {j}", description=f"Corpus job {j} for measurement")
        for j in range(jobs)
    ]

    step_records: list[Step] = []
    for j in range(jobs):
        for stage in JOB_STAGE_ORDER:
            step_records.append(
                Step(
                    id=_step_id(j, JOB_STAGE_INDEX[stage]),
                    job_id=_job_id(j),
                    name=f"{JOB_STAGE_INDEX[stage]}. {_STAGE_VERBS[JOB_STAGE_INDEX[stage] - 1]} the work",
                    order=JOB_STAGE_INDEX[stage],
                    stage=stage,
                    stage_index=JOB_STAGE_INDEX[stage],
                )
            )

    outcome_records: list[Outcome] = []
    evidence_records: list[Evidence] = []
    for i in range(outcomes):
        job_index = i % jobs
        step_index = (i // jobs) % len(JOB_STAGE_ORDER) + 1
        importance = float(1 + (i % 10))
        satisfaction = float(1 + ((i * 7) % 10))
        outcome_records.append(
            Outcome(
                id=_outcome_id(i),
                job_id=_job_id(job_index),
                step_id=_step_id(job_index, step_index),
                statement=(
                    f"Minimize the time it takes to finish study task {i} "
                    f"when working in job {job_index}"
                ),
                importance=importance,
                satisfaction=satisfaction,
                opportunity_score=compute_opportunity_score(importance, satisfaction),
            )
        )
        for k in range(EVIDENCE_PER_OUTCOME):
            evidence_records.append(
                Evidence(
                    id=_evidence_id(i * EVIDENCE_PER_OUTCOME + k),
                    source_name="corpus",
                    source_kind=CORPUS_SOURCE_KIND,
                    item_type="resource",
                    name=f"Corpus quote {i}-{k}",
                    content=f"Interviewee {i} described study task {i} taking too long.",
                    job_id=_job_id(job_index),
                    step_id=_step_id(job_index, step_index),
                    outcome_id=_outcome_id(i),
                    raw={"interview": i, "speaker": f"participant-{i % 40}"},
                )
            )

    return Corpus(
        jobs=job_records,
        steps=step_records,
        outcomes=outcome_records,
        evidence=evidence_records,
    )
