"""ALH-223 (M2-04.2) — the workbook reader, and the promises it makes on the way in.

Every test here is about the one place a spreadsheet and a CSV genuinely differ: where the rows
come from. Once a workbook has been read, its lines go to ALH-222's header, synonym and score
rules, which is the whole point — there is no second validator to drift. What the reader owns is
therefore narrow and worth pinning: never guess a sheet, never compute a formula, never turn a
score it cannot read into "no score entered", and hand back the row number a person sees in their
spreadsheet app.
"""

from __future__ import annotations

import datetime
import io
import sys
import types
from collections.abc import Sequence
from pathlib import Path

import openpyxl
import pytest
from agentic_odi_core.errors import error_status
from agentic_odi_core.outcome_import import (
    XLSX_FORMAT,
    ParsedTable,
    SheetSelectionError,
    UnsupportedFormatError,
    XlsxExtraMissingError,
    format_for_name,
    import_outcomes,
    parse_outcome_table,
    read_rows,
    read_xlsx_rows,
)
from agentic_odi_core.outcome_import import ServiceImportTarget as _Target
from agentic_odi_core.repository import InMemoryRepository
from agentic_odi_core.services import ODIService
from fixtures.xlsx_workbook import Formula, workbook_bytes, xlsx_from_csv

FIXTURE = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "outcomes_mixed_40.csv"

STATEMENT = "Minimize the time to reconcile a supplier invoice when the statement arrives late"

#: ALH-223's promise, in the store's own words: an import never asks a formula what it means.
UNCACHED = (
    "is a formula with no stored value; this import reads stored values and never computes "
    "them — paste it as values and import again"
)

HEADER = ["statement", "importance", "satisfaction", "theme", "stage"]


def _one_sheet(*rows: Sequence[object]) -> bytes:
    return workbook_bytes({"Q3": [HEADER, *rows]})


# --- which sheet is read --------------------------------------------------------


def test_a_workbook_with_rows_in_one_sheet_is_read_without_being_named() -> None:
    source = workbook_bytes(
        {"Q3": [["statement", "importance"], [STATEMENT, 7.0]], "Notes": [[None, None]]}
    )

    assert read_xlsx_rows(source).lines == [
        (1, ["statement", "importance"]),
        (2, [STATEMENT, "7"]),
    ]


def test_two_sheets_with_rows_refuse_and_name_them() -> None:
    source = workbook_bytes({"Q3": [["statement"], [STATEMENT]], "Notes": [["need"]]})

    with pytest.raises(SheetSelectionError) as excinfo:
        read_xlsx_rows(source)

    assert str(excinfo.value) == (
        "this workbook has rows in 2 sheets (Q3, Notes); name the one to read with --sheet"
    )
    assert read_xlsx_rows(source, sheet=" Notes ").lines == [(1, ["need"])]


def test_an_unknown_sheet_names_the_ones_that_exist() -> None:
    source = workbook_bytes({"Q3": [["statement"], [STATEMENT]], "Notes": [["need"]]})

    with pytest.raises(SheetSelectionError) as excinfo:
        read_xlsx_rows(source, sheet="Backlog")

    assert str(excinfo.value) == 'no sheet named "Backlog" in this workbook; it has Q3, Notes'


def test_a_named_sheet_with_no_rows_refuses_rather_than_trying_another() -> None:
    source = workbook_bytes({"Q3": [["statement"], [STATEMENT]], "Notes": [[None]]})

    with pytest.raises(SheetSelectionError) as excinfo:
        read_xlsx_rows(source, sheet="Notes")

    assert str(excinfo.value) == 'sheet "Notes" has no rows; nothing to import'


def test_a_workbook_with_no_rows_anywhere_refuses() -> None:
    with pytest.raises(SheetSelectionError) as excinfo:
        read_xlsx_rows(workbook_bytes({"Q3": [[None]]}))

    assert str(excinfo.value) == "this workbook has no rows in any sheet; nothing to import"


