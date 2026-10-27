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
    "evaluate_outcome",
    "get_odi_framework_guidelines",
    "get_capabilities",
    "schedule_work",
    "get_scheduled_work",
    "list_scheduled_work",
    "cancel_scheduled_work",
    "trigger_scheduled_work",
}


def test_local_handler_keys_are_contract_tools() -> None:
    assert set(_LOCAL_HANDLERS) == LOCAL_TOOLS
    assert LOCAL_TOOLS <= set(TOOL_NAMES)


# Tools the offline backend may not serve: they describe the ODI framework or
# evaluate a statement rather than touching the store. Anything else must work
# with `--backend local`, because the CLI advertises full offline parity.
REMOTE_ONLY_TOOLS = frozenset(
    {"evaluate_outcome", "get_odi_framework_guidelines", "get_capabilities"}
)


def test_every_tool_has_a_local_handler_or_an_allowlist_entry() -> None:
    missing = set(TOOL_NAMES) - set(_LOCAL_HANDLERS)

    assert missing <= REMOTE_ONLY_TOOLS, (
        "New MCP tools need a LocalBackend handler or a REMOTE_ONLY_TOOLS entry; "
        f"missing: {sorted(missing - REMOTE_ONLY_TOOLS)}"
    )


def test_the_allowlist_only_names_real_tools() -> None:
    assert REMOTE_ONLY_TOOLS <= set(TOOL_NAMES)
