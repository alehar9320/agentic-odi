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
  the pause at `studio/chat.py:779-790`. Since #483 it decides whether a call is a
  write from the shared `TOOL_SPECS` effect (`is_mutating_tool`, `chat.py:78-84`),
  which is the derivation this record's step 1 asked for.
- The domain does not ask: `ODIService.add_job` writes straight to the repository
  (`services.py:278`). The MCP server's handlers call `service.*` directly
  (`mcp_server.py:106`, `:369`, `:453`). The CLI's own loop calls whatever tool the
  model names (`apps/cli/.../chat.py:373`).

The consequence was documented rather than hidden: `consent.md` then listed
`schedule_work`, `trigger_scheduled_work`, and `cancel_scheduled_work` as
contract-classified writes the prefix check missed — a leak #483 closed by deriving
the set from `TOOL_SPECS`. What remains is the larger gap: CLI writes do not
prompt, and a client that is not the Studio — an external agent on
`AGENTIC_ODI_MCP_URL`, which the project explicitly supports and advertises — can
write without asking, and the mechanism that would classify a write correctly is
already written and unused.

A reproduction recorded on 2026-10-31 makes that second reading concrete. Against
a throwaway store, the MCP server accepts a write with no prompt and no operator
decision anywhere on the path:

```bash
AGENTIC_ODI_DB=$(mktemp -d)/probe.db uv run agentic-odi-server --port 8099
uv run agentic-odi --backend mcp --mcp-url http://127.0.0.1:8099/mcp jobs add --name probe
```

The second command returned a job id. The same write through the Studio's
`/api/chat` pauses for an approval card. So "the agent asks before it writes" is
true on one surface of three, and the two that do not ask are the two an outside
agent is most likely to reach.

## Decision

Proposed, in two steps, deliberately separable:

1. **Now.** Stop classifying writes by name. Derive the mutating-tool set from
   `TOOL_SPECS` (`contract.py`), which already knows what each tool does, so a tool
   added without a classification cannot silently default to "not a write". This
   changes no behaviour for any user; it removes a drift class. **Landed in #483**,
   which is why this record now decides only the second step.
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

### The decision this record asks for

One question, one answer, then this record moves to `accepted` with the losing
option crossed out and the reason recorded beside it.

**The question.** Is consent a domain invariant or a Studio courtesy?

**Recommendation: (A) consent is a domain invariant.** The reason is the one the
reproduction makes plain — a guarantee that holds on one surface of three is not a
guarantee, it is a property of that surface, and the two surfaces without it are
the two an outside agent reaches. Making the rule true in `ODIService` is also the
only option that leaves one place to check instead of three.

The two options and the surfaces each one covers:

| Option | What changes | Surfaces that ask before writing | Surfaces that do not |
|---|---|---|---|
| **(A) Domain invariant** | `ODIService` consults a grant before a mutating call; `ConsentRequired` travels as 403 | Studio, CLI, MCP — all three, through one door | None, once a surface is given a mandate or is refused |
| **(B) Studio courtesy** | `ConsentGate` is deleted or renamed; `consent.md` states the guarantee as a UI property | Studio sidecar only | CLI and MCP server, by design and in the docs |

**What a non-interactive surface does with no operator — the part that makes (A)
decidable.** "Deny by default, grant by an explicit environment or config
decision" is the honest answer for an unauthenticated loopback endpoint. A
surface with no person at the keyboard is refused a mutating call unless it
presents a **standing mandate** — an explicit decision in environment or config
that names the tools and the scope it covers, in the shape [#82](https://github.com/alehar9320/agentic-odi/issues/82)
§5.7 already designs. Absent a mandate, the call is refused; there is no third
state where an unauthenticated client writes silently. This is deliberately not
an identity: consent without authentication is a UX, and this record does not
pretend the mandate is one.

**What this unblocks.** The implementation slice for (A): a grant object on the
mutating service door, a standing mandate read from config for MCP and CLI,
`ConsentRequired` reachable through the envelope [#460](https://github.com/alehar9320/agentic-odi/issues/460)
added, and one test per surface. That slice is opened as its own issue, not done
here.

**This record is not `accepted` until a maintainer says so.** The recommendation
above is the agent's; the acceptance is a maintainer's one sentence, asked for in
the pull request that carries this change.

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
