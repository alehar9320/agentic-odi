"""The site's contract: structure, metadata, honesty, and links.

Every page the generator produces is checked here. The site is a product
surface, so the tests care about two things above all: that the structure is
honest, and that nothing on it is a dead end.
"""

from __future__ import annotations

import re

import pytest

import extract
from conftest import CORE_MODELS_PY, all_pages, h1_text, read_page

PAGES_URL = "https://alehar9320.github.io/agentic-odi/"

# Every external origin the site may reference. Nothing else may appear.
ALLOWED_EXTERNAL_PREFIXES = (
    "https://github.com/alehar9320/agentic-odi",
    "https://alehar9320.github.io/agentic-odi/",
    "https://agentic-odi.alehar.workers.dev/",
    "https://agentic-odi.fastmcp.app/mcp",
    "https://horizon.prefect.io/alhase/servers/agentic-odi/chat",
    "https://docs.astral.sh/uv/",
    "https://modelcontextprotocol.io",
    "https://www.python.org/downloads/",
    "https://www.prefect.io/horizon",
    "https://github.com/jlowin/fastmcp",
    "https://strategyn.com/outcome-driven-innovation/",
    "https://pypi.org/project/",
)

# The strings the site must carry. These are promises, not decoration.
REQUIRED_STRINGS = (
    "experimental",
    "your roadmap is a guess.",
    "we don't publish dates",
    "all rights reserved",
    "strategyn",
    "free prefect account",
    "open an issue",
    "http://localhost:8000/mcp",
)

# Strings the site must never carry.
FORBIDDEN_STRINGS = (
    "discord",
    "mailto:",
)

EMOJI = re.compile("[\u2600-\u27bf\U0001f300-\U0001faff]")
QUARTER = re.compile(r"\bQ[1-4]\b")
MONTH_YEAR = re.compile(
    r"\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+20\d\d"
)


def _meta(html: str, name: str) -> str | None:
    match = re.search(
        rf'<meta\s+(?:name|property)="{re.escape(name)}"\s+content="([^"]*)"', html
    )
    return match.group(1) if match else None


def _visible_text(html: str) -> str:
    """The page's text, with the markup removed."""
    return re.sub(r"<[^>]+>", "", html)


def _all_html() -> str:
    return "\n".join(read_page(page) for page in all_pages())


# ---------------------------------------------------------------- basics


@pytest.mark.parametrize("page", all_pages())
def test_page_has_the_required_basics(page: str):
    html = read_page(page)
    assert 'lang="en"' in html
    assert '<meta charset="utf-8">' in html
    assert "width=device-width" in html


@pytest.mark.parametrize("page", all_pages())
def test_page_has_exactly_one_h1(page: str):
    html = read_page(page)
    assert html.count("<h1") == 1, f"{page} must have exactly one <h1>"


@pytest.mark.parametrize("page", all_pages())
def test_page_headings_never_skip_a_level(page: str):
    html = read_page(page)
    levels = [int(level) for level in re.findall(r"<h([1-6])\b", html)]
    assert levels, f"{page} has no headings"
    assert levels[0] == 1, f"{page} must start at <h1>"
    for previous, current in zip(levels, levels[1:], strict=False):
        assert current <= previous + 1, f"{page} skips from <h{previous}> to <h{current}>"


@pytest.mark.parametrize("page", all_pages())
def test_page_has_the_landmarks(page: str):
    html = read_page(page)
    for landmark in ("<header", "<main", "<footer"):
        assert landmark in html, f"{page} is missing {landmark}>"


@pytest.mark.parametrize("page", all_pages())
def test_in_page_anchors_resolve(page: str):
    html = read_page(page)
    ids = set(re.findall(r'id="([^"]+)"', html))
    for anchor in re.findall(r'href="#([^"]+)"', html):
        assert anchor in ids, f"{page}: #{anchor} does not resolve"


@pytest.mark.parametrize("page", all_pages())
def test_no_third_party_requests(page: str):
    html = read_page(page)
    for url in re.findall(r'https?://[^"\')\s]+', html):
        assert url.startswith(ALLOWED_EXTERNAL_PREFIXES), f"{page}: unexpected {url}"


@pytest.mark.parametrize("page", all_pages())
def test_no_emoji(page: str):
    assert not EMOJI.search(read_page(page)), f"{page} contains an emoji"


