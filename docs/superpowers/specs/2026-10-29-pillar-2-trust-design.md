# Pillar 2 — Trust: A Number Means What It Says — Design

**Date:** 2026-10-29
**Status:** Approved for planning
**Linear:** [ALH-7](https://linear.app/alhase-personal/issue/ALH-7/pillar-2-trust-a-number-means-what-it-says)
**Milestone:** `M1 · The Loop Closes — 2026-11` (spans M1–M4)
**Scope:** The whole of ALH-7. This is a pillar, not one implementation request; the
plan breaks it into independently testable increments and lands them in dependency order.

---

## TL;DR

The product's central claim is that a score means something. Today it does not: a
number typed from one PM's intuition and a number computed from forty survey
responses render identically as "the opportunity". This pillar makes every score
carry its sample, its method, its band and its limitations, so a ranking can be
challenged without turning unknowns into facts.

ALH-7 is an umbrella. It coordinates **21 direct child issues** (and their
children) across four milestones. It is explicitly *not* one implementation
request. The deliverable of this design is a decomposition: what each increment
owns, what it must not duplicate, which decision blockers gate it, and the order
they land in.

## The thesis

One sentence: **nothing in the trust surface may fabricate precision.** Four
properties follow, and each increment serves at least one.

1. **A number carries its provenance.** Count and method travel with every score.
   A guess and a survey of forty stop rendering identically.
2. **A number carries its uncertainty.** A band, not a point. An estimate is
   explicitly *no band*, distinguishable from a zero-width survey interval.
3. **A ranking respects the evidence.** Measured, thin and missing evidence are
   separate bins; a thin high guess never outranks a measured need.
4. **A change is auditable.** Scores have append-only history, so "did it move?"
   is a subtraction, not a memory test.

## What already exists (ground truth, `origin/main` @ `3ec1a13`)

The pillar builds on a working spine. Verified by reading the code and running the
suite (1339 tests pass):

- `packages/core/src/agentic_odi_core/models.py` — `Outcome` with optional
  `importance`/`satisfaction` and a stored `opportunity_score`;
  `compute_opportunity_score(importance, satisfaction)`.
- `evaluation.py` — `classify_opportunity(score) -> underserved|appropriate|overserved|unscored`.
- `repository.py` — `rank_outcomes()` (highest opportunity first, unscored last),
  `sort_outcomes()`, `page()`; `Repository` protocol + `InMemoryRepository`.
- `services.py` — `ODIService` is the single write path (`add_outcome`,
  `update_outcome` recompute the score and re-validate the statement).
- `sqlite_repository.py` — append-only event log; `_apply_event` replays
  `OUTCOME_CREATED`/`OUTCOME_UPDATED`; a one-time `OUTCOME_BACKFILLED` migration.
- `contract.py` — `ToolName`, `TOOL_SPECS` (the single source of truth the MCP
  contract test enforces), `capability_manifest`, `capability_summary`.
- `apps/mcp-server` — FastMCP tools mirroring `TOOL_SPECS`.
- `apps/cli` — Typer groups (`jobs`, `steps`, `desired-outcomes`,
  `customer-outcomes`), `--json`, local/MCP backends.
- `apps/studio-api` — sidecar `AddOutcomeRequest`/`UpdateOutcomeRequest` schemas.
- `apps/studio/src/types.ts` — `Outcome` interface.

The pillar adds fields to `Outcome` and new entities alongside it; it does not
restructure the spine.

## Decomposition

Each row is a Linear issue. "Core slice" is what that issue's own PR must land;
"Adapters" is what a child issue lands. Completion of a parent requires the core
slice **and** every child. Readiness blockers are resolved *before* the affected
implementation starts — they are recorded in the issues, not invented here.

### B — Scores that mean something (M1)

| Issue | Owns | Depends on | Children |
|---|---|---|---|
| **B1** ALH-24 | `Outcome.importance_n`, `satisfaction_n`, `score_method`; validation; auditable backfill; plumbing through every layer | — | — |
| **B2** ALH-25 | `survey.py`: `parse_survey`, `aggregate`; CLI `odi survey import` | B1 | B2.2 ALH-156 |
| **B3** ALH-26 | `opportunity_interval(...)` percentile bootstrap (pure) | B2 | B3.1 ALH-178, B3.2 ALH-179 |
| **B4** ALH-27 | `rank_outcomes(by=...)`; landscape columns/partition | B3 | B4.1 ALH-180, B4.2 ALH-190 |
| **B6** ALH-29 | `ScoreSnapshot` append-only writer; note schema | B1 | B6.1 ALH-203 |
| **B2.2** ALH-156 | `--dry-run`, row-by-row report, `--match` confirmation | B2 | — |
| **B3.1** ALH-178 | Retained paired survey inputs + lineage | B2, B2.2 | — |
| **B3.2** ALH-179 | Persist bounds + provenance; invalidate stale bands | B3, B3.1 | — |
| **B4.1** ALH-180 | `classify_confidence` measured/thin/none; coverage; guidance | B1 | — |
| **B4.2** ALH-190 | CLI `odi top` over the shared ranking | B4, B4.1, B3.2 | — |
| **B6.1** ALH-203 | `outcome_history`, `outcome_delta`, CLI `--why`, detail note | B6 | — |

### M2 — Honest research at scale

| Issue | Owns | Depends on | Children |
|---|---|---|---|
| **M2-07** ALH-71 | `Alternative`, `AlternativeLink`; `has_existing_solution` | — | M2-07.2 ALH-166 |
| **M2-07.2** ALH-166 | Outcome-detail alternatives row; landscape *only workaround* facet; brief line | M2-07 | — |
| **M2-08** ALH-72 | `SuccessCriterion`; `criteria_gaps` | M2-07 | M2-08.1 ALH-204 |
| **M2-13** ALH-77 | `weight` column, `aggregate_weighted` (Kish `effective_n`) | M2-05 | M2-13.1 ALH-213, M2-13.2 ALH-215 |
| **M2-14** ALH-78 | `MIN_MEANINGFUL_N=20`, `n_advisory` | B1, B4.1 | — |
| **M2-15** ALH-79 | `segment_labels`, `aggregate_by_segment`, `segment_score_matrix` | M2-05, B2, B3.1, M2-13, M2-14 | M2-15.1 ALH-221 |
| **M2-17** ALH-81 | Landscape by job-map stage (composes coverage/ranking) | B4 | — |
| **M2-19** ALH-83 | Blind scoring: trusted-viewer visibility/submission | security gate | M2-19.1 ALH-228, M2-19.2 ALH-263 |
| **M2-20** ALH-84 | Inter-rater agreement report (descriptive only) | B1 | — |

### M3 / M4 — Explain, cite, attribute

| Issue | Owns | Depends on | Children |
|---|---|---|---|
| **M3-05** ALH-91 | Read-only arithmetic/provenance explanation | B1, B3 | — |
| **M3-07** ALH-93 | Citation grammar/resolution/audit | — | M3-07.1 ALH-234 |
| **M3-08** ALH-94 | Shared report/check status + four initial checks | — | M3-08.1 ALH-244, M3-08.2 ALH-248 |
| **M3-03.2** ALH-168 | Review/accept/export the instrument | M3-03 ALH-89 | M3-03.3 ALH-255 |
| **M4-05** ALH-111 | Explicit actor/event convention; score/decision pilot | — | M4-05.1 ALH-251, M4-05.2 ALH-254 |

## Decision blockers (do not invent defaults)

These are recorded in their owning issues and must be resolved and documented
before the affected implementation starts. The plan marks each gated task.

- **Import policy** (B2): p10/p90 quantile convention; duplicate respondent/outcome
  handling; missing-dimension eligibility; repeated-import replace/append.
- **Bootstrap convention** (B3): confidence level; percentile extraction/interpolation;
  singleton/empty handling; reproducibility/runtime contract; whether a percentile
  interval may exclude the plug-in midpoint.
- **Confidence table** (B4.1): unknown/unequal counts, estimates, one-response
  surveys; placement of missing/weighted bands.
- **Delta semantics** (B6.1): baseline selection, missing-dimension behavior,
  definition of `direction`.
- **Blind-scoring authorization** (M2-19): trusted-viewer identity and toggle
  authorization. An actor name is not authentication.
- **Provenance grammar** (M2-08, M3-07, M3-08): source provenance for direct
  customer criteria; citation marker/claim-span grammar; hole severity.
- **Instrument/export identity** (M3-03.2): stale-reference/acceptance policy;
  concrete export/vendor response schemas.

## Cross-cutting contracts every increment must honor

Copied from the repository's own guardrails; each is enforced by a test.

1. **Persistence checklist.** A new entity or field touches every link: `models.py`,
   `repository.py` (Protocol + `InMemoryRepository`), `sqlite_repository._apply_event`,
   `remote.py`/`schema.py`, `services.py`, `contract.TOOL_SPECS`, `mcp_server.py`,
   CLI, studio-api schemas, and `apps/studio/src/types.ts`. A missed link must fail a
   test, not diverge silently on replay.
2. **Contract synchronization.** `contract.py`, `mcp_server.py` and the
   `get_capabilities` string move together; `tests/contract/test_mcp_contract.py`
   enforces the surface.
3. **No fabricated data.** Every surface can say "nothing yet". A missing score,
   sample or band is *unknown*, never `0`, `1` or a plausible default.
4. **AI output is a proposal; a human accepts it.**
5. **Docs in the same change.** `README.md` for a new command/package, `docs/cli.md`
   for a flag, `docs/living-studio.md` for a surface, `docs/roadmap.md` ticked.
6. **Determinism.** Bands and bootstrap are reproducible for a given seed and input
   across runs and processes.

## Integration contract (pillar-level acceptance)

Restated from ALH-7 and made testable:

- One explicit fixture can be imported with per-outcome counts, persisted and
  replayed, ranked without mixing absent scores into zeroes, explained with
  recorded arithmetic/method, and shown with caveats.
- An invalid import leaves prior state unchanged.
- A score edit invalidates stale bands and weighting metadata.
- A blind-pending viewer cannot recover restricted raw or derived scores through
  an alternate read path.
- Criterion/inventory/gap/citation states stay consistent across owning services
  and adapters.
- Advanced methods stay blocked or unavailable until their exact contracts are
  approved.

## Non-goals

- No new statistics dependency; the standard library (`random`, `statistics`) is enough.
- No weighted intervals or weighted bootstrap until separately specified.
- No significance/p-value claims; descriptive overlap and spread only.
- No authentication system in this pillar; blind-scoring's security gate is a
  prerequisite, referenced not implemented here.
- No second ranking algorithm, no second aggregator, no second importer.

## Verification (pillar-wide)

```bash
uv run pytest
uv run ruff check . && uv run ruff format --check .
uv run mypy apps packages
npm --prefix apps/studio test -- --run
```

Each increment additionally names a focused selector in its own issue.

## Why this order

B1 first: every other increment reads the count/method fields it adds, and it has
no prerequisite. B2 next: it produces the responses B3 bootstraps and B4 ranks.
B4.1's confidence table is independent of the statistics and can land beside B2/B3.
B6 is independent after B1. The M2 increments follow once study/wave context
(ALH-69) and theme context (ALH-65) exist; the M3/M4 increments are independent
slices that reuse B1's fields. Blind scoring (M2-19) is gated on a security
decision and must not be claimed complete by an actor-name stand-in.
