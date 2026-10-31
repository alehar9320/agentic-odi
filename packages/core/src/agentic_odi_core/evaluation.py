"""Evaluate desired-outcome statements against the ODI format."""

from __future__ import annotations

import re
from typing import Any, Literal

from agentic_odi_core.errors import ValidationError

OpportunitySegment = Literal["underserved", "appropriate", "overserved", "unscored"]

#: How defensible a value estimate is. ``sized`` has a number and a real basis;
#: ``thin`` has a number but rests on one person's guess; ``unsized`` has no
#: number at all. A one-person guess is never presented as a measured value.
ValueSize = Literal["sized", "thin", "unsized"]

# Above 10 is underserved, exactly 10 is appropriately served, and below 10 is overserved.
UNDERSERVED_SCORE = 10.0
_CONTEXT_MARKERS = (" when ", " while ", " before ", " after ", " during ", " if ", " as ")
_SOLUTION_NOUNS = (
    "notification",
    "dashboard",
    "button",
    "feature",
    "screen",
    "email",
    "workflow",
    "integration",
    "report",
    "toggle",
)
_VAGUE_TERMS = ("better", "improve", "optimize", "faster", "easier")
_MIN_WORDS = 6
_MAX_CHARS = 200
_DIRECTIONS = ("minimize", "maximize")


class OutcomeStatementError(ValidationError):
    """Raised when a statement fails the ODI format check."""

    def __init__(self, verdict: dict[str, Any]) -> None:
        self.verdict = verdict
        self.issues = verdict["issues"]
        self.suggestions = verdict["suggestions"]
        super().__init__(
            "Outcome statement does not match the ODI format: " + " ".join(self.issues)
        )


def classify_opportunity(score: float | None) -> OpportunitySegment:
    """Bucket an outcome's opportunity score for segmentation."""
    if score is None:
        return "unscored"
    if score > UNDERSERVED_SCORE:
        return "underserved"
    if score == UNDERSERVED_SCORE:
        return "appropriate"
    return "overserved"


def classify_value(outcome: Any) -> ValueSize:
    """How defensible an outcome's value estimate is (W1/ALH-64).

    Mirrors :func:`classify_confidence` so a one-person guess is never presented
    as a measured value:

    * ``unsized`` — no ``value_estimate``. Nothing to show; the brief omits the
      section rather than printing a zero.
    * ``thin`` — an estimate that rests on a single person's guess: ``value_n``
      absent or one, with an ``estimate`` basis. A lone judgement is a hypothesis,
      not a measurement.
    * ``sized`` — a number with a defensible basis: a market/pilot source, or a
      sample of more than one person.
    """
    if getattr(outcome, "value_estimate", None) is None:
        return "unsized"
    basis = getattr(outcome, "value_basis", "estimate")
    sample = getattr(outcome, "value_n", None)
    if basis in ("market", "pilot"):
        return "sized"
    if sample is not None and sample > 1:
        return "sized"
    return "thin"


def _find_unit_of_measure(text: str) -> str | None:
    lowered = text.lower()
    units = (
        "time",
        "share",
        "hours",
        "minutes",
        "seconds",
        "days",
        "weeks",
        "months",
        "years",
        "cost",
        "number",
        "frequency",
        "rate",
        "percentage",
        "steps",
        "attempts",
        "likelihood",
        "duration",
        "errors",
    )
    if any(re.search(rf"\b{re.escape(unit)}\b", lowered) for unit in units):
        return next(unit for unit in units if re.search(rf"\b{re.escape(unit)}\b", lowered))
    if re.search(r"\d", text):
        return "number"
    return None


def evaluate_outcome_statement(statement: str) -> dict[str, Any]:
    """Return detailed, serializable feedback for a desired-outcome statement."""
    text = statement.strip()
    lowered = text.lower()
    padded = f" {lowered} "
    issues: list[str] = []
    suggestions: list[str] = []

    direction = next((value for value in _DIRECTIONS if lowered.startswith(value)), None)
    if direction is None:
        issues.append("Statement must start with 'Minimize' or 'Maximize'.")
        suggestions.append(
            "Start with 'Minimize' or 'Maximize', e.g. 'Minimize the time it takes to...'."
        )

    unit_of_measure = _find_unit_of_measure(text)
    if unit_of_measure is None:
        issues.append(
            "Statement must contain a unit of measure (time, cost, number, frequency, rate, percentage, steps, attempts, or a digit)."
        )
        suggestions.append("Add a unit of measure, e.g. 'time', 'cost', or 'number of …'.")

    object_of_control = "the" if " the " in padded else None
    if object_of_control is None:
        issues.append("Statement must name an object of control after 'the'.")
        suggestions.append("Name the object, e.g. 'the time it takes to …'.")

    contextual_clarifier = next(
        (marker.strip() for marker in _CONTEXT_MARKERS if marker in padded), None
    )
    if contextual_clarifier is None:
        issues.append(
            "Statement must state the context when it happens (when, while, before, after, during, if, as)."
        )
        suggestions.append("Add when it happens, e.g. '… when onboarding'.")

    word_count = len(text.split())
    if word_count < _MIN_WORDS:
        issues.append(f"Statement is too short ({word_count} words); needs at least {_MIN_WORDS}.")
        suggestions.append("Describe the metric, the object, and the context.")

    if len(text) > _MAX_CHARS:
        issues.append(
            f"Statement is longer than {_MAX_CHARS} characters; keep it to one measurable outcome."
        )
        suggestions.append("Split broad statements into separate outcomes.")

    vague = [term for term in _VAGUE_TERMS if term in lowered]
    if vague:
        issues.append(f"Replace vague terms with a measurable metric: {', '.join(vague)}.")
        suggestions.append("Use a metric such as time, cost, effort, errors, or likelihood.")

    solution_found = [noun for noun in _SOLUTION_NOUNS if f" {noun} " in padded]
    if solution_found:
        issues.append(
            f"Statement names a solution ({', '.join(solution_found)}), not a customer problem."
        )
        suggestions.append("Name the customer's problem instead of a feature or product.")

    return {
        "statement": text,
        "valid": not issues,
        "direction": direction,
        "issues": issues,
        "suggestions": suggestions,
        "unit_of_measure": unit_of_measure,
        "object_of_control": object_of_control,
        "contextual_clarifier": contextual_clarifier,
    }


def require_outcome_statement(statement: str) -> dict[str, Any]:
    """Validate a statement and raise :class:`OutcomeStatementError` if invalid."""
    verdict = evaluate_outcome_statement(statement)
    if not verdict["valid"]:
        raise OutcomeStatementError(verdict)
    return verdict


def statement_to_dict(verdict: dict[str, Any]) -> dict[str, Any]:
    """Preserve the evaluated statement's serializable mapping."""
    return verdict
