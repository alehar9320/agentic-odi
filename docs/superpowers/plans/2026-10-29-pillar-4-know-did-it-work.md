# Pillar 4 — Know: did it work (ALH-10)

## Objective

Implement the full M1 scope of the Linear pillar **ALH-10 — Pillar 4 · Know: did it work**
(`alexanderharenstam/alh-10-pillar-4-know-did-it-work`), against `alehar9320/agentic-odi`.

The pillar is **coordination-only**. Its stated outcome:

> A person can record a decision-linked expectation with a frozen baseline, compare it with
> eligible like-for-like observations, and see real changes, due work and the first missing
> link without invented numbers.

Full pillar completion also needs the M2/M3/M4 leaves (`ALH-80`, `ALH-104`, `ALH-114`). M1
completes when the M1 leaves below are done. This plan covers **M1 plus the pillar's later
horizons as separate, gated increments**.

## What the repo actually contains today (verified, not assumed)

Inspected `origin/main` at `d257cdb`:

- `packages/core` has `Job`, `Step`, `Outcome`, `CustomerOutcome`, `Evidence`. It has
  **no** `Decision`, **no** `ScoreSnapshot`, **no** `Bet`, **no** `Signal`, **no**
  `NotificationRule`, and **no** `coverage_report`.
- The event-sourced store (`events.py`, `intent_store.py`, `sqlite_repository.py`) is real and
  works: `_apply_event` replay, `InMemoryRepository`, `SQLiteRepository`, and an MCP adapter.
- The CLI (`apps/cli`) is Typer + a local/MCP backend seam (`backend._LOCAL_HANDLERS`). There is
  **no** `odi bets`, `odi digest`, or `odi status` command yet. `odi summary` exists.
- `apps/studio-api` exposes the canvas/chat/connectors API; read/dismiss/notification state does
  **not** exist server-side. `apps/studio` `CatchUpFeed.tsx` renders a `localStorage` notification
  store that only its own `+ Simulate update` button writes.
- `docs/architecture/notifications.md` exists.
- The contract test `tests/contract/test_cli_contract.py` asserts
  `set(_LOCAL_HANDLERS) == set(TOOL_NAMES)` — **every new MCP tool needs a local handler**.
- `tests/contract/test_mcp_contract.py` asserts the live FastMCP registry equals `TOOL_SPECS`.
- **`packages/core/tests/test_persistence_parity.py` does not exist** (the leaf contracts and
  this plan reference it).

Open PR **#277** (`issue-79-signals`, GitHub #79) implements a **write-emitted** signal inbox
(`SIGNAL_CREATED` events, six kinds, `list_signals`/`mark_signal_read`/`dismiss_signal`, `/api/signals`).
That is a *different* design from **E3/ALH-48**, which requires signals **derived on read** with a
stable hash id and **no signal table**. This conflict must be resolved before E3.

## Cross-pillar prerequisite gap (the blocker)

Every M1 leaf here depends on entities that live in *other* pillars and do not exist yet:

| Prereq | Issue | Status | Needed by |
|---|---|---|---|
| `Decision` | ALH-37 (C6) | Backlog, no code | E1, E4.1 |
| `ScoreSnapshot` + `outcome_delta` | ALH-29 (B6) | Backlog, no code | E1, E2, E3 |
| B3 band comparison | ALH-26 | Backlog, no code | E3, E6.1 |
| `coverage_report` | ALH-21 (A8) | Backlog, no code | E3 |
| decision CLI/API | ALH-158 (C6.2) | Backlog | E1.2 |

The leaf contracts also carry **unresolved product gates** (their own words): target
metric/units/direction and baseline provenance; snapshot comparability; signal bucket/hash/recurrence;
threshold equality/units and rule-kind mapping; spine stage definitions; date/timezone boundaries.
They say explicitly: *"Do not manufacture numeric tolerances, dates, cohorts, schemas or migration
choices during implementation."*

**Therefore the first step is not code.** It is to (a) land or approve the prerequisite interfaces,
and (b) get the product gates decided. Coding E1 before C6/B6 exist would fabricate the contracts the
leaves forbid inventing.

## Execution order

Work bottom-up; each step is one reviewable PR branched from `origin/main`.

### Phase 0 — Unblock (owned by other pillars, not this pillar)

