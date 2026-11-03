"""ALH-222 (M2-04.1) — read a spreadsheet of outcomes into rows.

Two doors, one file format: the CLI reads a path and the Studio sidecar reads an upload, and
both hand the same rows to the same loop. Nothing here writes, repairs or guesses. A cell that
cannot be used is reported as unused rather than quietly turned into something else, and every
line of the file is accounted for — a refusal names the line the person will find in their
spreadsheet app, with the header on line 1.
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field

from agentic_odi_core.errors import OdiError

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
