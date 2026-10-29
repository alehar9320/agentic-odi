"""MCP hydration and passthrough writes, ported from the Streamlit app."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any, Literal

from agentic_odi_core import ODIService, ToolName
from agentic_odi_core.remote import (
    StudioError,
    StudioErrorCode,
    parse_tool_result,
    tool_result_text,
)
from fastmcp import Client as McpClient
from fastmcp.exceptions import ToolError

from agentic_odi_studio_api.studio.errors import StudioHTTPError
from agentic_odi_studio_api.studio.probes import is_endpoint_reachable
from agentic_odi_studio_api.studio.seed import seed_payload

log = logging.getLogger(__name__)

MCP_CALL_TIMEOUT = 3.0

CanvasKind = Literal["live", "seed", "empty"]


def _provenance(
    kind: CanvasKind,
    reason: str,
    *,
    jobs: list[dict[str, Any]],
    steps: list[dict[str, Any]],
    outcomes: list[dict[str, Any]],
    evidence: list[dict[str, Any]],
) -> dict[str, Any]:
    """Say where the canvas came from instead of letting the UI guess."""
    return {
        "kind": kind,
        "reason": reason,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "record_counts": {
            "jobs": len(jobs),
            "steps": len(steps),
            "outcomes": len(outcomes),
            "evidence": len(evidence),
        },
    }


def _seed_canvas(reason: str) -> dict[str, Any]:
    seed = seed_payload()
    jobs = seed["jobs"]
    steps = seed["steps"]
    outcomes = seed["outcomes"]
    evidence: list[dict[str, Any]] = []
    return {
        **seed,
        "evidence": evidence,
        "source": "seed",
        "provenance": _provenance(
            "seed",
            reason,
            jobs=jobs,
            steps=steps,
            outcomes=outcomes,
            evidence=evidence,
        ),
    }


async def fetch_canvas(mcp_url: str) -> dict[str, Any]:
    """Fetch live canvas data from FastMCP, falling back to the seed prototype."""
    jobs: list[dict[str, Any]] = []
    outcomes: list[dict[str, Any]] = []
    steps: list[dict[str, Any]] = []
    evidence: list[dict[str, Any]] = []
    scheduled_work: list[dict[str, Any]] = []
    warnings: list[str] = []

    if not is_endpoint_reachable(mcp_url, timeout=0.3):
        log.warning("MCP endpoint unreachable at %s — falling back to seed data", mcp_url)
        return {**_seed_canvas("mcp_unreachable"), "warnings": ["MCP endpoint unreachable"]}

    try:
        mcp_client = McpClient(mcp_url)
        async with mcp_client:
            raw_jobs = await asyncio.wait_for(
                mcp_client.call_tool(ToolName.GET_JOBS.value, {}), timeout=1.5
            )
            try:
                parsed_jobs = json.loads(tool_result_text(raw_jobs))
                if isinstance(parsed_jobs, list):
                    jobs = parsed_jobs
            except Exception as exc:  # noqa: BLE001
                log.warning("Failed to parse jobs from MCP: %s", exc)
                jobs = []

            try:
                raw_scheduled = await asyncio.wait_for(
                    mcp_client.call_tool(ToolName.LIST_SCHEDULED_WORK.value, {}),
                    timeout=1.0,
                )
                parsed_scheduled = json.loads(str(raw_scheduled))
                if isinstance(parsed_scheduled, list):
                    scheduled_work = parsed_scheduled
            except Exception as exc:  # noqa: BLE001
                log.warning("Failed to fetch scheduled work from MCP: %s", exc)

            for job in jobs:
                job_id = job.get("id")
                if not job_id:
                    continue

                try:
                    raw_steps = await asyncio.wait_for(
                        mcp_client.call_tool(ToolName.GET_JOB_MAP.value, {"job_id": job_id}),
                        timeout=1.0,
                    )
                    parsed_steps = json.loads(tool_result_text(raw_steps))
                    if isinstance(parsed_steps, list):
                        steps.extend(parsed_steps)
                except Exception as exc:  # noqa: BLE001
                    msg = f"Failed to fetch steps for job {job_id}: {exc}"
                    log.warning(msg)
                    warnings.append(msg)

                try:
                    raw_outcomes = await asyncio.wait_for(
                        mcp_client.call_tool(ToolName.GET_OUTCOMES.value, {"job_id": job_id}),
                        timeout=1.0,
                    )
                    parsed_outcomes = json.loads(tool_result_text(raw_outcomes))
                    if isinstance(parsed_outcomes, list):
                        outcomes.extend(parsed_outcomes)
                except Exception as exc:  # noqa: BLE001
                    msg = f"Failed to fetch outcomes for job {job_id}: {exc}"
                    log.warning(msg)
                    warnings.append(msg)

            try:
                raw_evidence = await asyncio.wait_for(
                    mcp_client.call_tool(ToolName.LIST_EVIDENCE.value, {}), timeout=1.0
                )
                parsed_evidence = json.loads(tool_result_text(raw_evidence))
                if isinstance(parsed_evidence, list):
                    evidence = parsed_evidence
            except Exception as exc:  # noqa: BLE001
                msg = f"Failed to fetch evidence: {exc}"
                log.warning(msg)
                warnings.append(msg)
    except Exception as exc:  # noqa: BLE001
        log.warning("MCP canvas hydration failed entirely: %s", exc)
        warnings.append(f"MCP hydration error: {exc}")

    if not jobs:
        # The server answered: either it has no work, or nothing it sent was
        # usable. Both are empty, not the prototype dressed up as the user's.
        return {
            "jobs": [],
            "steps": [],
            "outcomes": [],
            "evidence": [],
            "source": "mcp",
            "warnings": warnings,
            "provenance": _provenance(
                "empty",
                "mcp_unreadable" if warnings else "no_jobs",
                jobs=[],
                steps=[],
                outcomes=[],
                evidence=[],
            ),
        }

    return {
        "jobs": jobs,
        "steps": steps,
        "outcomes": outcomes,
        "evidence": evidence,
        "scheduled_work": scheduled_work,
        "source": "mcp",
        "warnings": warnings,
        "provenance": _provenance(
            "live",
            "partial_hydration" if warnings else "mcp_live",
            jobs=jobs,
            steps=steps,
            outcomes=outcomes,
            evidence=evidence,
        ),
    }


def fetch_local_canvas(service: ODIService) -> dict[str, Any]:
    """Read the canvas directly from the local service, no HTTP round trip."""
    jobs = [job.model_dump() for job in service.get_jobs()]
    steps: list[dict[str, Any]] = []
    outcomes: list[dict[str, Any]] = []
    for job in jobs:
        job_id = job["id"]
        steps.extend(step.model_dump() for step in service.get_job_map(job_id))
        outcomes.extend(outcome.model_dump() for outcome in service.get_outcomes(job_id))
    evidence = [item.model_dump() for item in service.list_evidence()]
    scheduled_work = [item.model_dump() for item in service.list_scheduled_work()]
    empty = not jobs and not steps and not outcomes and not evidence and not scheduled_work
    return {
        "jobs": jobs,
        "steps": steps,
        "outcomes": outcomes,
        "evidence": evidence,
        "scheduled_work": scheduled_work,
        "source": "local",
        "provenance": _provenance(
            "empty" if empty else "live",
            "local_store_empty" if empty else "local_store",
            jobs=jobs,
            steps=steps,
            outcomes=outcomes,
            evidence=evidence,
        ),
    }


async def call_mcp_tool(mcp_url: str, tool: str, arguments: dict[str, Any]) -> str:
    """Invoke an MCP tool, surfacing failures as typed HTTP errors."""
    if not is_endpoint_reachable(mcp_url, timeout=0.3):
        raise StudioHTTPError(
            StudioError(
                code=StudioErrorCode.MCP_UNREACHABLE,
                message=f"MCP server unreachable at {mcp_url}",
                retryable=True,
            )
        )

    try:
        async with McpClient(mcp_url) as mcp_client:
            result = await asyncio.wait_for(
                mcp_client.call_tool(tool, arguments), timeout=MCP_CALL_TIMEOUT
            )
    except StudioHTTPError:
        raise
    except ToolError as exc:
        # The tool ran and refused: that is the tool's failure, not the
        # server's, and it is not worth retrying.
        raise StudioHTTPError(
            StudioError(
                code=StudioErrorCode.MCP_TOOL_FAILED,
                message=f"The {tool} tool failed: {exc}",
                retryable=False,
            )
        ) from exc
    except Exception as exc:  # noqa: BLE001
        raise StudioHTTPError(
            StudioError(
                code=StudioErrorCode.MCP_UNREACHABLE,
                message=f"Error calling {tool}: {exc}",
                retryable=True,
            )
        ) from exc

    text = tool_result_text(result)
    problem = parse_tool_result(text)
    if problem is not None:
        raise StudioHTTPError(problem)
    return text
