"""ALH-222 (M2-04.1) — reading a spreadsheet of outcomes, then filing it one row at a time.

The parser decides what a column means, which line a value came from, and what to say about
a column it cannot use. The loop decides what to do with a row: it writes through the same door
a person would use for one outcome, so an import cannot smuggle in a row the CLI would refuse,
and it accounts for every line it read. Both halves are shared by the CLI and the Studio upload,
so a person gets the same answer whichever door they came to, and the row numbers in a report
are the numbers in their spreadsheet app.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from agentic_odi_core.errors import error_status
from agentic_odi_core.models import ClaimCheck, JobStage, Step, Theme
from agentic_odi_core.outcome_import import (
    ImportAbortedError,
    ImportReport,
    ImportRow,
    ParsedTable,
    ServiceImportTarget,
    UnsupportedFormatError,
    import_outcomes,
    parse_outcome_table,
)
from agentic_odi_core.repository import InMemoryRepository
from agentic_odi_core.services import ODIService

FIXTURE = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "outcomes_mixed_40.csv"

WELL_FORMED = "Minimize the time to reconcile a supplier invoice when the statement arrives late"

#: The fixture's three broken lines: a score out of bounds, a statement that fails the format
#: check, and a stage no job map has. Every other line in the file is meant to be written.
BROKEN_LINES = [9, 18, 27]


def _table(text: str) -> ParsedTable:
    return parse_outcome_table(text)


def _fixture_table() -> ParsedTable:
    return parse_outcome_table(FIXTURE.read_bytes())


def _seeded(two_execute_steps: bool = False) -> tuple[ODIService, str]:
    """The seeding the fixture's lines assume: one EXECUTE step, Onboarding/Urgent/Urgent."""
    service = ODIService(InMemoryRepository())
    job = service.add_job("Reconcile supplier invoices")
    service.add_step(
        job.id, "Execute the reconciliation", 5, stage=JobStage.EXECUTE, allow_empty_job_map=True
    )
    if two_execute_steps:
        service.add_step(
            job.id, "Execute the second pass", 6, stage=JobStage.EXECUTE, allow_empty_job_map=True
        )
    service.add_theme("Onboarding", job_id=job.id)
    service.add_theme("Urgent", job_id=job.id)
    service.add_theme("Urgent")
    return service, job.id


def _run(
    service: ODIService, job_id: str, table: ParsedTable | None = None, **kwargs: Any
) -> ImportReport:
    return import_outcomes(
        table or _fixture_table(), ServiceImportTarget(service), job_id=job_id, **kwargs
    )


def _lines(entries: list[dict[str, Any]]) -> list[int]:
    return [entry["line"] for entry in entries]


def _reason_at(report: ImportReport, line: int) -> str:
    for entry in report.refused:
        if entry["line"] == line:
            return str(entry["reason"])
    raise AssertionError(f"line {line} was not refused: {_lines(report.refused)}")


class _RecordingTarget:
    """Wraps the service target and remembers the filings, so theme batching is visible."""

    def __init__(self, inner: ServiceImportTarget) -> None:
        self.inner = inner
        self.assignments: list[tuple[str, int]] = []

    def themes(self, job_id: str) -> list[Theme]:
        return self.inner.themes(job_id)

    def steps(self, job_id: str) -> list[Step]:
        return self.inner.steps(job_id)

    def existing_statements(self, job_id: str) -> list[str]:
        return self.inner.existing_statements(job_id)

    def add_outcome(
        self, job_id: str, row: ImportRow, claim_check: ClaimCheck | None, step_id: str | None
    ) -> str:
        return self.inner.add_outcome(job_id, row, claim_check, step_id)

    def assign_theme(self, outcome_ids: list[str], theme_id: str) -> None:
        self.assignments.append((theme_id, len(outcome_ids)))
        self.inner.assign_theme(outcome_ids, theme_id)


