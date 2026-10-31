"""Survey import (B2) against a hand-computed fixture."""

from __future__ import annotations

import pytest
from agentic_odi_core.errors import ValidationError
from agentic_odi_core.survey import (
    aggregate_survey,
    parse_survey,
    survey_csv_header,
)


def _rows(per_outcome: int = 40) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for outcome in ("o-1", "o-2", "o-3"):
        for i in range(per_outcome):
            rows.append(
                {
                    "outcome_id": outcome,
                    "importance": 8.0,
                    "satisfaction": 5.0,
                    "respondent_id": f"{outcome}-r{i}",
                }
            )
    return rows


def test_forty_rows_per_outcome_report_n_40_each() -> None:
    responses = parse_survey(_rows(40))
    result = aggregate_survey(responses, known_ids={"o-1", "o-2", "o-3"})

    assert set(result.aggregates) == {"o-1", "o-2", "o-3"}
    for aggregate in result.aggregates.values():
        assert aggregate.n == 40
        assert aggregate.importance_mean == 8.0
        assert aggregate.satisfaction_mean == 5.0


def test_a_shared_forty_row_fixture_splits_counts_across_outcomes() -> None:
    rows: list[dict[str, object]] = []
    for i in range(40):
        rows.append(
            {
                "outcome_id": ["o-1", "o-2", "o-3"][i % 3],
                "importance": 7.0,
                "satisfaction": 6.0,
                "respondent_id": f"r{i}",
            }
        )
    result = aggregate_survey(parse_survey(rows), known_ids={"o-1", "o-2", "o-3"})

    assert sum(a.n for a in result.aggregates.values()) == 40


def test_p10_p90_use_the_same_convention_for_singleton_and_constant_input() -> None:
    rows = [{"outcome_id": "o-1", "importance": 7.0, "satisfaction": 7.0, "respondent_id": "r1"}]
    result = aggregate_survey(parse_survey(rows), known_ids={"o-1"})
    aggregate = result.aggregates["o-1"]

    assert aggregate.importance_p10 == aggregate.importance_p90 == 7.0


def test_statement_joins_require_exactly_one_match() -> None:
    rows = [{"outcome_statement": "Minimize the wait", "importance": 8.0, "satisfaction": 4.0}]
    responses = parse_survey(rows)

    ok = aggregate_survey(
        responses, id_by_statement={"Minimize the wait": "o-1"}, known_ids={"o-1"}
    )
    assert ok.aggregates["o-1"].n == 1

    with pytest.raises(ValidationError):
        aggregate_survey(responses, id_by_statement={"Minimize the wait": None}, known_ids={"o-1"})
    with pytest.raises(ValidationError):
        aggregate_survey(responses, id_by_statement={}, known_ids={"o-1"})


def test_an_unknown_id_fails_without_a_partial_write() -> None:
    responses = parse_survey(_rows(2))
    with pytest.raises(ValidationError):
        aggregate_survey(responses, known_ids={"o-1"})  # o-2/o-3 unknown


def test_an_empty_file_fails() -> None:
    with pytest.raises(ValidationError):
        parse_survey([])


def test_a_missing_header_fails() -> None:
    with pytest.raises(ValidationError):
        parse_survey([{"importance": 8.0, "satisfaction": 5.0}])
    with pytest.raises(ValidationError):
        survey_csv_header({"outcome_id": "o-1"})


def test_malformed_numbers_fail() -> None:
    with pytest.raises(ValidationError):
        parse_survey([{"outcome_id": "o-1", "importance": "high", "satisfaction": 5.0}])
    with pytest.raises(ValidationError):
        parse_survey([{"outcome_id": "o-1", "importance": 11.0, "satisfaction": 5.0}])


def test_a_repeated_respondent_is_a_conflict() -> None:
    rows = [
        {"outcome_id": "o-1", "importance": 8.0, "satisfaction": 5.0, "respondent_id": "r1"},
        {"outcome_id": "o-1", "importance": 9.0, "satisfaction": 6.0, "respondent_id": "r1"},
    ]
    with pytest.raises(ValidationError):
        parse_survey(rows)
