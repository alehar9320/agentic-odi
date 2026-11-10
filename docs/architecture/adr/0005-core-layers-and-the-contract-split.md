# 0005 — Name core's four layers; do not split `contract.py` out yet

- **Status:** accepted
- **Date:** 2026-11-02

## Context

`packages/core` holds domain models, persistence, the methodology stages, and the
MCP wire contract in one namespace of 21 modules. Nothing in the repository states
a rule for that arrangement. The closest thing written down is ADR 0002's aside
about "a `packages/core` that holds domain, persistence, methodology stages, and
the MCP contract in one namespace", and that sentence was there to explain why
`import-linter` was not adopted. So a newcomer cannot say which group they are
editing or what it may import, while a tool-shape change edits a domain module and
a domain refactor can perturb the published contract, with nothing recording why
either is acceptable.

[ADR 0002](0002-package-diagram-as-contract.md) made the *between-package* graph
true and stated the remaining gap plainly: "call-level coupling inside
`packages/core` is unmeasured." `tests/test_architecture.py` builds its graph with
`grimp` over cross-distribution imports, so a `sqlite_repository` that reached
into `services` would not appear in the picture at all.

The proposal this record answers is to fix the size problem by splitting the
contract into its own distribution. Counting the consumers first changed the
shape of the question. `contract.py`'s tool names are read by three places in this
workspace — `apps/mcp-server`, `apps/cli`, and `apps/studio-api` — and by nothing
outside it. All three install `agentic-odi-core` anyway, so the import they pay for
the contract is already paid. One consumer *type*, three copies of it, no external
consumer: that is a file, not a boundary.

## Decision

Do not split. Record the trigger instead, and do the cheap step now: name the four
groups — **domain**, **persistence**, **methodology**, **contract** — in
[the architecture index](../README.md#inside-packagescore) and in `README.md`, one
rule each, and make the rule that matters machine-checkable.
`test_persistence_imports_no_methodology` parses the persistence modules' imports
and fails when one names a methodology module; `test_every_core_module_is_in_exactly_one_group`
fails when a module belongs to no group or to two, which is what keeps the table
from rotting. `__init__.py` is exempt because it re-exports all four.

**Split when a second *kind* of consumer needs the contract** — meaning one of:

1. a client SDK, published in this repository or another, that must import
   `TOOL_SPECS` rather than restate the tool list,
2. a second MCP server that is not `apps/mcp-server` — a different process, host,
   or language,
3. a generated artifact handed to someone outside the workspace (a JSON Schema or
   OpenAPI bundle built from `TOOL_SPECS` and shipped).

Anything else — "core feels big", "the file is 615 lines", another in-workspace
caller — does not meet the trigger, and a fourth Python app importing the same
module is the clearest example of why it should not.

**What the split would move,** when the trigger fires: `contract.py`, `errors.py`,
`remote.py`, `schema.py`, and `connection.py` into a new `agentic-odi-contract`
distribution that depends on nothing in the workspace, with `core` then depending on
it. `consent.py` stays: it reads the contract to decide approvals on the domain
path, which is [ADR 0003](0003-consent-on-the-domain-path.md)'s call, not wire
protocol. Naming a group here is not precommitting to that boundary line; it is
saying which files would be candidates.

## Consequences

**Easier**

- "Which group am I editing, and what may it import?" has a written answer for
  every one of the 21 modules, and a test that refuses an ungrouped new module.
- The persistence → methodology inversion — the coupling that would actually make
  a split painful — now fails a build instead of being reviewed by eye.
- The next person who proposes splitting gets a trigger to check rather than a
  debate to re-run.

**Harder**

- The group table is a fourth thing that must agree with the source. Adding a core
  module is now a module, a table row, and nothing else — the completeness test
  fails until the table says which group it is in.
- One rule enforced out of four is a partial guarantee, and the doc has to keep
  saying so rather than implying the layering is policed.
- `grimp` cannot see intra-package edges, so this rule is a hand-rolled AST walk.
  It reads import statements wherever they sit in a module, but it is a text-level
  check all the same: `importlib.import_module("agentic_odi_core.services")`, and
  a symbol pulled through `agentic_odi_core/__init__.py`, both get past it.

**Now we maintain**

- The table in `docs/architecture/README.md`, `CORE_LAYERS` in
  `tests/test_architecture.py`, and this record describe one decision. If they
  diverge, the tests lose.
- When the trigger fires, the split is a new distribution plus ADR 0002's three
  edits — declaration, `[tool.uv.sources]`, arrow — in one task.

## Alternatives considered

**Split `contract.py` out now.** Rejected: with no consumer outside the workspace,
it buys a version to publish, a lock entry, and a diagram edit, and resolves none
of the coupling that made anyone want it. Splitting early is also the one move that
cannot be undone cheaply — once a distribution is published, its name is API.

**`import-linter` with an intra-package layers contract.** The right tool for a
real multi-package graph, and ADR 0002 already rejected it for the workspace.
Rejected here as well: it would express the persistence rule cleanly but force a
third language for a single assertion, and its `layers` model assumes a total
order that four named groups inside one namespace do not have.

**Prose only, in `.agents/rules/agent_instructions.md`.** Cheapest, and it is where
the workspace-level dependency rule already lives. Rejected: an unenforced rule is
what produced the situation this record is writing down — ADR 0002 found an edge
that five source files used and no declaration existed for.

**A fifth group for signals.** Rejected on the facts — there is no `signals.py`. A
signal is a domain type that persistence stores and methodology raises, documented
in [Signals](../signals.md); inventing a group for a feature that cross-cuts four
would make the table wrong to be tidy.