class _AbortingTarget:
    """A target whose transport dies on the ``abort_at``-th write, halfway through the file."""

    def __init__(self, inner: ServiceImportTarget, abort_at: int) -> None:
        self.inner = inner
        self.abort_at = abort_at
        self.writes = 0

    def themes(self, job_id: str) -> list[Theme]:
        return self.inner.themes(job_id)

    def steps(self, job_id: str) -> list[Step]:
        return self.inner.steps(job_id)

    def existing_statements(self, job_id: str) -> list[str]:
        return self.inner.existing_statements(job_id)

    def add_outcome(
        self, job_id: str, row: ImportRow, claim_check: ClaimCheck | None, step_id: str | None
    ) -> str:
        self.writes += 1
        if self.writes == self.abort_at:
            raise ImportAbortedError("the MCP server is unreachable")
        return self.inner.add_outcome(job_id, row, claim_check, step_id)

    def assign_theme(self, outcome_ids: list[str], theme_id: str) -> None:
        self.inner.assign_theme(outcome_ids, theme_id)


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


def test_a_format_neither_door_reads_is_refused_by_name() -> None:
    with pytest.raises(UnsupportedFormatError) as excinfo:
        parse_outcome_table(FIXTURE.read_bytes(), fmt="xls")

    assert "csv" in str(excinfo.value)
    assert "xlsx" in str(excinfo.value)
    assert "xls'" in str(excinfo.value)


def test_a_wrong_format_is_a_bad_request_not_a_server_fault() -> None:
    assert error_status(UnsupportedFormatError("xls")) == 400


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


# --------------------------------------------------------------------------- the loop


def test_the_fixture_writes_thirty_seven_and_refuses_three() -> None:
    service, job_id = _seeded()

    report = _run(service, job_id)

    assert _lines(report.refused) == BROKEN_LINES
    assert len(report.created) == 37
    assert "must be between 1.0 and 10.0" in _reason_at(report, 9)
    assert len(service.get_outcomes(job_id)) == 37
    assert report.ignored_columns == {}
    assert report.job_id == job_id
    assert report.dry_run is False


def test_one_bad_score_does_not_cost_the_other_rows() -> None:
    service, job_id = _seeded()

    report = _run(service, job_id)

    assert 8 in _lines(report.created)
    assert 10 in _lines(report.created)
    assert 9 not in _lines(report.created)


def test_every_row_of_the_fixture_is_accounted_for() -> None:
    service, job_id = _seeded()

    report = _run(service, job_id)

    assert len(report.created) + len(report.refused) == 40
    assert set(_lines(report.created)) | set(_lines(report.refused)) == set(range(2, 42))
    assert not set(_lines(report.created)) & set(_lines(report.refused))
    assert len(report.as_dict()["created"]) == 37


def test_a_dry_run_writes_nothing_and_reports_the_same_run() -> None:
    service, job_id = _seeded()
    before = len(service.list_signals())

    first = _run(service, job_id, dry_run=True)
    second = _run(service, job_id, dry_run=True)

    assert first.as_dict() == second.as_dict()
    assert first.dry_run is True
    assert len(first.created) == 37
    assert all(entry["outcome_id"] is None for entry in first.created)
    assert service.get_outcomes(job_id) == []
    assert len(service.list_signals()) == before


def test_a_dry_run_report_equals_the_write_report_apart_from_ids() -> None:
    service, job_id = _seeded()

    preview = _run(service, job_id, dry_run=True)
    written = _run(service, job_id)

    assert _lines(preview.created) == _lines(written.created)
    assert _lines(preview.refused) == _lines(written.refused)
    assert [entry["statement"] for entry in preview.created] == [
        entry["statement"] for entry in written.created
    ]
    assert [entry["reason"] for entry in preview.refused] == [
        entry["reason"] for entry in written.refused
    ]
    assert all(entry["outcome_id"] is not None for entry in written.created)


def test_a_scored_row_is_written_with_the_by_hand_claim_check() -> None:
    service, job_id = _seeded()

    _run(service, job_id)

    scored = [o for o in service.get_outcomes(job_id) if o.importance is not None]
    assert scored
    for outcome in scored:
        assert outcome.claim_check is not None
        assert "by hand" in outcome.claim_check.skips[0].reason


