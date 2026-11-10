"""Canonical JSON schemas for every ODI entity.

These schemas are the machine-readable contract used by agents, connectors, and
CLI consumers. They are derived from the Pydantic models so there is exactly one
definition of the ODI dataset.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from agentic_odi_core.models import (
    V2MOM,
    Alternative,
    AlternativeLink,
    BusinessValue,
    CustomerOutcome,
    CustomerValue,
    Evidence,
    Job,
    Outcome,
    OutcomeAlignment,
    ScheduledWork,
    ScoreSnapshot,
    Segment,
    Step,
    Strategy,
    Study,
    SurveyInputSet,
    Theme,
    ValueMetric,
)

_SCHEMA_MODELS: dict[str, type[BaseModel]] = {
    "Job": Job,
    "Step": Step,
    "Outcome": Outcome,
    "OutcomeAlignment": OutcomeAlignment,
    "ValueMetric": ValueMetric,
    "CustomerValue": CustomerValue,
    "BusinessValue": BusinessValue,
    "CustomerOutcome": CustomerOutcome,
    "Alternative": Alternative,
    "AlternativeLink": AlternativeLink,
    "Evidence": Evidence,
    "Segment": Segment,
    "Strategy": Strategy,
    "Study": Study,
    "V2MOM": V2MOM,
    "ScheduledWork": ScheduledWork,
    "ScoreSnapshot": ScoreSnapshot,
    "SurveyInputSet": SurveyInputSet,
    "Theme": Theme,
}


def odi_schema() -> dict[str, Any]:
    """Return the JSON schema for each ODI entity keyed by model name."""
    return {name: model.model_json_schema() for name, model in _SCHEMA_MODELS.items()}
