import json

import pytest
from agentic_odi_mcp_server import mcp
from fastmcp import Client


async def _new_job(client) -> str:
    res = await client.call_tool("add_job", {"name": "J"})
    return json.loads(res.content[0].text.split(": ", 1)[1])["id"]  # type: ignore[index]


@pytest.mark.asyncio
async def test_step_and_outcome_get_update_delete():
    async with Client(mcp) as client:
        job_id = await _new_job(client)
        step = await client.call_tool("add_step", {"job_id": job_id, "name": "S", "order": 1})
        step_id = json.loads(step.content[0].text.split(": ", 1)[1])["id"]  # type: ignore[index]

        got = await client.call_tool("get_step", {"step_id": step_id})
        assert step_id in got.content[0].text  # type: ignore[index]

        upd = await client.call_tool("update_step", {"step_id": step_id, "name": "S2"})
        assert "updated successfully" in upd.content[0].text  # type: ignore[index]

        out = await client.call_tool(
            "add_outcome",
            {
                "job_id": job_id,
                "statement": "Minimize the time to ship a release when the build is green",
                "importance": 8,
                "satisfaction": 4,
            },
        )
        outcome_id = json.loads(out.content[0].text.split(": ", 1)[1])["id"]  # type: ignore[index]

        upd_o = await client.call_tool(
            "update_outcome", {"outcome_id": outcome_id, "importance": 9}
        )
        assert "updated successfully" in upd_o.content[0].text  # type: ignore[index]

        dele = await client.call_tool("delete_outcome", {"outcome_id": outcome_id})
        assert "deleted successfully" in dele.content[0].text  # type: ignore[index]

        assert (
            "deleted successfully"
            in (await client.call_tool("delete_step", {"step_id": step_id})).content[0].text
        )  # type: ignore[index]
        assert (
            "deleted successfully"
            in (await client.call_tool("delete_job", {"job_id": job_id})).content[0].text
        )  # type: ignore[index]


@pytest.mark.asyncio
async def test_update_customer_outcome_replaces_value_metrics():
    async with Client(mcp) as client:
        job_id = await _new_job(client)
        cv = {
            "direction": "minimize",
            "unit_of_measure": "time",
            "object_of_control": "x",
            "statement": "Min x",
            "importance": 5,
            "satisfaction": 5,
            "value_metrics": [
                {
                    "name": "m",
                    "direction": "minimize",
                    "unit_of_measure": "s",
                    "importance": 6,
                    "satisfaction": 2,
                }
            ],
        }
        bv = {"category": "cost_reduction", "statement": "Save"}
        created = await client.call_tool(
            "add_customer_outcome",
            {"job_id": job_id, "customer_value": cv, "business_value": bv},
        )
        oid = json.loads(created.content[0].text.split(": ", 1)[1])["id"]  # type: ignore[index]
        upd = await client.call_tool(
            "update_customer_outcome",
            {
                "outcome_id": oid,
                "value_metrics": [
                    {
                        "name": "m2",
                        "direction": "maximize",
                        "unit_of_measure": "s",
                        "importance": 9,
                        "satisfaction": 3,
                    }
                ],
            },
        )
        assert '"name":"m2"' in upd.content[0].text  # type: ignore[index]


@pytest.mark.asyncio
async def test_update_outcome_out_of_range_returns_error_string():
    async with Client(mcp) as client:
        job_id = await _new_job(client)
        out = await client.call_tool(
            "add_outcome",
            {
                "job_id": job_id,
                "statement": "Minimize the time to ship a release when the build is green",
                "importance": 8,
                "satisfaction": 4,
            },
        )
        outcome_id = json.loads(out.content[0].text.split(": ", 1)[1])["id"]  # type: ignore[index]

        res = await client.call_tool("update_outcome", {"outcome_id": outcome_id, "importance": 99})
        text = res.content[0].text  # type: ignore[index]
        assert "between 1.0 and 10.0" in text


@pytest.mark.asyncio
async def test_evaluate_outcome_reports_a_missing_job_as_an_error_string():
    async with Client(mcp) as client:
        res = await client.call_tool(
            "evaluate_outcome",
            {
                "statement": "Minimize the time to onboard a customer when they sign up",
                "job_id": "missing",
            },
        )

    text = res.content[0].text  # type: ignore[index]
    assert text == "Job not found: missing"
    assert "{" not in text


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("statement", "expected_valid"),
    [
        ("Minimize the time to onboard a customer when they sign up", True),
        ("Make it better", False),
    ],
)
async def test_evaluate_outcome_round_trips_as_json(statement: str, expected_valid: bool):
    async with Client(mcp) as client:
        res = await client.call_tool("evaluate_outcome", {"statement": statement})

    payload = json.loads(res.content[0].text)  # type: ignore[index]
    assert payload["valid"] is expected_valid
    assert isinstance(payload["issues"], list)
    assert all(isinstance(issue, str) for issue in payload["issues"])
    assert (payload["issues"] == []) is expected_valid
