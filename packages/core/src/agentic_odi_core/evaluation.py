"""Evaluate desired-outcome statements against the ODI format.

This module is also the evaluation harness: alongside the statement guard it
holds the check that judges a *service* by the shared scoring fixture. A service
that scores its outcomes with :func:`~agentic_odi_core.models.compute_opportunity_score`
passes; one that computes its own arithmetic fails with the offending pair named.

It also judges the interview behind a score: :func:`assert_asked_before_scoring`
reads a transcript in the order it happened, so a number written before the
questions reached the person is refused even when its claim check reads complete.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from agentic_odi_core.errors import OdiError, ValidationError
from agentic_odi_core.models import ClaimCheck, Outcome, compute_opportunity_score

OpportunitySegment = Literal["underserved", "appropriate", "overserved", "unscored"]

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


# -- The evaluation harness: judge a service by the fixture --------------------

#: The shared scoring fixture, committed next to the core tests. It is the
#: contract: the scorer and the harness both read it, and neither derives an
#: expected value of its own.
SCORE_FIXTURE_PATH = (
    Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "opportunity-score.json"
)


class OutcomeScoreMismatchError(OdiError):
    """A service reported an opportunity score its own inputs do not produce.

    The message names the outcome id and both values: the score the fixture's
    arithmetic expects, and the score the service reported.
    """

    def __init__(
        self,
        outcome_id: str,
        expected: float,
        reported: float,
        importance: float,
        satisfaction: float,
    ) -> None:
        self.outcome_id = outcome_id
        self.expected = expected
        self.reported = reported
        super().__init__(
            f"Outcome {outcome_id} scored {reported}, but importance {importance} and "
            f"satisfaction {satisfaction} score {expected}."
        )


def load_score_fixture(path: str | Path | None = None) -> dict[str, Any]:
    """Read the shared scoring fixture.

    The fixture is the contract; callers must not re-derive its expected values.
    """
    resolved = Path(path) if path is not None else SCORE_FIXTURE_PATH
    return json.loads(resolved.read_text(encoding="utf-8"))


def fixture_expected_scores(fixture: Mapping[str, Any]) -> dict[tuple[float, float], float]:
    """The fixture's arithmetic as ``(importance, satisfaction) -> score``.

    Only scored cases appear; an unscored case carries no expected value.
    """
    return {
        (case["importance"], case["satisfaction"]): case["score"]
        for case in fixture["cases"]
        if case["importance"] is not None and case["satisfaction"] is not None
    }


def assert_outcome_scores_match(
    outcomes: Iterable[Outcome],
    fixture: Mapping[str, Any] | None = None,
) -> None:
    """Judge a service's scored outcomes by the fixture's arithmetic.

    A service that scores its outcomes with the shared function passes. One that
    computes its own fails, and the error names the outcome id and both values.

    An unscored outcome is allowed and stays allowed: an outcome with no score,
    or with either input missing, is a legal record, not a mismatch.
    """
    expected_scores = fixture_expected_scores(fixture or load_score_fixture())
    for outcome in outcomes:
        importance = outcome.importance
        satisfaction = outcome.satisfaction
        reported = outcome.opportunity_score
        if importance is None or satisfaction is None or reported is None:
            continue
        expected = expected_scores.get(
            (importance, satisfaction), compute_opportunity_score(importance, satisfaction)
        )
        if reported != expected:
            raise OutcomeScoreMismatchError(
                outcome.id, expected, reported, importance, satisfaction
            )


# -- The evaluation harness: judge an interview by its transcript --------------

#: The questions that must reach the person before a number is written. The prompt
#: asks for three or four; this is the floor, and it is what an evaluation case fails on.
MIN_QUESTIONS_BEFORE_SCORING = 3


@dataclass(frozen=True)
class InterviewTurn:
    """One turn of an interview, listed in the order it happened."""

    speaker: Literal["customer", "agent"]
    text: str
    wrote_score: bool = False


class ScoreBeforeQuestionsError(OdiError):
    """A score was written that the interview behind it does not support.

    The message names what is missing: how many questions were put before the
    scoring turn, or the answer that no customer turn contains.
    """


def assert_asked_before_scoring(
    transcript: Sequence[InterviewTurn],
    check: ClaimCheck | None,
) -> None:
    """Judge a score by the turns that came before it.

    A transcript with no scoring turn has nothing to judge: an outcome captured
    without numbers is legal, and asking is what makes it scoreable later. Once a
    turn writes a score, three things have to already be true — a claim check
    exists, at least :data:`MIN_QUESTIONS_BEFORE_SCORING` questions were put by the
    agent, and every answer the check records appears in a customer turn. Skipping
    a question is allowed; a skip is simply absent from ``answers``.
    """
    scored_at = next(
        (index for index, turn in enumerate(transcript) if turn.wrote_score),
        None,
    )
    if scored_at is None:
        return
    if check is None:
        raise ScoreBeforeQuestionsError(
            f"Turn {scored_at} writes a score with no claim check; ask the questions, "
            "then pass the answers with the number."
        )
    asked = sum(
        1 for turn in transcript[:scored_at] if turn.speaker == "agent" and "?" in turn.text
    )
    if asked < MIN_QUESTIONS_BEFORE_SCORING:
        raise ScoreBeforeQuestionsError(
            f"Turn {scored_at} scores after {asked} of the three questions needed; ask "
            "three or four of them and let the person answer before any number appears."
        )
    for answer in check.answers:
        heard = any(
            turn.speaker == "customer" and answer.strip().casefold() in turn.text.casefold()
            for turn in transcript[:scored_at]
        )
        if not heard:
            raise ScoreBeforeQuestionsError(
                f"The answer {answer!r} is in no customer turn before the score; never "
                "answer your own question and count it."
            )
