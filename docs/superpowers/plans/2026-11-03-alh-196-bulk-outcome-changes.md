# ALH-196 · Bulk outcome changes with preview and undo — Implementation Plan

**Spec:** `docs/superpowers/specs/2026-11-03-alh-196-bulk-outcome-changes-design.md`

**Goal:** `bulk_update_outcomes(...)` / `undo_bulk(token)` in core, exposed as
`odi desired-outcomes bulk|undo`, moving a filtered set of outcomes (themes, stage, tags) in one
reviewable, reversible operation.

**Architecture:** Bulk is a *loop over the existing single-item paths* — `ODIService.update_outcome`
for `step_id`/`tags`, `Repository.change_theme_membership` for the theme delta — never a new write
primitive. The undo inverse is a persisted `BulkOperation` record on the `Repository` protocol,
following the `ScheduledWork` precedent (SQLite stores it as `BULK_UPDATE_APPLIED` /
`BULK_UPDATE_UNDONE` events and rebuilds it on replay; in-memory keeps it in a dict).

**Tech Stack:** Python 3.12, pydantic v2, Typer, pytest, SQLite event log.

## Global Constraints

- Contract sync: every new tool exists in `contract.py` (`ToolName` + `TOOL_SPECS`),
  `apps/mcp-server/.../mcp_server.py`, and `_LOCAL_HANDLERS` in the same change —
  `tests/contract/test_cli_contract.py` asserts `set(_LOCAL_HANDLERS) == set(TOOL_NAMES)`.
