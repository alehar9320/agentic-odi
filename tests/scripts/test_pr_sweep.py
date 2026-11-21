"""``scripts/pr_sweep.py``, the read-only view of the open pull request queue.

Fixture-driven and offline: no test here shells out to ``gh`` or touches the
network. The fixture is a saved ``gh pr list`` payload, so the parsing, the
bucketing precedence, and the rendering are all pinned against real shapes.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from pr_sweep import (
    ABANDONED_AFTER,
    BUCKETS,
    DEFAULT_FIXTURES,
    OpenPullRequest,
    SweepContext,
    bucket,
    bucket_all,
    context_for,
    filter_since,
    load_fixtures,
    load_merged_numbers,
    main,
    parse_payload,
    render_json,
    render_report,
    render_table,
)

# A fixed clock, so nothing here depends on the day the suite runs.
NOW = datetime(2026, 11, 16, 0, 0, tzinfo=timezone.utc)
# The fixture names #1090 as already merged; everything else is open.
MERGED = frozenset({1090})


def _pull_requests() -> list[OpenPullRequest]:
    return parse_payload(load_fixtures(DEFAULT_FIXTURES))


def _context(pull_requests: list[OpenPullRequest] | None = None) -> SweepContext:
    return context_for(pull_requests or _pull_requests(), NOW, MERGED)


def _by_number(pull_requests: list[OpenPullRequest]) -> dict[int, OpenPullRequest]:
    return {pr.number: pr for pr in pull_requests}


# --- Parsing -----------------------------------------------------------------


def test_parse_payload_reads_the_facts_a_disposition_needs() -> None:
    pull_requests = _by_number(_pull_requests())

    pr = pull_requests[1101]
    assert pr.title == "Add a helper for the ODX export path"
    assert pr.created_at == datetime(2026, 11, 10, 9, 0, tzinfo=timezone.utc)
    assert pr.updated_at == datetime(2026, 11, 15, 9, 0, tzinfo=timezone.utc)
    assert pr.is_draft is False
    assert pr.mergeable == "MERGEABLE"
    assert pr.base_ref == "main"
    assert pr.head_ref == "feat/a"
    assert pr.files == (
        "packages/core/src/agentic_odi_core/odx.py",
        "tests/core/test_odx.py",
    )


def test_parse_payload_skips_a_row_with_no_update_time() -> None:
    """A PR with no ``updatedAt`` cannot be aged, so it is dropped."""
    numbers = [pr.number for pr in _pull_requests()]

    assert 1110 not in numbers


def test_parse_payload_skips_malformed_rows_rather_than_dying() -> None:
    payload = [{"number": 1}, "not a dict", {"createdAt": "2026-11-01T00:00:00Z"}]

    assert parse_payload(payload) == []


def test_parse_payload_rejects_a_non_array() -> None:
    with pytest.raises(ValueError):
        parse_payload({"number": 1})


# --- The merged set ----------------------------------------------------------


def test_load_merged_numbers_reads_the_sibling_fixture() -> None:
    """The superseded bucket needs to know which numbers have already merged."""
    merged = load_merged_numbers(DEFAULT_FIXTURES)

    assert 1090 in merged
    assert 1101 not in merged


def test_load_merged_numbers_is_empty_when_the_sibling_is_absent(tmp_path: Path) -> None:
    """Better to call nothing superseded than to close a live pull request."""
    open_only = tmp_path / "open_prs.json"
    open_only.write_text("[]", encoding="utf-8")

    assert load_merged_numbers(open_only) == frozenset()


# --- Filtering ---------------------------------------------------------------


def test_filter_since_drops_pull_requests_before_the_cutoff() -> None:
    # 1103 and 1107 were created on 2026-10-18 and 2026-10-20.
    numbers = [pr.number for pr in filter_since(_pull_requests(), NOW - timedelta(days=14))]

    assert 1103 not in numbers
    assert 1107 not in numbers
    assert 1101 in numbers


# --- One bucket at a time ----------------------------------------------------


@pytest.mark.parametrize(
    ("number", "expected"),
    [
        (1101, "green-mergeable"),
        (1102, "green-superseded"),
        (1103, "abandoned"),
        (1104, "stacked"),
        (1105, "draft"),
        (1106, "needs-review"),
    ],
)
def test_each_pull_request_lands_in_the_expected_bucket(number: int, expected: str) -> None:
    pull_requests = _by_number(_pull_requests())

    assert bucket(pull_requests[number], _context()) == expected


def test_bucket_returns_a_name_from_the_constant() -> None:
    for pr in _pull_requests():
        assert bucket(pr, _context()) in BUCKETS


def test_a_base_that_is_another_open_head_is_stacked() -> None:
    """#1104's base ``feat/a`` is #1101's head, so it is a stack, not a merge."""
    pull_requests = _by_number(_pull_requests())

    assert pull_requests[1104].base_ref == pull_requests[1101].head_ref
    assert bucket(pull_requests[1104], _context()) == "stacked"