def test_an_unscored_row_is_written_without_a_claim_check() -> None:
    service, job_id = _seeded()

    report = _run(service, job_id, _table(f"statement\n{WELL_FORMED}\n"))

    assert len(report.created) == 1
    outcome = service.get_outcomes(job_id)[0]
    assert outcome.importance is None
    assert outcome.opportunity_score is None
    assert outcome.claim_check is None


def test_theme_names_are_matched_exactly_and_ambiguity_is_reported() -> None:
    service, job_id = _seeded()
    themes = service.list_themes(job_id)
    urgent_ids = sorted(theme.id for theme in themes if theme.name == "Urgent")
    onboarding = next(theme.id for theme in themes if theme.name == "Onboarding")

    report = _run(service, job_id)

    assert report.unmatched_themes == [{"name": "Retention", "lines": [8, 10, 11]}]
    assert report.ambiguous_themes == [
        {"name": "Urgent", "candidate_ids": urgent_ids, "lines": [12, 13]}
    ]
    filed = {outcome.id: outcome.theme_ids for outcome in service.get_outcomes(job_id)}
    assert sum(1 for ids in filed.values() if ids == [onboarding]) == 6
    assert not [ids for ids in filed.values() if set(ids) & set(urgent_ids)]


def test_a_theme_is_filed_once_with_all_of_its_rows() -> None:
    service, job_id = _seeded()
    onboarding = next(t.id for t in service.list_themes(job_id) if t.name == "Onboarding")
    target = _RecordingTarget(ServiceImportTarget(service))

    import_outcomes(_fixture_table(), target, job_id=job_id)

    assert target.assignments == [(onboarding, 6)]


def test_an_unknown_stage_refuses_the_row_with_the_query_sentence() -> None:
    service, job_id = _seeded()

    report = _run(service, job_id)

    assert "Unknown stage: collect" in _reason_at(report, 27)


def test_a_stage_with_two_matching_steps_refuses_naming_them() -> None:
    service, job_id = _seeded(two_execute_steps=True)
    step_ids = sorted(step.id for step in service.get_job_map(job_id))

    report = _run(service, job_id)

    reason = _reason_at(report, 4)
    assert all(step_id in reason for step_id in step_ids)
    assert 4 not in _lines(report.created)
    assert 5 not in _lines(report.created)


def test_a_row_naming_another_job_is_refused_and_both_ids_are_named() -> None:
    service, job_id = _seeded()

    table = _table(f"statement,job_id\n{WELL_FORMED},job-other\n{WELL_FORMED},\n")
    report = _run(service, job_id, table)

    assert _lines(report.refused) == [2]
    assert "job-other" in _reason_at(report, 2)
    assert job_id in _reason_at(report, 2)
    assert _lines(report.created) == [3]


def test_a_row_naming_its_own_job_is_written() -> None:
    service, job_id = _seeded()

    table = _table(f"statement,job_id\n{WELL_FORMED},{job_id}\n")
    report = _run(service, job_id, table)

    assert _lines(report.created) == [2]
    assert report.refused == []


def test_an_unknown_step_id_is_refused_with_the_not_found_sentence() -> None:
    service, job_id = _seeded()

    report = _run(service, job_id, _table(f"statement,step_id\n{WELL_FORMED},step-nope\n"))

    assert "not found" in _reason_at(report, 2)
    assert "step-nope" in _reason_at(report, 2)
    assert service.get_outcomes(job_id) == []


def test_a_row_is_filed_on_the_step_it_names() -> None:
    service, job_id = _seeded()
    step_id = service.get_job_map(job_id)[0].id

    report = _run(service, job_id, _table(f"statement,step_id\n{WELL_FORMED},{step_id}\n"))

    assert _lines(report.created) == [2]
    assert service.get_outcomes(job_id)[0].step_id == step_id


def test_a_stage_names_its_step_when_the_row_does_not_name_one() -> None:
    service, job_id = _seeded()
    step_id = service.get_job_map(job_id)[0].id

    report = _run(service, job_id, _table(f"statement,stage\n{WELL_FORMED},execute\n"))

    assert _lines(report.created) == [2]
    assert service.get_outcomes(job_id)[0].step_id == step_id