- No new dependency. Reuse-first: rungs that failed are named in the PR body's `Reuses:` block.
- In-memory/SQLite parity for anything the service reads or writes.
- Score/statement edits are out of scope for bulk.
- Tests: `uv run pytest` from the repo root, each under 1s, one behavior per test.
- Docs in the same task: `docs/cli.md`, `README.md`.
- Base branch: `qoder/ALH-195-landscape-search` (stacked; themes #656 and search #670 are unmerged).

## Review Focus

Input classes the spec implies that task tests must pin, because a wrong answer here is a silent
data loss for a person reviewing after the fact:

1. A theme id in both `add_theme_ids` and `remove_theme_ids` → the whole request is refused, not
   last-write-wins. (Task 3)
2. An outcome edited between the bulk run and its undo → that row is skipped with a reason; the
   others still restore. (Task 4)
3. A filter that matches more than one page → bulk applies to every match, not the first page. (Task 5)
4. `stage="locate"` on a job whose job map has no `locate` step → per-row skip naming the job,
   valid rows elsewhere still apply. (Task 3)
5. An undo token after a restart, or after a newer bulk write → refused with the reason that
   expired it, never silently re-applied. (Task 4)

---

### Task 1: `Outcome.tags` and tag filtering

**Files:**
- Modify: `packages/core/src/agentic_odi_core/models.py:168-190` (`Outcome`)
- Modify: `packages/core/src/agentic_odi_core/query.py:44-56` (`_validate_query`, `_matches_*`)
- Test: `packages/core/tests/test_outcome_search.py`, `packages/core/tests/test_service.py`

**Interfaces:**
- Produces: `Outcome.tags: list[str]` (default `[]`); `OutcomeQuery.tags` now filters.

- [ ] **Step 1: Failing tests** — in `test_outcome_search.py`, a store with two outcomes tagged
  `["churn"]` / `["pricing"]`; `search_outcomes(repo, OutcomeQuery(tags=["churn"]))` returns only
  the first; `tags=["churn", "pricing"]` returns both (OR within the dimension). In
  `test_service.py`, `add_outcome(..., tags=["churn"])` round-trips and `update_outcome(id,
  {"tags": [...]})` replaces.
- [ ] **Step 2:** `uv run pytest packages/core/tests/test_outcome_search.py packages/core/tests/test_service.py -k "tag"` → FAIL.
- [ ] **Step 3:** Add the field; delete the "tags cannot be filtered yet" refusal; match with the
  same shape as `_matches_theme_ids` (any overlap). No facet.
- [ ] **Step 4:** Same command → PASS, plus full `uv run pytest packages/core -q` for regressions
  in the studio-api/CLI search tests that asserted the refusal (update those expectations).
- [ ] **Step 5:** Commit `feat(core): outcomes hold tags, and the shared search matches them`.

### Task 2: `BulkOperation` on the repository protocol

**Files:**
- Modify: `packages/core/src/agentic_odi_core/models.py` (new model)
- Modify: `packages/core/src/agentic_odi_core/repository.py` (protocol + `InMemoryRepository`)
- Modify: `packages/core/src/agentic_odi_core/sqlite_repository.py` (`_apply_event`, add/get/list/update)
- Test: `packages/core/tests/test_bulk.py` (new), `packages/core/tests/test_sqlite_repository.py`

**Interfaces:**
- Produces:
  ```python
  class BulkChange(BaseModel):
      outcome_id: str
      before: dict[str, Any]   # {"step_id", "theme_ids", "tags"}
      after: dict[str, Any]

  class BulkOperation(BaseModel):
      id: str                       # the undo token (uuid4 hex)
      applied_at: datetime
      changes: list[BulkChange]
      requested: int
      skipped: list[dict[str, str]]  # {"id", "reason"}
      undone_at: datetime | None = None
  ```
  Protocol: `add_bulk_operation(op) -> BulkOperation`, `get_bulk_operation(id) -> BulkOperation |
  None`, `list_bulk_operations() -> list[BulkOperation]` (creation order), `update_bulk_operation(
  id, updates: dict) -> BulkOperation | None`.
- SQLite appends `BULK_UPDATE_APPLIED {op.model_dump(mode="json")}` on add, `BULK_UPDATE_UNDONE
  {id, undone_at}` on the undo update, and replays both into the snapshot dict.

- [ ] **Step 1: Failing test** — parametrized over both repositories (the existing parity pattern
  in `test_repository.py`): add → get returns it; `list_bulk_operations()` returns two adds in
  creation order; `update_bulk_operation(id, {"undone_at": dt})` persists.
- [ ] **Step 2: Failing reload test** in `test_bulk.py` — write a bulk operation to a
  `SQLiteRepository(tmp_path db)`, reopen, and assert the operation and its `changes` are intact.
- [ ] **Step 3:** Run → FAIL; then implement model + both repos + `_apply_event` branches.
- [ ] **Step 4:** Run → PASS.
- [ ] **Step 5:** Commit `feat(core): a persisted BulkOperation record, replayed from the event log`.

### Task 3: `ODIService.bulk_update_outcomes`

**Files:**
- Modify: `packages/core/src/agentic_odi_core/services.py` (after `search_outcomes`, ~line 636)
- Create: `packages/core/src/agentic_odi_core/bulk.py` (the `BulkReport` types and pure
  before/after computation, so the service stays a thin caller)
- Test: `packages/core/tests/test_bulk.py`

**Interfaces:**
- Consumes: `search_outcomes`, `update_outcome`, `change_theme_membership`,
  `_check_membership_targets` rules, `add_bulk_operation`.
- Produces:
  ```python
  @dataclass
  class BulkReport:
      requested: int
      changed: list[str]
      skipped: list[dict[str, str]]      # {"id", "reason"}
      changes: list[dict[str, Any]]      # per-id table: {outcome_id, field, from, to}
      undo_token: str | None

  def bulk_update_outcomes(
      self, outcome_ids: list[str] | None, *,
      add_theme_ids: list[str] | None = None, remove_theme_ids: list[str] | None = None,
      stage: str | None = None, add_tags: list[str] | None = None,
      query: OutcomeQuery | None = None, dry_run: bool = False,
  ) -> BulkReport
  ```
  Request-level `ValidationError` for: contradictory add/remove theme, unknown `stage`, empty
  selection, `dry_run` never raising for per-row reasons.

- [ ] **Step 1: Failing tests** (one behavior each, `ODIService(InMemoryRepository())` fixture):
  - preview: two matched outcomes → `changed` lists both, `changes` table names the moved field,
    `undo_token is None`, and the repository event count is unchanged.
  - preview == real: run dry, then real on the same input → identical `changed`/`skipped`.
  - per-row isolation: one unknown id + one cross-job theme + one good id → `changed == [good]`,
    `skipped` reasons contain `outcome not found` and the existing cross-job message.
  - dedup: the same id twice → `requested == 1`, one write.
  - empty: `bulk_update_outcomes([], ...)` raises `ValidationError("No outcomes selected")`.
  - contradiction: theme in both add and remove raises `ValidationError` naming it.
  - stage: `stage="locate"` sets `step_id` to the job's locate step; a job without one is skipped
    with reason `job has no stage 'locate'`; `stage="migrate"` raises.
  - tags: `add_tags=["x"]` appends with dedup; already-tagged row → `no change`.
  - no-op field set: all three requested changes already present → `skipped` reason `no change`,
    and no `BulkOperation` written.
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Implement. The real run writes per row: `update_outcome(id, {"step_id":…,
  "tags":…})` for the fields that moved, then `change_theme_membership(id, added, removed)` for
  the theme delta; then `add_bulk_operation(BulkOperation(...))` **after** the loop, holding only
  rows that actually changed. `requested` counts distinct ids after resolving `outcome_ids ∪
  query matches` with `limit=None`.
- [ ] **Step 4:** Run → PASS.
- [ ] **Step 5:** Commit `feat(core): bulk_update_outcomes with preview and per-row reasons`.

### Task 4: `ODIService.undo_bulk`

**Files:**
- Modify: `packages/core/src/agentic_odi_core/services.py`
- Test: `packages/core/tests/test_bulk.py`

**Interfaces:**
- Consumes: `BulkOperation.changes`, `list_bulk_operations`, `update_bulk_operation`.
- Produces: `undo_bulk(self, token: str) -> BulkReport` — same shape, `undo_token=None`.
  Raises `ValidationError` for unknown / already-undone / superseded tokens.

- [ ] **Step 1: Failing tests:**
  - restore: bulk (themes + stage + tags) then `undo_bulk(token)` → every field equals the
    original, including `step_id=None`.
  - superseded: a second bulk run then `undo_bulk(first_token)` raises with a reason naming the
    newer token.
  - repeated: `undo_bulk(t)` twice → the second raises `already undone`.
  - conflict: bulk, then a single-item `update_outcome` on one row, then undo → that row is
    `skipped` with `changed since the bulk update`, the other restored.
  - comparison is set-based for `theme_ids`/`tags` (reordered list is not a conflict) and
    value-based for `step_id`.
  - reload: SQLite bulk → reopen → `undo_bulk` restores.
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Implement; write through the same two single-item paths, then
  `update_bulk_operation(token, {"undone_at": now})`.
- [ ] **Step 4:** Run → PASS.
- [ ] **Step 5:** Commit `feat(core): undo_bulk restores through the normal validators`.

### Task 5: Contract, MCP, backend handlers

**Files:**
- Modify: `packages/core/src/agentic_odi_core/contract.py` (`BULK_UPDATE_OUTCOMES`,
  `UNDO_BULK` in `ToolName` + `TOOL_SPECS`, effect WRITE, arguments verbatim from the signatures)
- Modify: `apps/mcp-server/src/agentic_odi_mcp_server/mcp_server.py` (two `@mcp.tool`s with
  docstrings; return `"Error: …"` strings like `update_outcome`)
- Modify: `apps/cli/src/agentic_odi_cli/backend.py` (`_bulk_update_outcomes`, `_undo_bulk`,
  `_LOCAL_HANDLERS` entries)
- Test: `tests/contract/test_cli_contract.py`, `tests/contract/test_mcp_contract.py`,
  `apps/mcp-server/tests/`

**Interfaces:**
- Produces: tool names `bulk_update_outcomes`, `undo_bulk` callable through `run_tool`.

- [ ] **Step 1:** Add the failing contract assertions first: the tool-name set equality, the
  `TOOL_SPECS` argument tuples, and `get_capabilities` listing both with effect `write`; an MCP
  in-memory `Client(server)` round-trip for a dry-run bulk.
- [ ] **Step 2:** Run the contract tests → FAIL; implement all three surfaces; → PASS.
- [ ] **Step 3:** Commit `feat(core,cli,mcp-server): bulk and undo as contract tools`.

### Task 6: CLI commands and rendering

**Files:**
- Modify: `apps/cli/src/agentic_odi_cli/desired_outcomes.py` (two commands on
  `desired_outcomes_app`), `apps/cli/src/agentic_odi_cli/render.py` (`render_bulk_report`)
- Modify: `docs/cli.md`, `README.md`
- Test: `apps/cli/tests/test_bulk_cli.py` (new; the `CliRunner` + `--json` + `_seed` pattern of
  `test_themes_cli.py`)

**Interfaces:**
- Consumes: `run_tool("bulk_update_outcomes"|"undo_bulk", args)`, the shared search options
  already parsed in `desired_outcomes.py:138-178`.
- Produces: `odi desired-outcomes bulk [--id …] [search options] --add-theme --remove-theme
  --stage --add-tag [--dry-run] [--json]` and `odi desired-outcomes undo <TOKEN> [--json]`.

- [ ] **Step 1: Failing tests:** dry run prints the change table and writes nothing (event count
  unchanged) and exits 0; a real run prints the undo token and `undo <token>` restores, asserted
  via `--json` against the `BulkReport` shape; a contradictory theme exits 1 with `Error:` on
  stderr; `--id` combined with `--stage` acts on the union; a filter matching 3 outcomes on a
  paginated store applies to all 3, not one page.
- [ ] **Step 2:** Run → FAIL; implement; → PASS.
- [ ] **Step 3:** Update `docs/cli.md` and `README.md` with both commands and the undo limits
  (single active token, no permanent history, API/Studio in the sibling issue).
- [ ] **Step 4:** Commit `feat(cli): odi desired-outcomes bulk and undo`.

### Task 7: Full-suite gate and PR

- [ ] `uv run pytest` at the root → all green (record the count).
- [ ] `uv run ruff check .` and any repo format gate → clean.
- [ ] Push branch `qoder/ALH-196-bulk-outcome-changes` from the ALH-195 head; open a PR against
  `qoder/ALH-195-landscape-search` with the `Reuses:` block (rung 1: `update_outcome`,
  `change_theme_membership`, `search_outcomes`/`OutcomeQuery`, `ScheduledWork` persistence
  precedent; the only new files are `bulk.py` and two test modules), the readiness-blocker
  decisions, and the `desired-outcomes` vs `outcomes` naming deviation.
- [ ] Claim: create/label the GitHub issue mirror (`qoder/<date>-<issue>`, `status/in-progress`),
  move ALH-196 to In Review in Linear.
