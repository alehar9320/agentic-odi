# Integrate an external agent

Agentic ODI exposes its whole tool surface over the Model Context Protocol
(MCP), so an agent you already run — Claude, an SDK app, a script — can read
and write the ODI store without going through the Studio. This guide covers the
four things an integrator needs: how to connect, how to read, how to write
under consent, and how errors come back. It is written against the code that
ships, and every call below is executed by
[`tests/test_integration_example.py`](../tests/test_integration_example.py)
against a real server.

The runnable companion is
[`examples/agent_client/`](../examples/agent_client/): a small client you can
read in one sitting and run with:

```bash
uv run python -m examples.agent_client.client
```

## 1. Connect

The server is a [FastMCP](https://github.com/jlowin/fastmcp) server. Point a
`fastmcp.Client` at it — in-process for a test, or at the running endpoint for a
real deployment:

```python
from fastmcp import Client
from agentic_odi_mcp_server import mcp

async with Client(mcp) as client:
    tools = await client.list_tools()
    print(sorted(tool.name for tool in tools))
```

`list_tools()` is the discovery call. It returns the live registry — the same
42 tools the contract declares — so an agent can build its tool list at runtime
instead of hard-coding names.

### Read the contract before you call it

Two read-only tools describe the surface and the data, so an agent can learn
both without guessing:

- `get_capabilities_manifest` returns machine-readable JSON: every tool with its
  summary, effect, arguments, required subset, return description, and ODI
  stage.
- `get_odi_schema` returns the canonical JSON schema for every entity.

## 2. Read

Reads are the read-only tools — every name starting with `get_` or `list_`. They
never need consent and never change the store.

### Page every list

List tools take `limit` and `offset`. Walk them by page length: a page shorter
than the page size means there is no next page. Do not assume a total; the
store grows between calls.

```python
async def read_all_jobs(client, page_size=50):
    jobs, offset = [], 0
    while True:
        page = json.loads(
            (await client.call_tool("get_jobs", {"limit": page_size, "offset": offset}))
            .content[0]
            .text
        )
        jobs.extend(page)
        if len(page) < page_size:
            return jobs
        offset += page_size
```

### Read a score, and the honest empty state

`get_outcome_score` returns an outcome's sample: its `importance`,
`satisfaction`, `opportunity_score`, and `sample_size`. An outcome with no
scores returns `null` for the numbers — a sample that has not been taken, not a
measured zero. **Render "nothing yet"; never coerce a `null` to `0`.** An
opportunity score of `0` would be a claim about the customer that no one made.

### Check a statement before you save it

`evaluate_outcome` checks a desired-outcome statement against the ODI format
(direction, unit of measure, object of control, contextual clarifier) and
returns `valid`, the parsed parts, and any `issues`. Call it before a write: an
invalid statement is rejected by `add_outcome` and `accept_candidate` anyway,
and the tool tells you why in the same shape.

## 3. Write, under consent

Writes are the acting tools: everything that is not read-only. A write changes
someone's workspace, so it is a **proposal** until a person agrees. The MCP
protocol does not carry an actor — it does not say *who* is asking — so your
integration supplies that decision out of band. The product's own gate is
`agentic_odi_core.consent.ConsentGate`, and reusing it keeps your client's rule
identical to the Studio's:

```python
from agentic_odi_core.consent import ConsentGate
from agentic_odi_core.errors import ConsentRequired

gate = ConsentGate()
proposal = gate.request("add_job", {"name": "Onboard customers"})
# ... a person approves ...
gate.approve(proposal)
created = gate.execute(proposal, lambda args: run_tool(client, args))
```

The gate's guarantees, which your integration inherits:

- An acting call **does nothing** until it is approved. `execute` on a pending
  proposal raises `ConsentRequired` and the store is untouched.
- A **declined** proposal never runs.
- An approval **runs exactly once**; a second `execute` raises.
- Read-only tools do not need a gate and `request` refuses to open one for them.

The acting set is derived from the tool contract, so a tool added to the server
is treated as acting until it is deliberately classified read-only.

## 4. Errors

A tool never raises across the MCP boundary; it returns its result or an error
string beginning with `Error:`. Branch on the prefix, not on a status code:

```python
text = (await client.call_tool("get_job", {"job_id": "missing"})).content[0].text
if text.startswith("Error:"):
    ...  # e.g. "Error: Job with ID missing not found."
```

The same failures have typed exceptions inside the process
(`agentic_odi_core.errors`), each mapping to an HTTP status for the sidecar:
`ValidationError` → 400, `NotFoundError` → 404, `ConflictError` → 409,
`RateLimitError` → 429, `ConsentRequired` → 403, `StoreError` → 500,
`SerializationError` → 502. If you embed the core package directly rather than
the MCP endpoint, catch `OdiError` and use `error_status` to translate.

## The tool surface

<!-- BEGIN GENERATED TOOLS (scripts/integration_guide.py) -->

51 tools. Generated from the tool contract in `packages/core/src/agentic_odi_core/contract.py` and the server source; the effect column is the write contract, read from `TOOL_SPECS`.

| Tool | Effect | Stage | Required arguments | Purpose |
| ---- | ------ | ----- | ------------------ | ------- |
| `add_job` | `write` | 1 | `name` | Create a Job-to-be-Done. |
| `get_jobs` | `read` | 1 | — | List Jobs, one page at a time. |
| `get_job` | `read` | 1 | `job_id` | Fetch one Job by id. |
| `update_job` | `write` | 1 | `job_id` | Rename a Job or change its description. |
| `delete_job` | `destructive` | 1 | `job_id` | Delete a Job and everything under it. |
| `add_step` | `write` | 3 | `job_id`, `name`, `order` | Add a step to a Job's map. |
| `get_job_map` | `read` | 3 | `job_id` | Return a Job's ordered steps, one page at a time. |
| `get_step` | `read` | 3 | `step_id` | Fetch one step by id. |
| `update_step` | `write` | 3 | `step_id` | Rename a step or move it in the order. |
| `delete_step` | `destructive` | 3 | `step_id` | Delete a step. |
| `add_outcome` | `write` | 2 | `job_id`, `statement`, `importance`, `satisfaction` | Record a desired outcome with importance and satisfaction. |
| `get_outcomes` | `read` | 2 | `job_id` | List the desired outcomes of a Job or step, one page at a time. |
| `get_outcome` | `read` | 2 | `outcome_id` | Fetch one desired outcome by id. |
| `update_outcome` | `write` | 2 | `outcome_id` | Edit an outcome's statement or scores. |
| `delete_outcome` | `destructive` | 2 | `outcome_id` | Delete a desired outcome. |
| `add_customer_outcome` | `write` | — | `job_id`, `customer_value`, `business_value` | Record a customer outcome with customer and business value. |
| `get_customer_outcome` | `read` | — | `outcome_id` | Fetch one customer outcome by id. |
| `list_customer_outcomes` | `read` | — | — | List customer outcomes, optionally for one Job, one page at a time. |
| `update_customer_outcome` | `write` | — | `outcome_id` | Edit a customer outcome's values. |
| `delete_customer_outcome` | `destructive` | — | `outcome_id` | Delete a customer outcome. |
| `add_evidence` | `write` | — | `source_name`, `source_kind`, `name`, `content` | Attach a research record as evidence. |
| `get_evidence` | `read` | — | `evidence_id` | Fetch one evidence record by id. |
| `list_evidence` | `read` | — | — | List evidence, optionally for one Job, one page at a time. |
| `delete_evidence` | `destructive` | — | `evidence_id` | Delete an evidence record. |
| `promote_evidence` | `write` | — | `evidence_id`, `target` | Promote a record into a Job, outcome, or customer outcome. |
| `evaluate_outcome` | `write` | 2 | `statement` | Check a statement against the ODI format before saving it. |
| `get_odi_schema` | `read` | — | — | Return the canonical JSON schema for every ODI entity. |
| `compute_opportunity` | `write` | 4 | `importance`, `satisfaction` | Score an importance and satisfaction pair. |
| `get_odi_framework_guidelines` | `read` | — | — | Say which tool to use at each stage of ODI. |
| `get_capabilities` | `read` | — | — | Describe what the assistant can help with. |
| `get_capabilities_manifest` | `read` | — | — | Return the whole tool surface as machine-readable JSON. |
| `extract_candidates` | `write` | 2 | `quote_id`, `quote`, `job_id` | Propose outcomes from one quote; proposes, accepts nothing. |
| `list_candidates` | `read` | 2 | — | List proposed outcomes, optionally by quote, Job, or status, one page at a time. |
| `get_candidate` | `read` | 2 | `candidate_id` | Fetch one proposed outcome by id. |
| `accept_candidate` | `write` | 2 | `candidate_id`, `importance`, `satisfaction` | Accept a proposed outcome, creating exactly one Outcome. |
| `reject_candidate` | `write` | 2 | `candidate_id`, `reason` | Reject a proposed outcome; the reason is required and kept. |
| `merge_candidate` | `write` | 2 | `candidate_id`, `merged_into` | Fold a proposed outcome into an existing Outcome; creates none. |
| `get_outcome_score` | `read` | 4 | `outcome_id` | Read an outcome's scores as a sample; an unscored outcome reports nothing yet. |
| `get_brief` | `read` | — | `subject_id` | Render the brief for a subject; every figure carries its basis. |
| `record_decision` | `write` | — | `subject_id`, `choice`, `rationale` | Record a decision about a subject, with its rationale. |
| `track_bet` | `write` | — | `decision_id`, `statement`, `metric` | Track a bet under a decision, with the metric that would move. |
| `get_measurement` | `read` | — | `bet_id` | Read what a bet measured; an unmeasured bet reports nothing yet. |
| `list_signals` | `read` | — | — | List recorded signals, newest first, one page at a time. |
| `mark_signal_read` | `write` | — | `signal_id` | Mark a signal as read so it stops counting toward the unread badge. |
| `dismiss_signal` | `write` | — | `signal_id` | Dismiss a signal; it stays recorded but leaves the feed. |
| `get_health` | `read` | — | — | Check that the ODI store is reachable. |
| `schedule_work` | `write` | — | `name`, `schedule_expression` | Schedule agent work with a cron or one-shot expression. |
| `get_scheduled_work` | `read` | — | `work_id` | Fetch one scheduled work item by id. |
| `list_scheduled_work` | `read` | — | — | List scheduled work, optionally for one Job or status. |
| `cancel_scheduled_work` | `write` | — | `work_id` | Cancel a scheduled work item. |
| `trigger_scheduled_work` | `write` | — | `work_id` | Dispatch a scheduled work item immediately. |

<!-- END GENERATED TOOLS -->

## Versions

Two versions bound an integration. Read both before you rely on a shape.

| Surface | Value | Where it comes from |
| ------- | ----- | ------------------- |
| Package version | `0.14.0` | The workspace's `pyproject.toml` files; `scripts/check_version_parity.py` fails if they drift. |
| Store schema version | `1` | `agentic_odi_core.intent_store.CURRENT_SCHEMA_VERSION`; stamped in the store's `schema_meta` table. |
| MCP protocol version | `2026-07-28` | The `mcp` package's `LATEST_PROTOCOL_VERSION`; negotiated by the client at connect time. |

The store refuses to open a database stamped **newer** than it understands and
names the upgrade command; run `agentic-odi store` to print the version of your
own store. An integration that persists ids should re-read the schema version
after an upgrade rather than caching it.
