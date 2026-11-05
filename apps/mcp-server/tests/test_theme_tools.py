"""ALH-65 (M2-01) — themes round-trip through the live MCP registry."""

import json
from typing import Any

import pytest
from agentic_odi_mcp_server import mcp
from fastmcp import Client


def _text(result: Any) -> str:
    return result.content[0].text


def _payload(result: Any) -> Any:
    """Tool replies are prose-wrapped JSON; take the first JSON value in the text."""
    text = _text(result)
    start = min((index for index in (text.find("{"), text.find("[")) if index != -1), default=-1)
    assert start != -1, text
    return json.loads(text[start:])


async def _seed_job_with_outcome(client: Client) -> tuple[str, str]:
    job = _payload(await client.call_tool("add_job", {"name": "Reconcile supplier invoices"}))
    outcome = _payload(
        await client.call_tool(
            "add_outcome",
            {
                "job_id": job["id"],
                "statement": (
                    "Minimize the time it takes to find a payment when reconciling invoices"
                ),
            },
        )
    )
    return str(job["id"]), str(outcome["id"])


@pytest.mark.asyncio
async def test_a_theme_tree_builds_files_and_survives_deletion() -> None:
    async with Client(mcp) as client:
        job_id, outcome_id = await _seed_job_with_outcome(client)

        parent = _payload(
            await client.call_tool("add_theme", {"name": "Cash timing", "job_id": job_id})
        )
        child = _payload(
            await client.call_tool(
                "add_theme",
                {"name": "Payment windows", "job_id": job_id, "parent_id": parent["id"]},
            )
        )

        assigned = _payload(
            await client.call_tool(
                "assign_theme", {"outcome_ids": [outcome_id], "theme_id": child["id"]}
            )
        )
        assert assigned[0]["theme_ids"] == [child["id"]]

        renamed = _payload(
            await client.call_tool(
                "rename_theme", {"theme_id": child["id"], "name": "Payment timing"}
            )
        )
        assert renamed["name"] == "Payment timing"

        deleted = _payload(await client.call_tool("delete_theme", {"theme_id": parent["id"]}))
        assert deleted["theme_id"] == parent["id"]

        listed = _payload(await client.call_tool("list_themes", {"job_id": job_id}))
        assert [theme["parent_id"] for theme in listed] == [None]
        surviving = _payload(await client.call_tool("get_outcome", {"outcome_id": outcome_id}))
        assert surviving["theme_ids"] == [child["id"]]


@pytest.mark.asyncio
async def test_a_third_level_theme_is_refused() -> None:
    async with Client(mcp) as client:
        job_id, _ = await _seed_job_with_outcome(client)
        parent = _payload(
            await client.call_tool("add_theme", {"name": "Cash timing", "job_id": job_id})
        )
        child = _payload(
            await client.call_tool(
                "add_theme",
                {"name": "Payment windows", "job_id": job_id, "parent_id": parent["id"]},
            )
        )

        refused = await client.call_tool(
            "add_theme", {"name": "Too deep", "job_id": job_id, "parent_id": child["id"]}
        )

        refusal = _payload(refused)
        assert refusal["error"]["code"] == "validation", refused
        assert refusal["message"].startswith("Error:"), refusal
        assert "two levels" in refusal["message"]


@pytest.mark.asyncio
async def test_a_theme_on_a_foreign_job_is_named_and_refused() -> None:
    async with Client(mcp) as client:
        job_id, outcome_id = await _seed_job_with_outcome(client)
        other = _payload(await client.call_tool("add_job", {"name": "Onboard a new supplier"}))
        foreign = _payload(
            await client.call_tool("add_theme", {"name": "Not yours", "job_id": other["id"]})
        )

        refused = await client.call_tool(
            "assign_theme", {"outcome_ids": [outcome_id], "theme_id": foreign["id"]}
        )

        refusal = _payload(refused)
        assert refusal["error"]["code"] == "validation", refused
        assert refusal["message"].startswith("Error:"), refusal
        assert "workspace theme" in refusal["message"]
        unchanged = _payload(await client.call_tool("get_outcome", {"outcome_id": outcome_id}))
        assert unchanged["theme_ids"] == []


# --- the rollup over the wire (ALH-163) ------------------------------------

_TOP_STATEMENT = "Minimize the time to match a remittance when closing a month"


async def _add_outcome(
    client: Client,
    job_id: str,
    statement: str,
    *,
    importance: float | None = None,
    satisfaction: float | None = None,
) -> str:
    outcome = _payload(
        await client.call_tool("add_outcome", {"job_id": job_id, "statement": statement})
    )
    if importance is not None:
        await client.call_tool(
            "update_outcome",
            {
                "outcome_id": outcome["id"],
                "importance": importance,
                "satisfaction": satisfaction,
            },
        )
    return str(outcome["id"])


async def _add_theme(client: Client, job_id: str, name: str, **args: Any) -> str:
    theme = _payload(await client.call_tool("add_theme", {"name": name, "job_id": job_id, **args}))
    return str(theme["id"])


async def _file(client: Client, outcome_id: str, theme_id: str) -> None:
    await client.call_tool("assign_theme", {"outcome_ids": [outcome_id], "theme_id": theme_id})


