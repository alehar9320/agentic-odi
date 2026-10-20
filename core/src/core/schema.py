"""Canonical JSON schemas for every ODI entity.

These schemas are the machine-readable contract used by agents, connectors, and
CLI consumers. They are derived from the Pydantic models so there is exactly one
definition of the ODI dataset.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from core.models import (
    BusinessValue,
    CustomerOutcome,
    CustomerValue,
    Evidence,
    Job,
    Outcome,
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
}


def odi_schema() -> dict[str, Any]:
    """Return the JSON schema for each ODI entity keyed by model name."""
    return {name: model.model_json_schema() for name, model in _SCHEMA_MODELS.items()}
