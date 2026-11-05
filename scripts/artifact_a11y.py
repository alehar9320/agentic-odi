"""The structural rules an artifact's HTML must satisfy (issue ALH-238).

One owner for the rules the M5-11 epic states: a document has one title, its
headings do not skip a level, its data tables are captioned and their header
cells scoped, its images and charts are labelled for a reader who cannot see
them, and no two elements share an ``id``. Before this module the same rules
existed as hand-written regular expressions in ``website/tests/test_site.py``,
which only the website suite could use and which deliberately skipped the
self-contained pages — the 404 and the sample workspace, which are exactly the
pages that get shared.

Why ``scripts/``: this is tooling that ships with the checkout and must be
importable from the repository tests and the website tests alike, and
``scripts/`` is where the repository keeps standard-library-only tooling (see
``docs/architecture/reuse.md``). It is not in ``packages/core`` because no
runtime path renders artifact HTML — the decision brief is Markdown serialised
in the browser — so an auditor in the domain package would imply the domain
package does the auditing.

What passing does **not** mean:

* that a screen reader announces the document in the intended order — reading
  order needs a person and an assistive technology, which is ALH-252's evidence;
* WCAG conformance of any kind;
* that the words in a caption or a chart label describe the data;
* contrast, which needs rendered colour and is owned by
  ``apps/studio/src/test/contrast.ts`` and the token gate in ``theme.test.ts``.

Zero violations means the structure is navigable, not that the artifact reads well.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from html.parser import HTMLParser
from typing import Final

RULES: Final[tuple[str, ...]] = (
    "single-h1",
    "heading-order",
    "table-caption",
    "table-header-scope",
    "image-label",
    "duplicate-id",
)

SCOPES: Final[frozenset[str]] = frozenset({"row", "col", "rowgroup", "colgroup"})

# Elements whose children are text as far as HTML is concerned. A `<h1>` or an
# `id` written inside a stylesheet or a script is data about the page, not a
# heading or an element: counting it would let a page that stuffs markup into a
# script tag pass, and would make a research quote containing one angle bracket
# break an unrelated rule.
#
# `html.parser` does some of this on its own, but which elements it treats as
# raw text has moved between interpreter versions — it is a private constant
# here, and `<textarea>` content is a tag stream on the versions CI runs. The
# auditor suppresses explicitly rather than trusting whichever interpreter it
# happens to be handed.
_SUPPRESSED: Final[frozenset[str]] = frozenset({"script", "style", "textarea"})

_HEADING_TAGS: Final[frozenset[str]] = frozenset({"h1", "h2", "h3", "h4", "h5", "h6"})


@dataclass(frozen=True)
class Violation:
    """One structural defect, phrased as the change it asks for."""

    rule: str
    detail: str
    snippet: str

    def __str__(self) -> str:
        return f"{self.rule}: {self.detail} [{self.snippet}]"


@dataclass
class _Table:
    """One open `<table>`, accumulating what its rules will ask for."""

    start_tag: str
    line: int
    caption: bool = False
    headers: int = 0
    unscoped: list[tuple[str, int]] = field(default_factory=list)

    def add_header(self, scope: str | None, start_tag: str, line: int) -> None:
        self.headers += 1
        if (scope or "").lower() not in SCOPES:
            self.unscoped.append((start_tag, line))

    def check(self, report: Callable[[str, str, str, int], None]) -> None:
        if not self.caption:
            report(
                "table-caption",
                "a data table needs a <caption> that says what it shows",
                self.start_tag,
                self.line,
            )
        if not self.headers:
            report(
                "table-header-scope",
                "a data table needs a <th> header cell so each column is named",
                self.start_tag,
                self.line,
            )
        for start_tag, line in self.unscoped:
            report(
                "table-header-scope",
                "a <th> needs scope= with row, col, rowgroup or colgroup",
                start_tag,
                line,
            )


@dataclass
class _Chart:
    """One open `<svg>`, waiting to see whether anything labels it."""

    start_tag: str
    line: int
    labelled: bool = False

    def is_labelled_by(self, attributes: dict[str, str | None]) -> bool:
        if (attributes.get("aria-hidden") or "").lower() == "true":
            self.labelled = True
        if (attributes.get("aria-label") or "").strip():
            self.labelled = True
        if (attributes.get("aria-labelledby") or "").strip():
            self.labelled = True
        return self.labelled


def audit_html(html: str) -> list[Violation]:
    """Every structural violation in a document, in the order it appears."""
    auditor = _Audit()
    auditor.feed(html)
    auditor.close()
    return auditor.violations


class _Audit(HTMLParser):
    """One pass over a document, reporting the defects a reader would meet."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._found: list[tuple[int, int, Violation]] = []
        self._sequence = 0
        self._suppressed = 0
        self._document_tag = ""
        self._levels: list[tuple[int, int, str]] = []
        self._h1s: list[tuple[int, str]] = []
        self._ids: dict[str, tuple[int, str]] = {}
        self._tables: list[_Table] = []
        self._charts: list[_Chart] = []

    @property
    def violations(self) -> list[Violation]:
        return [violation for _, _, violation in sorted(self._found, key=_order)]

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._visit(tag, attrs, self.get_starttag_text() or f"<{tag}>")

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        # `<svg … />` and `<img …>` have no children, so they arrive here with
        # no matching end tag to close whatever they opened.
        self._visit(tag, attrs, self.get_starttag_text() or f"<{tag}>")
        if tag == "svg" and self._charts:
            self._close_chart()

    def handle_endtag(self, tag: str) -> None:
        if tag in _SUPPRESSED:
            self._suppressed = max(0, self._suppressed - 1)
            return
        if self._suppressed or tag in _HEADING_TAGS:
            return
        if tag == "table" and self._tables:
            self._tables.pop().check(self._report)
        elif tag == "svg" and self._charts:
            self._close_chart()

    def close(self) -> None:
        """Finish an abrupt end: an unclosed table or chart is still a defect."""
        super().close()
        while self._tables:
            self._tables.pop().check(self._report)
        while self._charts:
            self._close_chart()
        self._check_title()
        self._check_heading_order()

    def _visit(self, tag: str, attrs: list[tuple[str, str | None]], start_tag: str) -> None:
        line = self.getpos()[0]
        self._document_tag = self._document_tag or start_tag
        if tag in _SUPPRESSED:
            self._suppressed += 1
            return
        if self._suppressed:
            return

        attributes = dict(attrs)
        self._check_id(attributes, start_tag, line)

        if tag in _HEADING_TAGS:
            self._levels.append((int(tag[1]), line, start_tag))
            if tag == "h1":
                self._h1s.append((line, start_tag))
        elif tag == "table":
            self._tables.append(_Table(start_tag=start_tag, line=line))
        elif tag == "caption" and self._tables:
            self._tables[-1].caption = True
        elif tag == "th" and self._tables:
            self._tables[-1].add_header(attributes.get("scope"), start_tag, line)
        elif tag == "img":
            self._check_image(attributes, start_tag, line)
        elif tag == "svg":
            chart = _Chart(start_tag=start_tag, line=line)
            self._charts.append(chart)
            chart.is_labelled_by(attributes)
        elif tag == "title" and self._charts:
            # `<title>` is how an inline SVG names itself without a label.
            self._charts[-1].labelled = True

    def _check_id(self, attributes: dict[str, str | None], start_tag: str, line: int) -> None:
        value = (attributes.get("id") or "").strip()
        if not value:
            return
        earlier = self._ids.get(value)
        if earlier is not None:
            self._report(
                "duplicate-id",
                f'id="{value}" is already used, so an in-page link or a label '
                "points at the wrong element",
                start_tag,
                line,
            )
        else:
            self._ids[value] = (line, start_tag)

    def _check_image(self, attributes: dict[str, str | None], start_tag: str, line: int) -> None:
        if attributes.get("alt") is None:
            self._report(
                "image-label",
                'an <img> needs alt=, or alt="" when it is decoration',
                start_tag,
                line,
            )

    def _close_chart(self) -> None:
        chart = self._charts.pop()
        if not chart.labelled:
            self._report(
                "image-label",
                'an <svg> is either decoration with aria-hidden="true" or a chart '
                'with role="img" and a label',
                chart.start_tag,
                chart.line,
            )

    def _check_title(self) -> None:
        if len(self._h1s) == 1:
            return
        detail = (
            "the document has no <h1>, so a reader has no title to start from"
            if not self._h1s
            else f"the document has {len(self._h1s)} <h1> elements; one document is one title"
        )
        snippet = self._h1s[1][1] if len(self._h1s) > 1 else self._document_tag
        line = self._h1s[1][0] if len(self._h1s) > 1 else 1
        self._report("single-h1", detail, snippet, line)

    def _check_heading_order(self) -> None:
        for (level, _, _), (next_level, next_line, next_tag) in zip(
            self._levels, self._levels[1:], strict=False
        ):
            if next_level > level + 1:
                self._report(
                    "heading-order",
                    f"a <h{next_level}> follows an <h{level}>, skipping <h{level + 1}>",
                    next_tag,
                    next_line,
                )

    def _report(self, rule: str, detail: str, snippet: str, line: int) -> None:
        self._sequence += 1
        self._found.append(
            (line, self._sequence, Violation(rule=rule, detail=detail, snippet=snippet))
        )


def _order(entry: tuple[int, int, Violation]) -> tuple[int, int]:
    return (entry[0], entry[1])
