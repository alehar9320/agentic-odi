"""Every page of the site gets its own social card.

The card is generated from the page's own metadata, and its optional figure is a
number the page itself renders - never an invented one. A page with nothing to
show gets the section card with no number at all.
"""

from __future__ import annotations

import re

import build_site
import make_og
import pytest
from site_support import _build_the_site, all_pages, read_page

PAGES_URL = build_site.PAGES_URL


def _built_cards() -> dict[str, bytes]:
    root = _build_the_site()
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted((root / "og").rglob("*.png"))
    }


def _og_image(html: str) -> str | None:
    match = re.search(r'<meta property="og:image" content="([^"]+)"', html)
    return match.group(1) if match else None


def test_every_page_has_an_og_image_tag():
    for page in all_pages():
        assert _og_image(read_page(page)), f"{page} has no og:image"


def test_every_og_image_points_at_a_file_that_exists():
    cards = _built_cards()
    for page in all_pages():
        url = _og_image(read_page(page))
        assert url is not None and url.startswith(PAGES_URL), f"{page}: {url!r}"
        relative = url[len(PAGES_URL) :]
        assert relative in cards, f"{page} names {relative}, which was not built"


def test_the_referenced_card_is_not_a_stub():
    cards = _built_cards()
    for page in all_pages():
        data = cards[_og_image(read_page(page))[len(PAGES_URL) :]]
        assert data[:8] == b"\x89PNG\r\n\x1a\n", f"{page}'s card is not a PNG"
        assert len(data) > 1_000, f"{page}'s card is trivially small"


def test_twitter_image_matches_the_og_image():
    for page in all_pages():
        html = read_page(page)
        twitter = re.search(r'<meta name="twitter:image" content="([^"]+)"', html)
        assert twitter is not None, f"{page} has no twitter:image"
        assert twitter.group(1) == _og_image(html), f"{page} advertises two different cards"


def test_different_pages_get_different_cards():
    cards = _built_cards()
    seen: dict[bytes, list[str]] = {}
    for page in all_pages():
        digest = cards[_og_image(read_page(page))[len(PAGES_URL) :]]
        seen.setdefault(digest, []).append(page)
    duplicated = {page for pages in seen.values() if len(pages) > 1 for page in pages}
    assert not duplicated, f"shared card between {sorted(duplicated)}"


def test_a_figure_is_a_number_the_page_itself_renders():
    """The claimed figure must be present in the page's own rendered content."""
    for page in all_pages():
        html = read_page(page)
        figure = build_site.page_figure(page, html)
        if figure is None:
            continue
        assert figure in html, f"{page} claims {figure!r}, which it does not render"


def test_pages_with_no_figure_get_no_number():
    plain = [page for page in all_pages() if build_site.page_figure(page, read_page(page)) is None]
    assert plain, "every page claims a figure, which cannot be right"
    for page in plain:
        html = read_page(page)
        title = build_site.page_title(html)
        section = build_site.page_section(page)
        assert make_og.render_card(title, section) == make_og.render_card(title, section, None)
        assert make_og.render_card(title, section) != make_og.render_card(title, section, "0")


def test_the_landing_stat_is_the_landing_figure():
    html = read_page("index.html")
    stat = build_site.page_figure("index.html", html)
    assert stat is not None, "the landing page renders a stat the card could not claim"
    assert stat in html


def test_build_fails_when_a_page_would_ship_without_a_card(monkeypatch, tmp_path):
    real_plan = build_site.og_plan

    def dropping_plan(pages):
        plan = dict(real_plan(pages))
        plan.pop(next(iter(sorted(plan))))
        return plan

    monkeypatch.setattr(build_site, "og_plan", dropping_plan)
    with pytest.raises(build_site.MissingCardError):
        build_site.build(tmp_path)
