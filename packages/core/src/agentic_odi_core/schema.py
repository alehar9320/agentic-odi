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
    Evidence,
    Job,
    Outcome,
    ScheduledWork,
    ScoreSnapshot,
    Segment,
    Step,
    Strategy,
    ValueMetric,
)

#: The version of the canonical entity schema. It is stamped on exported
#: artifacts (M3-11.2/ALH-171) so a file says which shape it was read from. It
#: is a code-owned constant, not a measurement: bump it when a persisted field's
#: meaning changes.
SCHEMA_VERSION = 1

_SCHEMA_MODELS: dict[str, type[BaseModel]] = {
    "Job": Job,
    "Step": Step,
    "Outcome": Outcome,
    "ValueMetric": ValueMetric,
    "CustomerValue": CustomerValue,
    "BusinessValue": BusinessValue,
    "CustomerOutcome": CustomerOutcome,
    "Decision": Decision,
    "Evidence": Evidence,
    "ScoreSnapshot": ScoreSnapshot,
    "Bet": Bet,
    "V2MOM": V2MOM,
    "ScheduledWork": ScheduledWork,
    "Segment": Segment,
    "Strategy": Strategy,
}


def odi_schema() -> dict[str, Any]:
    """Return the JSON schema for each ODI entity keyed by model name."""
    return {name: model.model_json_schema() for name, model in _SCHEMA_MODELS.items()}
