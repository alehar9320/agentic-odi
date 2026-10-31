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

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any, Literal

from agentic_odi_core.errors import ValidationError
from agentic_odi_core.stats import percentile

#: The outcome reference column, in the order they are preferred.
OUTCOME_REF_KEYS = ("outcome_id", "outcome_statement")
IMPORTANCE_KEY = "importance"
SATISFACTION_KEY = "satisfaction"
RESPONDENT_KEY = "respondent_id"

#: A row's fate in an import plan (B2.2). ``accepted`` rows resolve to exactly
#: one outcome; the other three are named reasons a row cannot be written.
RowStatus = Literal["accepted", "unmatched", "ambiguous", "invalid"]


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


@dataclass(frozen=True)
class RowReport:
    """One source row's fate in an import plan, named by its CSV line (B2.2).

    ``line`` is the 1-based physical line including the header, so a rejected
    row can be found in the spreadsheet it came from. ``suggestion`` carries a
    single candidate outcome id for a ``--match`` proposal; it is never applied
    without human confirmation.
    """

    line: int
    status: RowStatus
    reason: str
    outcome_ref: str = ""
    suggestion: str | None = None


@dataclass(frozen=True)
class SurveyPlan:
    """A validated, side-effect-free import plan (B2.2).

    Every input row appears exactly once in :attr:`rows`, so nothing is dropped
    silently. The plan holds only rows that will be written in
    :attr:`accepted`; a plan with any non-accepted row is not writable until the
    caller resolves or confirms it.
    """

    rows: list[RowReport]
    accepted: list[SurveyResponse]
    aggregates: dict[str, SurveyAggregate]

    @property
    def rejected(self) -> list[RowReport]:
        """Rows that would not be written, in input order."""
        return [row for row in self.rows if row.status != "accepted"]

    @property
    def writable(self) -> bool:
        """True when every row is accepted, so the plan may be committed."""
        return not self.rejected


def _normalize(value: str) -> str:
    """Case- and whitespace-insensitive key for a match *proposal* (B2.2).

    This is not fuzzy matching: it only collapses case and runs of whitespace, so
    a suggestion is a spelling variant of an exact reference. It is still only a
    proposal a person confirms.
    """
    return " ".join(value.split()).casefold()


def suggest_matches(
    refs: Iterable[str],
    *,
    id_by_statement: Mapping[str, str | None] | None = None,
    known_ids: set[str] | None = None,
) -> dict[str, str]:
    """Propose one candidate outcome id per unresolved reference (B2.2).

    A suggestion is returned only when exactly one id or statement matches the
    reference after normalization; an ambiguous or absent match yields no entry,
    so a proposal never guesses. The caller must confirm before writing.
    """
    id_by_statement = id_by_statement or {}
    known_ids = known_ids or set()
    normalized_ids: dict[str, str] = {}
    ambiguous_ids: set[str] = set()
    for outcome_id in known_ids:
        key = _normalize(outcome_id)
        if key in normalized_ids or key in ambiguous_ids:
            ambiguous_ids.add(key)
            normalized_ids.pop(key, None)
        else:
            normalized_ids[key] = outcome_id
    normalized_statements: dict[str, str] = {}
    ambiguous_statements: set[str] = set()
    for statement, statement_id in id_by_statement.items():
        key = _normalize(statement)
        if statement_id is None or key in normalized_statements or key in ambiguous_statements:
            ambiguous_statements.add(key)
            normalized_statements.pop(key, None)
        else:
            normalized_statements[key] = statement_id

    suggestions: dict[str, str] = {}
    for ref in refs:
        key = _normalize(ref)
        candidate = normalized_ids.get(key) or normalized_statements.get(key)
        if candidate:
            suggestions[ref] = candidate
    return suggestions


