# Preview bulk organisation changes in the landscape — design

**Issue:** [ALH-197](https://linear.app/alhase-personal/issue/ALH-197) · M2-03.2
**Depends on:** ALH-196 (M2-03.1, `bulk_update_outcomes` / `undo_bulk` in core, contract, MCP and CLI)
and ALH-195 (M2-02.2, the landscape's store-backed search and facets).

## Intent

A person reviewing the landscape should be able to tick a set of outcomes, see the exact
table of what a bulk organisation change would write, apply it, read which rows were
skipped and why, and take the run back — without opening a terminal. Everything the
Studio shows is computed by the same service the CLI already calls; the browser holds no
second copy of the rules.

## Why this shape

ALH-196 settled the semantics: a bulk run is a loop over the single-item writers, the
inverse is persisted as a `BulkOperation` replayed from the event log, a newer run expires
an older token, and a row someone edited after the run is left alone and reported rather
than overwritten. ALH-197 adds a surface, not a system. So:

* No preview calculator in the frontend. The Studio asks the API for `dry_run: true` and
  renders what comes back.
* No new validators. The route calls the service, the service's existing refusals come
  back through the shared Studio error envelope.
* No permanent undo system. The undo token is the one ALH-196 already mints and expires.

## The one decision the issue demanded first

*"Define selected visible page versus all filtered results explicitly … never silently
expand the set."*

**Decision:** the checked rows are exactly the ids the run writes. Widening to the whole
filtered set is a separate, named action that states the count it is about to write:
**Preview all 137 matching**, beside **Preview 12 selected**. Expanding is therefore never
a side effect of pressing a button that said something else.

When the person chooses the wider action, the route resolves the extra ids by calling the
same `search_outcomes` the landscape itself is paging — in pages of 200, until it has
`total` ids — and then hands the service an explicit id list. Two consequences worth
naming:

* The HTTP surface, the MCP tool surface and the CLI stay identical: all three send
  `outcome_ids`. `OutcomeQuery` never leaves the store-side function that already takes it.
* The set the preview table counted is the set the apply writes, because both go through
  the same search. If the library changes in between, the apply run's own skip reasons say
  so; the run never guesses at rows it did not show.

## Routes

`POST /api/outcomes/bulk` — body `BulkRequest`:

| field | meaning |
| --- | --- |
| `mcp_url` | which server answers; `""` means the local store (the existing convention) |
| `outcome_ids` | the checked rows, in selection order |
| `query` | the landscape's current narrowing, present only for the wider action |
| `stage`, `add_theme_ids`, `remove_theme_ids`, `add_tags` | the change itself, passed straight through |
| `dry_run` | `true` for the table, `false` for the write |

Returns the `BulkReport` dictionary unchanged: `requested`, `changed`, `skipped`
(`{id, reason}`), `changes` (`{outcome_id, field, from, to}`), `undo_token` (null on a
preview).

`POST /api/outcomes/bulk/undo` — body `{mcp_url, token}` → the same report shape for the
restored rows.

Both follow `router.py`'s existing shape: `_uses_mcp(request)` → `call_mcp_tool(ToolName…)`
else `_service(request)…`, with every exception through `_as_http_error`. A refused run
(empty selection, an unknown stage, a theme that organizes a different job, an expired or
already-used token) is a 400 with the shared `{error: {code, message, …}}` envelope, so
the bar can show the sentence the service wrote rather than a generic failure.

## The landscape surface

* **Selection.** A checkbox on each outcome card and each table row, held as a `Set` in
  the landscape's own state. Selecting does not move focus or open the detail panel, so
  ticking ten rows is one interaction, not twenty. The matrix view keeps its single-node
  focus: nodes there are positions, not rows, and a checkbox on a 200-point scatter would
  be noise. Documented as a limitation.
* **The change bar.** A docked bar that appears once something is selected: how many are
  selected, the stage picker (the shared `JOB_STAGES`), theme add/remove from the themes
  the landscape already fetched, a tag field, and the two preview actions named above.
  It clears with a **Clear selection** control.
* **The change dialog.** Preview opens a focus-trapped dialog (the `ChangelogModal`
  pattern) listing the table — outcome, field, from, to — then the skipped rows with their
  reasons. **Apply** is the dialog's own action, so nobody writes from a bar they were only
  reading. After a write the dialog shows `12 changed · 3 skipped` and an **Undo** button;
  it never words a partial run as a success.
* **Failure keeps context.** A rejected request leaves the drafted change and the
  selection in place so the person can fix it and retry; an undo whose token expired shows
  the service's sentence and refreshes the canvas, because the store — not the screen —
  holds the truth.

## What stays honest

An outcome a person edited after the run is skipped on undo and reported; a stale preview
table can therefore name rows that the write then refuses. The dialog shows what the
service returned on the write, not what it promised on the preview, and the canvas
refreshes after both.

## Acceptance, as tests

* The UI preview and the CLI preview return the same table on the same unchanged fixture,
  and a preview writes no events.
* One bad selected id is visibly reported as skipped while the good rows update; the copy
  never implies all rows succeeded.
* Undo invokes the shared service and restores the fixture; an expired token is shown
  without an optimistic change.
* An empty selection cannot submit — disabled in the UI, refused by the route.
* A failed request keeps enough context to retry.

## Out of scope

Saved views, bulk editing scores or statements (the service refuses them), a permanent
undo history, keyboard drag-select across pages, and any change to the contract's tool
surface.

## Calls I made

* Wider-than-selection runs resolve ids through `search_outcomes` in the route rather than
  exposing `OutcomeQuery` on a new tool argument.
* Selection lives on the cards and table views only; the matrix keeps single focus.
* The preview table and the apply action share one dialog so the counted set is the set
  offered for writing.
