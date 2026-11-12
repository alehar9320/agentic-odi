# Consent and approvals

An agent that can write should ask first. This document records how the Studio
does that today, where the gate lives, and — honestly — what it does not cover
yet.

## What it is

When a conversational turn opts in with `approvals: true`, read tools run
immediately and acting tools are paused for an approval card. The turn waits for
a decision (or a timeout), then performs the call or returns a refusal the model
can read. Clients that do not opt in keep the existing ungated behavior.

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

The gate uses the shared MCP `TOOL_SPECS` effect: writes and destructive calls
require approval, reads do not. Unknown tools are treated as acting, including
unknown external MCP tools. Local `add_connector` is also gated; `render_ui` and
`remember` retain their existing ungated presentation and memory-suggestion
flows. This classification applies only when approvals are requested and a
registry is supplied.

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

- **Gate by tool-name prefix.** Rejected: a write with a different name can
  escape the prompt. The chat uses `ToolEffect` instead; the separate
  `ConsentGate` in core is not used by the chat loop.
- **No prompt, log instead.** Rejected: a log records what happened after it is
  too late to stop it.
- **Per-session blanket consent.** Not implemented; each call is a decision.

## What this does not do

- **Decisions are not persisted.** The registry is memory-only
  (`approvals.py:63-65`) and the SQLite schema has no approvals table. There is
  no audit trail of who approved what, or why; the `reason` lives only on the
  transient decision.
- **Not a security boundary for remote clients.** Approvals are opt-in, and
  `remember` writes a suggested observation without a tool approval. This is
  not authentication or a durable authorization policy.
- **Not every write path goes through the chat.** CLI writes do not prompt (only
  some deletes and interactive commits do), `connectors add` has no
  confirmation, and `POST /api/connectors` is ungated. The consent model covers
  the conversational agent, not the operator's direct commands.
- **No escalation levels.** There is no notion of "ask once per session" or
  "never ask for this tool"; every gated call asks.
- **No audit export.** This is the gap
  [#82](https://github.com/alehar9320/agentic-odi/issues/82) tracks.
