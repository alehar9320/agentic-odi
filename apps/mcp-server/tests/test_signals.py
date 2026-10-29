"""The three signal tools round-trip through the live MCP registry."""

import json

import pytest
from agentic_odi_mcp_server import mcp
from fastmcp import Client


@pytest.mark.asyncio
async def test_add_job_emits_a_signal_the_tools_can_read() -> None:
    async with Client(mcp) as client:
        await client.call_tool("add_job", {"name": "Ship it"})
        listed = json.loads((await client.call_tool("list_signals", {})).content[0].text)

    assert [signal["kind"] for signal in listed] == ["job_added"]
    assert listed[0]["subject_kind"] == "job"
    assert listed[0]["fingerprint"]


@pytest.mark.asyncio
async def test_read_and_dismiss_update_the_signal_in_place() -> None:
    async with Client(mcp) as client:
        await client.call_tool("add_job", {"name": "Ship it"})
        listed = json.loads((await client.call_tool("list_signals", {})).content[0].text)
        signal_id = listed[0]["id"]

        read_text = (
            (await client.call_tool("mark_signal_read", {"signal_id": signal_id})).content[0].text
        )
        assert read_text.startswith("Signal marked as read:")
        unread = json.loads(
            (await client.call_tool("list_signals", {"unread_only": True})).content[0].text
        )
        assert unread == []

        dismissed_text = (
            (await client.call_tool("dismiss_signal", {"signal_id": signal_id})).content[0].text
        )
        assert dismissed_text.startswith("Signal dismissed:")
        feed = json.loads((await client.call_tool("list_signals", {})).content[0].text)
        assert feed == []


@pytest.mark.asyncio
async def test_unknown_signal_ids_answer_with_error_strings() -> None:
    async with Client(mcp) as client:
        for tool in ("mark_signal_read", "dismiss_signal"):
            text = (await client.call_tool(tool, {"signal_id": "nope"})).content[0].text
            assert text == "Error: Signal with ID nope not found."
