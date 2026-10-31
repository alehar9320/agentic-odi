# The Signal Inbox

"Catch up" reads the store. A **Signal** is a record of something that actually
changed in the ODI data, produced by `ODIService` at the moment it changed, and
read back by every surface — CLI, MCP client, Studio.

## What emits a signal

`SignalKind` in `packages/core/src/agentic_odi_core/models.py` has exactly six
emitters:

| Kind | Emitted when | Severity |
|---|---|---|
| `job_added` | `add_job` | info |
| `outcome_scored` | an outcome's importance or satisfaction changed | info |
| `opportunity_crossed` | an opportunity score crosses 10, up or down | urgent up, notice down |
| `evidence_ingested` | `add_evidence` | info |
| `evidence_promoted` | `promote_evidence` turns evidence into an outcome | notice |
| `job_map_completed` | a job map covers all 8 Universal Job Map stages | notice |

Deletions emit nothing: removing a record is not news worth interrupting for.
Connector and agent-work kinds belong to
[#95](https://github.com/alehar9320/agentic-odi/issues/95), not here.

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
- **Studio:** the bell badge is `/api/signals/unread-count`. The Catch Up lens
  loads on boot, re-reads after every canvas refresh (including the `canvas_dirty`
  chat frame), and polls every 60 s while the window is visible.

There is no browser-side notification store any more; nothing in the feed is
kept only in `localStorage`.

## The catch-up lens

- **First run is empty.** The feed only contains signals the store recorded.
- **There is no simulator.** No button fabricates a signal. The three example
  signals live in `components/notifications/__fixtures__/signals.ts` and are
  imported by tests only, never by the application; the empty feed instead
  explains the three real triggers (an outcome re-scored, evidence captured, a
  job map completed) and offers **Capture evidence**, which opens the capture
  panel so a real signal can be recorded.
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
