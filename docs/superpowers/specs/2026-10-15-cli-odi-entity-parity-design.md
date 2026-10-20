# CLI ODI Entity Parity & Shared Store — Design

Date: 2026-10-15
Status: Draft (design); builder check + implementation plan pending

## Intent and why

A Product Manager (or an AI agent acting for them) should be able to run the
**entire** Outcome-Driven Innovation loop from the `agentic-odi` CLI: capture
Jobs, break them into Job-Map Steps, record Desired Outcomes with importance
and satisfaction, compute Opportunity Scores, and link outcomes to business
value via Customer Outcomes. Today the CLI only exposes Customer Outcomes, and
it writes to the MCP server's **in-memory** repository, so nothing survives a
restart and Jobs/Steps/Desired Outcomes are unreachable from the terminal at
all.

The objective is to help the PM **think in outcomes, not solutions**. The tool
must make the framework's core concept — the desired outcome — the obvious
center of gravity, and it must accumulate the PM's and the agent's thinking in
one durable place.

Two entry paths must converge on the same data:

- the PM typing at the terminal (CLI, `local` backend), and
- the AI agent calling tools over MCP (`mcp` server).

## Goals

- CLI input and output (create, list, get, update, delete) for **every** ODI
  entity the domain models: `Job`, `Step`, `Outcome` (desired outcome), and
  `CustomerOutcome` (including nested `value_metrics`).
- **Full parity** between the CLI and the MCP tool surface: anything a PM can
  do by hand, the agent can do over MCP, and vice versa.
- **One persistent store** shared by the CLI and the MCP server, so data
  survives restarts and both paths see each other's writes.
- Vocabulary a PM already holds: the word *outcome* means the framework's
  desired outcome, with no second competing meaning.

## Non-goals

- Replacing or redesigning the Streamlit "Living Studio" GUI.
- Changing the ODI domain model itself (fields, scoring formula, enums).
- The bundled-binary distribution and self-update work (see the separate
  `2026-10-15-cli-bundled-distribution-design.md`); this design must not
  conflict with it but does not implement it.
- Multi-user auth, remote/hosted storage, or sync beyond a single local
  SQLite file.

## Anti-goals (would make this a failure even if it "works")

- A CLI that reports success while the agent (or a second terminal) can't see
  the data, or loses it on restart.
- Two commands whose names both suggest "outcome", forcing the user to
  remember an internal distinction.
- Breaking the live GUI/agent path silently.
- A test suite that writes to the user's real `~/.agentic-odi/odi.db`.

## Constraints

- Python 3.10+, `uv` workspace with six packages: `core`, `mcp_server`,
  `local_server`, `client`, `cli`, `connectors`.
- `core` already models `Job`, `Step`, `Outcome`, `CustomerOutcome`,
  `CustomerValue`, `ValueMetric`, `BusinessValue` and computes the Opportunity
  Score. `SQLiteRepository` already persists Job/Step/Outcome/CustomerOutcome
  using an append-only `IntentStore` (SQLite, WAL).
- The CLI is a Typer app; each entity lives in its own module and is mounted
  in `cli/cli.py`.
- Cross-process sharing must work while the long-running MCP server is up and
  a short-lived CLI process writes concurrently (SQLite WAL allows this).
- CI runs `ruff check`, `ruff format --check`, per-project `mypy`, per-project
  `pytest`, and `bandit`.

## The how (decided with the human partner)

### Vocabulary / command surface

Chosen per the "one obvious meaning per word" directive — the framework's
central entity gets the plain word:

| Concept | Model | CLI group |
|---|---|---|
| Job | `Job` | `jobs` |
| Job-Map Step | `Step` | `steps` |
| Desired Outcome | `Outcome` | `outcomes` |
| Customer Outcome | `CustomerOutcome` | `customer-outcomes` |
| Opportunity Score | `compute_opportunity_score` | top-level `score` |

