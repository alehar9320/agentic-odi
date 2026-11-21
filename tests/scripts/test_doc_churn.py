"""``scripts/doc_churn.py``, the instrument that makes conflicts measurable.

Fixture-driven and offline: no test here shells out to ``gh`` or touches the
network. The fixture is a saved ``gh pr list --json number,mergedAt,files``
payload, so the parsing, the ranking, and the share arithmetic are all pinned
against real shapes.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from doc_churn import (
    DEFAULT_FIXTURES,
    MergedPullRequest,
    build_report,
    directory_counts,
    directory_of,
    file_counts,
    filter_since,
    load_fixtures,
    main,
    parse_payload,
    parse_window,
    rank,
    render_json,
    render_table,
)

CUTOFF = datetime(2026, 10, 20, tzinfo=timezone.utc)


def _fixtures() -> object:
    return load_fixtures(DEFAULT_FIXTURES)


def _pull_requests() -> list[MergedPullRequest]:
    return filter_since(parse_payload(_fixtures()), CUTOFF)


# --- Parsing -----------------------------------------------------------------


def test_parse_window_reads_a_day_count() -> None:
    assert parse_window("30d") == timedelta(days=30)
    assert parse_window("1d") == timedelta(days=1)


@pytest.mark.parametrize("bad", ["30", "d", "30w", "", "-1d", "0d", "1.5d"])
def test_parse_window_rejects_anything_but_n_days(bad: str) -> None:
    with pytest.raises(ValueError):
        parse_window(bad)


def test_parse_payload_reads_number_time_and_paths() -> None:
    pull_requests = parse_payload(_fixtures())

    assert [pr.number for pr in pull_requests] == [901, 902, 903, 904, 905]
    assert pull_requests[0].files == ("docs/a.md", "docs/a.md", "scripts/x.py")
    assert pull_requests[0].merged_at == datetime(2026, 11, 5, 10, 0, tzinfo=timezone.utc)


def test_parse_payload_skips_a_row_with_no_merge_time() -> None:
    """A PR whose ``mergedAt`` is empty cannot be placed in a window."""
    numbers = [pr.number for pr in parse_payload(_fixtures())]

    assert 906 not in numbers


def test_parse_payload_skips_malformed_rows_rather_than_dying() -> None:
    payload = [{"number": 1}, "not a dict", {"mergedAt": "2026-11-01T00:00:00Z"}]

    assert parse_payload(payload) == []


def test_parse_payload_rejects_a_non_array() -> None:
    with pytest.raises(ValueError):
        parse_payload({"number": 1})


# --- Filtering ---------------------------------------------------------------


def test_filter_since_drops_pull_requests_before_the_cutoff() -> None:
    numbers = [pr.number for pr in _pull_requests()]

    # 905 merged on 2026-09-01, well before the 2026-10-20 cutoff.
    assert 905 not in numbers
    assert numbers == [901, 902, 903, 904]


# --- Counting ----------------------------------------------------------------


def test_a_file_touched_twice_in_one_pull_request_counts_once() -> None:
    """The unit is "pull requests that touched this file", not file entries."""
    counts = file_counts(_pull_requests())

    # 901 lists docs/a.md twice, and 902 and 904 also touch it: three PRs.
    assert counts["docs/a.md"] == 3


def test_file_counts_rank_the_busiest_file_first() -> None:
    counts = file_counts(_pull_requests())

    assert counts["README.md"] == 2
    assert counts["scripts/x.py"] == 1


def test_directory_of_takes_the_top_level() -> None:
    assert directory_of("docs/a.md") == "docs"
    assert directory_of("apps/studio/src/App.tsx") == "apps"
    assert directory_of("README.md") == "README.md"


def test_directory_counts_rank_the_busiest_directory() -> None:
    counts = directory_counts(_pull_requests())

    # docs/ is touched by 901, 902, 903 (docs/b.md) and 904: four PRs.
    assert counts["docs"] == 4
    assert counts["scripts"] == 1
    assert counts["README.md"] == 2


# --- Ranking and shares ------------------------------------------------------


def test_rank_orders_by_count_then_name() -> None:
    from collections import Counter

    counts = Counter({"b": 2, "a": 2, "c": 1})

    assert [name for name, _count, _share in rank(counts, total=2, top=10)] == ["a", "b", "c"]


def test_rank_reports_the_share_of_pull_requests_that_touched_a_file() -> None:
    counts = file_counts(_pull_requests())
    rows = rank(counts, total=4, top=10)
    shares = {name: share for name, _count, share in rows}

    assert shares["docs/a.md"] == 0.75
    assert shares["README.md"] == 0.5


def test_rank_truncates_to_top() -> None:
    counts = file_counts(_pull_requests())

    assert len(rank(counts, total=4, top=1)) == 1


def test_rank_share_is_zero_when_nothing_merged() -> None:
    from collections import Counter

    assert rank(Counter({"a": 0}), total=0, top=5)[0][2] == 0.0


# --- Rendering ---------------------------------------------------------------


def test_render_table_names_the_window_total_and_each_path() -> None:
    files, _directories, total = build_report(_fixtures(), CUTOFF, top=10)
    table = render_table(files, total)

    assert "4 merged pull request(s)" in table
    assert "`docs/a.md`" in table
    assert "75%" in table


def test_render_json_is_parseable_and_carries_both_rankings() -> None:
    files, directories, total = build_report(_fixtures(), CUTOFF, top=10)
    payload = json.loads(render_json(files, directories, total, "30d"))

    assert payload["window"] == "30d"
    assert payload["total_pull_requests"] == 4
    assert payload["files"][0]["path"] == "docs/a.md"
    assert payload["files"][0]["pull_requests"] == 3
    assert payload["directories"][0]["directory"] == "docs"


# --- The command line --------------------------------------------------------


def test_main_prints_the_table_from_the_fixtures(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--since", "10000d"]) == 0
    output = capsys.readouterr().out

    assert "merged pull request(s) in the window" in output
    assert "By directory:" in output


def test_main_json_prints_the_report(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--since", "10000d", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)

    assert payload["files"]
    assert payload["directories"]


def test_main_rejects_a_bad_window(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--since", "30"]) == 2
    assert "invalid --since" in capsys.readouterr().err


def test_main_reports_a_missing_fixtures_file(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    missing = tmp_path / "gone.json"

    assert main(["--fixtures", str(missing)]) == 1
    assert "could not read merged pull requests" in capsys.readouterr().err
