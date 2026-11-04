"""``odi desired-outcomes import`` over the local backend: a CSV and a workbook, one door.

The command is a thin door: it reads the file, hands the rows to the shared loop, and echoes the
report. What matters here is that the loop writes through ``run_tool``, the same door
``desired-outcomes add`` uses, so an import cannot file a row the CLI would refuse, and that a
``--dry-run`` says exactly what the real run will do — same lines, same refusals, no ids.
ALH-223 adds the workbook to that same door, so the tests below compare the two files rather than
re-check the rows, and pin the three ways a workbook can refuse the whole run: no reader built in,
more than one sheet with rows, a name that is not a spreadsheet.
"""

from __future__ import annotations

import csv
import io
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from agentic_odi_cli.cli import app
from typer.testing import CliRunner

#: One fixture, both doors: the Studio upload test reads these same bytes.
FIXTURE = (
    Path(__file__).resolve().parents[3]
    / "packages"
    / "core"
    / "tests"
    / "fixtures"
    / "outcomes_mixed_40.csv"
)


def _csv(tmp_path) -> str:
    document = tmp_path / "outcomes.csv"
    document.write_bytes(FIXTURE.read_bytes())
    return str(document)


def _invoke(runner: CliRunner, db: str, args: list[str]):
    return runner.invoke(app, ["--db", db, *args])


def _json(runner: CliRunner, db: str, args: list[str]) -> Any:
    result = _invoke(runner, db, args)
    assert result.exit_code == 0, result.output
    return json.loads(result.output)


def _seed(tmp_path) -> tuple[str, str]:
    """db path and job id, with the one EXECUTE step and three themes the fixture assumes."""
    db = str(tmp_path / "odi.db")
    runner = CliRunner()
    job_id = str(
        _json(runner, db, ["jobs", "add", "--name", "Reconcile supplier invoices", "--json"])["id"]
    )
    _json(
        runner,
        db,
        [
            "steps",
            "add",
            "--job-id",
            job_id,
            "--name",
            "Execute the reconciliation",
            "--order",
            "5",
            "--stage",
            "execute",
            "--allow-empty-job-map",
            "--json",
        ],
    )
    _json(runner, db, ["themes", "add", "--name", "Onboarding", "--job", job_id, "--json"])
    _json(runner, db, ["themes", "add", "--name", "Urgent", "--job", job_id, "--json"])
    _json(runner, db, ["themes", "add", "--name", "Urgent", "--json"])
    return db, job_id


def test_a_dry_run_reports_the_run_and_writes_nothing(tmp_path) -> None:
    db, job_id = _seed(tmp_path)
    runner = CliRunner()

    result = _invoke(
        runner,
        db,
        ["desired-outcomes", "import", _csv(tmp_path), "--job-id", job_id, "--dry-run"],
    )

    assert result.exit_code == 0, result.output
    assert "Would create 37 outcome(s)" in result.output
    assert "3 refused" in result.output
    assert _json(runner, db, ["desired-outcomes", "list", "--job-id", job_id, "--json"]) == []


def test_the_json_report_is_the_report(tmp_path) -> None:
    db, job_id = _seed(tmp_path)
    runner = CliRunner()

    report = _json(
        runner,
        db,
        ["desired-outcomes", "import", _csv(tmp_path), "--job-id", job_id, "--dry-run", "--json"],
    )

    assert report["dry_run"] is True
    assert report["job_id"] == job_id
    assert len(report["created"]) == 37
    assert [entry["line"] for entry in report["refused"]] == [9, 18, 27]
    assert report["unmatched_themes"] == [{"name": "Retention", "lines": [8, 10, 11]}]
    assert [entry["name"] for entry in report["ambiguous_themes"]] == ["Urgent"]
    assert report["aborted"] is None
    assert report["warnings"] == []


def test_the_write_run_is_its_preview_apart_from_ids(tmp_path) -> None:
    db, job_id = _seed(tmp_path)
    runner = CliRunner()
    preview = _json(
        runner,
        db,
        ["desired-outcomes", "import", _csv(tmp_path), "--job-id", job_id, "--dry-run", "--json"],
    )

    written = _json(
        runner, db, ["desired-outcomes", "import", _csv(tmp_path), "--job-id", job_id, "--json"]
    )

    assert all(entry["outcome_id"] is None for entry in preview["created"])
    assert all(entry["outcome_id"] for entry in written["created"])
    assert {
        **written,
        "dry_run": True,
        "created": [{**row, "outcome_id": None} for row in written["created"]],
    } == preview
    assert len(_json(runner, db, ["desired-outcomes", "list", "--job-id", job_id, "--json"])) == 37


