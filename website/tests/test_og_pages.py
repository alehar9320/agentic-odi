# website/tests/test_og_pages.py
"""Every published page has its own social card, and the card is honest.

A card is a claim about the page it links to. Two things must therefore hold:
the claim is drawn from the page's own content (its title, its section, and a
figure the page itself states), and the claim is real (the file exists, its
bytes are a real image, and two pages never share one). A page with no figure
gets a card with no number rather than a `0`, because zero is a claim.
"""

from __future__ import annotations

import hashlib
import io
import re
import struct

import build_site
import make_og
import pytest
from PIL import Image
from site_support import _built_root, all_pages, read_page

PAGES_URL = "https://alehar9320.github.io/agentic-odi/"


def _meta(html: str, name: str) -> str | None:
    match = re.search(rf'<meta\s+(?:name|property)="{re.escape(name)}"\s+content="([^"]*)"', html)
    return match.group(1) if match else None


def _dims(png: bytes) -> tuple[int, int]:
    assert png[:8] == b"\x89PNG\r\n\x1a\n", "not a PNG"
    return struct.unpack(">II", png[16:24])


def _cards() -> dict[str, bytes]:
    """A fresh render of every published page's card."""
    rendered = build_site._render_pages(build_site.environment())
    pages = {name: html for name, html in rendered.items() if name != "404.html"}
    return make_og.render_site(pages, build_site.PAGES_URL, build_site._page_sections())


# ------------------------------------------------------- the card exists


@pytest.mark.parametrize("page", all_pages())
def test_every_page_points_at_its_own_existing_card(page: str):
    html = read_page(page)
    url = _meta(html, "og:image")
    assert url is not None, f"{page} has no og:image"
    assert url.startswith(PAGES_URL), url
    rel = url[len(PAGES_URL) :]
    card = _built_root(rel)
    assert card.is_file(), f"{page} points at a missing card: {rel}"
    data = card.read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n", f"{rel} is not a PNG"
    assert len(data) > 1000, f"{rel} is a stub, not a card"
    assert _dims(data) == (1200, 630)


@pytest.mark.parametrize("page", all_pages())
def test_every_page_has_a_text_equivalent_for_its_card(page: str):
    # A card is an image; its meaning must survive without seeing it.
    html = read_page(page)
    assert _meta(html, "og:image:alt"), f"{page} has no og:image:alt"
    assert _meta(html, "twitter:image:alt"), f"{page} has no twitter:image:alt"
    assert _meta(html, "og:title"), f"{page} has no og:title"
    assert _meta(html, "og:description"), f"{page} has no og:description"


def test_the_build_emits_exactly_one_card_per_published_page():
    cards = _cards()
    assert set(cards) == {f"assets/og/{make_og.og_name(page)}" for page in all_pages()}
    # The 404 page is not published, so it has no card.
    assert "assets/og/404.png" not in cards


# ------------------------------------------------------- the card is unique


def test_two_different_pages_produce_different_images():
    cards = _cards()
    digests = {name: hashlib.sha256(data).hexdigest() for name, data in cards.items()}
    assert len(set(digests.values())) == len(digests), "two pages share one card image"


def test_the_cards_are_deterministic():
    assert _cards() == _cards()


def test_a_content_change_regenerates_the_card():
    # The card is a function of the page's own content, so changing the page
    # changes the card rather than reusing a stale image.
    first = make_og.render_site({"docs/x/index.html": "<h1>Alpha</h1>"}, PAGES_URL)
    second = make_og.render_site({"docs/x/index.html": "<h1>Beta</h1>"}, PAGES_URL)
    assert first != second
    assert set(first) == set(second)


def test_a_card_is_rendered_only_from_the_page_it_is_given():
    # Nothing outside the page's own HTML may reach a card, so no private
    # workspace data can leak into a public image.
    card = make_og.render_site(
        {"index.html": "<h1>Only This</h1><meta name='description' content='and this'>"},
        PAGES_URL,
    )
    assert set(card) == {"assets/og/index.png"}
    assert card["assets/og/index.png"] != _cards()["assets/og/index.png"]


# ------------------------------------------------------- the card is honest


def test_a_page_that_states_no_figure_draws_no_number():
    # docs/cli states no "<count> <noun>" of its own, so its card carries no
    # figure rather than a placeholder.
    html = read_page("docs/cli/index.html")
    card = make_og.page_card("docs/cli/index.html", html, "Build")
    assert card.figure is None


