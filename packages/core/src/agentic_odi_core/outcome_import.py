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
from pathlib import PurePosixPath
from typing import Any, Protocol, runtime_checkable

from agentic_odi_core.errors import OdiError, ValidationError
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
#: The workbook path, which needs the optional ``xlsx`` extra and says so when it is missing.
XLSX_FORMAT = "xlsx"

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


class UnsupportedFormatError(ValidationError):
    """Raised when the import is handed a file neither door reads.

    A ``ValidationError``, because a wrong suffix is a mistake in the request: the upload answers
    it with the shared envelope rather than a report, and ``error_status()`` never sends it to 500.
    """


class XlsxExtraMissingError(ValidationError):
    """Raised when this build was installed without the optional ``xlsx`` extra."""


class SheetSelectionError(ValidationError):
    """Raised when the workbook does not say, unambiguously, which sheet to read.

    Guessing the sheet Excel happens to have marked active is how forty rows of notes become
    desired Outcomes, and an import has no undo token to take them back.
    """


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
    #: The file's own condition, which the report says before anything the store knew about it.
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class TableLines:
    """What the two formats genuinely have to agree on: numbered rows of text.

    ``formula_cells`` is the workbook path's extra answer to one question — *was this empty cell a
    formula nobody recalculated?* — because ``data_only`` cannot tell an empty cell from an
    uncached one. Only the parser decides what that means: a refusal in a column the import needs,
    a warning in one it does not.
    """

    lines: list[tuple[int, list[str]]]
    formula_cells: dict[int, list[int]] = field(default_factory=dict)


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


def _unknown_format(tried: str) -> UnsupportedFormatError:
    return UnsupportedFormatError(
        f"'{tried}' is not a format this import reads; only '.{READABLE_FORMAT}' and "
        f"'.{XLSX_FORMAT}' are. Saving the spreadsheet as {READABLE_FORMAT.upper()} loses "
        "nothing a research file carries."
    )


def format_for_name(filename: str) -> str:
    """Which reader a file's name asks for — the one rule both doors share.

    A person names the format by saving the file, so the suffix is not a guess the surface makes;
    it is the only signal either door has, and it is read the same way here in both.
    """
    suffix = PurePosixPath(filename).suffix.lower().lstrip(".")
    if suffix in ("", READABLE_FORMAT):
        return READABLE_FORMAT
    if suffix == XLSX_FORMAT:
        return XLSX_FORMAT
    raise _unknown_format(suffix)


def read_rows(source: str | bytes) -> TableLines:
    """Every line of a CSV, numbered the way ``csv`` counts them, blanks included."""
    text = source.decode("utf-8-sig", errors="replace") if isinstance(source, bytes) else source
    reader = csv.reader(io.StringIO(text, newline=""))
    return TableLines(lines=[(reader.line_num, cells) for cells in reader])


def _column_letter(index: int) -> str:
    """The spreadsheet's own name for a 0-based column, so a refusal points at a cell."""
    letters = ""
    while index >= 0:
        index, remainder = divmod(index, 26)
        letters = chr(ord("A") + remainder) + letters
        index -= 1
    return letters


def _cell_text(value: Any) -> str:
    """A cell's stored value as the text a CSV would have carried — never a computed one."""
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def _load_workbook() -> Any:
    """The guarded import that makes the extra optional in every environment."""
    try:
        from openpyxl import load_workbook
    except ImportError:
        # ``from None``: the sentence is the whole answer, and a ModuleNotFoundError stack above
        # it would say less than the install path does.
        raise XlsxExtraMissingError(
            f"reading a .{XLSX_FORMAT} needs the optional xlsx extra: "
            "pip install 'agentic-odi-core[xlsx]' — or save the workbook as "
            f"{READABLE_FORMAT.upper()}, which this build reads without it"
        ) from None
    return load_workbook


def _has_rows(worksheet: Any) -> bool:
    return next(worksheet.iter_rows(values_only=True), None) is not None


def _select_sheet(workbook: Any, sheet: str | None) -> Any:
    """The sheet to read, or the reason this workbook does not say which one it is."""
    names = list(workbook.sheetnames)
    with_rows = [name for name in names if _has_rows(workbook[name])]
    wanted = sheet.strip() if sheet else ""
    if wanted:
        if wanted not in names:
            raise SheetSelectionError(
                f'no sheet named "{wanted}" in this workbook; it has {", ".join(names)}'
            )
        if wanted not in with_rows:
            raise SheetSelectionError(f'sheet "{wanted}" has no rows; nothing to import')
        return workbook[wanted]
    if not with_rows:
        raise SheetSelectionError("this workbook has no rows in any sheet; nothing to import")
    if len(with_rows) > 1:
        raise SheetSelectionError(
            f"this workbook has rows in {len(with_rows)} sheets ({', '.join(with_rows)}); "
            "name the one to read with --sheet"
        )
    return workbook[with_rows[0]]