@pytest.mark.parametrize("page", all_pages())
def test_no_milestone_dates(page: str):
    html = read_page(page)
    assert not QUARTER.search(html), f"{page} contains a quarter"
    assert not MONTH_YEAR.search(html), f"{page} contains a month and year"


@pytest.mark.parametrize("page", all_pages())
def test_decorative_svg_is_hidden_from_assistive_tech(page: str):
    html = read_page(page)
    for tag in re.findall(r"<svg\b[^>]*>", html):
        assert "aria-hidden" in tag or "role=" in tag, f"{page}: {tag}"


# ---------------------------------------------------------------- landing


def test_landing_has_exactly_one_h1_inside_main():
    html = read_page("index.html")
    assert h1_text(html) == "Your roadmap is a guess."
    main = html.split("<main", 1)[1].split("</main>", 1)[0]
    assert "<h1" in main


def test_landing_sections_have_stable_ids():
    html = read_page("index.html")
    for anchor in ("top", "problem", "insight", "run", "status"):
        assert f'id="{anchor}"' in html


def test_opportunity_formula_matches_the_core_source():
    compact = re.sub(r"\s+", "", _visible_text(read_page("index.html"))).lower()
    assert "importance+max(importance-satisfaction,0)" in compact


def test_the_rendered_formula_is_generated_from_the_core_source():
    # The page must not merely *contain* the formula — it must contain the
    # formula the core module actually computes, read from the source.
    source = extract.read_odi_formula(CORE_MODELS_PY)
    assert "importance + max(importance - satisfaction, 0)" in source
    compact = re.sub(r"\s+", "", _visible_text(read_page("index.html"))).lower()
    assert re.sub(r"\s+", "", source).lower() in compact


def test_the_formula_is_not_typed_into_the_content_file():
    from conftest import SITE

    content = (SITE / "content" / "landing.json").read_text(encoding="utf-8")
    assert "importance - satisfaction" not in content


# ---------------------------------------------------------------- metadata


def test_the_landing_carries_complete_social_metadata():
    html = read_page("index.html")
    assert _meta(html, "og:type") == "website"
    assert _meta(html, "og:site_name") == "Agentic ODI"
    assert _meta(html, "og:url") == PAGES_URL
    assert _meta(html, "og:image") == PAGES_URL + "assets/og.png"
    assert _meta(html, "twitter:card") == "summary_large_image"
    assert _meta(html, "twitter:title")
    assert _meta(html, "twitter:description")
    assert _meta(html, "twitter:image") == PAGES_URL + "assets/og.png"
    assert f'<link rel="canonical" href="{PAGES_URL}">' in html
    assert html.count('name="theme-color"') == 1


def test_the_title_and_description_are_well_formed():
    html = read_page("index.html")
    title = re.search(r"<title>(.*?)</title>", html).group(1).strip()
    assert "Agentic ODI" in title
    assert len(title) <= 60
    description = _meta(html, "description")
    assert description
    assert len(description) <= 160
    assert description.endswith(".") or description.endswith("them.")


# ---------------------------------------------------------------- honesty


def test_the_required_strings_are_present():
    html = _all_html().lower()
    for string in REQUIRED_STRINGS:
        assert string in html, f"the site is missing {string!r}"


def test_the_forbidden_strings_are_absent():
    html = _all_html().lower()
    for string in FORBIDDEN_STRINGS:
        assert string not in html, f"the site contains {string!r}"


def test_the_auth_gated_surfaces_are_labeled_before_the_link():
    html = read_page("index.html")
    for url in ("agentic-odi.fastmcp.app/mcp", "horizon.prefect.io"):
        position = html.index(url)
        window = html[position : position + 600].lower()
        assert "auth" in window or "prefect account" in window, f"{url} is not labeled"


def test_the_three_hosted_surfaces_are_distinguished():
    html = read_page("index.html")
    assert "agentic-odi.fastmcp.app/mcp" in html
    assert "agentic-odi.alehar.workers.dev" in html
    assert "horizon.prefect.io" in html


# ---------------------------------------------------------------- 404


def test_the_404_page_is_self_contained():
    html = read_page("404.html")
    assert 'lang="en"' in html
    assert "<h1" in html
    assert PAGES_URL in html
    assert "<link" not in html
    assert "<script" not in html
    assert "<img" not in html
