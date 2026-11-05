"""The shared structural audit for artifact HTML (issue ALH-238).

The rules come from the M5-11 epic: one `h1`, ordered headings, data tables
with a caption and scoped headers, every image and chart labelled, no repeated
`id`. What matters here is that they are checked in one place, because the same
five rules existed as hand-written regexes in `website/tests/test_site.py` and
nothing else could use them.

Each negative fixture differs from `conforming.html` in exactly one way, so the
test asserts the *set* of rules a fixture trips. A fixture that reports a second
rule is a badly written fixture, and this file says so loudly rather than
shrugging at an extra violation.

Zero violations from these rules is a structural check. It is not WCAG
conformance and it is not a screen-reader certification; the reading-order
evidence that would make it the latter is ALH-252's, and it is not claimed here.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from artifact_a11y import RULES, audit_html

FIXTURES = Path(__file__).parent / "fixtures" / "artifact_audit"


def fixture(name: str) -> str:
    return (FIXTURES / f"{name}.html").read_text(encoding="utf-8")


# Each fixture breaks exactly one rule; the second column is that rule.
NEGATIVES = [
    ("no_h1", "single-h1"),
    ("two_h1", "single-h1"),
    ("skipped_heading", "heading-order"),
    ("no_caption", "table-caption"),
    ("no_th", "table-header-scope"),
    ("bad_scope", "table-header-scope"),
    ("img_no_alt", "image-label"),
    ("svg_no_label", "image-label"),
    ("duplicate_id", "duplicate-id"),
]


def test_conforming_artifact_has_no_violations() -> None:
    assert audit_html(fixture("conforming")) == []


@pytest.mark.parametrize(("name", "rule"), NEGATIVES)
def test_each_negative_fixture_reports_exactly_its_rule(name: str, rule: str) -> None:
    violations = audit_html(fixture(name))
    assert {v.rule for v in violations} == {rule}, f"{name} must isolate one rule"


def test_every_rule_has_a_negative_fixture() -> None:
    """A rule nothing tests is a rule nothing enforces."""
    assert {rule for _, rule in NEGATIVES} == set(RULES)


@pytest.mark.parametrize(("name", "_rule"), NEGATIVES)
def test_an_error_tells_a_reader_what_to_change(name: str, _rule: str) -> None:
    for violation in audit_html(fixture(name)):
        assert violation.detail, "an error must name the fix, not just the rule"
        assert violation.snippet, "an error must show the element it found"


def test_an_artifact_with_nothing_recorded_still_passes() -> None:
    """The brief prints "Not recorded." rather than dropping a section.

    An empty artifact is the case a reader is most likely to be told "there is
    no data" by, so the audit must not go quiet on it — and must not invent a
    defect because the body is thin.
    """
    assert audit_html(fixture("empty_artifact")) == []


def test_a_labelled_chart_with_a_data_table_passes() -> None:
    """The evidence chart's bar: a picture a reader can name, and the same
    numbers as a table, so nothing is carried by colour alone."""
    assert audit_html(fixture("chart_with_table")) == []


def test_markup_in_a_script_style_or_textarea_is_not_structure() -> None:
    """A quote or a stylesheet that contains a heading is not a heading.

    Research text is quoted into these artifacts. If the auditor counted tags
    inside a `<textarea>` or a `<style>` block, a page carrying markup as data
    would either pass while broken or fail for a reason no author can fix.
    """
    html = """
      <html><head><style>/* h1 { } */ a { id="main" }</style></head>
      <body><main id="main">
        <h1>Payments platform</h1>
        <textarea><h3>quoted from the interview</h3><p id="main"></textarea>
        <script>var s = "<h5>not a heading</h5>";</script>
      </main></body></html>
    """
    assert audit_html(html) == []


def test_violations_come_back_in_document_order() -> None:
    """A reader fixes a document top to bottom; a shuffled list costs them a
    re-read of the file to work out where each error is."""
    html = """
      <html><body><main>
        <h1>Payments platform</h1>
        <h3>Evidence</h3>
        <img src="quote.png">
        <h1>Again</h1>
      </main></body></html>
    """
    assert [v.rule for v in audit_html(html)] == [
        "heading-order",
        "image-label",
        "single-h1",
    ]


def test_a_table_left_open_is_still_checked() -> None:
    """A truncated render is a defect, not a silent pass."""
    html = "<html><body><main><h1>Payments platform</h1><table><tr><td>OUT-1</td>"
    rules = {v.rule for v in audit_html(html)}
    assert rules == {"table-caption", "table-header-scope"}
