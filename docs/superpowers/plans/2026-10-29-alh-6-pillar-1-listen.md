# ALH-6 — Pillar 1 · Listen: conversations become outcomes

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Research enters the product as conversations and leaves as staged, deduplicated outcomes a person accepted, with the quote still attached — delivered increment by increment, never as one combined change.

**Architecture:** ALH-6 is a **coordination parent**, not one assignment. It is complete only when every active scoped descendant meets its acceptance and replay/contract checks. The M1 backbone (`A1 → A2/A4 → A5.1a/b/c → A5.2`, plus `A7 → A7.2`, `A8`, `A9 → A9.2`, `A10`) is the critical path; M2 and M3 epics build on it. Every new entity follows the epic's **Persistence checklist**: models → repository Protocol + in-memory → SQLite `_apply_event` → remote adapter → schema → service → contract/MCP → CLI → studio-api → studio types, with docs in the same PR.

**Tech Stack:** Python 3.10+, pydantic v2, Typer CLI, FastMCP server, FastAPI sidecar (`apps/studio-api`), React + TypeScript SPA (`apps/studio`), SQLite event store, uv workspace.

**Spec / parent:** [ALH-6](https://linear.app/alhase-personal/issue/ALH-6/pillar-1-listen-conversations-become-outcomes) · milestone `M1 · The Loop Closes — 2026-11`.

## Global Constraints

- Branch from `origin/main`. One PR per child issue; the parent is not a single change.
- **Persistence checklist** for any new entity/field, all in one PR: `models.py`, `repository.py` (Protocol + `InMemoryRepository`), `sqlite_repository.py` (`_apply_event`, and `_merge_updates` for updates), `remote.py` (if the adapter mirrors the surface), `schema.py` (`_SCHEMA_MODELS`), `services.py`, `contract.py` (`ToolName`/`TOOL_SPECS`/`get_capabilities`), CLI local backend + command, `apps/studio-api` router/schemas, `apps/studio` types/catalog.
- Cascades/inverses are **recorded in events**; never depend on write-time-only side effects for replay.
- Reuse the existing parity test and each issue's focused tests. **No live model/network tests** — inject fixture implementations.
- Docs land in the same PR: `README.md` (new command/package), `docs/cli.md` (new flag/command), `docs/living-studio.md` (new surface), `docs/roadmap.md` (tick a milestone item).
- No fabricated data; every surface can say "nothing yet". AI output is a proposal a human accepts.
- Never invent score/stage values, bypass `ODIService.add_outcome`, or silently relax validation to make acceptance succeed.

## Review Focus

Uncovered inputs/conditions most likely to bite, each with a test in the owning task:

1. **Legacy store without the new entities** — open + full replay must not crash and must not invent rows. (Task 1)
2. **Write-time cascade vs replay** — a delete whose cascade is computed only at write time diverges on replay. Every cascade records the removed ids in the event payload. (Task 1)
3. **Ordinal determinism** — two quotes in the same millisecond still order deterministically; ordinals are service-assigned, not timestamp-derived. (Task 1, Task 3)
4. **Malformed transcript** — a parse failure must create no interview and no partial quotes; refusals name the file/stdin and the line/reason. (Task 3)
5. **Re-extraction idempotency** — re-running extraction cannot duplicate candidates or reset a human decision. (Task 4)
6. **Acceptance atomicity** — a failed evidence write cannot leave an accepted candidate with missing evidence or an orphan outcome. (Task 5)
7. **Provenance survives deletion** — deleting an interview keeps the evidence readable with a nulled link, and leaves unrelated outcomes/evidence untouched. (Task 8)
8. **Honest states** — empty vs unknown vs failed are distinct everywhere (CLI, API, card).

## Implementation status

- **Task 0 (parity harness)** — done in this branch: `packages/core/tests/test_persistence_parity.py` drives both repositories and fails on a missed link.
- **Task 1 (A1 — interviews and quotes)** — done in this branch: models, repository (Protocol + in-memory + SQLite), schema, service, contract, MCP tools, CLI group + renderers, docs, and tests.
- **Task 9 (A7 — stages become data)** — done in this branch: `order`↔`stage` agreement on the model and service, `STEP_STAGE_BACKFILLED` on open, schema enum, CLI/MCP/API stage updates, docs, and `packages/core/tests/test_stages.py`.
- **Task 10 (A7.2 — the map draws the stages it is given)** — done in this branch: `stage_catalog()` + `GET /api/schema`, the Studio fetches the stages at boot and `JobMap` renders exactly that list.
- **Task 11 (A8 — coverage)** — done in this branch: `build_coverage_report` + `coverage_report(job_id)`, `get_coverage` MCP tool, `GET /api/jobs/{id}/coverage`, the CLI's `coverage`, the Studio's **Coverage** lens, docs, and tests in `packages/core/tests/test_coverage.py`, `apps/cli/tests/test_coverage_cli.py`, `apps/mcp-server/tests/test_coverage_tool.py`, `apps/studio-api/tests/test_studio_coverage.py`.
- **Tasks 2–14 and Phases 2–4** — not started; each is its own issue and PR.

---

## Phase 0 — Unblock the persistence contract

### Task 0: Restore the missing parity harness

The **Persistence checklist** in every child points at `packages/core/tests/test_persistence_parity.py` (from `M0-13`), and ALH-6's own verification says to reuse it. It does not exist in the tree.

**Files:**
- Create: `packages/core/tests/test_persistence_parity.py`

**Interfaces:**
- Produces: a table-driven parity harness `assert_repository_parity(seed, *, entities)` that, for a seed of writes, asserts `InMemoryRepository` and `SQLiteRepository` produce identical reads and that a reload of the SQLite event log reproduces the same state.

- [ ] **Step 1:** Enumerate the entity surface from `Repository` (jobs, steps, outcomes, customer_outcomes, evidence) and drive both repositories through create/update/delete/cascade.
- [ ] **Step 2:** Assert equality of every read after (a) live writes, (b) `reload()` from the event log, (c) a fresh `SQLiteRepository` on the same path.
- [ ] **Step 3:** Make the harness entity-registry driven so a new entity is one line, and let it **fail on a missed link** (a new model with no `_apply_event` branch) rather than pass silently.
- [ ] **Step 4:** Run `uv run pytest packages/core/tests/test_persistence_parity.py`; confirm green on `main`'s current surface.

**Acceptance:** the harness passes on the current surface and fails red if any single link is removed (add a temporary negative case, then remove it).

---

## Phase 1 — The M1 backbone (the loop closes)

### Task 1: A1 — Interview records and quotes, persisted ([ALH-14])

**Files:** `models.py`, `repository.py`, `sqlite_repository.py`, `schema.py`, `services.py`, `remote.py`, `contract.py`, `apps/mcp-server/.../mcp_server.py`, `apps/cli/src/agentic_odi_cli/backend.py` + new `interviews.py`, `apps/studio-api/.../schemas.py`, `apps/studio/src/api/schema.d.ts`; tests `packages/core/tests/test_interview*.py`.

**Interfaces (produces):**
- `Interview{id, job_id?, title, participant_label, participant_role?, conducted_at?, source_kind, notes?}`
- `InterviewQuote{id, interview_id, speaker?, text, ordinal, start_ms?, end_ms?}`
- Events `INTERVIEW_CREATED|UPDATED|DELETED`, `QUOTE_CREATED`.
- Service: `add_interview`, `get_interview`, `list_interviews`, `add_quote`, `list_quotes` (ordered by `ordinal`), `delete_interview` (cascade ids recorded in the delete payload).
- New `InterviewNotFoundError` beside the existing not-found classes.

- [ ] **Step 1:** Add both models; `participant_label` is free text, never an email/phone/company; no raw-transcript BLOB.
- [ ] **Step 2:** Extend `Repository` Protocol + `InMemoryRepository`; cascade delete removes only that interview's quotes.
- [ ] **Step 3:** Add `_apply_event` branches for all four events; the `INTERVIEW_DELETED` payload carries the cascaded quote ids.
- [ ] **Step 4:** Assign `ordinal = max(ordinal)+1` in the service (not the caller, not `created_at`); reject `add_quote` for a missing interview with no event written.
- [ ] **Step 5:** Register both models in `_SCHEMA_MODELS`; mirror in `remote.py`; add contract tools (`add_interview`, `get_interview`, `list_interviews`, `add_quote`, `list_quotes`, `delete_interview`) and MCP handlers; wire the CLI local handlers so `set(_LOCAL_HANDLERS) == set(TOOL_NAMES)` still holds.
- [ ] **Step 6:** Tests: one interview with three quotes round-trips a reload; quotes in `ordinal` order; delete removes only its quotes; `get_odi_schema` exposes both; legacy store without these entities opens cleanly; equal `created_at` still deterministic.

**Readiness blocker (surface, do not invent):** the issue's opening claim of "a retained raw transcript" has no model field and conflicts with the quote-row-only guidance. Confirm the retention contract before adding any raw-file storage. Coordinate the deletion behavior with ALH-23: retained `Evidence` snapshots must not cascade away with quotes.

### Task 2: A2 — Import a transcript from the command line ([ALH-15], parser from deleted ALH-16)

**Files:** new `packages/core/src/agentic_odi_core/transcript.py`; `apps/cli/src/agentic_odi_cli/interviews.py`; `docs/cli.md`; tests `packages/core/tests/test_transcript.py`, `apps/cli/tests/test_interviews_cli.py`.

**Interfaces (produces):**
- Pure `parse_transcript(text: str, fmt: str) -> list[Turn]`, `Turn(speaker: str | None, text: str, start_ms: int | None, end_ms: int | None)`.
- `parse_vtt`, `parse_srt`, `parse_markdown_dialogue` (`**Ana:** …` and `Ana: …`), `parse_prose`.
- CLI `odi interviews import <path|-> --job <id> --title ... --participant ... --role ... [--format auto|md|txt|vtt|srt]`.

- [ ] **Step 1:** Implement the four parsers; handle BOM, CRLF, blank runs, wrapped lines, missing `WEBVTT` header; unknown speaker stays `None`; malformed timestamp reports the line and never drops a turn.
- [ ] **Step 2:** Format sniffing is **extension first, then a content check**; unknown format is refused, never guessed. Parse **before** any service write so a refusal leaves no partial interview.
- [ ] **Step 3:** Persist via Task 1's service (service assigns ordinals). Refusals name the supplied filename (or `stdin`) and the line/reason.
- [ ] **Step 4:** Register the `interviews` Typer group in `cli.py`; add the command to `docs/cli.md`.
- [ ] **Step 5:** Tests: a table-driven suite of ≥12 cases across all four formats, stdin, empty/unknown input; `.vtt` yields speaker+timestamp quotes; plain text yields one quote per paragraph with `speaker=None`; empty file refused with the filename; failed validation creates no interview/quotes.

**Readiness blocker (settle before coding):** the spec alternates between a parser returning `Quote{ordinal,…}` and persistence-assigned ordinals. Fix the pure-parser return type (`Turn`, no ordinal) and the format/extension mismatch behavior, and keep the final interface identical for the HTTP path (Task 7).

### Task 3: A4 — Extract candidate outcomes from one quote ([ALH-17], normaliser from deleted ALH-19)

**Files:** new `packages/core/src/agentic_odi_core/similarity.py`, `packages/core/src/agentic_odi_core/extraction.py`; plus the full persistence checklist for `OutcomeCandidate`; tests `packages/core/tests/test_similarity.py`, `test_extraction.py`, `test_outcome_candidate*.py`.

**Interfaces (produces):**
- `similarity.normalize(text) -> str` (lowercase, punctuation removal, stopword handling) and `similarity.similar(a, b) -> float` (token-set overlap + `difflib.SequenceMatcher`).
- `StatementExtractor` Protocol: `async def propose(quote, job_name, stage_hint) -> list[Proposal]` with a **fixture** implementation; core must not import `openai`.
- `OutcomeCandidate{id, interview_id, quote_id, statement, rationale, confidence, status: proposed|accepted|rejected|merged, merged_into?, outcome_id?}` — event-sourced.
- Service: `extract_candidates(quote_id, extractor)`, `list_candidates(interview_id=None, status=None)`, candidate update path.

- [ ] **Step 1:** Implement `similarity.py` with a single documented normaliser and stopword vocabulary; define empty-normalised handling.
- [ ] **Step 2:** Implement `extraction.py`; every proposal passes `evaluate_outcome_statement` **before** storage; an invalid one is stored `status='rejected'` with the validator's message in `rationale` (keep the evidence the extractor is wrong).
- [ ] **Step 3:** Key candidates on `(quote_id, normalised_statement)` for idempotency; re-running extraction adds nothing and never resets a human decision.
- [ ] **Step 4:** Persist `outcome_id` on the candidate (readiness blocker from ALH-191: the listed fields omit it although acceptance requires it).
- [ ] **Step 5:** Full checklist wiring for `OutcomeCandidate` (events `CANDIDATE_CREATED|UPDATED`, schema, contract/MCP, CLI backend, studio-api, studio types).
- [ ] **Step 6:** Tests: fixture extractor returning three statements, one invalid → two `proposed`, one `rejected` with the message; **no** `Outcome` exists after extraction; re-extraction does not duplicate; malformed payload / confidence outside `[0,1]` / missing quote / extractor failure are explicit and leave no partial invalid state; normalised repeated statements collapse.

**Readiness blocker:** pin the stopword vocabulary and the empty-normalised behavior; do not invent score/stage values to make future acceptance pass.

### Task 4: A5.1a — Accept or reject a candidate without losing evidence ([ALH-191])

**Files:** `services.py` (state machine), `apps/studio-api/.../router.py` + `schemas.py`; tests `packages/core/tests/test_candidate_accept.py`, `apps/studio-api/tests/test_candidates.py`.

**Interfaces (produces):**
- `GET /api/candidates?interview_id=&status=proposed`, `PATCH /api/candidates/{id}` `{status, statement?, reason?}`.
- Service `decide_candidate(candidate_id, status, statement=None, reason=None)`.

- [ ] **Step 1:** Acceptance calls `ODIService.add_outcome` (validator + score rules apply), writes the verbatim `Evidence` snapshot from Task 8, then records `accepted` + `outcome_id`. Retry cannot duplicate outcome or evidence.
- [ ] **Step 2:** Rejection requires a nonblank reason and retains the candidate. Skip is no write.
- [ ] **Step 3:** Failure boundary: invalid statement / missing quote/interview / failed evidence write leaves **no** accepted candidate with missing evidence and **no** orphan outcome; verify by reload/replay.
- [ ] **Step 4:** Router tests assert filter isolation and per-decision store state; unknown candidate id returns the established not-found error.

**Readiness blocker (must resolve first):** how a newly accepted candidate supplies the **required stage/score inputs** of the outcome contract. Do not invent measurements or a stage, bypass `add_outcome`, or relax validation to make acceptance succeed. Decide the input contract (default scores from the review pass? explicit reviewer entry?) before coding.

### Task 5: A5.1b — Merge candidate evidence into a reviewer-selected outcome ([ALH-192])

**Files:** `services.py` (`merge_candidates(target_id, merged_ids)`), `similarity.py` (`find_duplicate_groups(candidates, threshold=0.82)`), router `PATCH` merge branch; tests `packages/core/tests/test_merge_candidates.py`.

- [ ] **Step 1:** `find_duplicate_groups` is read-only (no write during detection); a match is only a suggestion; the person chooses the target.
- [ ] **Step 2:** Mark sources `merged` with `merged_into`, retain originals and verbatim evidence; five paraphrases merge into one outcome with five distinct evidence links and no second outcome; two unrelated statements are not suggested.
- [ ] **Step 3:** A repeated merge changes nothing and duplicates no evidence; unknown target / invalid source transition fails with no partial moves. Document the recovery limit (no UI undo; re-extract from originals).

**Readiness blocker:** the absorbed spec calls its target a candidate while the active PATCH contract requires an outcome — confirm target semantics and eligible source states; do not silently reinterpret ids. Must not merge accepted library outcomes (that is ALH-85).

### Task 6: A5.1c — Review candidate decisions beside their source quote ([ALH-193])

**Files:** `apps/studio/src/ui/catalog.ts` (read-only `candidate_queue` entry with actions), `apps/studio/src/ui/protocol.ts`, component + tests.

- [ ] **Step 1:** Card shows quote + statement + actions (accept, edit-and-accept, reviewer-selected merge, reject-with-reason, skip); no arbitrary HTML, no second state machine.
- [ ] **Step 2:** A candidate cannot disappear as accepted until its write succeeds; rejection without a reason and invalid edited statements show the server's reason and retain the item.
- [ ] **Step 3:** Empty queue / loading / failed fetch are distinguishable; retry/double-click cannot duplicate outcomes or evidence; candidate and source quote stay paired after progression; merge requires an explicit target.

### Task 7: A5.2 — Work the review queue at the keyboard ([ALH-153])

**Files:** `apps/cli/src/agentic_odi_cli/interviews.py` (`review` command), `docs/cli.md`; tests `apps/cli/tests/test_interviews_review.py`.

- [ ] **Step 1:** `odi interviews review <id>` with `a`/`e`/`m`/`r`/`s`/`q`, progress `3/17`, and a `--yes` non-interactive mode; each prompt shows the statement beside its quote.
- [ ] **Step 2:** Drives the same service state machine as the API; `--yes` is explicit human-issued batch consent, touches only `proposed` candidates, prints accurate success/failure counts, and never accepts on `q`.
- [ ] **Step 3:** Scripted stdin covers edit-with-validation-error, merge with invalid/valid target, blank/nonblank reject reason, skip, quit, EOF; skip/quit/EOF preserve every remaining candidate; empty queue prints a meaningful zero-work result; re-running cannot duplicate outcomes/evidence.

### Task 8: A10 — Provenance travels with the number ([ALH-23])

**Files:** `services.py` (acceptance writes the `Evidence` row; deletion-safe provenance), `apps/studio-api/.../router.py` (`GET /api/outcomes/{id}/evidence`), `apps/studio/src/ui/cards.tsx` (quote chip); tests `packages/core/tests/test_provenance.py`.

- [ ] **Step 1:** On acceptance, write `Evidence{outcome_id, content: quote.text, source_name: interview title, source_kind: "interview", raw: {interview_id, quote_id}}` — content verbatim, never a whole transcript.
- [ ] **Step 2:** `GET /api/outcomes/{id}/evidence`; outcome detail and landscape row show a quote count computed from `list_evidence` (never a stored counter), that opens the quotes.
- [ ] **Step 3:** Deleting an interview **keeps** the evidence and nulls the link; record that in `docs/living-studio.md`. Repeated acceptance/retry has one evidence link per source; unknown speaker/date stay visibly unknown.

**Readiness blocker:** define whether `raw.interview_id` remains as an unavailable historical id or is also nulled, and which event records the change; confirm which snapshot fields retain speaker/date once the interview is gone. Do not fabricate attribution from deleted records.

### Task 9: A7 — Stages become data ([ALH-20])

**Files:** `models.py` (`JobStage` enum + `Step.stage` derived from `order`), `services.py`, `sqlite_repository.py` (`STEP_STAGE_BACKFILLED` on open), `schema.py`; tests `packages/core/tests/test_stages.py`.

- [x] **Step 1:** `order`↔`stage` agree (1↔define … 8↔conclude); a disagreeing pair is rejected naming both.
- [x] **Step 2:** Backfill on open emits `STEP_STAGE_BACKFILLED` per changed step (auditable, not an in-place edit); opening the same legacy store twice emits backfill events only the first time; replay reproduces the same stage values.
- [x] **Step 3:** Explicitly unset/invalid legacy order acquires no invented stage; `get_odi_schema` exposes the enum.

**Readiness blocker:** resolve one persistence/serialization contract with GH-83 (stage stored vs derived vs backfilled) and the behavior for existing steps outside 1–8 before implementing; do not store contradictory truths or silently remap history.

### Task 10: A7.2 — The map draws the stages it is given ([ALH-155])

**Files:** `apps/studio/src/components/canvas/JobMap.tsx`; component tests.

- [x] **Step 1:** Read the enum from `GET /api/schema` (the request the Studio already makes) and render in the returned order; delete the local literal array (no fallback).
- [x] **Step 2:** A reduced/reordered fixture renders exactly what was supplied; a separate production-schema contract test fails if a canonical stage is missing.
- [x] **Step 3:** A failed fetch renders the failure panel and names the request, not an empty map; loading is visible; rendering writes nothing.

### Task 11: A8 — Coverage: what the research does not cover ([ALH-21])

**Files:** `services.py` (`coverage_report(job_id) -> CoverageReport`), `apps/cli/.../coverage.py` + `docs/cli.md`, `apps/studio-api` route `GET /api/jobs/{job_id}/coverage`, Studio `coverage` catalog entry; tests `packages/core/tests/test_coverage.py`, `apps/cli/tests/test_coverage_cli.py`.

**Interfaces (produces):** `CoverageReport{per_stage: list[StageCoverage{stage, outcomes, measured, quotes}], totals, gaps: list[JobStage]}`, explicit `unassigned`.

- [x] **Step 1:** All eight stage rows in stable order; explicit `unassigned` totals; `gaps` are stages with **zero** outcomes; `quotes` counts evidence rows linked to that stage's outcomes (not global quotes).
- [x] **Step 2:** Empty job returns a zeroed report; unknown job uses established not-found handling (distinct from an empty job); no cross-job leakage; report execution writes no events.
- [x] **Step 3:** CLI JSON / API / card counts match exactly; fixture covers unstaged, measured/unmeasured, duplicate-evidence cases.

**Readiness blockers:** define what qualifies as "measured" and the identity of a counted evidence row when one quote supports multiple outcomes.

### Task 12: A9 — Twenty outcomes in one keyboard pass ([ALH-22])

**Files:** `apps/studio-api` `POST /api/outcomes/score-batch` + schema, `apps/cli/.../score_pass.py` + `docs/cli.md`; tests `apps/cli/tests/test_score_pass.py`, `apps/studio-api/tests/test_score_batch.py`.

- [ ] **Step 1:** Batch endpoint takes `[{outcome_id, importance, satisfaction, why?}]` and returns a **per-item** result so one bad row cannot abort the batch; every write goes through `ODIService.update_outcome` (1–10 bounds + recompute).
- [ ] **Step 2:** CLI `odi score [--job] [--unscored] [--limit]`: `1-10`, `s`, `q`, `u` (undo the last, replayed through the same endpoint), progress `3/20`, summary.
- [ ] **Step 3:** Tests: scoring three of five leaves two unscored; `11` rejected for that item only with the rest applied; `u` restores the previous value; scripted stdin covers skip/invalid/undo/quit; empty selection renders an honest completion state; API failure never appears as success.

**Readiness blocker:** define how truly unscored outcomes are represented/restored when the prior score pair is absent, and whether `1-10` means two sequential prompts or a pair; do not invent a zero score or hidden default.

### Task 13: A9.2 — The same pass in the Studio ([ALH-154])

**Files:** Studio `batch_scoring` card; component tests.

- [ ] **Step 1:** Drive the same `score-batch` endpoint one outcome at a time with the same skip/undo semantics and progress; no second scoring endpoint (asserted by the router enumeration).
- [ ] **Step 2:** Component fixtures cover importance/satisfaction, skip, undo, invalid row, request failure, completion; persisted result matches the CLI sequence; progress advances only on a real result, not optimistic success; double-submit/retry cannot silently score the next item; empty list / missing evidence / unavailable previous value are honest states.

### Task 14: A2.2 — Import a transcript from the thread ([ALH-152])

**Files:** `apps/studio-api` `POST /api/interviews/import` + schema, `apps/studio/src/lib/commands.ts` (`/interview`); tests `apps/studio-api/tests/test_interview_import.py`, `apps/studio/src/lib/commands.test.ts`.

- [ ] **Step 1:** Route takes `{text, title, job_id, participant, role}` (+ the agreed filename/format metadata from the readiness blocker) and returns the interview id + quote count; it calls Task 2's shared importer, never a second browser parser.
- [ ] **Step 2:** `/interview` hands the composer's attachment to the route and **not** to the chat turn; a refusal renders in the thread with filename + reason; CLI and HTTP fixture imports yield identical ordered quote text/speaker/times; retries do not submit twice; loading/completion visible.

**Readiness blocker:** agree how attachment metadata carries filename/format to the shared importer (including extensionless text) before extending the request.

---

## Phase 2 — M2 · Research at Scale (2026-12)

Each is its own issue + PR; they consume the M1 contracts above. Grouped by theme:

- **Organise:** ALH-65 (themes), ALH-163 (tree rollup), ALH-66 (search/filter), ALH-67 (bulk edit), ALH-68 (spreadsheet import + report), ALH-86 (saved views), ALH-82 (source library), ALH-85 (library-wide near-duplicate detection).
- **Library:** ALH-70 (outcome hierarchy / decompose).
- **Study:** ALH-69 (study + waves), ALH-164 (compare wave 1 vs wave 2), ALH-165 (scope canvas to a wave), ALH-74 (guide builder), ALH-75 (screener), ALH-76 (participant roster + quotas), ALH-167 (recruitment gap in the app), ALH-73 (how many interviews is enough), ALH-227 (build/select guides in Studio).

**Shared readiness blockers to decide with the method owner before coding:** wave-copy/matching policy (shared with ALH-80), participant rule/unknown eligibility and quota counting, search facets/default-view predicates.

## Phase 3 — M3 · The Agent Does the Work (2027-01)

- **Interpret:** ALH-92 (ask the past with citations) + ALH-170 (ask from composer/CLI) — must not acquire a resolver dependency cycle with ALH-93 (cite the evidence behind any claim).
- **Guide/Instrument/Draft:** ALH-87 (draft a guide from the job), ALH-100 (suggest the next question), ALH-101 (coach coverage gaps — needs approved effort inputs), ALH-102 (propose themes for a batch), ALH-105 (study plan page — needs real timeline/linkage fields), ALH-106 (stage-aware method guidance — needs method-owner approval of workspace-phase vs customer-job-stage mapping).

## Phase 4 — M5 (docs reach)

- ALH-128 (a PM's guide to the eight stages) — `area/docs`, lowest priority; tick `docs/roadmap.md` when it lands.

---

## Coordination completion

ALH-6 is complete when **all active scoped descendants** meet their acceptance and replay/contract checks, and a fixture can extract → review → reload with no duplicate outcomes or lost evidence. The parent's completion does **not** assert that unresolved work is implementation-ready or failure-proof; the readiness blockers above must be decided by the method owner, not invented.

**Deleted duplicates (historical, do not recreate):** ALH-16, ALH-19.

## Verification (per child PR)

```bash
uv run pytest packages/core/tests/test_persistence_parity.py   # the checklist
uv run pytest <focused tests for the child>
uv run ruff check . && uv run ruff format --check .
uv run mypy apps packages
npm --prefix apps/studio test -- --run   # when the SPA changes
```

## Self-review notes

- **Scope:** the parent explicitly forbids implementing the combined scope in one change. This plan sequences the M1 backbone as the critical path and enumerates M2/M3 as their own increments.
- **Reality checks performed against the tree:** `transcript.py`, `similarity.py`, `extraction.py`, `authoring.py` and `test_persistence_parity.py` are absent (Phase 0 restores the last); `Step.stage`/`stage_index` and `JobStage` already exist (Task 9 extends rather than adds); `Evidence` has no `origin` field (Task 8's spec mentions one — reconcile before adding).
- **Blocker honesty:** every child's readiness blocker is surfaced, not resolved by invention.
