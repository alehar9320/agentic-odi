# Consent and approvals

An agent that can write should ask first. This document records how the Studio
does that today, where the gate lives, and — honestly — what it does not cover
yet.

## What it is

A conversational turn can call tools. Read tools run immediately; tools that
change data are paused and turned into an approval card in the thread. The turn
waits for a decision (or a timeout), then either performs the call or returns a
refusal the model can read.

The pieces:

- **`ApprovalRegistry`** (`apps/studio-api/src/agentic_odi_studio_api/studio/approvals.py`)
  holds one pending request per tool call as an `asyncio` future.
- **The gate** (`studio/chat.py:59-81`, `:719-731`) decides which calls need
  approval, emits an SSE `approval` frame, and awaits the decision.
- **The frame** carries `id`, `tool_call_id`, `name`, `arguments`, `prompt`, and
  `created_at`.
- **The decision** is `POST /api/approvals/{id}` (`studio/router.py:963-980`)
  with an allow/deny choice and an optional reason.
- **The card** is the Allow / Don't allow surface in
  `apps/studio/src/assistant/parts.tsx:168-219`; the SPA sends the decision
  through `apps/studio/src/api/studioApi.ts:626-640`.

A request expires after 300 seconds (`approvals.py:25`) — long enough to read,
short enough that a forgotten tab does not hold a turn forever. All pending
requests are cancelled when the sidecar shuts down, because nothing may outlive
the process waiting on a decision.

## What needs approval

The gate is prefix-based. A tool name starting with `add_`, `create_`, `update_`,
`delete_`, `ingest_`, or `remove_`, plus `promote_evidence`, is gated
(`chat.py:59-81`). Everything else runs without asking.

That covers the write surface the chat can reach, including destructive deletes,
and deliberately excludes reads so a turn does not turn into a sequence of
prompts.

## The mandate

`get_capabilities` describes the surface from the shared contract: every tool,
its effect (`read` / `write` / `destructive`), its arguments, and its ODI stage
(`contract.py:375-387`). The same manifest is renderable as a machine-readable
document (`capability_manifest()`, `contract.py:472-490`) and is served at
`GET /api/capabilities`. The mandate is descriptive, not per-agent — one person,
one sidecar, one surface.

## Why approve at all

The alternative is a chat that can delete a job between two sentences. The
approval card is the human-in-the-loop seam: the operator sees the exact tool
and arguments before the store changes. It also gives the model a refusal it can
work with, instead of an opaque failure.

## What the alternatives were

- **Gate by `ToolEffect`.** The contract already classifies every tool, and a
  `ConsentGate` class exists (`packages/core/src/agentic_odi_core/consent.py`)
  with tests, but the chat loop does not use either; it uses name prefixes. That
  keeps the gate readable, at the cost of a new tool whose name does not match
  the prefixes slipping through.
- **No prompt, log instead.** Rejected: a log records what happened after it is
  too late to stop it.
- **Per-session blanket consent.** Not implemented; each call is a decision.

## What this does not do

- **Decisions are not persisted.** The registry is memory-only
  (`approvals.py:63-65`) and the SQLite schema has no approvals table. There is
  no audit trail of who approved what, or why; the `reason` lives only on the
  transient decision.
- **The gate is name-based, not effect-based.** `schedule_work`,
  `trigger_scheduled_work`, `cancel_scheduled_work`, `mark_signal_read`, and
  `dismiss_signal` are writes by the contract's own classification but do not
  match the prefixes, so they are ungated.
- **Not every write path goes through the chat.** CLI writes do not prompt (only
  some deletes and interactive commits do), `connectors add` has no
  confirmation, and `POST /api/connectors` is ungated. The consent model covers
  the conversational agent, not the operator's direct commands.
- **No escalation levels.** There is no notion of "ask once per session" or
  "never ask for this tool"; every gated call asks.
- **No audit export.** This is the gap
  [#82](https://github.com/alehar9320/agentic-odi/issues/82) tracks.
