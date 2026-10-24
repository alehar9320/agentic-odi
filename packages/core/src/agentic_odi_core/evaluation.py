"""Evaluate desired-outcome statements against the ODI format."""

from __future__ import annotations

from typing import Any, Literal

OpportunitySegment = Literal["underserved", "appropriate", "overserved", "unscored"]

# The ODI reading of an opportunity score: above 10 is underserved, exactly
# 10 is appropriately served, below 10 is overserved.
UNDERSERVED_SCORE = 10.0

_CONTEXT_MARKERS = (
    " when ",
    " while ",
    " before ",
    " after ",
    " during ",
    " if ",
    " as ",
)

_VAGUE_TERMS = ("better", "improve", "optimize", "faster", "easier")


def classify_opportunity(score: float | None) -> OpportunitySegment:
    """Bucket an outcome's opportunity score for segmentation."""
    if score is None:
        return "unscored"
    if score > UNDERSERVED_SCORE:
        return "underserved"
    if score == UNDERSERVED_SCORE:
        return "appropriate"
    return "overserved"


def evaluate_outcome_statement(statement: str) -> dict[str, Any]:
    """Return format feedback for a desired-outcome statement."""
    text = statement.strip()
    lowered = text.lower()
    padded = f" {lowered} "
    issues: list[str] = []
    suggestions: list[str] = []

    direction: str | None = None
    if lowered.startswith("minimize"):
        direction = "minimize"
    elif lowered.startswith("maximize"):
        direction = "maximize"
    else:
        issues.append("Statement must start with 'Minimize' or 'Maximize'.")
        suggestions.append("Start with 'Minimize/Maximize the [metric] ...'.")

    if " the " not in padded:
        issues.append("Name the object of control after 'the'.")
        suggestions.append("Say what is being minimized or maximized, e.g. 'the time to ...'.")

    if not any(marker in padded for marker in _CONTEXT_MARKERS):
        issues.append("Add the execution context with 'when ...', 'while ...', or 'before ...'.")
        suggestions.append("Close with the situation, e.g. '... when onboarding a new customer'.")

    if len(text.split()) < 4:
        issues.append("Statement is too short to describe a measurable outcome.")
        suggestions.append("Describe the metric, the object, and the context.")

    if len(text) > 200:
        issues.append("Statement is longer than 200 characters; keep it to one measurable outcome.")
        suggestions.append("Split broad statements into separate outcomes.")

    vague = [term for term in _VAGUE_TERMS if term in lowered]
    if vague:
        issues.append(f"Replace vague terms with a measurable metric: {', '.join(vague)}.")
        suggestions.append("Use a metric such as time, cost, effort, errors, or likelihood.")

    return {
        "statement": text,
        "valid": not issues,
        "direction": direction,
        "issues": issues,
        "suggestions": suggestions,
    }