def test_a_twenty_day_old_untouched_pull_request_is_abandoned() -> None:
    pull_requests = _by_number(_pull_requests())

    # 1103 was last touched 2026-10-27, twenty days before the fixed clock.
    assert NOW - pull_requests[1103].updated_at == timedelta(days=20)
    assert bucket(pull_requests[1103], _context()) == "abandoned"


def test_a_pull_request_at_the_abandonment_boundary_is_not_abandoned() -> None:
    pr = OpenPullRequest(
        number=1,
        title="",
        created_at=NOW - timedelta(days=30),
        updated_at=NOW - ABANDONED_AFTER,
        is_draft=False,
        mergeable="MERGEABLE",
        base_ref="main",
        head_ref="feat/x",
        body="",
        files=(),
    )

    assert bucket(pr, SweepContext(now=NOW)) == "green-mergeable"


def test_draft_outranks_abandoned() -> None:
    """#1107 is a draft and quiet for weeks; an open draft is not yet review."""
    pull_requests = _by_number(_pull_requests())

    assert bucket(pull_requests[1107], _context()) == "draft"


def test_stacked_outranks_superseded() -> None:
    """#1108 is stacked on #1101 and its body names a merged PR: stack wins."""
    pull_requests = _by_number(_pull_requests())

    assert bucket(pull_requests[1108], _context()) == "stacked"


def test_abandoned_outranks_stacked() -> None:
    """#1109 is stacked on #1101 but untouched for weeks: close it, do not merge."""
    pull_requests = _by_number(_pull_requests())

    assert bucket(pull_requests[1109], _context()) == "abandoned"


def test_a_green_pull_request_naming_no_merged_pr_is_mergeable() -> None:
    pr = OpenPullRequest(
        number=2,
        title="",
        created_at=NOW - timedelta(days=1),
        updated_at=NOW - timedelta(hours=1),
        is_draft=False,
        mergeable="MERGEABLE",
        base_ref="main",
        head_ref="feat/y",
        body="No reference to a merged pull request.",
        files=(),
    )

    assert bucket(pr, SweepContext(now=NOW)) == "green-mergeable"


def test_an_unknown_mergeable_state_is_needs_review() -> None:
    pr = OpenPullRequest(
        number=3,
        title="",
        created_at=NOW - timedelta(days=1),
        updated_at=NOW - timedelta(hours=1),
        is_draft=False,
        mergeable="UNKNOWN",
        base_ref="main",
        head_ref="feat/z",
        body="",
        files=(),
    )

    assert bucket(pr, SweepContext(now=NOW)) == "needs-review"


# --- The whole queue ---------------------------------------------------------


def test_bucket_all_places_every_pull_request_exactly_once() -> None:
    pull_requests = _pull_requests()
    grouped = bucket_all(pull_requests, _context(pull_requests))

    placed = [pr.number for name in BUCKETS for pr in grouped[name]]
    assert sorted(placed) == sorted(pr.number for pr in pull_requests)
    assert grouped["green-mergeable"][0].number == 1101


def test_bucket_all_orders_each_bucket_by_number() -> None:
    pull_requests = _pull_requests()
    grouped = bucket_all(pull_requests, _context(pull_requests))

    # 1104 and 1108 are both stacked; they come out in ascending number order.
    assert [pr.number for pr in grouped["stacked"]] == [1104, 1108]


# --- Rendering ---------------------------------------------------------------


