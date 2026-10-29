"""The CLI's local backend must stay aligned with the core contract."""

from __future__ import annotations

from agentic_odi_cli.backend import _LOCAL_HANDLERS
from agentic_odi_core.contract import TOOL_NAMES

LOCAL_TOOLS = {
    "add_job",
    "get_jobs",
    "get_job",
    "update_job",
    "delete_job",
    "add_step",
    "get_job_map",
    "get_step",
    "update_step",
    "delete_step",
    "add_outcome",
    "get_outcomes",
    "get_outcome",
    "update_outcome",
    "delete_outcome",
    "add_customer_outcome",
    "get_customer_outcome",
    "list_customer_outcomes",
    "update_customer_outcome",
    "delete_customer_outcome",
    "add_evidence",
    "get_evidence",
    "list_evidence",
    "delete_evidence",
    "promote_evidence",
    "get_odi_schema",
    "compute_opportunity",
}


def test_local_handler_keys_are_contract_tools() -> None:
    assert set(_LOCAL_HANDLERS) == LOCAL_TOOLS
    assert LOCAL_TOOLS <= set(TOOL_NAMES)
