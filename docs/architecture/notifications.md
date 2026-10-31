"Catch up" reads the store. A **Signal** is a record of something that actually
changed in the ODI data, produced by `ODIService` at the moment it changed, and
read back by every surface — CLI, MCP client, Studio.

## What emits a signal

`SignalKind` in `packages/core/src/agentic_odi_core/models.py` has these
emitters:

| Kind | Emitted when | Severity |
|---|---|---|
| `job_added` | `add_job` | info |
| `outcome_scored` | an outcome's importance or satisfaction changed | info |
| `opportunity_crossed` | an opportunity score crosses 10, up or down | urgent up, notice down |
| `evidence_ingested` | `add_evidence` | info |
| `evidence_promoted` | `promote_evidence` turns evidence into an outcome | notice |
| `job_map_completed` | a job map covers all 8 Universal Job Map stages | notice |
| `score_moved` | a recorded snapshot moves the score past the policy threshold | urgent up, notice down |
| `decision_superseded` | a new decision supersedes the live one for a job | notice |
| `bet_due` | a planned or running bet reaches its measure-by date | notice |
| `coverage_gap` | a job-map stage still has no outcomes | info |

The first six are emitted by `ODIService` at the moment of the write.
`score_moved` and `decision_superseded` are also written at write time (a
snapshot, a superseding decision); `bet_due` and `coverage_gap` are the two
kinds no write can see, so `emit_know_signals` records them by reading the
store. All ten carry a deterministic discriminator, so a re-run writes nothing
new.

Deletions emit nothing: removing a record is not news worth interrupting for.
Connector and agent-work kinds belong to
[#95](https://github.com/alehar9320/agentic-odi/issues/95), not here.

## The Monday digest and the spine

`odi know digest [--since 7d] [--out FILE]` refreshes the inbox, then writes a
deterministic markdown digest of the signals inside the window, grouped by the
four know kinds. It is deterministic: the same store and the same window
produce byte-identical output. An empty window prints `No changes in this
period.` — never a fabricated row.

`odi know spine [--job ID]` walks the evidence chain stage by stage —
`captured → scored → decided → bet → measured` — and shows the first stage with
no records and what would unblock it. Where the chain stops is stated, not
guessed at.

## The notification policy

The interruption policy is one stored source of truth, not a client setting.
Signal kinds and the score-move threshold live behind `GET`/`PUT
/api/notification-rules`; the CLI digest reads the same policy and Settings
edits it. A kind turned off stops interrupting everywhere while the signal
stays visible in the feed. The defaults are documented in
`agentic_odi_core.signals.default_rules`: bet-due and superseded decisions
interrupt, score movement interrupts past ±0.5, and coverage gaps are shown but
never interrupt.

## Identity and dedupe

`fingerprint = sha256("kind|subject_kind|subject_id|discriminator")`. Recording a
signal whose fingerprint already exists returns the existing record instead of
creating a second one, so re-running an ingest cannot flood the inbox.

## Storage

The store is append-only, so signals are events too: `SIGNAL_CREATED`,
`SIGNAL_READ`, `SIGNAL_DISMISSED` in the same `events` table as everything else,
replayed by `SQLiteRepository` on open. Read and dismissed timestamps survive a
reload. A signal is **never** cascade-deleted with the record it describes — the
inbox is a history, and history outlives the thing it is about.

## Attention budget

`SignalBudget` (`packages/core`) caps what the inbox surfaces: at most
`AGENTIC_ODI_SIGNAL_BUDGET` signals per day, default 20. `urgent` signals bypass
the cap. Suppressed signals stay in the store and stay reachable by id; they are
only hidden from the feed and the unread count.

## Surfaces

- **MCP tools:** `list_signals`, `mark_signal_read`, `dismiss_signal`
  (registered in `contract.py`, so the CLI's local backend must implement them
  too — `tests/contract/test_cli_contract.py` enforces that).
- **CLI:** `odi signals list [--unread] [--limit N] [--json]`, `odi signals
  unread`, `odi signals read <id>`, `odi signals dismiss <id>`. An unknown id
  exits non-zero.
- **Studio API:** `GET /api/signals`, `GET /api/signals/unread-count`, `POST
  /api/signals/{id}/read`, `POST /api/signals/{id}/dismiss` — under both the
  `local` and `mcp` backends; unknown id is 404.
- **Studio:** the bell badge is `/api/signals/unread-count`. It counts the unread
  signals the shared notification policy lets interrupt, so a kind turned off in
  Settings (or a coverage gap under the defaults) stays real in the feed without
  ringing the bell. The Catch Up lens
  loads on boot, re-reads after every canvas refresh (including the `canvas_dirty`
  chat frame), and polls every 60 s while the window is visible.

There is no browser-side notification store any more; nothing in the feed is
kept only in `localStorage`.

## The catch-up lens

- **First run is empty.** The feed only contains signals the store recorded.
  Nothing in the Studio can fabricate a signal: the three example signals live
  only in `apps/studio/src/components/notifications/__fixtures__/signals.ts`,
  imported by tests, never by the app. When the feed is empty it names the three
  real triggers and offers **Capture evidence**, which opens the capture panel.
- Cards are reachable and activatable by keyboard alone; activating one marks the
  signal read and opens the lens on the record it names. Filters are toggle
  buttons with `aria-pressed`, not tabs. The feed itself is a named `region`
  landmark so screen-reader users can jump straight to it.

## The eight stages are one constant

`JOB_STAGE_ORDER` / `job_stage_catalog()` in `packages/core` is the only copy of
the Universal Job Map stages. `scripts/gen_job_stages.py` renders them to
`apps/studio/src/domain/jobStages.ts`, which `JobMap.tsx` and the UI catalog both
import; `tests/scripts/test_gen_job_stages.py` fails if the generated file is
stale. Regenerate after editing the Python constant:

```bash
uv run python scripts/gen_job_stages.py
```

## Keyboard model

There is no mouse-only surface in the Catch Up feed or the job map:

- Phase cards are real buttons with `aria-pressed`; Tab reaches them and
  Enter/Space toggles the filter.
- Step rows take focus, Arrow Up/Down swap them with their neighbour, and every
  action (Edit, Remove, Move up, Move down) is a normal button.
- The changelog and connector-suggestion dialogs use `useFocusTrap`
  (`apps/studio/src/lib/useFocusTrap.ts`): focus moves into the dialog on open,
  Tab/Shift+Tab wrap at the edges, and focus returns to the opener on close.
