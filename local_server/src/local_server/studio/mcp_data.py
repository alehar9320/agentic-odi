"""MCP hydration and passthrough writes, ported from the Streamlit app."""

from __future__ import annotations

import asyncio
import contextlib
import json
from typing import Any

from fastapi import HTTPException
from fastmcp import Client as McpClient

from local_server.studio.probes import is_endpoint_reachable
from local_server.studio.seed import seed_payload

MCP_CALL_TIMEOUT = 3.0


async def fetch_canvas(mcp_url: str) -> dict[str, Any]:
    """Fetch live canvas data from FastMCP, falling back to the seed prototype."""
    jobs: list[dict[str, Any]] = []
    outcomes: list[dict[str, Any]] = []
    steps: list[dict[str, Any]] = []

    if not is_endpoint_reachable(mcp_url, timeout=0.3):
        return {**seed_payload(), "source": "seed"}

    with contextlib.suppress(Exception):
        mcp_client = McpClient(mcp_url)
        async with mcp_client:
            raw_jobs = await asyncio.wait_for(mcp_client.call_tool("get_jobs", {}), timeout=1.5)
            try:
                parsed_jobs = json.loads(str(raw_jobs))
                if isinstance(parsed_jobs, list):
                    jobs = parsed_jobs
            except Exception:  # noqa: BLE001
                jobs = []

            for job in jobs:
                job_id = job.get("id")
                if not job_id:
                    continue

                with contextlib.suppress(Exception):
                    raw_steps = await asyncio.wait_for(
                        mcp_client.call_tool("get_job_map", {"job_id": job_id}), timeout=1.0
                    )
                    parsed_steps = json.loads(str(raw_steps))
                    if isinstance(parsed_steps, list):
                        steps.extend(parsed_steps)

                with contextlib.suppress(Exception):
                    raw_outcomes = await asyncio.wait_for(
                        mcp_client.call_tool("get_outcomes", {"job_id": job_id}), timeout=1.0
                    )
                    parsed_outcomes = json.loads(str(raw_outcomes))
                    if isinstance(parsed_outcomes, list):
                        outcomes.extend(parsed_outcomes)

    if not jobs:
        return {**seed_payload(), "source": "seed"}

    return {"jobs": jobs, "steps": steps, "outcomes": outcomes, "source": "mcp"}


async def call_mcp_tool(mcp_url: str, tool: str, arguments: dict[str, Any]) -> str:
    """Invoke an MCP tool, surfacing failures as HTTP 502."""
    if not is_endpoint_reachable(mcp_url, timeout=0.3):
        raise HTTPException(status_code=502, detail=f"MCP server unreachable at {mcp_url}")

    try:
        async with McpClient(mcp_url) as mcp_client:
            result = await asyncio.wait_for(
                mcp_client.call_tool(tool, arguments), timeout=MCP_CALL_TIMEOUT
            )
            return str(result)
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"Error calling {tool}: {exc}") from exc
