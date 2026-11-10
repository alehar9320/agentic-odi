"""ALH-222 (M2-04.1) — read a spreadsheet of outcomes, then file it one row at a time.

Two doors, one file format: the CLI reads a path and the Studio sidecar reads an upload, and
both hand the same rows to the same loop. Nothing here writes, repairs or guesses. A cell that
cannot be used is reported as unused rather than quietly turned into something else, and every
line of the file is accounted for — a refusal names the line the person will find in their
spreadsheet app, with the header on line 1.

The loop writes through an :class:`ImportTarget`, which is the same single-outcome door a person
uses: a row the CLI would refuse an import refuses too, and a row it would score by hand carries
the same honest claim check. One loop over three batched reads means a forty-line file costs
forty writes and not a hundred and sixty.
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from agentic_odi_core.errors import OdiError
from agentic_odi_core.evaluation import evaluate_outcome_statement
from agentic_odi_core.models import ClaimCheck, JobStage, Step, Theme
from agentic_odi_core.services import (
    InvalidOutcomeStatementError,
    ODIService,
    StepNotFoundError,
    ValueOutOfRangeError,
    manual_claim_check,
)

READABLE_FORMAT = "csv"

#: The one column a row cannot do without, and the two synonyms a research file arrives with.
STATEMENT_HEADERS = ("statement", "outcome", "need")
NUMERIC_FIELDS = ("importance", "satisfaction", "importance_n", "satisfaction_n")
TEXT_FIELDS = ("theme", "stage", "step_id", "job_id")

#: Headers a person's file legitimately carries and an Outcome has nowhere to put. They are
#: reported rather than dropped: an ignored column that says so is honest, and one that says
#: nothing is a silent loss of research.
IGNORED_HEADERS = {
    "id": "the id of a row that already exists; a new outcome gets its own",
    "opportunity_score": "opportunity is computed from the two scores, never entered",
    "importance_n": "no field on an Outcome holds a count",
    "satisfaction_n": "no field on an Outcome holds a count",
}


class UnsupportedFormatError(OdiError):
    """Raised when the import is handed a file this increment does not read."""


@dataclass(frozen=True)
class ImportRow:
    """One line of the file, as read rather than as the importer would like it."""

    line: int
    statement: str
    importance: float | None = None
    satisfaction: float | None = None
    importance_n: float | None = None
    satisfaction_n: float | None = None
    theme: str | None = None
    stage: str | None = None
    step_id: str | None = None
    job_id: str | None = None
    #: Why this line cannot be filed, in the words a report shows. Empty means the row is
    #: readable; it does not mean the row is valid — that is the loop's judgement.
    problems: list[str] = field(default_factory=list)


@dataclass
class ParsedTable:
    rows: list[ImportRow] = field(default_factory=list)
    ignored_columns: dict[str, str] = field(default_factory=dict)
    #: A file-level problem: the whole table is unusable, so ``rows`` is empty.
    problems: list[str] = field(default_factory=list)


def _normalise(header: str) -> str:
    return "_".join(header.strip().lower().split())


def _number(field_name: str, raw: str) -> tuple[float | None, str | None]:
    """Read a score cell: empty is absent, text is a problem, and neither is ever a zero."""
    if not raw:
        return None, None
    try:
        return float(raw), None
    except ValueError:
        return None, f'{field_name} must be a number, got "{raw}"'


def parse_outcome_table(source: str | bytes, fmt: str = READABLE_FORMAT) -> ParsedTable:
    if _normalise(fmt) != READABLE_FORMAT:
        raise UnsupportedFormatError(
            f"'{fmt}' is not a format this import reads; only '{READABLE_FORMAT}' is. "
            "Saving the spreadsheet as CSV loses nothing a research file carries."
        )
    text = source.decode("utf-8-sig", errors="replace") if isinstance(source, bytes) else source
    reader = csv.reader(io.StringIO(text, newline=""))

    header: list[str] = []
    for cells in reader:  # the first non-blank line is the header
        header = cells
        break
    if not any(cell.strip() for cell in header):
        return ParsedTable(problems=["no header row: the file must name its columns"])

    statement_columns: list[tuple[int, str]] = []
    field_columns: list[tuple[int, str]] = []
    ignored: dict[str, str] = {}
    for index, cell in enumerate(header):
        name = _normalise(cell)
        if not name:
            continue
        if name in STATEMENT_HEADERS:
            statement_columns.append((index, name))
        elif name in NUMERIC_FIELDS or name in TEXT_FIELDS:
            field_columns.append((index, name))
            if name in IGNORED_HEADERS:
                # Read into the row, because the documented row shape names it; reported as
                # ignored, because an Outcome has no field to hold a count.
                ignored[name] = IGNORED_HEADERS[name]
        else:
            ignored[name] = IGNORED_HEADERS.get(name, "not an outcome column; ignored")

    if not statement_columns:
        return ParsedTable(
            ignored_columns=ignored,
            problems=[
                "the file names no statement column; expected one of "
                + ", ".join(f"'{name}'" for name in STATEMENT_HEADERS)
            ],
        )

    rows: list[ImportRow] = []
    for cells in reader:
        if not any(cell.strip() for cell in cells):
            continue
        values = {
            name: cells[index].strip() if index < len(cells) else ""
            for index, name in field_columns
        }
        problems: list[str] = []

        named = [
            (name, cells[index].strip())
            for index, name in statement_columns
            if index < len(cells) and cells[index].strip()
        ]
        if not named:
            statement = ""
            problems.append("statement is empty; nothing to file")
        elif len({value for _, value in named}) > 1:
            statement = named[0][1]
            problems.append(
                "statement is ambiguous: "
                + " and ".join(f'"{name}"' for name, _ in named)
                + " name two different needs"
            )
        else:
            statement = named[0][1]

        scores: dict[str, float | None] = {}
        for name in NUMERIC_FIELDS:
            value, problem = _number(name, values.get(name, ""))
            scores[name] = value
            if problem is not None:
                problems.append(problem)

        rows.append(
            ImportRow(
                line=reader.line_num,
                statement=statement,
                importance=scores["importance"],
                satisfaction=scores["satisfaction"],
                importance_n=scores["importance_n"],
                satisfaction_n=scores["satisfaction_n"],
                theme=values.get("theme") or None,
                stage=values.get("stage") or None,
                step_id=values.get("step_id") or None,
                job_id=values.get("job_id") or None,
                problems=problems,
            )
        )

    if not rows:
        return ParsedTable(
            ignored_columns=ignored, problems=["no data rows: the file has nothing to import"]
        )
    return ParsedTable(rows=rows, ignored_columns=ignored)


# --------------------------------------------------------------------------- the loop


class ImportAbortedError(OdiError):
    """Raised by a target whose transport died, which is not the row's fault.

    A row that the store refuses is a refusal; a server that cannot be reached is a stop.
    Conflating them turns one dead connection into forty invented problems about the person's
    own file, and the rows already written would be reported as missing.
    """


@runtime_checkable
class ImportTarget(Protocol):
    """What the loop needs from wherever outcomes live: three reads, two writes."""

    def themes(self, job_id: str) -> list[Theme]: ...

    def steps(self, job_id: str) -> list[Step]: ...

    def existing_statements(self, job_id: str) -> list[str]: ...

    def add_outcome(
        self, job_id: str, row: ImportRow, claim_check: ClaimCheck | None, step_id: str | None
    ) -> str: ...

    def assign_theme(self, outcome_ids: list[str], theme_id: str) -> None: ...


class ServiceImportTarget:
    """The loop's door to a service in this process."""

    def __init__(self, service: ODIService) -> None:
        self.service = service

    def themes(self, job_id: str) -> list[Theme]:
        #: A job's themes and the workspace-wide ones are one read, which is exactly the
        #: scope a spreadsheet's theme column is written against.
        return self.service.list_themes(job_id)

    def steps(self, job_id: str) -> list[Step]:
        return self.service.get_job_map(job_id)

    def existing_statements(self, job_id: str) -> list[str]:
        return [outcome.statement for outcome in self.service.get_outcomes(job_id)]

    def add_outcome(
        self, job_id: str, row: ImportRow, claim_check: ClaimCheck | None, step_id: str | None
    ) -> str:
        outcome = self.service.add_outcome(
            job_id,
            row.statement,
            row.importance,
            row.satisfaction,
            step_id=step_id,
            claim_check=claim_check,
        )
        return outcome.id

    def assign_theme(self, outcome_ids: list[str], theme_id: str) -> None:
        self.service.assign_theme(outcome_ids, theme_id)