1. **Land `Decision` (C6/ALH-37)** — `Decision{id, job_id, chosen_outcome_ids, rejected:[{outcome_id, reason}], rationale, decided_by, decided_at, confidence, superseded_at?, superseded_by?}`,
   event-sourced, supersede-not-overwrite, full persistence checklist.
2. **Land `ScoreSnapshot` (B6/ALH-29)** — append-only, one writer helper called from every
   score-mutating path, `outcome_history`/`outcome_delta` per ALH-203.
3. **Land B3 band (ALH-26)** and **A8 coverage (ALH-21)** interfaces, or record their approved
   signatures for E3 to consume.
4. **Create `packages/core/tests/test_persistence_parity.py`** (M0-13) — it is referenced everywhere
   and missing. Until it exists, "persistence parity" cannot be verified.

If these cannot be landed in this effort, stop and report — do not stub fabricated versions.

### Phase 1 — E1 · Bet model + persistence (ALH-46)

- `models.Bet{id, decision_id, outcome_id, hypothesis, baseline: float, target: float, measure_by: date, status: planned|running|measured|abandoned, measured_at?}`.
- `baseline` **stored at creation** from the outcome's score then; never recomputed.
- Status transitions validated in the model: `planned→running→measured`, `planned→abandoned`;
  `measured`/`abandoned` terminal; illegal transition refused **naming the legal successors**, no event.
- Refuse a bet without a decision; refuse missing/unknown decision/outcome, invalid ownership
  (decision/outcome must belong to the same job), blank hypothesis, non-finite target/baseline,
  malformed date — atomically, naming the field.
- Full persistence checklist in one PR: `models`, `repository` Protocol + `InMemoryRepository`,
  `sqlite_repository._apply_event` + writer, remote adapter, `schema.py`, `services.ODIService`,
  `contract.TOOL_SPECS` + `ToolName` + `get_capabilities`, CLI, studio-api, studio types.
- Tests: table-driven legal/illegal transitions; baseline provenance identical after re-score,
  replay, SQLite restart, remote round-trip; parity test.
- **Gate:** approve the canonical target metric/units/direction and baseline provenance with E2 first.

### Phase 2 — E1.2 · `odi bets add|list|show` (ALH-159)

- Typer group `bets_app`; pydantic validates at the boundary, the service validates again.
- `list` ordered by `measure_by` (deterministic same-date tiebreak), overdue marked using the
  approved clock/timezone; terminal bets not marked overdue unless policy says so.
- `show` prints the **stored** baseline, never the current score.
- Empty list: honest empty message, no sample rows.
- Add local backend handlers + `docs/cli.md` + `README.md`; golden/error fixtures.

### Phase 3 — E2 · `measure_bet` (ALH-47)

- `measure_bet(bet_id) -> {result: met|missed|no_data, looked_at: date, deltas..., snapshot_id?}`.
- Latest snapshot **at or after `measure_by`**; if none, `no_data` with the date looked — never the
  latest snapshot overall, never a zero, never an exception.
- Deltas for importance, satisfaction, opportunity against the **stored** baseline; reuse B6
  `outcome_delta` and `evaluation.compute_opportunity_score`. No p-value / significance claim.
- Measuring twice writes nothing new and does not silently transition the bet.
- Result exposes selected snapshot identity/time and baseline provenance for audit.

### Phase 4 — E3 · Derived-on-read signals (ALH-48)

- New `packages/core/src/agentic_odi_core/signals.py`.
- `Signal{id, kind: bet_due|score_moved|decision_superseded|coverage_gap, subject_id, at, summary, href}`
  derived on read from bets, snapshots, decisions, coverage.
- Stable id = hash of `(kind, subject_id, bucket)` — no derivation time, no `hash()`, no summary text.
- Empty store → `[]`. Re-derivation is idempotent (two runs, identical ids). Producer writes nothing.
- **Gate:** reconcile with PR #277 / GitHub #79 (write-emitted) — pick one model; do not ship two.
  Approve bucket width/timezone/anchor, recurrence/coalescing, `at` source for `coverage_gap`.

### Phase 5 — E3.2 · `/api/signals` + feed (ALH-162)

