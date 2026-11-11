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
from collections.abc import Callable, Iterable, Mapping, Sequence
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
_UNITS = (
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


class OutcomeStatementError(ValidationError):
    """Raised when a statement fails the ODI format check."""

    #: The field the statement belongs to. A desired outcome is always a
    #: statement, so callers default to ``"statement"`` and let a subclass
    #: narrow it — e.g. a customer outcome's ``business_statement``.
    field: str = "statement"

    def __init__(self, verdict: dict[str, Any], field: str | None = None) -> None:
        self.verdict = verdict
        self.issues = verdict["issues"]
        self.suggestions = verdict["suggestions"]
        if field is not None:
            self.field = field
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
    if any(re.search(rf"\b{re.escape(unit)}\b", lowered) for unit in _UNITS):
        return next(unit for unit in _UNITS if re.search(rf"\b{re.escape(unit)}\b", lowered))
    if re.search(r"\d", text):
        return "number"
    return None


@dataclass(frozen=True)
class _RuleContext:
    """The parsed statement a rule inspects, computed once per evaluation."""

    text: str
    lowered: str
    padded: str
    direction: str | None
    unit_of_measure: str | None
    object_of_control: str | None
    contextual_clarifier: str | None


@dataclass(frozen=True)
class _OutcomeRule:
    """One published check: its identity, its guidance, and its predicate.

    ``check`` returns the issue message when the statement fails the rule, or
    ``None`` when it passes. The message and ``fix`` are what the verdict
    reports; ``label``, ``summary`` and ``examples`` are what the rubric
    publishes, and every one of them is derived from the validator constants so
    the published rubric cannot drift from the check that runs.
    """

    id: str
    label: str
    summary: str
    fix: str
    good: str
    bad: str
    check: Callable[[_RuleContext], str | None]


def _check_direction(context: _RuleContext) -> str | None:
    if context.direction is None:
        return "Statement must start with 'Minimize' or 'Maximize'."
    return None


def _check_unit_of_measure(context: _RuleContext) -> str | None:
    if context.unit_of_measure is None:
        return (
            "Statement must contain a unit of measure (time, cost, number, frequency, "
            "rate, percentage, steps, attempts, or a digit)."
        )
    return None


def _check_object_of_control(context: _RuleContext) -> str | None:
    if context.object_of_control is None:
        return "Statement must name an object of control after 'the'."
    return None


def _check_context(context: _RuleContext) -> str | None:
    if context.contextual_clarifier is None:
        return (
            "Statement must state the context when it happens "
            "(when, while, before, after, during, if, as)."
        )
    return None


def _check_min_words(context: _RuleContext) -> str | None:
    word_count = len(context.text.split())
    if word_count < _MIN_WORDS:
        return f"Statement is too short ({word_count} words); needs at least {_MIN_WORDS}."
    return None


def _check_max_chars(context: _RuleContext) -> str | None:
    if len(context.text) > _MAX_CHARS:
        return (
            f"Statement is longer than {_MAX_CHARS} characters; keep it to one measurable outcome."
        )
    return None


def _check_vague(context: _RuleContext) -> str | None:
    vague = [term for term in _VAGUE_TERMS if term in context.lowered]
    if vague:
        return f"Replace vague terms with a measurable metric: {', '.join(vague)}."
    return None


def _check_solution(context: _RuleContext) -> str | None:
    solution_found = [noun for noun in _SOLUTION_NOUNS if f" {noun} " in context.padded]
    if solution_found:
        return f"Statement names a solution ({', '.join(solution_found)}), not a customer problem."
    return None


#: The rules, in the order their issues are reported. Every summary is built
#: from the same constants the checks read, so editing a constant edits the
#: published rubric with it.
_OUTCOME_RULES: tuple[_OutcomeRule, ...] = (
    _OutcomeRule(
        id="direction",
        label="Direction",
        summary="Starts with one of: " + ", ".join(_DIRECTIONS) + ".",
        fix="Start with 'Minimize' or 'Maximize', e.g. 'Minimize the time it takes to...'.",
        good="Minimize the time it takes to onboard a customer when they sign up",
        bad="The time to onboard a customer when they sign up",
        check=_check_direction,
    ),
    _OutcomeRule(
        id="unit_of_measure",
        label="Unit of measure",
        summary="Contains a unit of measure: " + ", ".join(_UNITS) + ", or a digit.",
        fix="Add a unit of measure, e.g. 'time', 'cost', or 'number of …'.",
        good="Minimize the cost of onboarding a customer when they sign up",
        bad="Minimize the effort of onboarding a customer when they sign up",
        check=_check_unit_of_measure,
    ),
    _OutcomeRule(
        id="object_of_control",
        label="Object of control",
        summary="Names an object after 'the'.",
        fix="Name the object, e.g. 'the time it takes to …'.",
        good="Minimize the time it takes to onboard a customer when they sign up",
        bad="Minimize onboarding time when a customer signs up",
        check=_check_object_of_control,
    ),
    _OutcomeRule(
        id="contextual_clarifier",
        label="Contextual clarifier",
        summary="States the context with one of: "
        + ", ".join(marker.strip() for marker in _CONTEXT_MARKERS)
        + ".",
        fix="Add when it happens, e.g. '… when onboarding'.",
        good="Minimize the time it takes to onboard a customer when they sign up",
        bad="Minimize the time to deploy",
        check=_check_context,
    ),
    _OutcomeRule(
        id="min_words",
        label="Length floor",
        summary=f"Contains at least {_MIN_WORDS} words.",
        fix="Describe the metric, the object, and the context.",
        good="Minimize the time it takes to onboard a customer when they sign up",
        bad="Minimize the time",
        check=_check_min_words,
    ),
    _OutcomeRule(
        id="max_chars",
        label="Length ceiling",
        summary=f"Contains at most {_MAX_CHARS} characters.",
        fix="Split broad statements into separate outcomes.",
        good="Minimize the time it takes to onboard a customer when they sign up",
        bad="Minimize the total elapsed time from a customer asking a question to a "
        "support engineer closing the loop while the account is in its first ninety "
        "days and the request spans more than one timezone while the team works "
        "across two continents",
        check=_check_max_chars,
    ),
    _OutcomeRule(
        id="vague_terms",
        label="No vague terms",
        summary="Avoids vague terms: " + ", ".join(_VAGUE_TERMS) + ".",
        fix="Use a metric such as time, cost, effort, errors, or likelihood.",
        good="Minimize the time it takes to onboard a customer when they sign up",
        bad="Make it faster",
        check=_check_vague,
    ),
    _OutcomeRule(
        id="solution_nouns",
        label="No solution nouns",
        summary="Names no solution nouns: " + ", ".join(_SOLUTION_NOUNS) + ".",
        fix="Name the customer's problem instead of a feature or product.",
        good="Minimize the time it takes to onboard a customer when they sign up",
        bad="I want a notification",
        check=_check_solution,
    ),
)


def outcome_rubric() -> dict[str, Any]:
    """Publish the rules the statement guard enforces, for any caller to explain.

    The rubric is generated from the same constants and rule objects the
    evaluation runs, so a constant edit that changes a check changes the
    published rubric with it — there is no second copy to drift.
    """
    return {
        "version": 1,
        "rules": [
            {
                "id": rule.id,
                "label": rule.label,
                "summary": rule.summary,
                "fix": rule.fix,
                "examples": {"good": rule.good, "bad": rule.bad},
            }
            for rule in _OUTCOME_RULES
        ],
    }


def evaluate_outcome_statement(statement: str) -> dict[str, Any]:
    """Return detailed, serializable feedback for a desired-outcome statement.

    ``issues`` and ``suggestions`` are unchanged for every existing fixture;
    ``checks`` adds one verdict per rule so a caller can route a rejection to
    the field that needs it instead of printing one sentence.
    """
    text = statement.strip()
    lowered = text.lower()
    padded = f" {lowered} "

    direction = next((value for value in _DIRECTIONS if lowered.startswith(value)), None)
    unit_of_measure = _find_unit_of_measure(text)
    object_of_control = "the" if " the " in padded else None
    contextual_clarifier = next(
        (marker.strip() for marker in _CONTEXT_MARKERS if marker in padded), None
    )
    context = _RuleContext(
        text=text,
        lowered=lowered,
        padded=padded,
        direction=direction,
        unit_of_measure=unit_of_measure,
        object_of_control=object_of_control,
        contextual_clarifier=contextual_clarifier,
    )

    issues: list[str] = []
    suggestions: list[str] = []
    checks: list[dict[str, Any]] = []
    for rule in _OUTCOME_RULES:
        message = rule.check(context)
        if message is not None:
            issues.append(message)
            suggestions.append(rule.fix)
        checks.append({"id": rule.id, "ok": message is None, "message": message, "fix": rule.fix})

    return {
        "statement": text,
        "valid": not issues,
        "direction": direction,
        "issues": issues,
        "suggestions": suggestions,
        "unit_of_measure": unit_of_measure,
        "object_of_control": object_of_control,
        "contextual_clarifier": contextual_clarifier,
        "checks": checks,
    }


def require_outcome_statement(statement: str, field: str = "statement") -> dict[str, Any]:
    """Validate a statement and raise :class:`OutcomeStatementError` if invalid.

    ``field`` names the input that holds the statement — a desired outcome's
    statement, a customer outcome's ``business_statement``, and so on. It
    travels onto the exception so a form can show the message next to the
    field that needs it instead of on top of the whole form.
    """
    verdict = evaluate_outcome_statement(statement)
    if not verdict["valid"]:
        raise OutcomeStatementError(verdict, field=field)
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
