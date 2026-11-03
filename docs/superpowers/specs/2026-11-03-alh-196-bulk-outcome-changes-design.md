# ALH-196 · M2-03.1 — Preview and undo bulk outcome changes from the CLI

Linear: ALH-196. Follows ALH-194/#670 (`OutcomeQuery`), ALH-65/#656 (themes), ALH-20 (stages as data).

## Intent and why

Organising a filtered set of outcomes — move them under a theme, re-stage them, tag them —
today means one edit per outcome. A person who has just narrowed the library to "everything
missing a stage" wants to fix the whole set in one reviewable operation: see exactly what
would change, run it, and be able to take it back if the review afterwards says it was wrong.

Success looks like: `odi outcomes bulk` previews and applies a narrowing's worth of changes,
each row succeeding or reporting its own reason, and `odi outcomes undo <token>` restoring
the set through the normal validators.

## Goals

- `bulk_update_outcomes(ids, {add_theme_ids, remove_theme_ids, stage, add_tags}, *, dry_run=False)`
  in core, returning `BulkReport{requested, changed, skipped:[{id, reason}], undo_token}`.
- `undo_bulk(token)` restoring themes, stage, and added tags exactly.
- CLI `odi desired-outcomes bulk --search ... --add-theme ... --stage ... --dry-run` and
  `odi desired-outcomes undo <token>`, with `--json`. (ALH-196 says `odi outcomes bulk`; that
  group is the customer-outcome alias — see *CLI surface*.)
- Dry-run writes no events and lists the exact affected ids and change table a real run on
  unchanged input produces.
- Per-item semantics: one invalid id or validation failure does not abort valid rows.
- The undo inverse is recorded at write time; the token expires on the next bulk write.

## Non-goals

- API/Studio surfaces (sibling child issues of ALH-196).
- Permanent undo history — one active bulk token at a time.
- Tag facets, saved views, cross-artifact search.
- Bulk score edits (importance/satisfaction) — they emit signals and are not metadata moves.

## Anti-goals

- A bulk SQL bypass: every write must ride the existing single-item paths
  (`ODIService.update_outcome`, `Repository.change_theme_membership` semantics) and their
  validators. Reuse-first rung 1.
- Silent last-write-wins on contradictory input.
- Undo clobbering a later, deliberate edit.

## Constraints (repo guardrails)

- Contract synchronization: every new tool appears simultaneously in `contract.py`
  (`ToolName` + `TOOL_SPECS`), `mcp_server.py`, and `_LOCAL_HANDLERS`; contract tests assert
  the set equality.
- In-memory/SQLite repository parity; anything persisted must ride the event stream
  (the CLI process is short-lived per command).
- New CLI command/flag → `docs/cli.md` and `README.md` updated in the same task.
- Tests: fast, one behavior per test, mirror code structure.

## The design

### Scope of a bulk change

One operation over an id list may: add themes, remove themes, move every outcome to a stage,
add tags. It never changes scores or statements. Fields not requested are untouched.

### Prerequisite: outcomes get a `tags` field

`Outcome` (models.py) gains `tags: list[str] = []`. `query.py` currently refuses tag
filtering with "no outcome holds tags … add the tag field first" — this change is that
first step, so the refusal is replaced by real matching.

- Matching semantics: an outcome matches `OutcomeQuery.tags` when it holds **any** of the
  queried tags (OR within the dimension, same as `theme_ids`).
- No tag facet (out of scope); CLI `--tag` search starts working unchanged.
- Pydantic ignores unknown fields on old stored events, so replay of pre-tags events yields
  `tags=[]` — reload-safe without a migration event.

### Stage means the job's step for that stage

An outcome carries no stage; stage lives on `Step.stage`, and `Outcome.step_id` points at a
step. `stage="locate"` in a bulk change resolves, per affected outcome, to
"the step of that outcome's job whose stage is `locate`" and writes `step_id`.

- No step of that stage exists in the outcome's job → that row is skipped with reason
  `job has no stage '<x>'`; valid rows elsewhere still apply.
- A job may hold several steps with the same stage and nothing prevents it today. The pick is
  deterministic: lowest `stage_index`, then the order `get_steps_for_job` returns. Undo
  restores the recorded previous `step_id`, so the pick only has to be stable, not clever.
- An unknown stage string (not a `JobStage` value) is a request-level refusal — the whole
  call raises `ValidationError(f"Unknown stage: {stage}")`, the existing contract (query.py).
- Undo restores the recorded previous `step_id` (which may be `None`).
- `update_outcome` does not today validate `step_id`; bulk resolution guarantees the step
  exists and belongs to the outcome's job before calling it. No new setter is invented.