def test_a_sheet_problem_refuses_the_file_at_both_doors() -> None:
    source = workbook_bytes({"Q3": [["statement"], [STATEMENT]], "Notes": [["need"]]})

    with pytest.raises(SheetSelectionError) as excinfo:
        parse_outcome_table(source, fmt=XLSX_FORMAT)

    assert "--sheet" in str(excinfo.value)


def test_a_blank_row_keeps_the_number_the_spreadsheet_shows() -> None:
    source = workbook_bytes(
        {"Q3": [["statement"], [STATEMENT], None, ["Minimize the cost of a duplicate charge"]]}
    )

    assert [row.line for row in parse_outcome_table(source, fmt=XLSX_FORMAT).rows] == [2, 4]


# --- what a cell is worth -------------------------------------------------------


def test_numbers_arrive_as_a_csv_would_have_carried_them() -> None:
    source = _one_sheet([STATEMENT, 7.0, 7.5, None, None])

    table = parse_outcome_table(source, fmt=XLSX_FORMAT)

    assert read_xlsx_rows(source).lines[1][1][1:3] == ["7", "7.5"]
    assert (table.rows[0].importance, table.rows[0].satisfaction) == (7.0, 7.5)


def test_a_formula_with_a_stored_value_is_read_as_that_value() -> None:
    table = parse_outcome_table(
        _one_sheet([STATEMENT, Formula("=AVERAGE(B2:B9)", cached=7.5), 2, None, None]),
        fmt=XLSX_FORMAT,
    )

    assert table.rows[0].importance == 7.5
    assert table.rows[0].problems == []
    assert table.warnings == []


def test_an_uncached_formula_refuses_its_row_and_names_the_cell() -> None:
    filler = [
        [f"Minimize the cost of a duplicate charge {n}", 6, 1, None, None] for n in range(2, 12)
    ]
    table = parse_outcome_table(
        workbook_bytes({"Q3": [HEADER, *filler, [STATEMENT, Formula("=B7+C7"), 1, None, None]]}),
        fmt=XLSX_FORMAT,
    )

    scored = [row for row in table.rows if row.line == 12]
    assert [row.problems for row in scored] == [[f"cell B12 {UNCACHED}"]]
    #: A score nobody calculated is never filed as "unscored", and it never costs the other rows.
    assert scored[0].importance is None
    assert all(not row.problems for row in table.rows if row.line != 12)


def test_an_uncached_formula_in_an_optional_column_warns_instead_of_refusing() -> None:
    rows: list[Sequence[object]] = [
        HEADER,
        [STATEMENT, 6, 1, Formula("=D2"), Formula("=E2")],
        ["Minimize the cost of a duplicate charge", 6, 1, Formula("=D3"), None],
    ]

    table = parse_outcome_table(workbook_bytes({"Q3": rows}), fmt=XLSX_FORMAT)

    assert table.warnings == [
        "3 optional cells hold a formula with no stored value (theme, stage); "
        "they were read as empty"
    ]
    assert [row.problems for row in table.rows] == [[], []]
    assert [row.theme for row in table.rows] == [None, None]


def test_one_optional_formula_cell_says_so_in_the_singular() -> None:
    table = parse_outcome_table(
        _one_sheet([STATEMENT, 6, 1, Formula("=D2"), None]), fmt=XLSX_FORMAT
    )

    assert table.warnings == [
        "1 optional cell holds a formula with no stored value (theme); it was read as empty"
    ]


def test_a_date_in_a_score_column_is_refused_by_the_number_rule() -> None:
    book = openpyxl.Workbook()
    book.active.title = "Q3"
    book.active.append(["statement", "importance"])
    book.active.append([STATEMENT, datetime.datetime(2026, 11, 4)])
    buffer = io.BytesIO()
    book.save(buffer)

    table = parse_outcome_table(buffer.getvalue(), fmt=XLSX_FORMAT)

    assert table.rows[0].problems == ['importance must be a number, got "2026-11-04 00:00:00"']


