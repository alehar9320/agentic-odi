"""The sample workspace: honest, self-contained, and impossible to drift.

The page is generated from ``website/content/sample-study.json``, which is
itself derived from the demo loader's fixture. These tests hold the two
promises the page makes: every row says it is a sample, and every numeral on it
comes from the fixture.
"""

from __future__ import annotations

import json
import re

import build_sample
import pytest
from site_support import SITE, read_page

FIXTURE = SITE / "content" / "sample-study.json"
PAGE = SITE / "sample" / "index.html"


@pytest.fixture(scope="module")
def fixture() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def page() -> str:
    return PAGE.read_text(encoding="utf-8")


def _rows(html: str) -> list[str]:
    """Every data row: the ``<tr>`` elements inside a ``<tbody>``."""
    bodies = re.findall(r"<tbody\b[^>]*>(.*?)</tbody>", html, re.DOTALL)
    return [row for body in bodies for row in re.findall(r"<tr\b[^>]*>.*?</tr>", body, re.DOTALL)]


def _external_references(html: str) -> list[str]:
    return [
        ref
        for ref in re.findall(r'(?:src|href)="([^"]+)"', html)
        if ref.startswith(("http://", "https://", "//"))
    ]


# ---------------------------------------------------------------- the fixture


def test_the_fixture_marks_every_row_as_sample(fixture):
    for row in (fixture["job"], *fixture["steps"], *fixture["outcomes"], *fixture["evidence"]):
        assert row["origin"] == "sample", row


def test_the_fixture_is_derived_from_the_demo_loader(fixture):
    # One corpus, two presentations: the committed fixture must equal a fresh
    # derivation from the demo seed, or the sample has quietly become a second
    # corpus that can drift from the product.
    assert build_sample.build_fixture(generated=fixture["generated"]) == fixture


def test_the_fixture_carries_no_fabricated_outcome_fields(fixture):
    # The demo seed's Outcome rows carry ``evidence`` and ``telemetry`` keys
    # that are not fields of the model. They must not reach the sample.
    for outcome in fixture["outcomes"]:
        assert set(outcome) == {
            "id",
            "job_id",
            "statement",
            "importance",
            "satisfaction",
            "opportunity_score",
            "origin",
        }


# ---------------------------------------------------------------- the marker


def test_every_table_row_carries_the_sample_marker(page):
    rows = _rows(page)
    assert rows, "the sample page has no data rows"
    for row in rows:
        assert 'data-origin="sample"' in row, row
        assert "sample-chip" in row, row


def test_the_page_renders_exactly_the_fixtures_rows(page, fixture):
    expected = 1 + len(fixture["steps"]) + len(fixture["outcomes"]) + len(fixture["evidence"])
    assert len(_rows(page)) == expected


def test_no_row_renders_without_the_marker():
    # The acceptance criterion is a negative: a row that loses its marker must
    # fail the build, not merely be absent from a count.
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    with_marker = build_sample.render(fixture)
    stripped = with_marker.replace(' data-origin="sample"', "")
    with pytest.raises(ValueError, match="sample row is missing its marker"):
        build_sample.check_rows(stripped, fixture)


# ---------------------------------------------------------------- the numerals


def test_every_numeral_on_the_page_is_in_the_fixture(page, fixture):
    allowed = build_sample.fixture_numerals(fixture) | build_sample.chrome_numerals(fixture)
    stray = {number for number in build_sample.page_numerals(page) if number not in allowed}
    assert stray == set(), f"the page renders numerals absent from the fixture: {sorted(stray)}"


def test_the_build_rejects_an_invented_numeral(fixture):
    # The 'no invented number' rule, asserted against a page that breaks it.
    with pytest.raises(ValueError, match="numerals absent from the fixture"):
        build_sample.check_numerals("<table><tbody><tr><td>4242</td></tr></tbody></table>", fixture)


def test_the_generation_date_is_the_only_numeral_the_chrome_owns(page, fixture):
    assert f"generated {fixture['generated']}" in page.lower()


# ---------------------------------------------------------------- self-contained


def test_the_sample_page_makes_no_external_request(page):
    assert _external_references(page) == []
    assert "<script" not in page.lower()
    assert "<link" not in page.lower()
    assert "<img" not in page.lower()


def test_the_sample_page_looks_nothing_like_a_live_surface(page):
    # No timers, no form, no control that implies a mutation.
    lowered = page.lower()
    assert "<button" not in lowered
    assert "<form" not in lowered
    assert "<input" not in lowered
    assert "setinterval" not in lowered
    assert "settimeout" not in lowered


def test_the_page_states_it_is_read_only(page):
    assert "read-only" in page.lower()
    assert "sample" in page.lower()


# ---------------------------------------------------------------- published


def test_the_sample_page_is_published_by_the_site_build():
    # build_sample.py owns the page; the site build publishes the same render,
    # so a visitor reaches it under the site root like any other page.
    assert read_page("sample/index.html") == PAGE.read_text(encoding="utf-8")


# ---------------------------------------------------------------- drift


def test_check_mode_passes_on_the_committed_sample():
    build_sample.build(SITE, check=True)


def test_check_mode_fails_when_the_page_drifts(tmp_path):
    build_sample.build(tmp_path)
    (tmp_path / "sample" / "index.html").write_text("stale", encoding="utf-8")
    with pytest.raises(SystemExit):
        build_sample.build(tmp_path, check=True)


def test_check_mode_fails_when_the_fixture_drifts(tmp_path):
    build_sample.build(tmp_path)
    (tmp_path / "content" / "sample-study.json").write_text("{}\n", encoding="utf-8")
    with pytest.raises(SystemExit):
        build_sample.build(tmp_path, check=True)


def test_the_build_is_deterministic(tmp_path):
    first = tmp_path / "a"
    second = tmp_path / "b"
    build_sample.build(first)
    build_sample.build(second)
    for name in ("content/sample-study.json", "sample/index.html"):
        assert (first / name).read_bytes() == (second / name).read_bytes()


def test_the_committed_page_carries_a_do_not_edit_header(page):
    assert "GENERATED by website/tools/build_sample.py" in page
    assert "do not edit" in page.lower()