@dataclass
class ImportReport:
    """What an import read, wrote, refused, and could not decide."""

    job_id: str
    dry_run: bool = False
    created: list[dict[str, Any]] = field(default_factory=list)
    refused: list[dict[str, Any]] = field(default_factory=list)
    unmatched_themes: list[dict[str, Any]] = field(default_factory=list)
    ambiguous_themes: list[dict[str, Any]] = field(default_factory=list)
    ignored_columns: dict[str, str] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    aborted: dict[str, Any] | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "dry_run": self.dry_run,
            "created": self.created,
            "refused": self.refused,
            "unmatched_themes": self.unmatched_themes,
            "ambiguous_themes": self.ambiguous_themes,
            "ignored_columns": self.ignored_columns,
            "warnings": self.warnings,
            "aborted": self.aborted,
        }


def _canonical(statement: str) -> str:
    """The statement as a duplicate check sees it: casefolded, inner runs of spaces collapsed.

    A spreadsheet's cell and a research note rarely agree on spacing, and a substring match
    would call "…arrives late" the same need as "…arrives late before payment terms expire".
    """
    return " ".join(statement.casefold().split())


def _row_problem(row: ImportRow) -> str | None:
    """Why this line cannot be filed, in the words the single-outcome door would use."""
    if row.problems:
        return "; ".join(row.problems)
    for name in ("importance", "satisfaction"):
        value = getattr(row, name)
        if value is not None and not 1.0 <= value <= 10.0:
            return str(ValueOutOfRangeError(f"{name} must be between 1.0 and 10.0"))
    verdict = evaluate_outcome_statement(row.statement)
    if not verdict["valid"]:
        return str(InvalidOutcomeStatementError(verdict))
    return None