The existing `outcomes` group (today's Customer Outcome) is **renamed** to
`customer-outcomes`, and `outcomes` is reassigned to the desired-outcome
entity. This is a breaking change; the README and tests are updated in the
same change. No ambiguous alias is provided.

Every group gets full CRUD: `add`, `list`, `get <id>`, `update <id>`,
`delete <id> [-y/--yes]`.

### value_metrics

`ValueMetric` is nested in `CustomerValue` (inside `CustomerOutcome`); it is
not a top-level entity and has no repository identity. It is exposed on
`customer-outcomes`:

- input: a repeatable `--value-metric '<json>'` option, each a JSON object with
  `name`, `direction`, `unit_of_measure`, `importance`, `satisfaction`.
- output: nested under `customer_value.value_metrics`, each with its computed
  `opportunity_score`.

This mirrors how MCP already accepts `customer_value` as a dict.

### Shared persistent store (decided)

- Both the MCP server and the CLI `local` backend use `SQLiteRepository`
  against the same path: `AGENTIC_ODI_DB`, defaulting to
  `~/.agentic-odi/odi.db`.
- The MCP server currently hardcodes `InMemoryRepository()`. It will instead
  select its repository at startup via a `build_repository()` factory in
  `core`: SQLite by default, with an explicit in-memory option
  (e.g. `AGENTIC_ODI_DB=:memory:`) used by tests.
- Because `SQLiteRepository` caches a materialized snapshot at construction and
  never re-reads the file, a long-running server would miss writes made by a
  short-lived CLI run. `SQLiteRepository` will become **read-through**: it
  tracks the last applied event id and applies newly appended events before
  reads, so concurrent processes converge without a restart. Event application
  is refactored into a single `_apply_event` used by both initial load and
  incremental sync.

### CLI backend selection (decided)

- A global `--backend local|mcp` option plus the existing
  `AGENTIC_ODI_BACKEND` env var, defaulting to `local` (matching the bundled
  distribution design). `--db PATH` overrides the store path.
- All entity commands route through `backend.get_backend(...)`. The `outcomes`
  commands currently hardcode `mcp` and will be corrected.
- `LocalBackend.call` implements every tool name; `MCPBackend.call` already
  passes through to the server.

### Full parity (decided)

The MCP server gains tools it lacks today so the agent matches the CLI:
`get_step`, `get_outcome`, and `update`/`delete` for Job, Step, and Outcome.
`update_customer_outcome` gains the ability to replace `value_metrics`.

## Verification / acceptance

The explicit "successfully stored data types" criterion is tested by a
round-trip: through `LocalBackend`, create each entity type (including nested
`value_metrics`), then open a **fresh** `SQLiteRepository` on the same path and
assert every field — including computed `opportunity_score` values — survives.

Additional tests:

- CLI input and output for each group (mirroring `cli/tests/test_outcomes_cli.py`).
- Backend routing: default `local`, and `--backend mcp` still reaches the
  MCP tool path.
- Core service/repository CRUD for Job/Step/Outcome.
- MCP tool parity for the new tools.
- MCP test suite isolated from the real DB via the in-memory store option.

Quality gates: `uv run ruff check .`, `uv run ruff format --check .`,
per-project `uv run --directory <pkg> mypy .`, per-project
`uv run --directory <pkg> pytest`, and
`uv run bandit -c pyproject.toml -r core/src mcp_server/src ...`.

## Resolved during builder check (builder's calls unless marked)

These were open after the first draft; a fresh builder review listed the
questions a planner would still have. The following are settled here.

- **Opportunity score on `Outcome` update.** `opportunity_score` is a stored
  field. `update_outcome` recomputes it whenever `importance` and
  `satisfaction` are both present after the merge; if either is absent, the
  score is `None`. This mirrors `add_outcome` exactly.
- **Repository thread/process safety.** The read-through `SQLiteRepository`
  guards `_sync()` and all mutations with a re-entrant lock and opens its
  `IntentStore` connection with `check_same_thread=False`; WAL gives
  cross-process visibility. Every read syncs first under the lock.
- **`--db` vs backend.** `--db PATH` (and `AGENTIC_ODI_DB`) selects the store
  for the `local` backend only. With `--backend mcp` the **server** owns the
  store; a supplied `--db` is ignored with a warning. "Shared store" means the
  CLI's local process and the server resolve the same path from
  `AGENTIC_ODI_DB`/default, not that the CLI pushes a path to the server.
- **List/get surface (exact).**
  - `jobs list` → `get_jobs`; `jobs get <id>` → `get_job`.
  - `steps add` → `add_step`; `steps list --job-id` → `get_job_map`;
    `steps get <id>` → **new** `get_step`; `steps update|delete` → **new**
    tools.
  - `outcomes add` → `add_outcome`; `outcomes list --job-id [--step-id]` →
    `get_outcomes`; `outcomes get <id>` → **new** `get_outcome`;
    `outcomes update|delete` → **new** tools.
  - `customer-outcomes` keeps today's shape (`list` with optional job filter).
  - No job-optional `list_steps`/`list_outcomes` tools are added; Step and
    Desired Outcome are job-scoped.
- **Update mutability.** Updates follow the existing `is not None` sentinel
  convention: only explicitly provided fields change, and a field is never
  cleared by passing null. `job_id` is immutable after creation; `step_id`
  may be set but not cleared to null.
- **`score` command.** Top-level `score <importance> <satisfaction>` only
  (the old `outcomes score` is removed in the rename).
- **Test isolation for the MCP server.** `conftest.py` sets the in-memory
  store option before importing `mcp_server`, so the suite never touches the
  real `~/.agentic-odi/odi.db`.

## Decided by the human partner

- **Referential integrity: cascade delete + validate FKs.** Deleting a Job
  removes its Steps, Desired Outcomes, and Customer Outcomes (recursive, with
  confirmation or `--yes`). `add_step`, `add_outcome`, and
  `add_customer_outcome` reject an unknown `job_id`/`step_id` with a clear
  error. Repository delete events must encode the cascade so replay is
  deterministic.

## Left to the builder

- Exact `--value-metric` parsing/validation and error messages.
- Exact shape of the new repository methods and event names
  (`*_UPDATED`, `*_DELETED`).
- Whether the CLI `local` and `mcp` backends share one code path for output
  formatting.
- Whether the GUI/agent rename needs a deprecation window (decision: no
  alias — one word, one meaning).
