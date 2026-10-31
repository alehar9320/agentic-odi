"""Survey import: turn a table of responses into per-outcome means (B2).

A survey response names an outcome (by id or by exact statement), gives an
importance and a satisfaction value, and optionally names the respondent. This
module is pure: it takes rows, not a path, so the same functions serve a CSV, a
JSON payload and a test fixture.

Provisional import policy (pending the B2 gate; see ``docs/superpowers/plans``):

* A row must carry both dimensions and both must be finite and in 1-10.
* A respondent is identified by ``respondent_id`` when present, otherwise by the
  row's position (``row-<n>``). A repeated respondent for the same outcome is a
  conflict, not a silent overwrite, because the accepted observation set must be
  explicit.
* References are exact: an ``outcome_id`` must exist; an ``outcome_statement``
  must match exactly one outcome. A miss or an ambiguity fails the whole import
  without a partial write; nothing is fuzzy-matched.
* An outcome keeps only its own accepted observations, so no outcome borrows
  another's sample size.

These choices are the ones the B2 issue says must be approved; they are named
here and pinned by tests rather than scattered through the command.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping

from agentic_odi_core.errors import ValidationError
from agentic_odi_core.stats import percentile

#: The outcome reference column, in the order they are preferred.
OUTCOME_REF_KEYS = ("outcome_id", "outcome_statement")
IMPORTANCE_KEY = "importance"
SATISFACTION_KEY = "satisfaction"
RESPONDENT_KEY = "respondent_id"


@dataclass(frozen=True)
class SurveyResponse:
    """One respondent's paired answers, before aggregation."""

    outcome_ref: str
    importance: float
    satisfaction: float
    respondent: str
    outcome_ref_kind: str = "outcome_id"


@dataclass(frozen=True)
class SurveyAggregate:
    """One outcome's accepted sample: means, spread and count (B2).

    A mean without a spread is the number that makes people defend a guess, so
    ``p10``/``p90`` travel with it. ``n`` counts accepted observations for this
    outcome only, so no outcome borrows another's sample size.
    """

    outcome_id: str
    importance_mean: float
    satisfaction_mean: float
    importance_p10: float
    importance_p90: float
    satisfaction_p10: float
    satisfaction_p90: float
    n: int


@dataclass(frozen=True)
class SurveyImportResult:
    """The whole-import outcome: aggregates plus per-row diagnostics."""

    aggregates: dict[str, SurveyAggregate]
    responses: list[SurveyResponse] = field(default_factory=list)


def _number(value: Any, *, field_name: str, row: int) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValidationError(f"row {row}: {field_name} must be a number, got {value!r}")
    if number != number or number in (float("inf"), float("-inf")):
        raise ValidationError(f"row {row}: {field_name} must be finite, got {value!r}")
    if not (1.0 <= number <= 10.0):
        raise ValidationError(f"row {row}: {field_name} must be between 1 and 10, got {value!r}")
    return number


def parse_survey(rows: Iterable[Mapping[str, Any]]) -> list[SurveyResponse]:
    """Parse raw rows into responses, or fail before anything is aggregated.

    Header detection accepts ``outcome_id`` or ``outcome_statement`` plus
    ``importance`` and ``satisfaction``; ``respondent_id`` is optional. An empty
    file, a missing header or a malformed number fails here, so a bad file never
    produces a partial aggregate.
    """
    rows = list(rows)
    if not rows:
        raise ValidationError("survey file has no rows")

    responses: list[SurveyResponse] = []
    seen: set[tuple[str, str]] = set()
    for offset, row in enumerate(rows):
        line = offset + 2  # header is line 1; a row is a human-facing 1-based line
        ref_key = next((key for key in OUTCOME_REF_KEYS if key in row), None)
        if ref_key is None:
            raise ValidationError(
                f"row {line}: missing an outcome reference; expected one of "
                f"{', '.join(OUTCOME_REF_KEYS)}"
            )
        for required in (IMPORTANCE_KEY, SATISFACTION_KEY):
            if required not in row:
                raise ValidationError(f"row {line}: missing required column {required!r}")
        ref = str(row[ref_key]).strip()
        if not ref:
            raise ValidationError(f"row {line}: outcome reference is empty")
        respondent = str(row.get(RESPONDENT_KEY) or f"row-{line}").strip()
        response = SurveyResponse(
            outcome_ref=ref,
            importance=_number(row[IMPORTANCE_KEY], field_name=IMPORTANCE_KEY, row=line),
            satisfaction=_number(row[SATISFACTION_KEY], field_name=SATISFACTION_KEY, row=line),
            respondent=respondent,
            outcome_ref_kind=ref_key,
        )
        key = (ref, respondent)
        if key in seen:
            raise ValidationError(
                f"row {line}: respondent {respondent!r} already answered for {ref!r}; "
                "a repeated respondent is a conflict, not an overwrite"
            )
        seen.add(key)
        responses.append(response)
    return responses


def aggregate_survey(
    responses: list[SurveyResponse],
    *,
    id_by_statement: Mapping[str, str | None] | None = None,
    known_ids: set[str] | None = None,
) -> SurveyImportResult:
    """Resolve references and aggregate responses into one mean per outcome.

    Resolution is exact and job-scoped: an ``outcome_id`` must be in
    ``known_ids``; an ``outcome_statement`` must map to exactly one id via
    ``id_by_statement`` (``None`` means the statement is unknown or ambiguous).
    Any unresolved reference fails the whole call, so an import never half-lands.
    """
    id_by_statement = id_by_statement or {}
    known_ids = known_ids or set()

    resolved: list[tuple[str, SurveyResponse]] = []
    for response in responses:
        if response.outcome_ref_kind == "outcome_id":
            outcome_id = response.outcome_ref
            if outcome_id not in known_ids:
                raise ValidationError(
                    f"no outcome with id {outcome_id!r}; references must be exact"
                )
        else:
            outcome_id = id_by_statement.get(response.outcome_ref)  # type: ignore[assignment]
            if outcome_id is None:
                raise ValidationError(
                    f"statement {response.outcome_ref!r} matched no outcome or more than "
                    "one; references must be exact"
                )
        resolved.append((outcome_id, response))

    by_outcome: dict[str, list[SurveyResponse]] = {}
    for outcome_id, response in resolved:
        by_outcome.setdefault(outcome_id, []).append(response)

    aggregates: dict[str, SurveyAggregate] = {}
    for outcome_id, group in by_outcome.items():
        importance = sorted(r.importance for r in group)
        satisfaction = sorted(r.satisfaction for r in group)
        aggregates[outcome_id] = SurveyAggregate(
            outcome_id=outcome_id,
            importance_mean=sum(importance) / len(importance),
            satisfaction_mean=sum(satisfaction) / len(satisfaction),
            importance_p10=percentile(importance, 0.10),
            importance_p90=percentile(importance, 0.90),
            satisfaction_p10=percentile(satisfaction, 0.10),
            satisfaction_p90=percentile(satisfaction, 0.90),
            n=len(group),
        )
    return SurveyImportResult(aggregates=aggregates, responses=responses)


def survey_csv_header(row: Mapping[str, Any]) -> None:
    """Validate a CSV header row without parsing data rows."""
    if not any(key in row for key in OUTCOME_REF_KEYS):
        raise ValidationError(
            f"survey header needs one of {', '.join(OUTCOME_REF_KEYS)}; got {sorted(row)}"
        )
    for required in (IMPORTANCE_KEY, SATISFACTION_KEY):
        if required not in row:
            raise ValidationError(f"survey header needs a {required!r} column")