def test_a_clean_workbook_is_opened_once(monkeypatch: pytest.MonkeyPatch) -> None:
    loads: list[object] = []

    def counting_load(*args: object, **kwargs: object) -> object:
        loads.append(kwargs.get("data_only"))
        return openpyxl.load_workbook(*args, **kwargs)  # type: ignore[arg-type]

    stub = types.ModuleType("openpyxl")
    stub.load_workbook = counting_load  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "openpyxl", stub)

    read_xlsx_rows(workbook_bytes({"Q3": [["statement", "importance"], [STATEMENT, 6]]}))
    assert loads == [True], "a file with nothing empty has nothing to investigate"

    loads.clear()
    read_xlsx_rows(_one_sheet([STATEMENT, 6, 1, None, None]))
    assert loads == [True, False], "an empty cell is asked what it really was"


# --- the extra is optional, and says so ----------------------------------------


def test_a_build_without_the_xlsx_extra_names_the_install_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(sys.modules, "openpyxl", None)

    with pytest.raises(XlsxExtraMissingError) as excinfo:
        read_xlsx_rows(workbook_bytes({"Q3": [["statement"], [STATEMENT]]}))

    message = str(excinfo.value)
    assert "pip install 'agentic-odi-core[xlsx]'" in message
    assert "save the workbook as CSV" in message
    #: A missing extra is a bad request, never a server fault and never a traceback.
    assert error_status(excinfo.value) == 400


def test_the_parser_routes_a_workbook_to_the_workbook_reader() -> None:
    table = parse_outcome_table(_one_sheet([STATEMENT, 6, 1, None, None]), fmt="XLSX ")

    assert [row.line for row in table.rows] == [2]


def test_a_csv_handed_a_sheet_is_refused() -> None:
    with pytest.raises(SheetSelectionError) as excinfo:
        parse_outcome_table(f"statement\n{STATEMENT}\n", sheet="Backlog")

    assert str(excinfo.value) == "a CSV has no sheets; --sheet is for a .xlsx workbook"


# --- the two doors still agree --------------------------------------------------


def test_the_workbook_of_the_csv_fixture_has_the_same_lines_as_the_csv() -> None:
    assert (
        read_xlsx_rows(xlsx_from_csv(FIXTURE.read_text(encoding="utf-8"))).lines
        == read_rows(FIXTURE.read_bytes()).lines
    )


def test_the_report_puts_the_files_own_warning_before_what_the_store_knew() -> None:
    service = ODIService(InMemoryRepository())
    job = service.add_job("Reconcile supplier invoices")
    service.add_outcome(job.id, STATEMENT, 8.0, 2.0)

    report = import_outcomes(
        parse_outcome_table(_one_sheet([STATEMENT, 6, 1, Formula("=D2"), None]), fmt=XLSX_FORMAT),
        _Target(service),
        job_id=job.id,
        dry_run=True,
    )

    assert "optional cell holds a formula" in report.warnings[0]
    assert "repeats a statement already filed" in report.warnings[1]


def test_a_workbook_and_a_csv_of_the_same_rows_build_the_same_table() -> None:
    from_csv = parse_outcome_table(FIXTURE.read_bytes())
    from_workbook = parse_outcome_table(
        xlsx_from_csv(FIXTURE.read_text(encoding="utf-8")), fmt=XLSX_FORMAT
    )

    assert isinstance(from_csv, ParsedTable)
    assert [row.line for row in from_workbook.rows] == [row.line for row in from_csv.rows]
    assert [
        (row.line, row.statement, row.importance, row.satisfaction, row.theme, row.problems)
        for row in from_workbook.rows
    ] == [
        (row.line, row.statement, row.importance, row.satisfaction, row.theme, row.problems)
        for row in from_csv.rows
    ]


def test_format_for_name_is_the_rule_both_doors_share() -> None:
    assert format_for_name("out.csv") == "csv"
    assert format_for_name("out.CSV") == "csv"
    assert format_for_name("notes") == "csv"
    assert format_for_name("wb.xlsx") == XLSX_FORMAT
    assert format_for_name("wb.XLSX") == XLSX_FORMAT

    for tried in ("wb.xls", "notes.txt"):
        with pytest.raises(UnsupportedFormatError) as excinfo:
            format_for_name(tried)
        assert f"'{Path(tried).suffix.lstrip('.')}'" in str(excinfo.value)
