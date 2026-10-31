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
    Bet,
    BusinessValue,
    CustomerOutcome,
    CustomerValue,
    Decision,
    DisproofCondition,
    Evidence,
    Job,
    NotificationRule,
    Outcome,
    ScheduledWork,
    ScoreSnapshot,
    Signal,
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
    "Decision": Decision,
    "ScoreSnapshot": ScoreSnapshot,
    "Bet": Bet,
    "DisproofCondition": DisproofCondition,
    "Signal": Signal,
    "NotificationRule": NotificationRule,
}


def odi_schema() -> dict[str, Any]:
    """Return the JSON schema for each ODI entity keyed by model name."""
    return {name: model.model_json_schema() for name, model in _SCHEMA_MODELS.items()}