def test_a_page_that_states_a_figure_carries_it():
    html = read_page("docs/mcp/index.html")
    card = make_og.page_card("docs/mcp/index.html", html, "Build")
    assert card.figure is not None
    assert re.fullmatch(r"\d+ tools", card.figure)


def test_a_card_with_no_figure_renders_and_differs_from_one_with_a_figure():
    html = read_page("docs/cli/index.html")
    no_figure = make_og.render_page(
        make_og.page_card("docs/cli/index.html", html, "Build"), PAGES_URL
    )
    with_figure = make_og.render(
        headline="CLI Reference", subhead="x", url="example.com", pill="Build", figure="31 tools"
    )
    assert _dims(no_figure) == (1200, 630)
    assert no_figure != with_figure


def test_a_figure_must_be_a_number_the_page_states():
    # The figure comes from the page's own visible text, never from markup.
    assert make_og.figure_for("<p>31 tools</p>") == "31 tools"
    assert make_og.figure_for("<p>16 presets and 31 tools</p>") == "31 tools"
    assert make_og.figure_for("<svg><path d='M12 31 tools'/></svg>") is None
    assert make_og.figure_for("<script>var s = '31 tools'</script>") is None


def test_a_year_or_example_number_never_becomes_a_figure():
    assert make_og.figure_for("<p>2026 presets</p>") is None
    assert make_og.figure_for("<p>8000 commands</p>") is None


def test_a_genuine_zero_stays_distinguishable_from_no_figure():
    # "0 connectors" is a claim the page made; no figure at all is not.
    assert make_og.figure_for("<p>0 connectors</p>") == "0 connectors"
    assert make_og.figure_for("<p>no connectors</p>") is None


# ------------------------------------------------------- safe, unique paths


def test_card_names_are_safe_and_cannot_escape_or_collide():
    assert make_og.og_name("index.html") == "index.png"
    assert make_og.og_name("docs/mcp/index.html") == "docs-mcp.png"
    assert make_og.og_name("docs/a/b/index.html") == "docs-a-b.png"
    # Case-folded, so two pages cannot differ only by case.
    assert make_og.og_name("Docs/MCP/index.html") == "docs-mcp.png"
    # A hostile slug cannot escape the output directory.
    assert "/" not in make_og.og_name("../../etc/passwd")
    assert ".." not in make_og.og_name("../../etc/passwd")


def test_two_pages_that_normalize_to_one_name_are_rejected():
    pages = {
        "docs/mcp/index.html": "<h1>A</h1>",
        "docs-mcp/index.html": "<h1>B</h1>",
    }
    with pytest.raises(ValueError, match="share one card path"):
        make_og.render_site(pages, PAGES_URL)


# ------------------------------------------------------- hard titles


def test_a_long_or_non_ascii_title_renders_without_crashing():
    for title in ("A" * 400, "Café — ünïcödé", "日本語のタイトル", "Türkçe Şğüı & <b>markup</b>"):
        html = (
            "<html><head><title>t</title>"
            f"<meta name='description' content='d'></head><body><h1>{title}</h1></body></html>"
        )
        png = make_og.render_page(make_og.page_card("docs/x/index.html", html, "Build"), PAGES_URL)
        assert _dims(png) == (1200, 630)


def test_a_title_is_drawn_as_text_not_as_markup():
    html = "<html><body><h1>Roadmap &amp; Next Steps</h1></body></html>"
    card = make_og.page_card("docs/roadmap/index.html", html, "Operate")
    assert card.title == "Roadmap & Next Steps"


# ------------------------------------------------------- the build gate


def test_the_build_fails_when_a_page_has_no_card(tmp_path, monkeypatch):
    # A page published without a card would show someone else's image, so the
    # build must stop rather than ship it.
    monkeypatch.setattr(make_og, "render_site", lambda *args, **kwargs: {})
    with pytest.raises(SystemExit):
        build_site.build(tmp_path)


def test_the_cards_are_a_real_image_not_a_placeholder():
    # A card is a rendered PNG, not an empty buffer.
    data = _cards()["assets/og/index.png"]
    image = Image.open(io.BytesIO(data))
    assert image.size == (1200, 630)
    assert len(set(image.convert("RGB").get_flattened_data())) > 8, "the card is a flat fill"