def test_a_refusal_names_its_line_and_the_range_sentence(tmp_path) -> None:
    db, job_id = _seed(tmp_path)
    runner = CliRunner()

    result = _invoke(runner, db, ["desired-outcomes", "import", _csv(tmp_path), "--job-id", job_id])

    assert "must be between 1.0 and 10.0" in result.output
    assert "9" in result.output
    assert "Unknown stage: collect" in result.output


def test_the_theme_notes_are_in_the_human_report(tmp_path) -> None:
    db, job_id = _seed(tmp_path)
    runner = CliRunner()

    result = _invoke(runner, db, ["desired-outcomes", "import", _csv(tmp_path), "--job-id", job_id])

    assert "Retention" in result.output
    assert "Urgent" in result.output


def test_a_write_run_says_how_to_take_it_back(tmp_path) -> None:
    db, job_id = _seed(tmp_path)
    runner = CliRunner()

    result = _invoke(runner, db, ["desired-outcomes", "import", _csv(tmp_path), "--job-id", job_id])

    created = _json(runner, db, ["desired-outcomes", "list", "--job-id", job_id, "--json"])
    assert len(created) == 37
    assert "desired-outcomes delete" in result.output
    assert all(str(item["id"]) in result.output for item in created)


def test_an_unknown_job_exits_one_and_writes_nothing(tmp_path) -> None:
    db, _ = _seed(tmp_path)
    runner = CliRunner()

    result = _invoke(runner, db, ["desired-outcomes", "import", _csv(tmp_path), "--job-id", "nope"])

    assert result.exit_code == 1
    assert "nope" in result.output


def test_a_path_that_is_not_there_names_the_path(tmp_path) -> None:
    db, job_id = _seed(tmp_path)
    runner = CliRunner()
    missing = str(tmp_path / "gone.csv")

    result = _invoke(runner, db, ["desired-outcomes", "import", missing, "--job-id", job_id])

    assert result.exit_code == 1
    assert "gone.csv" in result.output


def test_a_file_with_no_statement_column_is_one_problem_at_line_one(tmp_path) -> None:
    db, job_id = _seed(tmp_path)
    runner = CliRunner()
    document = tmp_path / "notes.csv"
    document.write_text("notes,importance\nchurn,1\n", encoding="utf-8")

    report = _json(
        runner,
        db,
        ["desired-outcomes", "import", str(document), "--job-id", job_id, "--json"],
    )

    assert report["created"] == []
    assert [entry["line"] for entry in report["refused"]] == [1]
    assert "statement" in report["refused"][0]["reason"]
    assert _json(runner, db, ["desired-outcomes", "list", "--job-id", job_id, "--json"]) == []


def test_a_scored_row_imported_without_a_claim_check_is_marked_as_by_hand(tmp_path) -> None:
    db, job_id = _seed(tmp_path)
    runner = CliRunner()

    _invoke(runner, db, ["desired-outcomes", "import", _csv(tmp_path), "--job-id", job_id])

    outcomes = _json(runner, db, ["desired-outcomes", "list", "--job-id", job_id, "--json"])
    scored = [item for item in outcomes if item["importance"] is not None]
    assert scored
    assert all("by hand" in item["claim_check"]["skips"][0]["reason"] for item in scored)


def test_an_import_of_the_same_file_twice_warns_about_the_repeat(tmp_path) -> None:
    db, job_id = _seed(tmp_path)
    runner = CliRunner()
    _invoke(runner, db, ["desired-outcomes", "import", _csv(tmp_path), "--job-id", job_id])

    second = _json(
        runner,
        db,
        ["desired-outcomes", "import", _csv(tmp_path), "--job-id", job_id, "--json"],
    )

    assert len(second["warnings"]) == 37
    assert len(second["created"]) == 37
    assert len(_json(runner, db, ["desired-outcomes", "list", "--job-id", job_id, "--json"])) == 74


# --- ALH-223: the same door, opened with a workbook -----------------------------


def _value(cell: object) -> object:
    """A cell the way ``Save as`` writes one: a number in the file stays a number."""
    if isinstance(cell, str):
        try:
            return float(cell)
        except ValueError:
            return cell
    return cell


def _workbook(tmp_path, name: str, sheets: Mapping[str, Sequence[Sequence[object]]]) -> str:
    import openpyxl

    book = openpyxl.Workbook()
    for index, (sheet, rows) in enumerate(sheets.items()):
        worksheet = book.active if index == 0 else book.create_sheet()
        worksheet.title = sheet
        for row in rows:
            worksheet.append([_value(cell) for cell in row])
    document = tmp_path / name
    book.save(document)
    return str(document)