def read_xlsx_rows(source: bytes, sheet: str | None = None) -> TableLines:
    """One sheet of a workbook, as numbered rows of text.

    Read with ``data_only`` first: that is the only value a person's file stores for a formula, and
    this import never computes one. A cell that came back empty in a row that has other content is
    then asked what it really was, from a second load of the same bytes — an uncached formula is
    indistinguishable from an empty cell otherwise, and an empty score would otherwise be filed as
    research nobody measured. A workbook with nothing empty is opened once.
    """
    load = _load_workbook()
    worksheet = _select_sheet(load(io.BytesIO(source), data_only=True), sheet)

    lines: list[tuple[int, list[str]]] = []
    empty: list[tuple[int, int]] = []
    for cells in worksheet.iter_rows():
        number = cells[0].row if cells else 1
        text = [_cell_text(cell.value) for cell in cells]
        lines.append((number, text))
        if any(text):
            empty.extend((number, cell.column) for cell in cells if not text[cell.column - 1])

    formulas: dict[int, list[int]] = {}
    if empty:
        probe = _select_sheet(load(io.BytesIO(source), data_only=False), sheet)
        for number, column in empty:
            if probe.cell(row=number, column=column).data_type == "f":
                formulas.setdefault(number, []).append(column - 1)
    return TableLines(lines=lines, formula_cells=formulas)


def parse_outcome_table(
    source: str | bytes, fmt: str = READABLE_FORMAT, sheet: str | None = None
) -> ParsedTable:
    kind = _normalise(fmt)
    if kind not in (READABLE_FORMAT, XLSX_FORMAT):
        raise _unknown_format(kind)
    if kind == XLSX_FORMAT:
        raw = source if isinstance(source, bytes) else source.encode("utf-8")
        return _build_rows(read_xlsx_rows(raw, sheet=sheet))
    if sheet is not None and sheet.strip():
        raise SheetSelectionError(
            f"a {READABLE_FORMAT.upper()} has no sheets; --sheet is for a .{XLSX_FORMAT} workbook"
        )
    return _build_rows(read_rows(source))


def _build_rows(table: TableLines) -> ParsedTable:
    """ALH-222's row rules, fed by whichever reader the format asked for."""
    if not table.lines:
        return ParsedTable(problems=["no header row: the file must name its columns"])
    _, header = table.lines[0]
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

    #: The columns a row cannot be filed without, so an unreadable cell in one is a refusal.
    needed = {index for index, _ in statement_columns} | {
        index for index, name in field_columns if name in ("importance", "satisfaction")
    }
    names = {index: name for index, name in statement_columns + field_columns}
    order = {name: index for index, name in enumerate(header)}

    rows: list[ImportRow] = []
    unreadable_optional: dict[str, int] = {}
    for number, cells in table.lines[1:]:
        if not any(cell.strip() for cell in cells) and number not in table.formula_cells:
            continue
        values = {
            name: cells[index].strip() if index < len(cells) else ""
            for index, name in field_columns
        }
        problems: list[str] = []

        for index in table.formula_cells.get(number, []):
            if index in needed:
                problems.append(
                    f"cell {_column_letter(index)}{number} is a formula with no stored value; "
                    "this import reads stored values and never computes them — "
                    "paste it as values and import again"
                )
            else:
                name = names.get(index) or _normalise(
                    header[index] if index < len(header) else f"column {_column_letter(index)}"
                )
                unreadable_optional[name] = unreadable_optional.get(name, 0) + 1

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
                line=number,
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

    warnings = _unreadable_optional_warning(unreadable_optional, order)

    if not rows:
        return ParsedTable(
            ignored_columns=ignored,
            problems=["no data rows: the file has nothing to import"],
            warnings=warnings,
        )
    return ParsedTable(rows=rows, ignored_columns=ignored, warnings=warnings)


def _unreadable_optional_warning(counts: dict[str, int], order: dict[str, int]) -> list[str]:
    """One sentence for the optional cells that held a formula and nothing else.

    A note that silently disappears is a filing detail the report can be read and fixed from; a
    score that silently disappears is a lie about the research, and that case is a refusal instead.
    """
    total = sum(counts.values())
    if not total:
        return []
    names = ", ".join(sorted(counts, key=lambda name: order.get(name, len(order))))
    if total == 1:
        return [
            f"1 optional cell holds a formula with no stored value ({names}); it was read as empty"
        ]
    return [
        f"{total} optional cells hold a formula with no stored value ({names}); "
        "they were read as empty"
    ]


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
    #: The file's own condition goes first: it is what the person can fix in their spreadsheet,
    #: while everything below it is what the store already knew.
    report.warnings.extend(table.warnings)
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