async def _branch(client: Client) -> dict[str, str]:
    """One parent, two children, and an outcome filed in the parent and a child alike.

    The overlap is the point. Adding each theme's own memberships gives five; the branch holds
    four outcomes, and exactly one of those four has been scored.
    """
    job = _payload(await client.call_tool("add_job", {"name": "Reconcile supplier invoices"}))
    job_id = str(job["id"])
    shared = await _add_outcome(client, job_id, _TOP_STATEMENT, importance=9, satisfaction=1)
    parent_own = await _add_outcome(
        client, job_id, "Minimize the number of invoices chased before the week closes"
    )
    leaf = await _add_outcome(
        client, job_id, "Minimize the number of exceptions a reviewer handles while closing"
    )
    quiet = await _add_outcome(
        client, job_id, "Minimize the time a feed waits to be checked when it arrives"
    )
    parent = await _add_theme(client, job_id, "Cash timing")
    windows = await _add_theme(client, job_id, "Payment windows", parent_id=parent, ordinal=1)
    cutoffs = await _add_theme(client, job_id, "Cut-off times", parent_id=parent, ordinal=2)
    unused = await _add_theme(client, job_id, "Bank feeds", ordinal=1)
    await _file(client, shared, parent)
    await _file(client, shared, windows)
    await _file(client, parent_own, parent)
    await _file(client, leaf, windows)
    await _file(client, quiet, cutoffs)
    return {
        "job_id": job_id,
        "shared": shared,
        "parent_own": parent_own,
        "leaf": leaf,
        "quiet": quiet,
        "parent": parent,
        "windows": windows,
        "cutoffs": cutoffs,
        "unused": unused,
    }


@pytest.mark.asyncio
async def test_a_parent_rollup_counts_its_branch_as_one_set() -> None:
    async with Client(mcp) as client:
        branch = await _branch(client)

        rollup = _payload(
            await client.call_tool("get_theme_rollup", {"theme_id": branch["parent"]})
        )

        assert rollup["theme_id"] == branch["parent"]
        assert rollup["name"] == "Cash timing"
        assert rollup["parent_id"] is None
        assert (rollup["outcomes"], rollup["measured"]) == (4, 1)
        assert rollup["top_opportunity"] == 17.0
        assert rollup["top_statement"] == _TOP_STATEMENT


@pytest.mark.asyncio
async def test_a_child_rollup_counts_itself_and_not_its_parent() -> None:
    async with Client(mcp) as client:
        branch = await _branch(client)

        rollup = _payload(
            await client.call_tool("get_theme_rollup", {"theme_id": branch["windows"]})
        )

        assert rollup["parent_id"] == branch["parent"]
        assert (rollup["outcomes"], rollup["measured"]) == (2, 1)
        assert rollup["top_opportunity"] == 17.0


@pytest.mark.asyncio
async def test_a_rollup_with_nothing_measured_leaves_the_top_out_rather_than_invent_it() -> None:
    """A theme holding unscored work has no opportunity to name, and says so by naming nothing."""
    async with Client(mcp) as client:
        branch = await _branch(client)

        unscored = _payload(
            await client.call_tool("get_theme_rollup", {"theme_id": branch["cutoffs"]})
        )
        assert unscored["outcomes"] == 1
        assert unscored["measured"] == 0
        assert unscored["top_opportunity"] is None, "an unscored branch must not read as a 0.0"
        assert unscored["top_statement"] is None

        empty = _payload(await client.call_tool("get_theme_rollup", {"theme_id": branch["unused"]}))
        assert (empty["outcomes"], empty["measured"]) == (0, 0)
        assert empty["top_opportunity"] is None


@pytest.mark.asyncio
async def test_list_theme_rollups_answers_the_whole_tree_in_one_read() -> None:
    async with Client(mcp) as client:
        branch = await _branch(client)

        rows = _payload(await client.call_tool("list_theme_rollups", {"job_id": branch["job_id"]}))

        assert isinstance(rows, list)
        #: Parent first, its children in order, then the next root — the order a tree is drawn in.
        assert [row["name"] for row in rows] == [
            "Cash timing",
            "Payment windows",
            "Cut-off times",
            "Bank feeds",
        ]
        assert [row["outcomes"] for row in rows] == [4, 2, 1, 0]


@pytest.mark.asyncio
async def test_get_theme_rollup_of_an_unknown_theme_is_a_not_found_envelope() -> None:
    """Missing is its own answer, distinct from the refusal a malformed call gets."""
    async with Client(mcp) as client:
        refused = await client.call_tool("get_theme_rollup", {"theme_id": "t-ghost"})

        envelope = _payload(refused)
        assert envelope["error"]["code"] == "not_found", refused
        assert envelope["message"] == "Error: theme not found: t-ghost. add a theme first"


@pytest.mark.asyncio
async def test_a_search_can_answer_for_a_whole_branch() -> None:
    async with Client(mcp) as client:
        branch = await _branch(client)

        own = _payload(await client.call_tool("search_outcomes", {"theme_ids": [branch["parent"]]}))
        assert sorted(item["id"] for item in own["items"]) == sorted(
            [branch["shared"], branch["parent_own"]]
        )

        subtree = _payload(
            await client.call_tool(
                "search_outcomes",
                {"theme_ids": [branch["parent"]], "include_children": True},
            )
        )
        assert sorted(item["id"] for item in subtree["items"]) == sorted(
            [branch["shared"], branch["parent_own"], branch["leaf"], branch["quiet"]]
        )
        assert subtree["total"] == 4
        #: The facet stays each theme's own count while the list is the branch.
        facet = subtree["facets"]["theme"]
        assert (facet[branch["parent"]], facet[branch["windows"]]) == (2, 2)