def _fixture_rows() -> list[list[str]]:
    return [row for row in csv.reader(io.StringIO(FIXTURE.read_text(encoding="utf-8"))) if row]


def test_a_workbook_and_a_csv_of_the_same_rows_report_the_same_run(tmp_path) -> None:
    db, job_id = _seed(tmp_path)
    runner = CliRunner()
    document = _workbook(tmp_path, "outcomes.xlsx", {"Outcomes": _fixture_rows()})

    from_csv = _json(
        runner,
        db,
        ["desired-outcomes", "import", _csv(tmp_path), "--job-id", job_id, "--dry-run", "--json"],
    )
    from_workbook = _json(
        runner,
        db,
        ["desired-outcomes", "import", document, "--job-id", job_id, "--dry-run", "--json"],
    )

    assert from_workbook == from_csv


def test_a_workbook_with_rows_in_two_sheets_names_the_tabs_it_could_read(tmp_path) -> None:
    db, job_id = _seed(tmp_path)
    runner = CliRunner()
    document = _workbook(
        tmp_path,
        "plans.xlsx",
        {
            "Backlog": [
                ["statement", "importance"],
                ["Minimize the cost of a duplicate charge when the ledger closes twice", 6],
            ],
            "Q3": [
                ["statement"],
                [
                    "Minimize the time to reconcile a supplier invoice when the statement "
                    "arrives late"
                ],
            ],
        },
    )

    result = _invoke(runner, db, ["desired-outcomes", "import", document, "--job-id", job_id])

    assert result.exit_code == 1
    assert "Backlog" in result.output and "Q3" in result.output
    assert "--sheet" in result.output
    assert _json(runner, db, ["desired-outcomes", "list", "--job-id", job_id, "--json"]) == []

    picked = _json(
        runner,
        db,
        [
            "desired-outcomes",
            "import",
            document,
            "--job-id",
            job_id,
            "--sheet",
            "Backlog",
            "--json",
        ],
    )

    assert [entry["statement"] for entry in picked["created"]] == [
        "Minimize the cost of a duplicate charge when the ledger closes twice"
    ]


def test_a_sheet_with_nothing_on_it_is_said_rather_than_skipped(tmp_path) -> None:
    db, job_id = _seed(tmp_path)
    runner = CliRunner()
    document = _workbook(
        tmp_path,
        "plans.xlsx",
        {
            "Outcomes": [["statement"], ["Minimize the cost of a duplicate charge"]],
            "Parking": [],
        },
    )

    result = _invoke(
        runner,
        db,
        ["desired-outcomes", "import", document, "--job-id", job_id, "--sheet", "Parking"],
    )

    assert result.exit_code == 1
    assert "Parking" in result.output and "no rows" in result.output


def test_a_build_without_the_xlsx_extra_names_the_install_path(tmp_path, monkeypatch) -> None:
    import sys

    db, job_id = _seed(tmp_path)
    runner = CliRunner()
    document = _workbook(
        tmp_path, "outcomes.xlsx", {"Outcomes": [["statement"], ["Minimize anything at all"]]}
    )
    monkeypatch.setitem(sys.modules, "openpyxl", None)

    result = _invoke(runner, db, ["desired-outcomes", "import", document, "--job-id", job_id])

    assert result.exit_code == 1
    assert "agentic-odi-core[xlsx]" in result.output
    assert "csv" in result.output.lower()
    assert _json(runner, db, ["desired-outcomes", "list", "--job-id", job_id, "--json"]) == []


def test_a_suffix_neither_door_reads_exits_one_naming_it(tmp_path) -> None:
    db, job_id = _seed(tmp_path)
    runner = CliRunner()
    document = tmp_path / "notes.txt"
    document.write_text("statement\nMinimize anything at all\n", encoding="utf-8")

    result = _invoke(runner, db, ["desired-outcomes", "import", str(document), "--job-id", job_id])

    assert result.exit_code == 1
    assert "'txt'" in result.output
    assert _json(runner, db, ["desired-outcomes", "list", "--job-id", job_id, "--json"]) == []


def test_a_csv_handed_a_sheet_is_refused_the_same_way(tmp_path) -> None:
    db, job_id = _seed(tmp_path)
    runner = CliRunner()

    result = _invoke(
        runner,
        db,
        [
            "desired-outcomes",
            "import",
            _csv(tmp_path),
            "--job-id",
            job_id,
            "--sheet",
            "Backlog",
        ],
    )

    assert result.exit_code == 1
    assert "CSV has no sheets" in result.output