def test_a_repeat_statement_warns_and_still_writes() -> None:
    service, job_id = _seeded()
    table = _table(f"statement,importance\n{WELL_FORMED},8\n")
    _run(service, job_id, table)

    report = _run(service, job_id, table)

    assert len(report.created) == 1
    assert any("line 2" in warning for warning in report.warnings)
    assert "already" in report.warnings[0]
    assert len(service.get_outcomes(job_id)) == 2


def test_a_repeat_inside_one_file_warns_about_the_later_row() -> None:
    service, job_id = _seeded()

    table = _table(f"statement,importance\n{WELL_FORMED},8\n{WELL_FORMED},9\n")
    report = _run(service, job_id, table)

    assert len(report.created) == 2
    assert len(report.warnings) == 1
    assert "line 3" in report.warnings[0]
    assert "line 2" not in report.warnings[0]


def test_a_dry_run_warns_about_a_repeat_before_it_is_written() -> None:
    service, job_id = _seeded()
    _run(service, job_id, _table(f"statement\n{WELL_FORMED}\n"))
    already = len(service.get_outcomes(job_id))

    report = _run(service, job_id, _table(f"statement\n{WELL_FORMED}\n"), dry_run=True)

    assert len(report.warnings) == 1
    assert "line 2" in report.warnings[0]
    assert len(service.get_outcomes(job_id)) == already


def test_duplicate_matching_is_casefolded_and_whitespace_collapsed() -> None:
    service, job_id = _seeded()
    service.add_outcome(job_id, WELL_FORMED)

    table = _table(
        "statement\n"
        "  Minimize the TIME  to reconcile a supplier invoice "
        "when the statement arrives late  \n"
        f"{WELL_FORMED} before payment terms expire\n"
    )
    report = _run(service, job_id, table)

    # One warning, for the row that is the same statement typed with different spacing — and
    # not for the longer one that merely contains it, which is a different need.
    assert len(report.warnings) == 1
    assert "line 2" in report.warnings[0]
    assert len(report.created) == 2


def test_a_row_with_a_non_numeric_score_is_refused_before_any_write() -> None:
    service, job_id = _seeded()

    report = _run(service, job_id, _table(f"statement,importance\n{WELL_FORMED},soon\n"))

    assert _lines(report.refused) == [2]
    assert 'importance must be a number, got "soon"' in _reason_at(report, 2)
    assert service.get_outcomes(job_id) == []


def test_a_blank_statement_row_is_refused_with_the_parser_sentence() -> None:
    service, job_id = _seeded()

    table = _table(f"statement,importance\n,8\n{WELL_FORMED},9\n")
    report = _run(service, job_id, table)

    assert _reason_at(report, 2) == "statement is empty; nothing to file"
    assert _lines(report.created) == [3]


def test_an_unreadable_file_is_one_refusal_at_line_one() -> None:
    service, job_id = _seeded()

    report = _run(service, job_id, _table("notes,importance\nchurn,1\n"))

    assert report.created == []
    assert len(report.refused) == 1
    assert report.refused[0]["line"] == 1
    assert "statement" in report.refused[0]["reason"]
    assert service.get_outcomes(job_id) == []


def test_a_transport_failure_aborts_the_run_and_keeps_the_written_rows() -> None:
    service, job_id = _seeded()
    target = _AbortingTarget(ServiceImportTarget(service), abort_at=20)

    report = import_outcomes(_fixture_table(), target, job_id=job_id)

    # The two lines that fail validation before any write are refused as always; the twentieth
    # row the loop tried to write stops the run, and nothing after it is reported.
    assert _lines(report.refused) == [9, 18]
    assert len(report.created) == 19
    assert report.aborted is not None
    assert report.aborted["line"] == 23
    assert "unreachable" in report.aborted["reason"]
    assert max(_lines(report.created)) == 22
    assert len(service.get_outcomes(job_id)) == 19