def test_render_table_names_every_bucket_and_the_pull_requests() -> None:
    pull_requests = _pull_requests()
    grouped = bucket_all(pull_requests, _context(pull_requests))
    table = render_table(grouped, len(pull_requests), "30d", NOW)

    for name in BUCKETS:
        assert f"## {name}" in table
    assert "#1101" in table
    assert "green-mergeable (1)" in table


def test_render_json_is_parseable_and_carries_the_counts() -> None:
    pull_requests = _pull_requests()
    grouped = bucket_all(pull_requests, _context(pull_requests))
    payload = json.loads(render_json(grouped, len(pull_requests), "30d", NOW))

    assert payload["window"] == "30d"
    assert payload["total_pull_requests"] == len(pull_requests)
    assert payload["counts"]["green-mergeable"] == 1
    assert payload["buckets"]["stacked"][0]["number"] == 1104
    assert payload["buckets"]["stacked"][0]["files_touched"] == 1


def test_the_same_input_twice_gives_identical_output() -> None:
    pull_requests = _pull_requests()
    grouped = bucket_all(pull_requests, _context(pull_requests))

    first = render_json(grouped, len(pull_requests), "30d", NOW)
    second = render_json(grouped, len(pull_requests), "30d", NOW)

    assert first == second


# --- The command line --------------------------------------------------------


def test_main_prints_the_table_from_the_fixtures(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--since", "10000d"]) == 0
    output = capsys.readouterr().out

    assert "open pull request(s) within --since 10000d" in output
    assert "## green-mergeable" in output


def test_main_json_prints_the_report(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--since", "10000d", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)

    assert payload["counts"]["draft"] == 2
    assert payload["buckets"]["abandoned"]


def test_main_buckets_a_superseded_pull_request_from_the_offline_fixtures(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """End to end: the sibling merged fixture drives the superseded bucket."""
    assert main(["--since", "10000d", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)

    assert payload["counts"]["green-superseded"] == 1
    assert payload["buckets"]["green-superseded"][0]["number"] == 1102


def test_main_rejects_a_bad_window(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--since", "30"]) == 2
    assert "invalid --since" in capsys.readouterr().err


def test_main_reports_a_missing_fixtures_file(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    missing = tmp_path / "gone.json"

    assert main(["--fixtures", str(missing)]) == 1
    assert "could not read open pull requests" in capsys.readouterr().err


# --- Rendering a saved report ------------------------------------------------


def test_render_report_reproduces_the_table_from_the_saved_json() -> None:
    """The workflow posts the report it validated, so both forms must agree."""
    pull_requests = _pull_requests()
    grouped = bucket_all(pull_requests, _context(pull_requests))
    report = json.loads(render_json(grouped, len(pull_requests), "30d", NOW))

    assert render_report(report) == render_table(grouped, len(pull_requests), "30d", NOW)


def test_render_report_rejects_a_payload_without_buckets() -> None:
    with pytest.raises(ValueError):
        render_report({"window": "30d", "total_pull_requests": 1})


def test_render_report_rejects_a_row_missing_a_table_field() -> None:
    """A damaged report must fail loudly, not render blanks into the comment."""
    payload = {
        "window": "30d",
        "total_pull_requests": 1,
        "buckets": {"draft": [{"number": 1}]},
    }

    with pytest.raises(ValueError):
        render_report(payload)


def test_main_render_prints_the_saved_report(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    pull_requests = _pull_requests()
    grouped = bucket_all(pull_requests, _context(pull_requests))
    report = tmp_path / "sweep-report.json"
    report.write_text(render_json(grouped, len(pull_requests), "30d", NOW), encoding="utf-8")

    assert main(["--render", str(report)]) == 0
    output = capsys.readouterr().out

    assert "open pull request(s) within --since 30d" in output
    assert "## green-mergeable (1)" in output
    assert "#1101" in output


def test_main_render_reports_a_missing_file(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["--render", str(tmp_path / "gone.json")]) == 1
    assert "could not read the saved report" in capsys.readouterr().err


def test_main_render_reports_a_malformed_report(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    report = tmp_path / "sweep-report.json"
    report.write_text("{}", encoding="utf-8")

    assert main(["--render", str(report)]) == 1
    assert "could not render the saved report" in capsys.readouterr().err