- `GET /api/signals` in studio-api; `CatchUpFeed.tsx` renders exactly what the API returns, no
  client-side derivation.
- Remove `+ Simulate update` from the shipped path; if kept, behind a dev flag with a visible *demo* label.
- Empty → "nothing yet" + real next step. Failed fetch distinct from successful emptiness.
- Assert the production build contains no `Simulate update` string.

### Phase 6 — E5 · Read/dismiss state (ALH-50)

- Persist `{signal_id, read_at, dismissed_at}` in `studio/memory.py` (same SQLite file, same failure
  tolerance); `POST /api/signals/{id}/read` and `/dismiss`, idempotent, return new count.
- Bell count = derived signals − dismissed − read, computed at read time (never stored).
- Re-derived same id does not resurrect a dismissed signal; unknown id → shared 404 body, no write.

### Phase 7 — E6.1 · Shared notification policy (ALH-187)

- One stored `NotificationRule{kind, threshold}` per supported kind + documented defaults; pure
  `should_notify(signal)` shared by bell and digest. Server/shared store, not `localStorage`.
- **Gate:** rule-kind mapping to the four signal kinds; category crossing vs uncertainty-band overlap;
  ±0.5 inclusive equality and units; missing-value handling. `Signal` has no typed numeric fields yet —
  decide how evaluation gets proven values without parsing summaries.

### Phase 8 — E6.2 · Apply policy across bell + digest (ALH-242)

- `SettingsPanel.tsx` reads/updates the shared rules; bell count and CLI digest use the same
  `should_notify`. Suppressed signals stay real feed data. **Gate:** whether the digest includes
  read/dismissed signals.

### Phase 9 — E4 · `odi digest` (ALH-49)

- `odi digest [--since 7d] [--job] [--out path]`, deterministic markdown, stable heading + one dated
  bullet per proven signal. No LLM, no email, no scheduler.
- `--since` grammar (`7d`, `24h`) in one shared helper; invalid/zero/negative handled; one captured
  evaluation clock; deterministic tie order.
- Empty period prints exactly `No changes in this period`. `--out` writes the same bytes and prints
  the path. Add `docs/cli.md` + `README.md`.

### Phase 10 — E4.1 · `odi status --spine` (ALH-243)

- Extend `odi status` with a read-only stage/count/next-blocker table for
  captured → scored → decided → bet → measured; real due date when present.
- Empty store prints `no job yet` and only the first blocker. Writes nothing. Byte-stable output.
- **Gate:** exact stage definitions, multi-job selection, whether `no_data`/abandoned count as
  measured, deterministic first-blocker priority. Totals must not imply one closed chain.

### Later horizons (separate, not M1)

- **M2-16 (ALH-80)** wave comparison; **M3-18 (ALH-104)** disproof; **M4-08 (ALH-114)** email digest.
  Each has its own child leaves and gates.

## Verification bar (every leaf)

```bash
uv run pytest <focused>                     # leaf-specific
uv run pytest packages/core/tests/test_persistence_parity.py   # once created
uv run ruff check . && uv run ruff format --check .
uv run mypy apps packages
npm --prefix apps/studio test -- --run
```

Plus, per leaf: happy-path, boundary, empty, failure and repeat-read/retry fixtures. A no-data
fixture must stay visibly different from met/missed/holding on every surface. Derived reads write
nothing. Same fixed store/window/clock/policy → stable results across processes.

## Docs to keep current with each change

`README.md` (new command/package), `docs/cli.md` (new flags/commands), `docs/living-studio.md`
(new surfaces), `docs/roadmap.md` (tick completed items), `docs/architecture/notifications.md`.

## Deliverables

- One branch/PR per leaf, branched from `origin/main`, each with tests and docs in the same PR.
- The pillar itself is completed by landing its leaves, not by a separate implementation PR.
- Final report back to ALH-10 with links to each leaf PR and its verification evidence.

## Immediate next actions

1. **Decide the prerequisite path** for C6/B6/B3/A8 (land here vs. separate effort) — this is the
   single blocking question.
2. **Create `test_persistence_parity.py`** (M0-13) since all leaves depend on it.
3. **Resolve the PR #277 vs. E3 signal-model conflict** before any E3 work.
4. Get the Phase-1 product gates answered (target metric/units/direction, baseline provenance).
