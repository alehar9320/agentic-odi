# Pillar 3 — Decide: this, not that, and here is why — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a person defend a choice with sourced measurements — compare alternatives, record
the decision with its rejected options, derive and render a roadmap, and later review it — without
inventing a number, a value, or an approval.

**Architecture:** One deterministic factual spine in `packages/core`
(`brief.py` → `roadmap.py`) feeds thin, closed-catalog surfaces. Persistence is event-sourced:
new entities append events to the existing `IntentStore` and are replayed by `SQLiteRepository`.
Every user-facing surface (MCP tool, CLI command, Studio API route, Studio card) is a thin adapter
over one shared `ODIService` call. Optional LLM narration is a separate, labelled layer that never
touches the factual default.

**Tech Stack:** Python 3.10+, pydantic, `fastmcp`, FastAPI sidecar, Typer CLI, React + TypeScript +
Vite Studio, pytest + pytest-asyncio (strict), ruff, mypy.

**Spec:** Linear epic [ALH-8](https://linear.app/alhase-personal/issue/ALH-8/pillar-3-decide-this-not-that-and-here-is-why)
and its 33 active child increments. Each increment's own description is the authoritative spec for
that increment; this plan sequences them and pins the shared contracts.

## Global Constraints

- Branch from `origin/main` (this plan runs on `alexanderharenstam/alh-8-pillar-3-decide-this-not-that-and-here-is-why`).
- **No fabricated data.** Every numeral in output must exist in the input. A missing measurement
  renders `not measured` / an omission with a one-line reason — never `0`, never `N/A`, never an
  invented placeholder.
- **Deterministic.** Same input + explicit clock ⇒ identical bytes. Renderers are pure functions of
  their inputs: no repository access, no LLM, no fetching, no writes.
- **AI output is a proposal; a human accepts it.** Generated critique or narration is never persisted
  or applied without an explicit human acceptance step.
- **New entity ⇒ full persistence checklist in one PR:** `models.py`, `repository.py` Protocol +
  in-memory, `sqlite_repository._apply_event`, `remote.py`, `schema.py`, `services.py`,
  `contract.py` (`ToolName`/`TOOL_SPECS`), MCP tool, CLI, studio-api, Studio `types.ts`.
  Pure renderers and thin adapters do **not** inherit persistence.
- **Contract sync is mandatory:** any MCP tool change updates `contract.py` and the
  `get_capabilities` summary in the same commit; `tests/contract/test_mcp_contract.py` enforces it.
- **Docs land in the same PR:** `README.md` (new command/package), `docs/cli.md` (new flag/command),
  `docs/living-studio.md` (new surface), `docs/roadmap.md` (tick completed items),
  `docs/architecture/` (package-graph or data-flow change).
- **Errors:** reuse the shared hierarchy in `errors.py` and the one Studio error body
  (`apps/studio-api/.../studio/errors.py`). No raw traceback to a user.
- **Run:** `uv run pytest`, `uv run ruff check . && uv run ruff format --check .`,
  `uv run mypy apps packages`, `npm --prefix apps/studio test -- --run`.
- Coverage floor is 89% (`pyproject.toml`); every increment adds tests.

## Readiness gates — do not invent missing contracts

ALH-8 is explicit that the following choices are **unresolved blockers**, documented per increment.
Each must be pinned in a fixture and recorded in the increment's PR **before** that increment's code
lands. Do not silently pick a default.

| Blocker | Owning increment | Choice to pin |
|---|---|---|
| Input fixture/schema for the brief; selection & tie-break of the "three most underserved"; which input supplies the decision-consideration text | ALH-32 | Recorded in `test_brief.py` fixture + a `README`/plan note |
| `What we would build` picks "lowest score" vs "highest-underserved" | ALH-157 | Product confirms direction + tie-break; record, don't infer |
| Canonical shape of `superseded_at`/`superseded_by`; actor/timestamp provenance; latest/history tie-break; validation of empty/duplicate/overlapping ids | ALH-37 | Pinned in `Decision` model + parity fixture |
| `decided-but-unmoved` definition; baseline/target provenance; supersession & repeated outcomes; `horizon=4` meaning; review metric direction | ALH-38 / ALH-39 | Shared derivation fixture + explicit `today` clock |
| Value representation (Outcome field vs `BusinessValue`), currency/time/unit, classification, mixed-unit ordering | ALH-64 | Recorded in W1's own increment |
| Lowest-score build recommendation vs opportunity ranking; new-market coverage vs checked absence; disruptive cost-to-serve source | ALH-157 / ALH-64 | Recorded per increment |
| Candidate naming/deciles/fingerprints, acceptance retries, cross-job minimum membership | ALH-40/41/161/103 | Recorded in D-increment fixtures |
| Narrative token/source association and bounded retry; accepted-review payload/idempotency | ALH-90/169, ALH-205 | Recorded in M3 increments |
| Collaboration actor/transition/retry/atomicity, approval revision path, full role matrix, local fallback, event-log total order | ALH-107…110, ALH-117/175 | Recorded in M4 increments |

Cross-pillar prerequisites (owned elsewhere, **not** implemented here): provenance [ALH-23],
precision/bands [ALH-27], score history [ALH-29], bet state [ALH-46], alternatives [ALH-71],
criteria [ALH-72], near-duplicate detection [ALH-85], citation audit/holes [ALH-93]/[ALH-94],
actor propagation [ALH-111]. Where an increment depends on one of these and it is not yet on `main`,
**stop and record the missing choice** rather than stubbing it.

## Increment map and dependency order

```
M1 · The Loop Closes — 2026-11  (factual spine; the acceptance path for this pillar)
  C1  ALH-32  render_brief (pure, factual)            area/core
  C1.2 ALH-157 deterministic argument sections        area/core      ← depends C1
  C2  ALH-33  opportunity_brief card in the thread    area/studio*    ← depends C1
  C3  ALH-34  GET /api/compare + compare card         area/studio*    ← depends C1
  C4  ALH-35  odi brief export md|html                area/cli        ← depends C1
  C6  ALH-37  Decision entity + service + supersede   area/core,mcp,cli ← depends C3
  C6.2 ALH-158 odi decide + POST /api/decisions       area/core,mcp,cli ← depends C6
  C7  ALH-38  build_roadmap derivation                area/core,studio ← depends C6
  C7.2 ALH-160 render roadmap (md + card)             area/core,studio ← depends C7
  C8  ALH-39  decision review vs today's numbers      area/core,studio ← depends C7

W1  ALH-64  opportunity value model/persistence only  area/studio,core,cli (capture/display split: ALH-186/188/189)
D   ALH-40/41/161/42/43/182/184 segments & strategy   area/core,mcp,studio,cli
M3  ALH-90/169, ALH-97/171, ALH-98, ALH-99, ALH-95/96, ALH-205/206/207,
    ALH-103/172/232/233  optional narrative, memo, challenge, portfolio
M4  ALH-107/108/109/110, ALH-118, ALH-117/175, ALH-208/209/229/230/231, ALH-261/262
    collaboration, activity feed, role policy rollout
```

Ownership rules that constrain sequencing:
- **A structural parent is not a serialization point.** Follow the explicit prerequisite contracts;
  no cycles. A composed adapter (e.g. ALH-182 MCP segments) waits for the services it exposes; core
  CRUD does not wait for downstream inference/UI.
- **Default factual outputs stay byte-compatible.** Narration/ordering are opt-in and must not
  change the default bytes.
- **Do not claim all-path role enforcement** ([ALH-175]) until the complete mutation inventory
  ([ALH-261]/[ALH-262]) is covered.

## Review Focus

Inputs/conditions the pillar's spec implies but no single increment's tests fully pin, most likely to
bite first:

1. **A missing measurement rendered as zero.** Score, `n`, effort, baseline, target must render
   `not measured`/omitted-with-reason; a real recorded `0` stays `0`. (Owner: C1, C3, C7.)
2. **A fabricated numeral that belongs to the wrong fact.** The numeral walk proves a number exists
   *somewhere*; it does not prove value-to-source association. Assert association and escaped hostile
   text separately. (Owner: C1, C1.2.)
3. **A quote containing HTML treated as markup.** Quotes are text; escape them in every renderer and
   the HTML export. (Owner: C1, C4.)
4. **A superseded decision disappearing.** The predecessor must stay readable after reload and event
   replay, and a second decision must supersede atomically. (Owner: C6.)
5. **An undecided outcome silently dropped from the roadmap.** Exclusions carry an explicit count and
   reason; a missing measurement is never zero progress. (Owner: C7.)
6. **An LLM narration leaking into the factual default.** `--no-narrate` / no-narration must be
   byte-identical to the pre-change output; narration is labelled and separately guarded. (Owner: M3-04.)

---

## Task 1: C1 — `render_brief`, the pure factual case (`ALH-32`)

**Files:**
- Create: `packages/core/src/agentic_odi_core/brief.py`
- Create: `packages/core/tests/test_brief.py`
- Modify: `packages/core/src/agentic_odi_core/__init__.py` (export `render_brief`, `BriefInput`)
- Modify: `README.md` (Code Overview: `packages/core` row mentions the brief renderer)

**Interfaces:**
- Produces:
  ```python
  @dataclass(frozen=True)
  class BriefOutcome:
      outcome_id: str
      statement: str
      score: float | None
      band: str | None          # evaluation.classify_opportunity(score)
      n: int | None             # sample size, supplied
      method: str | None
      quote: str | None
      sources: tuple[str, ...]  # evidence ids/names, supplied

  @dataclass(frozen=True)
  class BriefInput:
      job_id: str
      job_name: str
      decision_consideration: str | None
      outcomes: tuple[BriefOutcome, ...]
      evidence_count: int
      generated_at: str         # supplied clock, never read inside

  def render_brief(brief: BriefInput) -> str: ...
  def select_underserved(outcomes: Sequence[BriefOutcome], limit: int = 3) -> list[BriefOutcome]: ...
  ```
- Consumes: `evaluation.classify_opportunity`, `repository.rank_outcomes` conventions.

- [ ] **Step 1: Write the failing golden-file test.** Fixture job with three scored outcomes, one
  unscored, one with a quote containing `<script>`. Assert `render_brief` output equals a committed
  golden file byte-for-byte; assert the unscored outcome produces an omission-with-reason line;
  assert `<script>` appears escaped.
- [ ] **Step 2: Run it and verify it fails** (`uv run pytest packages/core -k brief`).
- [ ] **Step 3: Implement `brief.py`** with `select_underserved` reusing `rank_outcomes` (ties broken
  by stable insertion order — **record this choice**), sections *The job* · *The decision we are
  considering* · *Underserved outcomes* · *Sources*, omission-with-one-line-reason for empty sections.
- [ ] **Step 4: Add the numeral-walk test** that collects every numeral in the output and proves it
  exists in the fixture, plus a value-to-source association assertion and a hostile-text escape
  assertion.
- [ ] **Step 5: Run tests, ruff, mypy.** Commit.

**Readiness to pin first:** input fixture/schema, the "three most underserved" selection + tie-break,
and which input supplies the decision-consideration text. Record in the test module docstring.

## Task 2: C1.2 — the case makes its argument (`ALH-157`)

**Files:** Modify `brief.py`, `packages/core/tests/test_brief.py`; extend the golden file.

**Interfaces:** `render_brief` gains three deterministic sections; each supported claim names the
outcome ids it rests on; the build section names the lowest-score outcome; risks names the holes.

- [ ] **Step 1: Write failing tests** for the three sections, the singular case (one measured
  outcome names the missing comparison), and the "no recorded holes says so in one line" case.
- [ ] **Step 2: Verify failure.**
- [ ] **Step 3: Implement the templates.** **Blocker:** confirm lowest-score vs highest-underserved
  and its tie-break before writing the build section — record the answer in the PR.
- [ ] **Step 4: Extend the numeral walk to the new sections.** Run tests, ruff, mypy. Commit.

## Task 3: C2 — `opportunity_brief` card in the thread (`ALH-33`)

**Files:** Modify `apps/studio/src/ui/catalog.ts`, `apps/studio/src/ui/cards.tsx`,
`apps/studio/src/ui/protocol.test.ts`, `apps/studio-api/.../studio/ui_spec.py`,
`apps/studio-api/.../studio/chat.py` (one prompt line), `docs/living-studio.md`.

- [ ] **Step 1: Write failing parity tests** — catalog entry ↔ card ↔ server validator, from one
  shared fixture (full/empty/partly-measured). Unknown prop is rejected by `UiCatalog.validate` and
  the error is fed back to the model.
- [ ] **Step 2: Verify failure** (`npm --prefix apps/studio test -- --run` + `uv run pytest apps/studio-api`).
- [ ] **Step 3: Add the catalog entry + card + validator**, reconcile nullable measurement fields and
  provenance (`method`/`source`) with Task 1's renderer; `generated_at` from supplied context.
- [ ] **Step 4: Add the one prompt line** (render once, then one sentence). Keyboard-reachable.
  Run both suites + ruff + mypy. Commit.

## Task 4: C3 — weigh two bets side by side (`ALH-34`)

**Files:** Create `GET /api/compare` in `apps/studio-api/.../studio/router.py`; alignment helper in
`packages/core/.../services.py`; `outcome_compare` catalog entry + card; tests in
`apps/studio-api/tests/test_studio_compare.py`.

- [ ] **Step 1: Write failing API tests** for 2 and 3 ids, a 4th refused naming the limit, and
  `not measured` for a missing metric while real `0` stays `0`.
- [ ] **Step 2: Verify failure.**
- [ ] **Step 3: Implement aligned rows** (one row per metric, one cell per outcome) over
  `rank_outcomes` + per-outcome metrics; no per-outcome fetch; no "winner".
- [ ] **Step 4: Add the catalog entry + card**, keyboard-readable headers, server/card parity from
  the same fixture. Run suites + ruff + mypy. Commit.

## Task 5: C4 — export the case (`ALH-35`)

**Files:** Create `apps/cli/src/agentic_odi_cli/brief.py` (`odi brief export`); reuse
`apps/studio/src/styles/print.css` tokens; tests in `apps/cli/tests/test_brief_cli.py`; `docs/cli.md`.

- [ ] **Step 1: Write failing CLI tests** — export writes a file and prints its path; HTML opens with
  no app CSS; a missing job exits 1 with a message; snapshot banner asserted; adversarial quotes
  escaped; unknown format exits nonzero.
- [ ] **Step 2: Verify failure** (`uv run pytest apps/cli -k brief`).
- [ ] **Step 3: Implement** one function over Task 1's markdown + an HTML wrapper that inlines the
  print tokens; no new dependency; pin overwrite/partial-file behaviour.
- [ ] **Step 4: Add `docs/cli.md` entry.** Run suites + ruff + mypy. Commit.

## Task 6: C6 — record the decision (`ALH-37`)

**Files:** Modify `packages/core/.../models.py` (`Decision`, `Rejection`),
`repository.py` (+Protocol/in-memory), `sqlite_repository.py` (`_apply_event` + cascade),
`remote.py`, `schema.py`, `services.py` (`record_decision`, `list_decisions`, `latest_decision`),
`contract.py` (+`record_decision` tool), `apps/mcp-server/.../mcp_server.py`,
`apps/studio-api/.../studio/schemas.py` + `types.ts`. New `test_decisions.py` +
`test_persistence_parity.py`.

- [ ] **Step 1: Write failing tests** — two decisions → two-entry ordered history; empty rationale
  refused; superseded decision stays readable after reload/replay; job deletion cascades with the
  cascade in the event payload; foreign/missing outcome ids, whitespace rejection reason, invalid
  confidence fail without an event.
- [ ] **Step 2: Verify failure** (`uv run pytest packages/core -k decision`).
- [ ] **Step 3: Add the entity + service + supersession.** **Pin first:** `superseded_at`/
  `superseded_by` shape, actor/timestamp provenance, latest/history tie-break, chosen/rejected overlap
  validation. `rejected` is a list of `{outcome_id, reason}` (not a JSON blob, not comma-separated);
  referenced outcomes must resolve within the decision's job.
- [ ] **Step 4: Wire the full persistence checklist + MCP tool + contract.**
- [ ] **Step 5: Add `test_persistence_parity.py`** covering in-memory, SQLite/replay, remote.
  Run suites + ruff + mypy. Commit.

## Task 7: C6.2 — record from CLI and API (`ALH-158`)

**Files:** `POST /api/decisions` in `studio/router.py` + schemas; `odi decide` in the CLI;
`docs/cli.md`; shared-fixture tests in `apps/cli` and `apps/studio-api`.

- [ ] **Step 1: Write failing tests** — both surfaces persist equal fields and the same predecessor
  through one service call; empty rationale refused identically; unknown job is not a success; error
  output has no traceback.
- [ ] **Step 2: Verify failure** (`uv run pytest apps/cli apps/studio-api -k decision`).
- [ ] **Step 3: Implement** argument parsing/transport only; project service errors to the shared
  body; name the superseded decision in both responses. **Pin first:** repeated id/reason encoding,
  explicit `decided_by` source, confidence vocabulary, HTTP fixture, retry/double-submit behaviour at
  the service contract.
- [ ] **Step 4: Add `docs/cli.md`** (rejection-reason syntax + supersession). Run suites + ruff +
  mypy. Commit.

## Task 8: C7 — derive the outcome roadmap (`ALH-38`)

**Files:** Create `packages/core/src/agentic_odi_core/roadmap.py`; `test_roadmap.py`.

**Interfaces:**
```python
@dataclass(frozen=True)
class RoadmapEntry:
    period: str          # e.g. "2026-Q4", computed from decision date in UTC
    outcome_id: str
    statement: str
    baseline: float | None
    target: float | None
    decision_id: str

def build_roadmap(job_id, decisions, outcomes, *, horizon: int = 4, today: date) -> tuple[list[RoadmapEntry], int]:
    """Return (entries in date order, count of undecided outcomes excluded)."""
```

- [ ] **Step 1: Write failing tests** — three decisions → three entries in date order; an undecided
  outcome excluded and counted; empty set returns the one-line `no decisions yet`; quarter boundaries
  in UTC; same-date decisions; missing baseline/target; supersession; horizon edges.
- [ ] **Step 2: Verify failure** (`uv run pytest packages/core -k roadmap`).
- [ ] **Step 3: Implement** the derivation only — no separate store, entries are outcome statements,
  `today` explicit so tests are clock-independent. **Pin first:** `decided-but-unmoved`, baseline/
  target provenance, supersession/repeated outcomes, `horizon=4` meaning. Missing measurement is never
  zero progress.
- [ ] **Step 4: Add the golden derivation test.** Run suites + ruff + mypy. Commit.

## Task 9: C7.2 — render the roadmap (`ALH-160`)

**Files:** Extend `roadmap.py` with a markdown renderer; `roadmap` catalog entry + card; tests.

- [ ] **Step 1: Write failing tests** — markdown and card show the same supplied facts (statement,
  baseline, target, decision); exclusion footer present.
- [ ] **Step 2: Verify failure.**
- [ ] **Step 3: Implement** the markdown renderer + catalog entry + card + validator + parity test.
  Run suites + ruff + mypy. Commit.

## Task 10: C8 — the decision review (`ALH-39`)

**Files:** `packages/core/.../review.py` (or extend `roadmap.py`); studio card; tests.

- [ ] **Step 1: Write failing tests** — a past decision is compared against today's numbers and
  flagged stale per the pinned metric direction; no-change/orphaned schema handled; missing
  measurement stays unknown, never "moved".
- [ ] **Step 2: Verify failure.**
- [ ] **Step 3: Implement.** **Pin first:** review metric direction and no-change/orphaned schema.
  Run suites + ruff + mypy. Commit.

---

## Later increments (own specs; sequenced after M1)

Each is its own bounded increment with the same readiness-gate discipline. Listed here for scope
completeness — do **not** implement before its prerequisites land:

- **W1 · ALH-64** value model/persistence only (capture [ALH-186], display [ALH-188], ordering
  [ALH-189] split out). Never infer money from an opportunity score; never sum overlapping estimates.
- **D1–D4 · ALH-40/41/161/42/43** segments as rows → candidates → acceptance → underserved/overserved
  → strategy record. Adapters [ALH-182] and ordering [ALH-184] are separate and wait for the services.
- **M3 · ALH-90/169, ALH-97/171, ALH-98, ALH-99, ALH-95/96, ALH-205/206/207, ALH-103/172/232/233**
  optional narration (labelled, `--no-narrate` byte-identical), memo/export, challenge proposals
  (no writes until accepted), portfolio recurrence/contradictions/leverage. Numeral membership is a
  safeguard, not proof of semantic correctness.
- **M4 · ALH-107/108/109/110, ALH-118, ALH-117/175, ALH-208/209/229/230/231, ALH-261/262**
  comments → mentions → review requests → approvals; activity feed; role policy model then
  enforcement rollout across the full mutation inventory. Declared-name collaboration is not
  authenticated access.

## Verification (whole pillar)

```bash
uv run pytest
uv run ruff check . && uv run ruff format --check .
uv run mypy apps packages
npm --prefix apps/studio test -- --run
```

Pillar completion requires traceable fixture coverage across
factual case → comparison → recorded decision → derived/rendered roadmap, optional enrichment without
default regression, human-explicit acceptance, and the collaboration/role rollout appropriate to each
later increment. Missing measurements, sources, value, or approval remain visible as
unknown/unavailable — not zero, success, or permission.
