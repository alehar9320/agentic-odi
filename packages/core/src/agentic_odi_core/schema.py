"""Canonical JSON schemas for every ODI entity.

These schemas are the machine-readable contract used by agents, connectors, and
CLI consumers. They are derived from the Pydantic models so there is exactly one
definition of the ODI dataset.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from agentic_odi_core.models import (
    JOB_STAGE_ORDER,
    V2MOM,
    BusinessValue,
    CustomerOutcome,
    CustomerValue,
    Evidence,
    Interview,
    InterviewQuote,
    Job,
    JobStage,
    Outcome,
    OutcomeCandidate,
    ScheduledWork,
    Step,
    ValueMetric,
)

_SCHEMA_MODELS: dict[str, type[BaseModel]] = {
    "Job": Job,
    "Step": Step,
    "Outcome": Outcome,
    "ValueMetric": ValueMetric,
    "CustomerValue": CustomerValue,
    "BusinessValue": BusinessValue,
    "CustomerOutcome": CustomerOutcome,
    "Evidence": Evidence,
    "V2MOM": V2MOM,
    "ScheduledWork": ScheduledWork,
    "Interview": Interview,
    "InterviewQuote": InterviewQuote,
    "OutcomeCandidate": OutcomeCandidate,
}

# One sentence per stage, so every surface that names a stage explains it the
# same way. The order lives in ``JOB_STAGE_ORDER``; this only adds copy.
JOB_STAGE_DESCRIPTIONS: dict[JobStage, str] = {
    JobStage.DEFINE: "Determine goals and criteria",
    JobStage.LOCATE: "Gather inputs and resources",
    JobStage.PREPARE: "Set up context and workspace",
    JobStage.CONFIRM: "Verify readiness to execute",
    JobStage.EXECUTE: "Carry out core job work",
    JobStage.MONITOR: "Track performance and errors",
    JobStage.MODIFY: "Adjust inputs or workflows",
    JobStage.CONCLUDE: "Finish and store outputs",
}


def odi_schema() -> dict[str, Any]:
    """Return the JSON schema for each ODI entity keyed by model name."""
    return {name: model.model_json_schema() for name, model in _SCHEMA_MODELS.items()}


def stage_catalog() -> list[dict[str, str]]:
    """The eight Universal Job Map stages, in canonical order, with display copy.

    The client renders exactly this list, so a stage added to ``JOB_STAGE_ORDER``
    reaches the screen without a component change and none can be dropped.
    """
    return [
        {
            "id": stage.value,
            "name": f"{index}. {stage.value.title()}",
            "description": JOB_STAGE_DESCRIPTIONS[stage],
        }
        for index, stage in enumerate(JOB_STAGE_ORDER, start=1)
    ]
