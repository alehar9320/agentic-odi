"""ALH-129 — the integration guide is executed, not just written.

The guide in ``docs/integration.md`` promises four things: a client can
discover the tool surface, page a list, read an honest empty score, and hold a
write behind consent. Each promise is a claim about the shipped server, so each
one is asserted here against a real FastMCP server, using the same
``examples/agent_client`` code the guide points at.

The server runs on a throwaway SQLite store, so these tests do not depend on
the order the rest of the suite ran in. The generated tool table is checked
against the contract in both directions: a tool cannot be added without a row,
and a row cannot outlive its tool.
"""

from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

import pytest
from agentic_odi_core.contract import TOOL_SPECS

# The server builds its repository at import time from AGENTIC_ODI_DB.
os.environ.setdefault("AGENTIC_ODI_DB", ":memory:")

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "examples" / "agent_client"
GUIDE = ROOT / "docs" / "integration.md"
GENERATOR = ROOT / "scripts" / "integration_guide.py"

if str(EXAMPLES) not in sys.path:
    sys.path.insert(0, str(EXAMPLES))

import client as agent_client  # noqa: E402


@pytest.fixture
def server(tmp_path, monkeypatch):
    """A server on its own SQLite file, built as an isolated module instance.

    ``mcp_server`` builds its repository at import time, so exercising a
    throwaway store means loading a fresh copy under a private name. Reloading
    the shared module would rebind the globals that the rest of the suite
    imports (``jobs_db``, ``mcp``, ...) and close the store out from under them.
    """
    db = str(tmp_path / "integration.db")
    monkeypatch.setenv("AGENTIC_ODI_DB", db)
    import importlib.util

    source = ROOT / "apps" / "mcp-server" / "src" / "agentic_odi_mcp_server" / "mcp_server.py"
    spec = importlib.util.spec_from_file_location("_integration_mcp_server", source)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    yield module
    module.shutdown_store()


def _load_generator():
    spec = importlib.util.spec_from_file_location("integration_guide", GENERATOR)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.asyncio
async def test_the_client_discovers_the_live_tool_surface(server) -> None:
    from fastmcp import Client

    async with Client(server.mcp) as client:
        names = await agent_client.tool_names(client)

    assert set(names) == set(TOOL_SPECS), "the example client sees a different tool surface"


@pytest.mark.asyncio
async def test_an_empty_workspace_reads_as_nothing_not_an_error(server) -> None:
    from fastmcp import Client

    async with Client(server.mcp) as client:
        jobs = await agent_client.read_all_jobs(client, page_size=2)

    assert jobs == [], "a fresh workspace must report no jobs, not an error"


@pytest.mark.asyncio
async def test_the_pagination_loop_terminates_on_a_short_page(server) -> None:
    from fastmcp import Client

    async with Client(server.mcp) as client:
        # Five jobs with a page size of two forces the short-page stop condition.
        for index in range(5):
            await client.call_tool("add_job", {"name": f"Job {index}"})

        jobs = await agent_client.read_all_jobs(client, page_size=2)

    assert len(jobs) == 5


@pytest.mark.asyncio
async def test_an_unscored_outcome_reports_nothing_yet(server) -> None:
    from fastmcp import Client

    async with Client(server.mcp) as client:
        created = agent_client._json(
            await client.call_tool("add_job", {"name": "Onboard customers"})
        )
        outcome = agent_client._json(
            await client.call_tool(
                "add_outcome",
                {
                    "job_id": created["id"],
                    "statement": (
                        "Minimize the time it takes to onboard when a customer signs up."
                    ),
                    "importance": 8,
                    "satisfaction": 4,
                },
            )
        )
        score = await agent_client.read_score(client, outcome["id"])

    # The numbers are present because the outcome carries them; the *sample*
    # is unknown, so it reports nothing rather than a fabricated size.
    assert score["sample_size"] is None
    assert score["opportunity_score"] == 12.0


@pytest.mark.asyncio
async def test_the_evaluate_tool_reports_a_verdict(server) -> None:
    from fastmcp import Client

    async with Client(server.mcp) as client:
        verdict = await agent_client.evaluate_statement(
            client, "Minimize the time it takes to onboard when a customer signs up."
        )

    assert verdict["valid"] is True
    assert verdict["direction"] == "minimize"


@pytest.mark.asyncio
async def test_a_refused_write_changes_nothing_and_an_approved_one_lands(server) -> None:
    from fastmcp import Client

    async with Client(server.mcp) as client:
        write = agent_client.propose("add_job", {"name": "Onboard customers"})

        refused = await agent_client.write_with_consent(client, write, approved=False)
        assert refused is None
        assert await agent_client.read_all_jobs(client) == []

        allowed = await agent_client.write_with_consent(client, write, approved=True)
        assert allowed is not None
        assert len(await agent_client.read_all_jobs(client)) == 1


def test_the_generated_tool_table_is_current() -> None:
    generator = _load_generator()
    block = generator.render()
    assert block in GUIDE.read_text(encoding="utf-8"), (
        "docs/integration.md is stale; run `uv run python scripts/integration_guide.py`"
    )


def test_every_tool_appears_in_the_generated_table() -> None:
    generator = _load_generator()
    rows = generator.tool_rows()
    assert {row["name"] for row in rows} == set(TOOL_SPECS)
