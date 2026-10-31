"""The site's contract: structure, metadata, honesty, and links.

Every page the generator produces is checked here. The site is a product
surface, so the tests care about two things above all: that the structure is
honest, and that nothing on it is a dead end.
"""

from __future__ import annotations

import html as html_module
import json
import re

import extract
import pytest
from site_support import (
    CATALOG_PY,
    CATALOG_TS,
    CONTRACT_PY,
    CORE_MODELS_PY,
    MCP_SERVER_PY,
    _built_root,
    all_pages,
    h1_text,
    read_page,
)

PAGES_URL = "https://alehar9320.github.io/agentic-odi/"

# Every external origin the site may reference. Nothing else may appear.
# The list covers the site's own links and every origin the repository's
# guides already link to.
ALLOWED_EXTERNAL_PREFIXES = (
    # The project itself.
    "https://github.com/alehar9320/agentic-odi",
    "https://github.com/",
    "https://alehar9320.github.io/agentic-odi/",
    "https://alehar9320.github.io",
    "https://agentic-odi.alehar.workers.dev/",
    "https://agentic-odi.fastmcp.app/mcp",
    "https://horizon.prefect.io/alhase/servers/agentic-odi/chat",
    # Tooling the guides mention.
    "https://docs.astral.sh/uv/",
    "https://modelcontextprotocol.io",
    "https://www.python.org/downloads/",
    "https://www.prefect.io/horizon",
    "https://github.com/jlowin/fastmcp",
    "https://strategyn.com/outcome-driven-innovation/",
    "https://pypi.org/project/",
    "https://codecov.io",
    "https://developers.cloudflare.com",
    "https://docs.entire.io",
    "https://www.chromatic.com",
    "https://playwright.dev",
    "https://freebuff.com",
    "https://pi.dev",
    # A placeholder in the connector documentation. It is not routable, and
    # it is shown as an example of what a connector URL looks like.
    "https://mcp.internal.example",
    # The local endpoints, which the site points developers at.
    "http://localhost:8000/mcp",
    "http://localhost:8000",
    "http://localhost:8001",
    "http://localhost:5173",
    "http://127.0.0.1:8100",
    "http://127.0.0.1:8001",
    "http://127.0.0.1:11434",
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

# The pages rendered verbatim from the repository's guides. Their prose is
# the maintainers', so the site's own copy rules do not apply to them.
MIRRORED_GUIDES = {
    "docs/architecture/index.html",
    "docs/cli/index.html",
    "docs/connectors/index.html",
    "docs/deployment/index.html",
    "docs/development/index.html",
    "docs/installation/index.html",
    "docs/local-llm/index.html",
    "docs/roadmap/index.html",
    "docs/studio/index.html",
}

QUARTER = re.compile(r"\bQ[1-4]\b")
MONTH_YEAR = re.compile(
    r"\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+20\d\d"
)


def _meta(html: str, name: str) -> str | None:
    match = re.search(rf'<meta\s+(?:name|property)="{re.escape(name)}"\s+content="([^"]*)"', html)
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
    html = html_module.unescape(read_page(page))
    for url in re.findall(r'https?://[^"\')\s<]+', html):
        assert url.startswith(ALLOWED_EXTERNAL_PREFIXES), f"{page}: unexpected {url}"


@pytest.mark.parametrize("page", all_pages())
def test_no_emoji(page: str):
    # The house rule is about the site's own copy: no emoji in the landing
    # page, the quick start, the reference, or the hub index. The
    # repository's guides are rendered as they are written — mangling a
    # maintainer's document to satisfy a marketing rule would be worse than
    # the emoji it removes.
    if page in MIRRORED_GUIDES:
        return
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
    from site_support import SITE

    content = (SITE / "content" / "landing.json").read_text(encoding="utf-8")
    assert "importance - satisfaction" not in content


# ---------------------------------------------------------------- run & status


def test_run_section_labels_every_hosted_surface():
    html = read_page("index.html")
    assert "http://localhost:8000/mcp" in html
    assert "http://127.0.0.1:8100" in html
    assert "agentic-odi.fastmcp.app/mcp" in html
    assert "agentic-odi.alehar.workers.dev" in html
    assert "horizon.prefect.io" in html
    assert "requires a free prefect account" in html.lower()


def test_the_run_section_has_install_tabs():
    html = read_page("index.html")
    assert 'role="tablist"' in html
    assert 'role="tab"' in html
    assert "install.sh" in html


def test_the_status_section_publishes_no_dates():
    html = read_page("index.html")
    assert not re.search(r"\bQ[1-4]\b", html)
    assert not re.search(
        r"\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+20\d\d",
        html,
    )


def test_the_tools_section_peeks_at_the_tool_surface():
    html = read_page("index.html")
    assert "get_job_map" in html
    assert "compute_opportunity" in html


def test_the_tool_count_on_the_page_matches_the_contract():
    tools = extract.read_tools(MCP_SERVER_PY, CONTRACT_PY)
    text = re.sub(r"\s+", " ", _visible_text(read_page("index.html")))
    assert f"See all {len(tools)} tools" in text


def test_the_status_list_reports_what_ships():
    text = re.sub(r"\s+", " ", _visible_text(read_page("index.html")))
    tools = extract.read_tools(MCP_SERVER_PY, CONTRACT_PY)
    connectors = extract.read_connectors(CATALOG_PY)
    cards = extract.read_catalog_cards(CATALOG_TS)
    assert f"{len(tools)} MCP tools" in text
    assert f"{len(cards)} agent-composed surfaces" in text
    assert f"{len(connectors)} connector presets" in text


def test_the_landing_sections_are_in_the_designed_order():
    html = read_page("index.html")
    order = [
        "top",
        "studio",
        "problem",
        "insight",
        "surfaces",
        "how",
        "connectors",
        "run",
        "tools",
        "status",
    ]
    positions = [html.index(f'id="{anchor}"') for anchor in order]
    assert positions == sorted(positions), "the landing sections are out of order"


# ---------------------------------------------------------------- surfaces


def test_surfaces_section_shows_every_catalog_card():
    html = read_page("index.html")
    for card in (
        "outcome-card",
        "opportunity-board",
        "impact-simulation",
        "evidence-quote",
        "job-map",
        "opportunity-thesis",
        "decision-record",
    ):
        assert card in html


def test_connectors_section_lists_every_preset():
    presets = extract.read_connectors(CATALOG_PY)
    html = read_page("index.html")
    for preset in presets:
        assert f'id="connector-{preset["id"]}"' in html


def test_landing_never_names_a_canvas_view():
    html = read_page("index.html").lower()
    assert "opportunity landscape" not in html
    assert "opportunity thesis" not in html


def test_the_connector_count_on_the_page_matches_the_catalog():
    presets = extract.read_connectors(CATALOG_PY)
    text = re.sub(r"\s+", " ", _visible_text(read_page("index.html")))
    assert f"{len(presets)} presets ship today" in text


# ---------------------------------------------------------------- demo


def test_demo_is_labeled_as_scripted():
    html = read_page("index.html")
    assert "scripted preview" in html.lower()


def test_demo_transcript_is_server_rendered():
    html = read_page("index.html")
    # All three scripted exchanges are present in the static HTML, so a
    # reader without JavaScript still sees the whole story.
    for fragment in (
        "reconcile invoices by hand",
        "which of these should we build first",
        "show me the job behind that",
    ):
        assert fragment in html.lower()


def test_demo_controls_are_buttons():
    html = read_page("index.html")
    assert 'type="button"' in html
    assert "demo__chip" in html
    assert "<textarea" in html


def test_demo_javascript_is_deferred_and_leaves_the_transcript_intact():
    html = read_page("index.html")
    tags = re.findall(r"<script[^>]*demo\.js[^>]*>", html)
    assert tags, "demo.js is not loaded"
    assert "defer" in tags[0], "demo.js must be deferred"
    # The live panel starts hidden; the script is what reveals it.
    assert "data-demo-live" in html
    assert re.search(r"data-demo-live[^>]*hidden", html)


def test_demo_scores_match_the_opportunity_formula():
    from site_support import SITE

    demo = json.loads((SITE / "content" / "demo.json").read_text(encoding="utf-8"))
    for exchange in demo["exchanges"]:
        card = exchange["card"]
        if card["type"] == "outcome-card":
            data = card["data"]
            assert data["opportunity"] == data["importance"] + max(
                data["importance"] - data["satisfaction"], 0
            )
        if card["type"] == "opportunity-board":
            for row in card["data"]["outcomes"]:
                assert row["opportunity"] == row["importance"] + max(
                    row["importance"] - row["satisfaction"], 0
                )


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


# ---------------------------------------------------------------- weight & links


@pytest.mark.parametrize("page", all_pages())
def test_every_page_resolves_its_own_assets(page: str):
    html = read_page(page)
    for ref in re.findall(r'(?:src|href)="((?!https?:|#|mailto:)[^"]+)"', html):
        if ref.endswith((".html", "/")):
            continue
        target = ref.split("#", 1)[0].split("?", 1)[0]
        assert _built_root(page).parent.joinpath(target).resolve().is_file(), (
            f"{page}: {ref} does not resolve"
        )


@pytest.mark.parametrize("page", all_pages())
def test_page_weights_are_within_budget(page: str):
    size = _built_root(page).stat().st_size
    # The MCP reference is the long pole: every tool's argument table and the
    # whole ODI schema live on that one page, so it grows with each paginated
    # list tool and each entity we add. The V2MOM entity, the five scheduled-work
    # tools, the three signal tools, the four Stage 5 and 6 tools, and the
    # interview/quote tools with their two schema entities and the evidence-claim
    # markers bring the page to ~93 KB.
    assert size <= 96 * 1024, f"{page}: {size} bytes"
