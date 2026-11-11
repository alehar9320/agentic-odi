# Grooming plan: six unstarted issues

**Date:** 2026-10-31  
**Role:** AI Native Steve Jobs + principal CTO  
**Goal:** Each issue gets a human-friendly value score (1–5), one valid end-user value increment, and an atomic, test-first implementation plan a dumb AI agent can execute without failure.

## The six issues, ranked by end-user value

| Rank | Issue | Title | Area | Value | Blocked by / depends on | Status note |
|------|-------|-------|------|-------|------------------------|-------------|
| 1 | #80 | Evidence must become outcomes | core | **5/5** | #83 outcome format + score rules, #84 tool manifest | Unstarted; full spec in issue body |
| 2 | #82 | The agent must ask before it acts | studio + core | **5/5** | #81 durable sessions (open, not in this batch); reconciles with #80's `approve_proposal` | Unstarted; full spec in issue body |
| 3 | #348 | SQLite is the only copy: verify, checkpoint, back up | core + infra | **5/5** | none | Unstarted; full spec in issue body |
| 4 | #94 | The local model must be real | studio + core | **4/5** | #83 (fallback must not fabricate scores) | Router already landed on `main`; spec has 2026-10-31 amendments (fix shipped code, choose Option B) |
| 5 | #310 | Give the Studio a persistent map | studio | **4/5** | #311 route-backed active state, #312 Vision panel | Rail already exists; spec has 2026-10-31 amendments (extend the rail, don't rebuild) |
| 6 | #88 | Hold the line: a coverage floor | CI | **3/5** | none | Label `claimed/GH-Impl-2` — may already be in progress by another agent; verify before touching |

## Value-score rationale (1 = nice to have, 5 = the product's reason to exist)

- **#80 = 5** — Mining evidence into scored opportunities is the ODI loop and the product's reason to exist. Without it, the Studio is a blank form.
- **#82 = 5** — The human-in-the-loop premise. Agents must not mutate data without approval; #95 (background agents) is a hazard without it.
- **#348 = 5** — Data durability. One SQLite file, no integrity gate, no backup — one corrupt file and the work is gone.
- **#94 = 4** — The "no model? no problem" brand promise. Fixing already-landed router code so tiers are honest, demote gracefully, and never fabricate scores.
- **#310 = 4** — Findability. A persistent, collapsible sidebar with accurate counts on empty repos and narrow screens.
- **#88 = 3** — Engineering hygiene. Prevents regressions but is not directly felt by users; may be claimed already.

## Sequence (respects dependencies)

1. **#88** — verify claim status first; if unclaimed, it gates quality for everything else.
2. **#94** — small, self-contained fix on shipped code; unblocks honest tiering used by #80/#82.
3. **#80** — core ODI value; needs #83/#84 (external). Sequence after #94 so the deterministic tier is honest before evidence proposals reference scores.
4. **#82** — needs #81 (external) and reconciliation with #80's `approve_proposal` into one `kind`-discriminated entity.
5. **#348** — data durability; self-contained, high trust value.
6. **#310** — depends on #311/#312 (external); sequence last, after the rail's count-parity and drawer are well-scoped.

## How to read the specs

Each spec below lives in `docs/superpowers/specs/2026-10-31-groom-<issue>-<topic>-design.md` and contains:

1. **Value score** (1–5) and the one end-user value increment.
2. **Preconditions / external dependencies** — what must land first.
3. **Atomic implementation steps** — each is one testable change; write the test first, then make it pass. Ordered so a dumb agent can't paint itself into a corner.
4. **Definition of done** — acceptance criteria + the verification command.
5. **Docs touched** — per the README maintenance guardrail, docs are updated in the same task.

## Convention

Specs are written so a fresh AI agent, given only the spec + the repository, can implement the issue without asking clarifying questions. Ambiguities are resolved in the spec; open questions are explicitly flagged for the human.
