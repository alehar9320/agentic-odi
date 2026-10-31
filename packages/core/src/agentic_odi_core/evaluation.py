"""Evaluate desired-outcome statements against the ODI format."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Literal

from agentic_odi_core.errors import ValidationError
from agentic_odi_core.models import Outcome

OpportunitySegment = Literal["underserved", "appropriate", "overserved", "unscored"]

# Above 10 is underserved, exactly 10 is appropriately served, and below 10 is overserved.
UNDERSERVED_SCORE = 10.0

#: M2-14 advisory threshold. This is a *product* warning line, not a claim that a
#: sample below it is statistically worthless or that one above it is reliable.
#: It is one named constant so the advice and the number it cites cannot drift
#: apart across the CLI, the landscape and the brief.
MIN_MEANINGFUL_N = 20
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


#: Which dimension triggered an advisory when the two samples differ.
AdvisoryDimension = Literal["importance", "satisfaction", "both"]


@dataclass(frozen=True)
class Advisory:
    """A below-threshold warning about a score's sample (M2-14).

    ``message`` is the one sentence every surface renders, so the CLI, the
    landscape chip and the brief cannot word the same warning differently.
    ``n``, ``threshold`` and ``method`` are the structured companions a test (and
    a UI chip) can assert against instead of parsing the sentence.

    The advisory is a statement about the data, never a verdict on the score: it
    does not hide the outcome, change its ranking, or promise that a sample at or
    above the threshold is statistically valid.
    """

    n: int
    threshold: int
    method: str
    dimension: AdvisoryDimension
    message: str


def n_advisory(outcome: Outcome) -> Advisory | None:
    """Warn when a score's recorded sample is below the advisory threshold (M2-14).

    Returns ``None`` when no advisory applies, which is the case for an estimate,
    an unknown count, a sample at or above :data:`MIN_MEANINGFUL_N`, or an
    outcome with no score. The advisory uses the *smaller* of the two counts and
    names the dimension that triggered it, because a single number would hide
    which half of the pair is thin.

    An estimate or an unknown count produces ``None`` rather than a fabricated
    ``n=0``: the confidence classifier already reports those as ``none``, and
    inventing a zero here would turn an unknown into a fact.
    """
    return advisory_for(
        method=outcome.score_method,
        importance_n=outcome.importance_n,
        satisfaction_n=outcome.satisfaction_n,
        opportunity_score=outcome.opportunity_score,
    )


def advisory_for(
    *,
    method: str,
    importance_n: int | None,
    satisfaction_n: int | None,
    opportunity_score: float | None,
) -> Advisory | None:
    """The advisory over raw score fields, so a dict-based surface agrees (M2-14).

    The CLI and the Studio read an outcome as a plain mapping, not an
    :class:`~agentic_odi_core.models.Outcome`; this is the one implementation
    they call so the wording and the triggering rule cannot drift from the model.
    """
    if opportunity_score is None or method == "estimate":
        return None
    known = {
        dimension: n
        for dimension, n in (("importance", importance_n), ("satisfaction", satisfaction_n))
        if n is not None
    }
    if not known:
        return None
    smallest = min(known.values())
    if smallest >= MIN_MEANINGFUL_N:
        return None
    below = [dimension for dimension, n in known.items() if n == smallest]
    if len(below) == 2:
        dimension: AdvisoryDimension = "both"
    elif below[0] == "importance":
        dimension = "importance"
    else:
        dimension = "satisfaction"
    return Advisory(
        n=smallest,
        threshold=MIN_MEANINGFUL_N,
        method=method,
        dimension=dimension,
        message=(
            f"n={smallest} ({dimension}) is below the advisory threshold of "
            f"{MIN_MEANINGFUL_N}; treat this score as a lead to confirm, not a finding."
        ),
    )


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
