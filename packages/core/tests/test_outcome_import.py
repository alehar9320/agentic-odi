"""ALH-222 (M2-04.1) — parsing a spreadsheet of outcomes into rows.

The parser decides what a column means, which line a value came from, and what to say about
a column it cannot use. It owns nothing about writing: the CLI and the Studio upload read the
same bytes through this function, so a person gets the same answer whichever door they came
to, and the row numbers in a report are the numbers in their spreadsheet app.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from agentic_odi_core.outcome_import import (
    UnsupportedFormatError,
    parse_outcome_table,
)

FIXTURE = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "outcomes_mixed_40.csv"

WELL_FORMED = "Minimize the time to reconcile a supplier invoice when the statement arrives late"


def _table(text: str):
    return parse_outcome_table(text)


def test_a_file_reads_into_one_row_per_line() -> None:
    table = _table(f"statement,importance,satisfaction\n{WELL_FORMED},8,2\n")

    assert table.problems == []
    assert len(table.rows) == 1
    row = table.rows[0]
    assert (row.line, row.statement, row.importance, row.satisfaction) == (2, WELL_FORMED, 8.0, 2.0)


def test_the_statement_column_accepts_its_documented_synonyms() -> None:
    for header in ("statement", "outcome", "need", " Statement "):
        table = _table(f"{header}\n{WELL_FORMED}\n")
        assert table.problems == [], header
        assert table.rows[0].statement == WELL_FORMED, header


def test_two_synonyms_that_mean_the_same_thing_are_not_an_error() -> None:
    table = _table(f"outcome,need\n{WELL_FORMED},{WELL_FORMED}\n")

    assert table.problems == []
    assert table.rows[0].statement == WELL_FORMED


def test_a_row_whose_two_statement_cells_disagree_is_refused_not_resolved() -> None:
    # The file still imports; one row that names two different needs is that row's problem,
    # because picking one would be the importer inventing research.
    other = "Maximize the number of exceptions caught before close when reconciling"
    table = _table(f"statement,need\n{WELL_FORMED},{other}\n{WELL_FORMED},{WELL_FORMED}\n")

    assert [row.line for row in table.rows] == [2, 3]
    assert table.problems == []
    assert table.rows[0].problems == [
        'statement is ambiguous: "statement" and "need" name two different needs'
    ]
    assert table.rows[1].problems == []


def test_line_numbers_are_physical_and_the_header_is_line_one() -> None:
    rows = FIXTURE.read_text(encoding="utf-8").splitlines()
    table = parse_outcome_table("\n".join(rows) + "\n")

    assert table.rows[0].line == 2
    assert [row.line for row in table.rows[-2:]] == [40, 41]


def test_a_blank_score_is_none_and_a_zero_score_is_zero() -> None:
    table = _table(f"statement,importance,satisfaction\n{WELL_FORMED},,\n{WELL_FORMED},0,0\n")

    unscored, zeroed = table.rows
    assert (unscored.importance, unscored.satisfaction) == (None, None)
    assert (zeroed.importance, zeroed.satisfaction) == (0.0, 0.0)


def test_a_cell_that_is_not_a_number_becomes_a_row_problem() -> None:
    table = _table(f"statement,importance\n{WELL_FORMED},soon\n")

    assert table.rows[0].importance is None
    assert table.rows[0].problems == ['importance must be a number, got "soon"']


def test_a_column_the_store_cannot_hold_is_reported_not_silently_dropped() -> None:
    table = _table(f"statement,Notes,importance_n,opportunity_score\n{WELL_FORMED},churn,4,13\n")

    # Read into the row, because the shape a spreadsheet arrives in is documented; reported as
    # ignored, because an Outcome has no field to hold a count and inventing one is not this
    # increment's to do.
    assert table.rows[0].importance_n == 4.0
    for header in ("notes", "importance_n", "opportunity_score"):
        assert header in table.ignored_columns, header
    assert "not an outcome column" in table.ignored_columns["notes"]
    assert "no field" in table.ignored_columns["importance_n"]
    assert "computed" in table.ignored_columns["opportunity_score"]


def test_the_import_columns_are_read() -> None:
    table = _table(
        f"statement,theme,stage,step_id,job_id\n{WELL_FORMED},Onboarding,execute,step-1,job-9\n"
    )

    row = table.rows[0]
    assert (row.theme, row.stage, row.step_id, row.job_id) == (
        "Onboarding",
        "execute",
        "step-1",
        "job-9",
    )


def test_text_and_bytes_parse_to_the_same_rows() -> None:
    document = f"statement,importance\n{WELL_FORMED},8\n"

    assert parse_outcome_table(document.encode("utf-8")).rows == parse_outcome_table(document).rows


def test_only_csv_is_read_and_the_refusal_names_the_format() -> None:
    with pytest.raises(UnsupportedFormatError) as excinfo:
        parse_outcome_table(FIXTURE.read_bytes(), fmt="xlsx")

    assert "csv" in str(excinfo.value)
    assert "xlsx" in str(excinfo.value)


@pytest.mark.parametrize(
    "document,expected",
    [
        ("\n", "no header row"),
        ("notes,importance\nx,1\n", "statement"),
        ("statement\n", "no data rows"),
    ],
)
def test_a_file_that_cannot_be_read_is_one_actionable_problem(document: str, expected: str) -> None:
    table = _table(document)

    assert table.rows == []
    assert len(table.problems) == 1
    assert expected in table.problems[0].lower()


def test_the_fixture_holds_forty_rows_and_three_broken_ones() -> None:
    table = parse_outcome_table(FIXTURE.read_bytes())

    assert len(table.rows) == 40
    assert table.problems == []
    broken = {row.line: row for row in table.rows if row.line in {9, 18, 27}}
    assert broken[9].importance == 11.0
    assert broken[18].statement == "Make it faster"
    assert broken[27].stage == "collect"
    assert all(row.statement or row.problems for row in table.rows)


def test_a_blank_statement_cell_stays_a_row_with_a_problem() -> None:
    # A row is never dropped: the report has to account for all forty lines, and an empty
    # cell is the row's own problem rather than a missing one.
    table = _table(f"statement,importance\n,8\n{WELL_FORMED},9\n")

    assert [row.line for row in table.rows] == [2, 3]
    assert table.rows[0].problems == ["statement is empty; nothing to file"]
    assert table.rows[1].problems == []


def test_an_exported_file_round_trips_through_the_import_columns() -> None:
    # The CLI's `export --format csv` header, imported back. `id` and `opportunity_score` come
    # out of the store and must not be obeyed; the scores and the step must survive.
    document = (
        "id,job_id,step_id,statement,importance,satisfaction,opportunity_score\n"
        f"o-1,job-1,step-1,{WELL_FORMED},8.0,2.0,14.0\n"
    )

    table = _table(document)

    assert table.rows[0].statement == WELL_FORMED
    assert table.rows[0].step_id == "step-1"
    assert table.rows[0].job_id == "job-1"
    assert (table.rows[0].importance, table.rows[0].satisfaction) == (8.0, 2.0)
    assert set(table.ignored_columns) == {"id", "opportunity_score"}
