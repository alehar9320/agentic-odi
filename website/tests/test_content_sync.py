"""The site must agree with the code it documents.

These are the drift alarms. If a tool is added to the MCP server, a
connector preset to the catalog, or a command to the CLI, the site's
reference pages must change with it — and CI fails if they do not.
"""

from __future__ import annotations

import json

import extract
from conftest import (
    CATALOG_PY,
    CATALOG_TS,
    CLI_PY,
    CONTRACT_PY,
    MCP_SERVER_PY,
    ROADMAP_MD,
    SITE,
    read_page,
)


def test_site_tool_list_matches_the_contract():
    tools = extract.read_tools(MCP_SERVER_PY, CONTRACT_PY)
    html = read_page("docs/mcp/index.html")
    for tool in tools:
        assert f'id="tool-{tool["name"]}"' in html, f"{tool['name']} is missing from the site"


def test_every_tool_signature_on_the_site_is_the_real_one():
    tools = extract.read_tools(MCP_SERVER_PY, CONTRACT_PY)
    html = read_page("docs/mcp/index.html")
    for tool in tools:
        expected = tool["name"] + "("
        assert expected in html
        for param in tool["params"]:
            assert param["name"] in html


def test_site_connector_list_matches_the_catalog():
    presets = extract.read_connectors(CATALOG_PY)
    html = read_page("index.html")
    for preset in presets:
        assert f'id="connector-{preset["id"]}"' in html, f"{preset['id']} is missing from the site"


def test_site_cli_commands_match_the_registry():
    commands = extract.read_cli(CLI_PY)
    assert commands, "no CLI commands were found"
    html = read_page("docs/cli/index.html")
    for command in commands:
        assert command["name"] in html, f"{command['name']} is missing from the site"


def test_the_catalog_cards_on_the_site_match_the_studio():
    cards = extract.read_catalog_cards(CATALOG_TS)
    html = read_page("index.html")
    for card in cards:
        assert card["type"] in html, f"{card['type']} is missing from the site"


def test_the_roadmap_page_is_rendered_from_the_repository():
    pending = extract.read_roadmap_pending(ROADMAP_MD)
    html = read_page("docs/roadmap/index.html")
    # Every checked item in the repository is a checked item on the site.
    for line in ROADMAP_MD.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("- [x]"):
            title = stripped[5:].strip().split("**")[1]
            assert title in html, f"{title!r} is missing from the roadmap page"
    assert len(pending) == 0, "the roadmap has pending items; the status copy must change"


def test_the_landing_counts_match_the_source():
    tools = extract.read_tools(MCP_SERVER_PY, CONTRACT_PY)
    connectors = extract.read_connectors(CATALOG_PY)
    cards = extract.read_catalog_cards(CATALOG_TS)
    text = read_page("index.html")
    assert f"{len(tools)} MCP tools" in text
    assert f"{len(cards)} agent-composed surfaces" in text
    assert f"{len(connectors)} connector presets" in text


def test_every_guide_in_the_navigation_exists_on_disk():
    nav = json.loads((SITE / "content" / "nav.json").read_text(encoding="utf-8"))
    for group in nav["groups"]:
        for guide in group["guides"]:
            source = guide.get("source")
            if source:
                assert (SITE.parents[0] / source).is_file(), f"{source} does not exist"
            page = read_page(f"docs/{guide['slug']}/index.html")
            assert "<h1" in page
