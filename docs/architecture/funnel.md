# The onboarding funnel

A first session either carries a person to a scored outcome or it does not, and
that is a fact you can check rather than a feeling. The funnel counts five
moments of that path on the machine they happen on. It is a measurement, not a
notification: nothing here is news, nothing is shown in the bell, and nothing
leaves the machine.

`packages/core/src/agentic_odi_core/funnel.py` is the whole implementation; the
operational surface is `odi stats` and two sidecar endpoints, listed below.

## The five names

The vocabulary is exactly five, and it is a tuple in the source
(`FUNNEL_NAMES`) rather than a convention:

| Name | Recorded when | Emitted by |
|---|---|---|
| `launch` | the sidecar's lifespan starts — one app session, one launch | `app.py` |
| `first_message` | a chat turn reached an ending (completed, partial, or rounds-exhausted) | `studio/chat.py` |
| `first_outcome` | the workspace wrote its first outcome | `services.py::_count_outcome_milestones` |
| `first_score` | an outcome carried both importance and satisfaction for the first time | the same method |
| `return_session` | a launch in a workspace whose log already had an earlier launch | `funnel.py::record_launch` |

A milestone is **first-ever-per-workspace**, so `record_milestone` returns early
when the name is already in that workspace's visible window. That is what lets
`add_outcome` and `update_outcome` both offer the milestone without a flag
remembering which one was first, and why five hundred outcomes produce one
`first_outcome`.

Failed turns record nothing: the person did not get an answer. A partial or
rounds-exhausted turn does — they got something.

`first_score` requires **both** scores. An outcome with one number is not yet a
ranked opportunity, and the counter must not claim it is.

## Why counters ride the event log

The store is already append-only. `SQLiteRepository._apply_event` is an if/elif
over the domain event types with no `else`, so a `FUNNEL_EVENT` replays as
nothing: the counters cannot change what a repository rebuild does, and there is
no second table, no second file, and no migration.

Every funnel event carries `{"name", "at", "session_id"}` and is written with the
workspace and device scope it belongs to, so a count is per workspace and a
conversion is per workspace, never a global blend.

## Identity

Each process draws one session id with `start_session()` at lifespan start, a
fresh `uuid4().hex`. It is deliberately **not** the device id: the device id is
stable per install and answers "which machine", the session id answers "which
time you opened it", and no funnel event borrows the device id for the second
question. `return_session` is therefore a real observation — a launch whose
workspace already saw an earlier launch — and not a device lookalike.

## The reset

`reset()` appends a `FUNNEL_RESET` marker. It is a **position in the log, not a
sixth counter**: the events it supersedes stay, and the visible window for the
five names starts after the newest marker. Deleting history was the alternative
and it is wrong twice over — `IntentStore.clear()` wipes the domain records too,
and a measurement you cannot re-check is not a measurement.

Because a reset erases a claim, the asking belongs to the caller: the CLI confirms
first unless `--yes` is passed, and the endpoint's docstring says so rather than
trusting a client.

## Honesty rules the module keeps

- **No network.** The module imports nothing that can reach a wire; a test reads
  its own source and fails on `httpx`, `requests`, or `urllib`.
- **A measurement never fails the thing it measures.** Every write is wrapped: a
  store that raises is logged with `exc_info` and the user's write still succeeds.
  Reading is wrapped the same way and answers with an empty view.
- **An absent store records nothing.** `target_for()` reads `.store` off a
  repository (or off a service's `repo`), so an `InMemoryRepository` — which has
  no event log — yields `None` and every entry point becomes a no-op rather than
  an error.
- **Nothing is invented.** `stats()` always names all five counters; one that has
  not happened reports a zero count and no timestamps rather than an implied
  history. `conversion` is `None` when there was nothing to convert from, which is
  a different fact from `0.0`.
- **A name outside the vocabulary is refused**, so a typo fails loudly at the call
  site instead of silently adding a sixth row.

## Surfaces

- **CLI:** `odi stats`, `--json` for the same data as `events` + `conversions`,
  `--reset` (confirming) and `--yes`.
- **Studio API:** `GET /api/stats`, `POST /api/stats/reset`.
- **MCP:** nothing. This is a local count, not a data tool, and adding it to the
  contract would change the pinned tool surface for no caller's benefit.

`odi stats` opens the local store directly. With `--backend mcp` it exits 1 and
says why: that backend has no local event log to count.

## What this does not do

- It gives the Studio no screen. The issue asked for an endpoint and a CLI
  reading; a chart would invite a claim the five counters cannot support.
- It does not identify a person, a team, or a machine across launches.
- It does not record *how far* — no depths, no funnel steps beyond the five, no
  per-session journey.
- It does not feed the assistant. Focus context (`#425`) is what the model is
  told about; this is what the operator can check about onboarding.

## What the alternatives were

- **A `funnel` table.** Rejected: it needs its own persistence rules and drifts
  from the log that already records the moments.
- **Deriving counts from the domain snapshots at read time.** Rejected: a snapshot
  cannot show that a turn *reached an ending*, or that a launch happened, and both
  are the point of the first two names.
- **Counting in `observability.log_turn`.** Rejected: that is a stdout log of
  agent turns — not durable, not per-workspace, and it has no idea about outcomes.
