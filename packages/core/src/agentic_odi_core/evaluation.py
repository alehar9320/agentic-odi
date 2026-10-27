"""Evaluate desired-outcome statements against the ODI format.

The single authority for what a well-formed desired-outcome statement looks
like. Every write path (service, MCP tool, CLI, Studio API) routes through
``evaluate_outcome_statement`` / ``require_outcome_statement`` so the store
only ever contains methodologically sound data.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from agentic_odi_core.errors import ValidationError

_CONTEXT_MARKERS = (
    " when ",
    " while ",
    " before ",
    " after ",
    " during ",
    " if ",
    " as ",
)

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


@dataclass(frozen=True)
class StatementIssue:
    """A single validation problem with a statement."""

    code: str
    message: str
    suggestion: str | None = None


@dataclass(frozen=True)
class StatementVerdict:
    """The result of evaluating a desired-outcome statement."""

    valid: bool
    direction: str | None
    unit_of_measure: str | None
    object_of_control: str | None
    contextual_clarifier: str | None
    issues: tuple[StatementIssue, ...]


class OutcomeStatementError(ValidationError):
    """Raised when a statement fails the ODI format check.

    The message is actionable: it says what is wrong and what to do about it.
    """

    def __init__(self, verdict: StatementVerdict) -> None:
        self.verdict = verdict
        lines = [f"Outcome statement is not valid: {verdict.direction or ''}".strip()]
        for issue in verdict.issues:
            lines.append(f"- {issue.message}")
            if issue.suggestion:
                lines.append(f"  Fix: {issue.suggestion}")
        super().__init__("\n".join(lines))


def _detect_direction(text: str) -> str | None:
    lowered = text.lower()
    for direction in _DIRECTIONS:
        if lowered.startswith(direction):
            return direction
    return None


def _find_unit_of_measure(text: str) -> str | None:
    lowered = text.lower()
    units = (
        "time",
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
        "time to",
        "steps",
        "attempts",
        "likelihood",
        "duration",
        "errors",
    )
    for unit in units:
        if (
            f" {unit} " in f" {lowered} "
            or lowered.startswith(f"{unit} ")
            or lowered.endswith(f" {unit}")
        ):
            return unit
    # Any digit present implies a measurable unit.
    import re

    if re.search(r"\d", text):
        return "number"
    return None


def _find_object_of_control(text: str) -> str | None:
    padded = f" {text.lower()} "
    if " the " in padded:
        return "the"
    return None


def _find_contextual_clarifier(text: str) -> str | None:
    padded = f" {text.lower()} "
    for marker in _CONTEXT_MARKERS:
        if marker in padded:
            return marker.strip()
    return None


def evaluate_outcome_statement(statement: str) -> StatementVerdict:
    """Return a :class:`StatementVerdict` for a desired-outcome statement."""
    text = statement.strip()
    lowered = text.lower()
    padded = f" {lowered} "
    issues: list[StatementIssue] = []

    direction = _detect_direction(text)
    if direction is None:
        issues.append(
            StatementIssue(
                code="missing_direction",
                message="Statement must start with 'Minimize' or 'Maximize'.",
                suggestion="Start with 'Minimize' or 'Maximize', e.g. 'Minimize the time it takes to...'.",
            )
        )

    unit_of_measure = _find_unit_of_measure(text)
    if unit_of_measure is None:
        issues.append(
            StatementIssue(
                code="missing_unit",
                message="Statement must contain a unit of measure (time, cost, number, frequency, rate, percentage, steps, attempts, or a digit).",
                suggestion="Add a unit of measure, e.g. 'time', 'cost', or 'number of …'.",
            )
        )

    object_of_control = _find_object_of_control(text)
    if object_of_control is None:
        issues.append(
            StatementIssue(
                code="missing_object",
                message="Statement must name an object of control after 'the'.",
                suggestion="Name the object, e.g. 'the time it takes to …'.",
            )
        )

    contextual_clarifier = _find_contextual_clarifier(text)
    if contextual_clarifier is None:
        issues.append(
            StatementIssue(
                code="missing_context",
                message="Statement must state the context when it happens (when, while, before, after, during, if, as).",
                suggestion="Add when it happens, e.g. '… when onboarding'.",
            )
        )

    word_count = len(text.split())
    if word_count < _MIN_WORDS:
        issues.append(
            StatementIssue(
                code="too_short",
                message=f"Statement is too short ({word_count} words); needs at least {_MIN_WORDS}.",
                suggestion="Describe the metric, the object, and the context.",
            )
        )

    if len(text) > _MAX_CHARS:
        issues.append(
            StatementIssue(
                code="too_long",
                message=f"Statement is longer than {_MAX_CHARS} characters; keep it to one measurable outcome.",
                suggestion="Split broad statements into separate outcomes.",
            )
        )

    vague = [term for term in _VAGUE_TERMS if term in lowered]
    if vague:
        issues.append(
            StatementIssue(
                code="vague_term",
                message=f"Replace vague terms with a measurable metric: {', '.join(vague)}.",
                suggestion="Use a metric such as time, cost, effort, errors, or likelihood.",
            )
        )

    solution_found = [noun for noun in _SOLUTION_NOUNS if f" {noun} " in padded]
    if solution_found:
        issues.append(
            StatementIssue(
                code="solution_framed",
                message=f"Statement names a solution ({', '.join(solution_found)}), not a customer problem.",
                suggestion="Name the customer's problem instead of a feature or product.",
            )
        )

    return StatementVerdict(
        valid=not issues,
        direction=direction,
        unit_of_measure=unit_of_measure,
        object_of_control=object_of_control,
        contextual_clarifier=contextual_clarifier,
        issues=tuple(issues),
    )


def require_outcome_statement(statement: str) -> StatementVerdict:
    """Validate a statement and raise :class:`OutcomeStatementError` if invalid."""
    verdict = evaluate_outcome_statement(statement)
    if not verdict.valid:
        raise OutcomeStatementError(verdict)
    return verdict


def statement_to_dict(verdict: StatementVerdict) -> dict[str, Any]:
    """Render a verdict as the legacy dict shape for MCP/CLI serialization."""
    return {
        "statement": "",
        "valid": verdict.valid,
        "direction": verdict.direction,
        "issues": [issue.message for issue in verdict.issues],
        "suggestions": [
            issue.suggestion for issue in verdict.issues if issue.suggestion is not None
        ],
        "unit_of_measure": verdict.unit_of_measure,
        "object_of_control": verdict.object_of_control,
        "contextual_clarifier": verdict.contextual_clarifier,
    }
