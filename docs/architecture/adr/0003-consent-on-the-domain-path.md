# 0003 — Put consent on the domain path, not the Studio's chat loop

- **Status:** proposed
- **Date:** 2026-10-31

## Context

The product's central safety claim is that the agent asks a person before it
writes. `docs/architecture/consent.md` states it, and states honestly that it is
not universally true.

Where the code stands today:

- `packages/core/.../consent.py` models the rule properly — `ConsentGate`,
  `READ_ONLY_TOOLS`/`ACTING_TOOLS`, raising `ConsentRequired`, mapped to 403 in
  `errors.py`. It is referenced outside its own module only by
  `packages/core/tests/test_consent_pause.py`. Nothing in production calls it.
- The enforcement that runs lives in `apps/studio-api`: `studio/approvals.py` and
  the pause at `studio/chat.py:779-790`. It decides whether a call is a write from
  a name-prefix heuristic plus a hand-maintained set (`chat.py:65-89`).
- The domain does not ask: `ODIService.add_job` writes straight to the repository
  (`services.py:278`). The MCP server's handlers call `service.*` directly
  (`mcp_server.py:106`, `:369`, `:453`). The CLI's own loop calls whatever tool the
  model names (`apps/cli/.../chat.py:373`).

The consequence is documented rather than hidden: `consent.md:76-79` lists
`schedule_work`, `trigger_scheduled_work`, and `cancel_scheduled_work` as
contract-classified writes the prefix check does not catch, and `:80-83` says CLI
writes do not prompt. So a client that is not the Studio — an external agent on
`AGENTIC_ODI_MCP_URL`, which the project explicitly supports and advertises — can
write without asking, and the mechanism that would classify a write correctly is
already written and unused.

## Decision

Proposed, in two steps, deliberately separable:

1. **Now.** Stop classifying writes by name. Derive the mutating-tool set from
   `TOOL_SPECS` (`contract.py`), which already knows what each tool does, so a tool
   added without a classification cannot silently default to "not a write". This
   changes no behaviour for any user; it removes a drift class.
2. **Then, on the answer to the question below.** Either consent is a domain
   invariant, in which case `ODIService` calls `ConsentGate` before a mutating
   write and every surface inherits it — the Studio supplies the approver, the CLI
   and MCP either supply one or are refused; or consent is a courtesy of the
   conversational surface, in which case `docs/architecture/consent.md` says so in
   those words and `ConsentGate` is deleted rather than left dormant.

**The question is which of those two this product is.** My recommendation is the
first: an agent that can write to a research repository without asking is not a
safer version of the same product, and the MCP surface is the one most likely to
be driven by someone else's agent.

## Consequences

**If consent becomes a domain rule — easier**

- The claim in `consent.md` becomes true for every client, and one enforcement
  point replaces three.
- `ConsentRequired` earns its 403 mapping instead of being unreachable from an MCP
  client.

**If consent becomes a domain rule — harder**

- A write needs an approver, so the CLI and raw MCP need an answer for "nobody is
  in the room": block, or an explicit `--yes`/session policy. That is a product
  decision, not an implementation detail.
- Approvals become stateful across a request boundary: `ApprovalRegistry` is
  process-local today, and an MCP call has no stream to hold a pending gate on.

**If consent stays Studio-only — easier**

- Nothing moves. The docs get shorter and more accurate.

**If consent stays Studio-only — harder**

- The safety story is a UI feature, and the README's "connect your agent" path is
  the exception to it. Every later claim about agent safety has to be qualified.

**Now we maintain (either way)**

- The mutating set derived from the contract, and a test that a new tool cannot be
  unclassified by omission.

## Alternatives considered

**Approve at the repository layer** (gate writes in `SQLiteRepository`). Rejected:
the repository cannot tell a model-initiated write from a user's own `odi jobs
add`, and it is the wrong place for an intent question.

**Gate in the MCP server only.** Would cover external agents while leaving the CLI
and the domain ungated, and puts the rule in one more surface. Rejected as a
half-measure that increases the number of places to check.

**Prompt-level "the model was told to ask".** What the system prompt does today,
alongside the real gate in the Studio. Rejected as the sole control: an
instruction is not a boundary, and this ADR is about boundaries.
