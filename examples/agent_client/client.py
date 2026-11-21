"""A minimal MCP client for the Agentic ODI store.

This is the runnable half of ``docs/integration.md``. It connects to the ODI
MCP server, reads the landscape, evaluates a statement, and shows how a write
is held behind consent. It is deliberately small: an integrator should be able
to read it in one sitting and copy the parts they need.

Every function takes an already-connected ``fastmcp.Client`` so the same code
runs against a real server and against the in-memory server the test suite
builds. Nothing here reaches the network, a model, or a user's default store.

Run it for a demonstration::

    uv run python -m examples.agent_client.client
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from agentic_odi_core.consent import ConsentGate
from agentic_odi_core.errors import ConsentRequired
from fastmcp import Client


def _text(result: Any) -> str:
    """The text of a tool result's first content block."""
    return result.content[0].text


def _json(result: Any) -> Any:
    """Parse a tool result into Python.

    Read tools return bare JSON. Create tools prefix their JSON with a short
    message (``Job created successfully: {...}``), and a failure returns an
    ``Error:`` string. Both are handled here so a caller has one parse path.
    """
    text = _text(result)
    if text.startswith("Error:"):
        return {"error": text}
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        _, _, payload = text.partition(": ")
        return json.loads(payload)


async def tool_names(client: Client) -> list[str]:
    """The tools the server exposes, as an agent would discover them."""
    return sorted(tool.name for tool in await client.list_tools())


async def page_jobs(client: Client, *, limit: int, offset: int) -> list[dict[str, Any]]:
    """One page of jobs. ``limit`` caps the page; ``offset`` skips the first N."""
    return _json(await client.call_tool("get_jobs", {"limit": limit, "offset": offset}))


async def read_all_jobs(client: Client, *, page_size: int = 2) -> list[dict[str, Any]]:
    """Walk every job, one page at a time, stopping on a short page.

    Termination is by page length, not by a total the caller guessed: a page
    shorter than ``page_size`` means there is no next page. This is the loop an
    integrator writes so a long list does not silently truncate.
    """
    jobs: list[dict[str, Any]] = []
    offset = 0
    while True:
        page = await page_jobs(client, limit=page_size, offset=offset)
        jobs.extend(page)
        if len(page) < page_size:
            break
        offset += page_size
    return jobs


async def read_landscape(client: Client, job_id: str) -> list[dict[str, Any]]:
    """The desired outcomes of a job — the landscape an agent reasons over."""
    return _json(await client.call_tool("get_outcomes", {"job_id": job_id}))


async def evaluate_statement(client: Client, statement: str) -> dict[str, Any]:
    """Check a statement against the ODI format before anyone saves it."""
    return _json(await client.call_tool("evaluate_outcome", {"statement": statement}))


async def read_score(client: Client, outcome_id: str) -> dict[str, Any]:
    """Read an outcome's scores as a sample.

    An unscored outcome reports ``importance: null`` and ``satisfaction: null``
    — a sample that has not been taken, not a measured zero. An integrator must
    render "nothing yet" rather than a ``0``.
    """
    return _json(await client.call_tool("get_outcome_score", {"outcome_id": outcome_id}))


@dataclass(frozen=True)
class Write:
    """A proposed write: a tool and its arguments, not yet executed."""

    tool: str
    arguments: Mapping[str, Any]


def propose(tool: str, arguments: Mapping[str, Any]) -> Write:
    """Describe a write without performing it."""
    return Write(tool=tool, arguments=dict(arguments))


async def write_with_consent(
    client: Client,
    write: Write,
    *,
    approved: bool,
) -> dict[str, Any] | None:
    """Run a proposed write only after consent.

    The MCP tool surface itself carries no actor: the protocol does not say who
    is asking, so an integration that writes must supply that decision out of
    band. Here the decision is the same :class:`ConsentGate` the product uses:
    the call is a proposal, and a person approves or declines it.

    A write that is not approved is never executed and the store is unchanged —
    a refused write is a call that does not happen, not an error to swallow.
    Returns the created row's JSON, or ``None`` when the write was refused.
    """
    gate = ConsentGate()
    proposal = gate.request(write.tool, write.arguments)

    async def action(arguments: Mapping[str, Any]) -> dict[str, Any]:
        return _json(await client.call_tool(write.tool, dict(arguments)))

    if not approved:
        gate.decline(proposal)
        try:
            await gate.execute(proposal, action)  # type: ignore[arg-type]
        except (ConsentRequired, ValueError):
            return None
        raise AssertionError("a declined write must not execute")  # pragma: no cover

    gate.approve(proposal)
    return await gate.execute(proposal, action)  # type: ignore[arg-type]


async def _demo() -> None:
    """A walkthrough a person can run, against an isolated in-memory store."""
    from agentic_odi_mcp_server import mcp

    async with Client(mcp) as client:
        names = await tool_names(client)
        print(f"{len(names)} tools available")

        jobs = await read_all_jobs(client, page_size=2)
        print(f"jobs on this (empty) workspace: {len(jobs)}")

        verdict = await evaluate_statement(
            client, "Minimize the time it takes to onboard when a customer signs up."
        )
        print(f"statement valid: {verdict.get('valid')}")

        write = propose("add_job", {"name": "Onboard customers"})
        refused = await write_with_consent(client, write, approved=False)
        print(f"write refused, nothing written: {refused is None}")

        allowed = await write_with_consent(client, write, approved=True)
        print(f"write approved, created: {allowed is not None}")


if __name__ == "__main__":
    asyncio.run(_demo())
