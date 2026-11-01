# 0004 — Two stores stay two stores; the reference between them becomes honest

- **Status:** proposed
- **Date:** 2026-10-31

## Context

Agentic ODI keeps two SQLite files. `~/.agentic-odi/odi.db` is the ODI repository:
an append-only event log replayed into snapshots (`sqlite_repository.py:45`,
`:58`), keyed by job, step, outcome, and evidence ids. `~/.agentic-odi/studio.db`
is the sidecar's memory: conversations, turns, turn citations, and remembered
observations (`studio/memory.py:174-205`).

The separation is deliberate and documented — `docs/architecture/README.md:49-51`
and `data-flow.md:65` both say memory is sidecar-local, never feeds the canvas, and
supplies bounded context to the next turn only. That is a good boundary: the
conversation is disposable, the research record is not.

But the two are not independent. `turn_citations.evidence_id`
(`memory.py:194-197`) stores ids of `Evidence` rows that live in the *other*
database, resolved on read through `claims.py:318`. In the same table,
`conversation_id` and `turn_id` are declared foreign keys with
`ON DELETE CASCADE` (`memory.py:184`, `:195`). The evidence reference has no
constraint, because SQLite cannot enforce one across files, and nothing else
checks it.

So the store that is meant to be disposable holds a live pointer into the store
that is meant to be the record. When evidence is deleted — or has its id rewritten
by the dedupe and promotion path landed in `319aa83` — a stored turn keeps a
citation that resolves to nothing, and a claim that was once grounded in evidence
becomes a claim that merely appears to be.

## Decision

Keep two databases and two owners. Make the cross-store reference explicit and
safe to fail:

- A citation whose evidence no longer resolves renders as **no longer available**,
  with the id kept for provenance, instead of resolving to nothing.
- The reference is a documented one, not an incidental one: `consent`-style
  wording in `docs/architecture/` — odi.db owns the record, studio.db may cite it
  and never mutates or joins on it.
- An integrity read over both files that reports dangling citations, run on demand
  (CLI) rather than in CI, to tell us whether this is theoretical.

## Consequences

**Easier**

- A stale citation becomes a visible, explainable state instead of a silent
  downgrade of provenance — which matters most in the product whose whole claim is
  evidence-grounded outcomes.
- The boundary between the stores becomes a stated rule with one direction, so the
  next feature that wants to "just join" the two has something to argue with.

**Harder**

- Read paths that show citations must handle a third state: resolved, dangling,
  never-cited.
- The integrity check has to know both schemas, and will be wrong if either store
  changes shape, so it wants a test next to each file's schema.

**Now we maintain**

- One documented statement of what a dangling citation means, and the rendering
  that follows from it.

## Alternatives considered

**One database, two areas.** Foreign keys would then be real, and `ON DELETE
CASCADE` would keep citations honest. Rejected for now: it drags conversation
history and PM memory into the repository that MCP clients read, against the
stated boundary in `README.md:49-51`, and makes a disposable thing look like a
record. Revisit if dangling citations turn out to be common rather than possible.

**Copy evidence into studio.db at citation time** (snapshot the quoted content).
Makes a turn self-describing and immune to later deletion — genuinely attractive —
but it means the chat can show evidence text that no longer exists in the record,
which is the failure the product exists to prevent. Rejected; a dangling citation
should say "dangling".

**Delete citations when evidence is deleted.** Keeps the reference clean and
silently rewrites history: the turn would lose a claim it visibly made. Rejected.

**Do nothing.** The docs would keep describing two independent stores while one
file quietly indexes the other. Rejected on the grounds that the quiet case — a
claim that looks evidenced and is not — is the one a reader cannot detect.
