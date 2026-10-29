# Conversation-first studio — implementation plan

**Design:** `docs/superpowers/specs/2026-10-21-conversation-first-studio-design.md`
**Branch:** `feat/conversation-first-studio`

## 1. Shell

- `App.tsx`: drop `Sidebar`, the collapse state, and `Cmd/Ctrl+B`. Render
  `StudioBar`, a `stage__split` with the thread column (`WorkbenchRail` +
  `ChatStage`) and the docked `WorkspacePanel` when a view is open. `Esc`
  closes the view.
- `components/layout/StudioBar.tsx` (new): home, new conversation, catch-up,
  connection status, settings. Keeps the existing accessible names
  (`Go to home`, `New conversation`, `Open settings`, `Catch up
  notifications`).
- `components/layout/Sidebar.tsx`: delete.

## 2. Rail

- `components/workspace/WorkbenchRail.tsx` (new): chips derived from canvas
  state, counts, `aria-current` for the open view, toggling. Renders `null`
  when there is nothing to show.
- CSS: `.rail`, `.rail__list`, `.rail__chip`, `.rail__count`, responsive
  horizontal scroll.

## 3. Lens

- `WorkspacePanel.tsx`: docked sheet, header with close, body scroll, footer
  with the panel's conversational exit. Mobile overlay + scrim via
  `useMediaQuery`.
- `panels.tsx`: definitions for `catchup`, `landscape`, `jobmap`, `evidence`,
  `capture` (offline), `settings`; each carries `talk?: { label, intent }`.
  Remove `impact`.
- `types.ts`: drop `"impact"` from `WorkspacePanelId`.

## 4. Conversational steps

- `StudioContext`: remove `pendingSimOutcome`, `requestSimulate`,
  `clearPendingSimOutcome`; add `ask(intent)` — close the lens, send the
  intent.
- `OutcomeCard`: `Simulate` → `ask(...)`, `Ask` → `ask(...)`.
- `JobMap`: remove the add-step form and `addStep` use; keep phase map,
  edit, delete.
- `lib/commands.ts` + `ChatStage`: `/impact` sends a bet to the agent;
  `/capture` sends a capture intent when a model is live and opens the offline
  form when it is not. Panel commands = the views that still exist.

## 5. Sidecar

- `apps/studio-api/.../chat.py`: one added block in `SYSTEM_PROMPT` making the
  thread the home of every artifact and forbidding "open the panel" answers.

## 6. Tests

- Update `App.test.tsx`: the composer survives an open view; close control
  name; slash-command behaviour; first-run surface interaction.
- Update `JobMap.test.tsx` and `OpportunityLandscape.test.tsx` mocks.
- Add `WorkbenchRail.test.tsx` (derivation, counts, toggling, hidden when
  empty) and `WorkspacePanel.test.tsx` (footer sends, close restores focus).

## 7. Housekeeping

- Remove sidebar CSS; add bar/rail/lens CSS; motion + reduced-motion.
- Rewrite the Interface table and slash-command table in
  `docs/living-studio.md`; update the README paragraph that mentions the
  drawer and full-screen surfaces.
- `npm run lint`, `npm run typecheck`, `npm test -- --run`, `npm run build`.
- Python: `ruff`, `mypy`, `pytest apps/studio-api`.