def _resolve_step(row: ImportRow, steps: list[Step]) -> tuple[str | None, str | None]:
    """The step this row belongs on, or why the row does not say which one it does."""
    if row.step_id is not None:
        if not any(step.id == row.step_id for step in steps):
            return None, str(StepNotFoundError(row.step_id))
        return row.step_id, None
    if row.stage is None:
        return None, None
    try:
        stage = JobStage(row.stage.strip().lower())
    except ValueError:
        return None, f"Unknown stage: {row.stage}"
    matches = sorted(step.id for step in steps if step.stage is stage)
    if not matches:
        return None, f"no step in this job map is in stage '{stage.value}'"
    if len(matches) > 1:
        return None, (
            f"stage '{stage.value}' names {len(matches)} steps, so a row cannot pick one: "
            + ", ".join(matches)
        )
    return matches[0], None


def _claim_check(row: ImportRow) -> ClaimCheck | None:
    """A scored row came from someone typing numbers, not from asking the customer."""
    if row.importance is None and row.satisfaction is None:
        return None
    return manual_claim_check()


def import_outcomes(
    table: ParsedTable, target: ImportTarget, *, job_id: str, dry_run: bool = False
) -> ImportReport:
    report = ImportReport(
        job_id=job_id, dry_run=dry_run, ignored_columns=dict(table.ignored_columns)
    )
    if table.problems:
        report.refused.append({"line": 1, "statement": "", "reason": table.problems[0]})
        return report

    theme_ids: dict[str, list[str]] = {}
    for theme in target.themes(job_id):
        theme_ids.setdefault(theme.name, []).append(theme.id)
    steps = target.steps(job_id)
    seen = {_canonical(statement) for statement in target.existing_statements(job_id)}

    filings: dict[str, list[str]] = {}
    unmatched: dict[str, list[int]] = {}
    ambiguous: dict[str, tuple[list[str], list[int]]] = {}

    for row in table.rows:
        problem = _row_problem(row)
        if problem is None and row.job_id is not None and row.job_id != job_id:
            problem = f'row names job "{row.job_id}"; this import writes to "{job_id}"'
        step_id: str | None = None
        if problem is None:
            step_id, problem = _resolve_step(row, steps)
        if problem is not None:
            report.refused.append({"line": row.line, "statement": row.statement, "reason": problem})
            continue

        canonical = _canonical(row.statement)
        if canonical in seen:
            report.warnings.append(
                f"line {row.line} repeats a statement already filed on this job; "
                "a second outcome will be created"
            )

        outcome_id: str | None = None
        if not dry_run:
            try:
                outcome_id = target.add_outcome(job_id, row, _claim_check(row), step_id)
            except ImportAbortedError as exc:
                report.aborted = {"line": row.line, "reason": str(exc)}
                break
            except OdiError as exc:
                report.refused.append(
                    {"line": row.line, "statement": row.statement, "reason": str(exc)}
                )
                continue

        report.created.append(
            {
                "line": row.line,
                "statement": row.statement,
                "importance": row.importance,
                "satisfaction": row.satisfaction,
                "outcome_id": outcome_id,
            }
        )
        seen.add(canonical)

        if row.theme is None:
            continue
        candidates = theme_ids.get(row.theme, [])
        if not candidates:
            unmatched.setdefault(row.theme, []).append(row.line)
        elif len(candidates) > 1:
            entry = ambiguous.setdefault(row.theme, (sorted(candidates), []))
            entry[1].append(row.line)
        elif outcome_id is not None:
            filings.setdefault(candidates[0], []).append(outcome_id)

    report.unmatched_themes = [{"name": name, "lines": lines} for name, lines in unmatched.items()]
    report.ambiguous_themes = [
        {"name": name, "candidate_ids": candidates, "lines": lines}
        for name, (candidates, lines) in ambiguous.items()
    ]

    if dry_run:
        return report
    for theme_id, outcome_ids in filings.items():
        try:
            target.assign_theme(outcome_ids, theme_id)
        except OdiError as exc:
            report.warnings.append(f"theme {theme_id} was not filed: {exc}")
    return report