### Contradictory add/remove theme (readiness blocker, pinned)

If a theme id appears in both `add_theme_ids` and `remove_theme_ids`, the **whole request is
refused** with a `ValidationError` naming the theme. This is request-shape validation, like
the unknown-stage refusal — not a per-row outcome — and it deliberately avoids
last-write-wins semantics.

### The id list and its guards

- Duplicate ids in the request are deduplicated at entry; `requested` counts the distinct
  ids after dedup. A repeated id cannot cause duplicate writes.
- An empty selection (after dedup) is refused with `ValidationError("No outcomes selected")`
  — nothing to preview, nothing to undo.
- Unknown ids are per-row skips with reason `outcome not found`.
- Theme existence and cross-job scope are checked per row with the service's existing
  membership rule — `ThemeNotFoundError` and the cross-job message become that row's skip
  reason; other rows still apply.

### How a row is written (real run)

For each outcome that survives validation:

1. Capture the before-image: `step_id`, `theme_ids`, `tags`.
2. Compute the after-image (theme adds with dedup / removes; resolved `step_id`; tags added
   with dedup).
3. If nothing differs, the row is skipped with reason `no change`.
4. Write through the two existing single-item paths, in this order:
   - `ODIService.update_outcome(id, {step_id, tags})` when either moved — it rides every
     existing validator and appends `OUTCOME_UPDATED`;
   - `Repository.change_theme_membership(id, added=[...], removed=[...])` when membership
     moved — the same call `assign_theme` uses, and the only writer of the
     `THEME_MEMBERSHIP_CHANGED` event. Theme existence and cross-job scope are checked first
     with the service's own `_check_membership_targets` rule, so a foreign theme is that
     row's skip reason rather than an unvalidated write.

No new event type writes outcome state; the only new events are the `BulkOperation` records.
`BulkReport.changed` lists ids that were written; `skipped` lists `{id, reason}` with the
reason being the human-readable validation error or `no change` / `outcome not found` /
missing-stage text.

### Dry-run (preview)

Identical pipeline, stopping before step 4: resolve, validate, compute after-images, and
report the same `changed`/`skipped` tables. Zero events appended, therefore no undo token —
`undo_token` is `None` on a dry run. The previewed `changed` ids and per-id change table
equal what a real run on unchanged input produces.

### The undo token: a persisted record, not an in-process secret

The CLI process lives for one command and `ODIService` is repository-agnostic — it never
touches `SQLiteRepository.store`. So the inverse rides the **repository protocol**, exactly
like `ScheduledWork` (a model + `add/get/list/update` on the protocol, persisted by SQLite as
events and replayed into a dict, held directly by `InMemoryRepository`).

New model `BulkOperation`:

```
id            # the undo token, uuid hex like new_event_id()
applied_at    # when the real run wrote
changes       # [{outcome_id, before: {step_id, theme_ids, tags}, after: {...}}] — changed ids only
requested, changed_ids, skipped  # the report, for the expiry message and audit
undone_at     # None until undone
```

Protocol additions: `add_bulk_operation`, `get_bulk_operation`, `list_bulk_operations`,
`update_bulk_operation`. SQLite persists them as new events `BULK_UPDATE_APPLIED` /
`BULK_UPDATE_UNDONE` and rebuilds them in `_apply_event` — the `SCHEDULED_WORK_*` precedent —
so the token survives a restart and in-memory parity holds.

Decisions on the remaining readiness blockers (all mine, flagged for review):

- **Expires on the next bulk write:** `undo_bulk(token)` refuses when
  `list_bulk_operations()` (creation order, preserved by event replay) holds a later
  operation. Ordering by position, not timestamp, so same-second writes cannot tie. The
  refusal names the newer token.
- **Conflict handling — undo cannot overwrite later changes:** for each changed id, undo
  compares the outcome's current `step_id`/`theme_ids`/`tags` to the recorded `after`.
  A mismatch (someone edited that outcome after the run, including while the CLI was closed)
  → the row is skipped with reason `changed since the bulk update`. Matching rows restore.
  `tags`/`theme_ids` compare as sets (order is not a user-visible change); `step_id` as a value.
- **Validity after non-bulk edits:** the token stays valid. Non-bulk edits do not expire it;
  they only make their own rows conflict-skipped at undo time. Expiry comes only from a newer
  bulk operation or its own undo.
- **A time limit:** none. "No permanent undo history" is enforced by single-active-token
  expiry, not a TTL.
