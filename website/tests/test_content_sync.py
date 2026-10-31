"""The site must agree with the code it documents.

These are the drift alarms. If a tool is added to the MCP server, a
connector preset to the catalog, or a command to the CLI, the site's
reference pages must change with it — and CI fails if they do not.
"""

from __future__ import annotations

import json

import extract
from site_support import (
    CATALOG_PY,
    CATALOG_TS,
    CLI_PY,
    CONTRACT_PY,
    MCP_SERVER_PY,
    ROADMAP_MD,
    SCHEMA_PY,
    SITE,
    read_page,
)


def test_site_tool_list_matches_the_contract():
    tools = extract.read_tools(MCP_SERVER_PY, CONTRACT_PY)
    html = read_page("docs/mcp/index.html")
    for tool in tools:
        assert f'id="tool-{tool["name"]}"' in html, f"{tool['name']} is missing from the site"


def test_every_tool_has_a_written_purpose():
    """No tool falls back to "See the MCP server source for details." on the site."""
    tools = extract.read_tools(MCP_SERVER_PY, CONTRACT_PY)
    undescribed = [tool["name"] for tool in tools if "See the MCP server source" in tool["purpose"]]
    assert not undescribed, f"tools without a one-line purpose: {undescribed}"


def test_the_integration_guide_lists_every_tool():
    tools = extract.read_tools(MCP_SERVER_PY, CONTRACT_PY)
    html = read_page("docs/integration/index.html")
    for tool in tools:
        assert f"<code>{tool['name']}</code>" in html, (
            f"{tool['name']} is missing from the integration guide"
        )


def test_the_integration_guide_hides_its_generation_markers():
    """The markers a tool writes into the guide are comments, not visible text."""
    html = read_page("docs/integration/index.html")
    assert "BEGIN GENERATED" not in html
    assert "END GENERATED" not in html


def test_every_tool_signature_on_the_site_is_the_real_one():
    tools = extract.read_tools(MCP_SERVER_PY, CONTRACT_PY)
    html = read_page("docs/mcp/index.html")
    for tool in tools:
        expected = tool["name"] + "("
        assert expected in html
        for param in tool["params"]:
            assert param["name"] in html


def test_tool_reference_does_not_repeat_defaults_outside_the_signature():
    html = read_page("docs/mcp/index.html")

    assert "<th>Default</th>" not in html
    assert "allow_empty_job_map: bool = False" in html


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


def test_the_odi_schema_on_the_site_matches_the_core():
    schema = extract.read_odi_schema(SCHEMA_PY)
    html = read_page("docs/mcp/index.html")
    assert 'id="odi-schema"' in html
    for entity in schema:
        assert entity in html, f"{entity} is missing from the schema on the site"


def test_every_guide_in_the_navigation_exists_on_disk():
    nav = json.loads((SITE / "content" / "nav.json").read_text(encoding="utf-8"))
    for group in nav["groups"]:
        for guide in group["guides"]:
            source = guide.get("source")
            if source:
                assert (SITE.parents[0] / source).is_file(), f"{source} does not exist"
            page = read_page(f"docs/{guide['slug']}/index.html")
            assert "<h1" in page


def test_the_docs_list_every_connector_preset_with_a_health_endpoint():
    # The connectors guide is the page a reader lands on when they want a
    # preset; the catalog is the code that decides which presets exist. The
    # page must name every preset and the endpoint that checks its health, or
    # a preset can ship without anyone being able to discover it.
    presets = extract.read_connectors(CATALOG_PY)
    html = read_page("docs/connectors/index.html")
    for preset in presets:
        assert f'id="preset-{preset["id"]}"' in html, f"{preset['id']} is missing from the docs"
        assert f"POST /api/connectors/{preset['id']}/health" in html


def test_every_tool_signature_has_a_copy_control():
    # The MCP reference is the page readers copy signatures from. Each tool's
    # code block must carry its own control, not one shared button that copies
    # whichever block happens to be first.
    tools = extract.read_tools(MCP_SERVER_PY, CONTRACT_PY)
    html = read_page("docs/mcp/index.html")
    for tool in tools:
        section = html.split(f'id="tool-{tool["name"]}"', 1)[1].split("</section>", 1)[0]
        assert 'class="copy-btn"' in section, f"{tool['name']} has no copy control"
        assert "data-copy" in section, f"{tool['name']} copy control is not wired"


def test_the_schema_block_has_a_copy_control():
    html = read_page("docs/mcp/index.html")
    section = html.split('id="odi-schema"', 1)[1].split("</section>", 1)[0]
    assert 'class="copy-btn"' in section
    assert "data-copy" in section


def test_the_copy_control_reports_that_it_copied():
    # The acceptance is a visible Copied state, not just a button. The script
    # is static, so this is the closest the site's test suite can get to the
    # click without a browser.
    script = (SITE / "assets" / "main.js").read_text(encoding="utf-8")
    assert 'document.querySelectorAll("[data-copy]")' in script
    assert 'button.textContent = "Copied"' in script