def plan_survey(
    rows: Iterable[Mapping[str, Any]],
    *,
    id_by_statement: Mapping[str, str | None] | None = None,
    known_ids: set[str] | None = None,
    confirmed_matches: Mapping[str, str] | None = None,
) -> SurveyPlan:
    """Build a side-effect-free import plan that accounts for every row (B2.2).

    The plan is the whole difference between an importer a researcher trusts and
    one they re-check in a spreadsheet: each row is either accepted or named with
    a reason and its line number, and nothing is silently dropped. A malformed
    value or a non-finite/out-of-range score makes only *that* row ``invalid``;
    the rest of the plan is still reported so the user sees the full picture.

    An unresolved row gets a ``suggestion`` — a single normalized-exact candidate
    — but a suggestion is never applied by itself. ``confirmed_matches`` maps a
    raw reference to an outcome id a person has confirmed; a confirmation only
    assigns when its target still exists in ``known_ids``, so a stale or
    ambiguous confirmation cannot assign a row.
    """
    rows = list(rows)
    id_by_statement = id_by_statement or {}
    known_ids = known_ids or set()
    confirmed_matches = confirmed_matches or {}

    reports: list[RowReport] = []
    accepted: list[SurveyResponse] = []
    seen: set[tuple[str, str]] = set()

    for offset, row in enumerate(rows):
        # Prefer the physical starting line a reader tagged (``_line``) so a
        # quoted multiline record names the line a person sees in their editor.
        line = int(row.get("_line", offset + 2))
        ref_key = next((key for key in OUTCOME_REF_KEYS if key in row), None)
        if ref_key is None:
            reports.append(
                RowReport(
                    line,
                    "invalid",
                    f"missing an outcome reference ({', '.join(OUTCOME_REF_KEYS)})",
                )
            )
            continue
        missing = next((key for key in (IMPORTANCE_KEY, SATISFACTION_KEY) if key not in row), None)
        if missing is not None:
            reports.append(RowReport(line, "invalid", f"missing required column {missing!r}"))
            continue
        ref = str(row[ref_key]).strip()
        if not ref:
            reports.append(RowReport(line, "invalid", "outcome reference is empty"))
            continue

        try:
            importance = _number(row[IMPORTANCE_KEY], field_name=IMPORTANCE_KEY, row=line)
            satisfaction = _number(row[SATISFACTION_KEY], field_name=SATISFACTION_KEY, row=line)
        except ValidationError as err:
            reports.append(RowReport(line, "invalid", str(err), outcome_ref=ref))
            continue

        if ref_key == "outcome_id":
            outcome_id: str | None = ref if ref in known_ids else None
        else:
            outcome_id = id_by_statement.get(ref)
        if outcome_id is None:
            confirmed = confirmed_matches.get(ref)
            if confirmed is not None and confirmed in known_ids:
                outcome_id = confirmed  # a person confirmed this exact assignment
        if outcome_id is None:
            status: RowStatus = (
                "ambiguous"
                if ref_key == "outcome_statement" and ref in id_by_statement
                else "unmatched"
            )
            reason = (
                "statement matched more than one outcome"
                if status == "ambiguous"
                else f"no outcome matches {ref!r}; references must be exact"
            )
            proposal = suggest_matches(
                [ref], id_by_statement=id_by_statement, known_ids=known_ids
            ).get(ref)
            reports.append(RowReport(line, status, reason, outcome_ref=ref, suggestion=proposal))
            continue

        respondent = str(row.get(RESPONDENT_KEY) or f"row-{line}").strip()
        key = (outcome_id, respondent)
        if key in seen:
            reports.append(
                RowReport(
                    line,
                    "invalid",
                    f"respondent {respondent!r} already answered for {outcome_id!r}; "
                    "a repeated respondent is a conflict, not an overwrite",
                    outcome_ref=ref,
                )
            )
            continue
        seen.add(key)
        accepted.append(
            SurveyResponse(
                outcome_ref=outcome_id,
                importance=importance,
                satisfaction=satisfaction,
                respondent=respondent,
                outcome_ref_kind="outcome_id",
            )
        )
        reports.append(RowReport(line, "accepted", "", outcome_ref=ref))

    aggregates = _aggregate_responses([(r.outcome_ref, r) for r in accepted]) if accepted else {}
    return SurveyPlan(rows=reports, accepted=accepted, aggregates=aggregates)


def _number(value: Any, *, field_name: str, row: int) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as err:
        raise ValidationError(f"row {row}: {field_name} must be a number, got {value!r}") from err
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

    return SurveyImportResult(
        aggregates=_aggregate_responses(resolved),
        responses=responses,
    )


def _aggregate_responses(
    resolved: list[tuple[str, SurveyResponse]],
) -> dict[str, SurveyAggregate]:
    """Aggregate already-resolved ``(outcome_id, response)`` pairs into means."""
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
    return aggregates


def survey_csv_header(row: Mapping[str, Any]) -> None:
    """Validate a CSV header row without parsing data rows."""
    if not any(key in row for key in OUTCOME_REF_KEYS):
        raise ValidationError(
            f"survey header needs one of {', '.join(OUTCOME_REF_KEYS)}; got {sorted(row)}"
        )
    for required in (IMPORTANCE_KEY, SATISFACTION_KEY):
        if required not in row:
            raise ValidationError(f"survey header needs a {required!r} column")