- **Repeated undo:** undo sets `undone_at` (appending `BULK_UPDATE_UNDONE`); a second attempt
  on the same token is refused with `already undone`.

### Undo writes

Per restored row, through the same single-item path: `update_outcome(id, before)` plus a
`THEME_MEMBERSHIP_CHANGED` inverse event when membership moved. Reload/replay preserves the
undo (it is normal `OUTCOME_UPDATED` events).

### Undo writes

Per restored row, through the same two paths: `update_outcome(id, before_step_and_tags)`, and
`change_theme_membership(id, added=before-only, removed=after-only)` when membership moved.
Reload/replay preserves the undo (they are normal `OUTCOME_UPDATED` /
`THEME_MEMBERSHIP_CHANGED` events).

### Tools and contract

- `bulk_update_outcomes` — effect WRITE (it can write; `dry_run` is a read-shaped use of a
  write tool, matching "approvals gate writes").
- `undo_bulk` — effect WRITE.
- Both get `TOOL_SPECS` entries, MCP tools with full docstrings, `_LOCAL_HANDLERS`
  entries, and CLI commands — one change, contract tests stay satisfied.

### CLI surface

ALH-196 names `odi outcomes bulk`, but in this repo `outcomes` is the hidden alias of
`customer-outcomes`, whose `CustomerOutcome` has no `theme_ids`, `step_id`, or `tags` — it is a
different entity. The bulk change operates on desired `Outcome`s and reuses the shared search
options, so the commands live on the **`desired-outcomes`** group. Deliberate deviation from
the issue's wording; stated in the pull request body.

- `odi desired-outcomes bulk [--id ...] [--search] [--stage] [--theme] [--min-score] ...
  --add-theme --remove-theme --stage --add-tag [--dry-run] [--json]`
  — ids and a filter combine; the resolved set is `ids ∪ every match of the filter`. The
  filter serializes through the existing `OutcomeQuery`/`search_outcomes` path with **no
  limit**, so a bulk over a narrowed set is not a bulk over one page. No second parser.
- Output: a change table (id, what moved), skipped rows with reasons, and on a real run the
  undo token and how to use it. `--json` emits the `BulkReport` verbatim.
- `odi desired-outcomes undo <token> [--json]` — same table shape for the restore report.

### Errors surface

Request-level refusals (contradictory theme, unknown stage, empty selection) exit 1 with the
`Error:` line like every other CLI refusal; per-row problems never abort the run.

## Acceptance and tests (mapping to the spec)

- Preview writes no events (assert event count unchanged) and its changed/skipped table
  equals a subsequent real run on unchanged input (two-phase test in core).
- One invalid id / failing cross-job theme check does not abort valid rows.
- Undo restores themes, stage and added tags exactly (field-for-field equality), and a
  SQLite reload after both bulk and undo preserves the result.
- Expired token (a newer bulk applied) refused with its reason; repeated undo refused.
- Empty selection refused; duplicate ids deduped — no duplicate writes (event count).
- Unknown stage string refused; cross-job theme reported per row through the existing
  contract error text.
- Contradictory add/remove refused request-level.
- CLI contract tests for both commands (CliRunner, `--json`), parity of tool-name sets,
  `docs/cli.md`/`README.md` updated.

## What's left to the builder

- Exact renderer wording for the change table.
- Whether `BULK_UPDATE_APPLIED.skipped` rides the event (report-only; undo doesn't use it).
- Fixture names and file split across `packages/core/tests/test_bulk.py`,
  `apps/cli/tests/test_bulk_cli.py`, contract additions.

## Calls I made (not the user's) — for review

1. Contradictory add/remove → refuse the whole request (vs per-row skip).
2. The inverse is a `BulkOperation` record on the `Repository` protocol, persisted by SQLite as
   `BULK_UPDATE_APPLIED`/`BULK_UPDATE_UNDONE` events — so it survives a restart and keeps
   in-memory parity. No TTL; expiry is ordering by creation position, not timestamp.
3. Non-bulk edits do not expire the token; they produce per-row conflict skips at undo.
4. `stage` is implemented as per-job `step_id` resolution (outcomes have no stage field);
   several same-stage steps resolve to the lowest `stage_index`.
5. `Outcome.tags: list[str]` added, tag search refusal lifted with OR-within-dimension
   matching, no facet.
6. Bulk write = `update_outcome` for `step_id`/`tags` plus `change_theme_membership` for the
   theme delta — the two existing single-item paths, no new state-writing event.
7. Dry run yields `undo_token=None`.
8. Commands live on `desired-outcomes`, not the `outcomes` alias the issue names, because the
   alias edits a different entity.
