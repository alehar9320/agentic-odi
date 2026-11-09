# Design: Give the Studio a persistent map (#310)

**Source issue:** https://github.com/alehar9320/agentic-odi/issues/310  
**Date:** 2026-10-31  
**Status:** groomed, ready to implement (amended 2026-10-31 — see below)  
**Labels carried over:** `spec`, `opportunity`, `priority/high`, `area/studio`, `theme/navigation`

---

## 1. Value score: 4 / 5

Findability. Today the Studio's only map (`WorkbenchRail`) is a conditional strip that disappears on an empty repository, names only four of eight destinations, has counts that disagree with the panels, has no collapsed state, no keyboard route, and no narrow-screen drawer. After this issue, the rail is a persistent, collapsible sidebar: every destination, a count that matches what the panel shows, a visible active state, a keyboard toggle, and a real drawer on narrow screens — present even on an empty repository.

**One value increment:** A PM opens the Studio on an empty repository and the sidebar is there: Vision, Landscape, Job map, Evidence, Memory, Catch up, Capture, Schedule, Settings, most with a quiet `0`. `Cmd/Ctrl+B` collapses it to icons; clicking Job map opens the empty job map. On a phone the same list opens as a drawer from the bar.

---

## 2. Preconditions / external dependencies

| Dependency | Issue | Notes |
|------------|-------|-------|
| Route-backed active state | #311 | Open issue outside this batch. The active row should be addressable by URL; #311 makes it so. Sequence #311 → #310 → #324 so the URL is the single source of "where am I." |
| Vision panel destination | #312 | Open issue. Until it lands, ship eight rows and add Vision with that panel. |

#311 and #312 are not in this batch. Sequence #310 after them, or treat them as preconditions.

## 2026-10-31 spec amendments (binding)

Reviewed against `main` (@ `ece6529`):
- **A rail already exists.** `apps/studio/src/components/workspace/WorkbenchRail.tsx` renders `<nav class="rail" aria-label="Your work">` with `rail__list`, `rail__status`, `rail__chip`, `rail__count`. It has a test (`WorkbenchRail.test.tsx`). The issue's premise ("the only map is a strip above the conversation") is no longer literally true — **rescope to extend the rail, not rebuild a greenfield map.**
- **What remains genuinely open:** whether the rail is persistent/collapsible, whether its counts match the panels, whether it names all eight destinations, and whether there is a narrow-screen drawer. Rescope to those four questions against the current rail.
- **Count parity is critical:** counts that disagree with panels are worse than no count. Add a test: for each rail item, the count equals the number of rows the panel renders for that item.
- **State the collapse behavior and default state per breakpoint** so the design doesn't drift.
- Keep keyboard toggle + real narrow-screen drawer as acceptance items.

---

## 3. Atomic implementation steps

### Step 1 — Information architecture: nine destinations

Define the nav order and map each to an existing `WorkspacePanelId` (`apps/studio/src/types.ts:236-244`):

| # | Label | `WorkspacePanelId` | Count source | Empty behaviour |
|---|-------|-------------------|--------------|-----------------|
| 1 | Vision | `vision` (new panel, #312) | none; a dot when a vision exists | Vision empty state |
| 2 | Landscape | `landscape` | `canvas.outcomes.length` | "No opportunities yet" |
| 3 | Job map | `jobmap` | `canvas.steps.length` | empty job map |
| 4 | Evidence | `evidence` | `canvas.evidence.length` | "no evidence" guidance |
| 5 | Memory | `memory` | `memory.length`; dot while any observation is `suggested` | empty memory panel |
| 6 | Catch up | `catchup` | `unreadNotificationCount` | "No activity yet" |
| 7 | Capture | `capture` | none | manual capture form |
| 8 | Schedule | `schedule` | `canvas.scheduled_work.length` (`SchedulePanel.tsx:39`) | scheduler |
| 9 | Settings | `settings` | none | Settings |

Until #312 lands, ship eight rows and add Vision when its panel exists. The Schedule destination exists in the union and registry (`panels.tsx:110`) but nothing opens it today — this issue wires `openPanel("schedule")`.

**Test:** unit test that all nine destination labels/ids render in order and each calls `openPanel(id)`.

**Definition of done:** Nine destinations present in order; each opens its panel; Schedule is no longer dead code.

---

### Step 2 — One count hook: `useNavigationCounts()`

Create `useNavigationCounts()`, memoised over `canvas`, `memory`, and `notifications`, so the sidebar, the rail replacement, and any future badge cannot disagree:
- Evidence count = `canvas.evidence.length` (must equal the list length the Evidence panel renders — **count parity**).
- Landscape count = `canvas.outcomes.length`.
- Job map count = `canvas.steps.length`.
- Memory count = `memory.length`.
- Catch up count = unread and not simulated (`StudioContext.tsx:478-481`).
- Schedule count = `canvas.scheduled_work.length`.
- A count above 99 renders `99+`; zero renders `0` (zero is information), not nothing.

**Test:** count-parity test per rail item — for each destination, the count equals the number of rows the panel renders for that item (empty, seeded, and simulated data).

**Definition of done:** Single source of truth for counts; Evidence count equals panel list length; zero renders as `0`.

---

### Step 3 — States and behaviour per breakpoint

- **Expanded** at 1280px and wider: 232px, label, icon, count.
- **Collapsed** between 1024px and 1279px, or when the user collapses it: 56px, icon and count only, label in `title` and `aria-label`, focus ring on the whole row.
- **Drawer** below 1024px, matching the existing lens breakpoint (`theme.css:2046`) and the Tauri desktop window minimum width of 1024 (`src-tauri/tauri.conf.json:19`). 280px wide, over a scrim, `role="dialog"` and `aria-modal`, focus trapped, closes on Escape, scrim click, and navigation.
- Collapse preference is a preference, not a location: `localStorage["studio.sidebar"] = "expanded" | "collapsed"`. Drawer open state is never persisted. URL state belongs to #311.
- Active row uses `activePanel` (`StudioContext.tsx:448`) and `aria-current="page"`.
- Toggle with `Cmd/Ctrl+B` from anywhere except a text field with a selection. Do not claim `Cmd/Ctrl+K` (#323 needs it for the global palette).
- Roving tabindex inside the nav: Up/Down move, Home/End jump, Enter opens. Tab leaves the nav in one press.
- Clicking a row calls `openPanel(id)` (`StudioContext.tsx:1005`); clicking the active row calls `closePanel()` (today's toggle behaviour).
- The bar keeps its bell, settings, and Customize buttons — shortcuts, not the only doors.

**Test:** keyboard navigation (Up/Down/Home/End/Enter/Tab), collapse toggle persistence, drawer open/close on Escape and scrim click, active row `aria-current="page"`.

**Definition of done:** Three breakpoint states work; keyboard nav complete; collapse persisted; drawer traps focus and closes correctly.

---

### Step 4 — Move the demo/offline chip to the sidebar header

The demo chip currently lives inside the rail (`canvasProvenance.ts:26-33`) and disappears with it. Move it to the sidebar header so "DEMO — sample data" is visible from every panel, including Settings. Demo records are excluded from any "your work" total; simulated notifications never contribute to the Catch up count.

**Test:** chip visible on an empty repository and on every panel; demo records excluded from counts.

**Definition of done:** Demo chip visible on every panel including Settings; demo/simulated data excluded from "your work" totals.

---

### Step 5 — Migration: remove `WorkbenchRail`

Remove `WorkbenchRail` rather than shipping two navigations. Its e2e helper (`e2e/workspace.spec.ts:26`) becomes a sidebar locator; its tests move to `Sidebar.test.tsx`. No panel is disabled on an empty repository — every panel has an empty state; the job is to make the destination findable.

**Test:** e2e test covers open, close, collapse, and the drawer; visual snapshots for light/dark × expanded/collapsed.

**Definition of done:** `WorkbenchRail` removed; `Sidebar.test.tsx` and e2e locator in place; visual snapshots exist.

---

## 4. Non-negotiable constraints

- Nine destinations present on a fresh repository, in the stated order, each opens its panel.
- Each count equals the number of records the destination renders (count parity test).
- Active row carries `aria-current="page"` and survives a panel switch.
- `Cmd/Ctrl+B` toggles expanded/collapsed; choice survives reload; collapsed rows still expose their label to assistive technology.
- Below 1024px the sidebar becomes a drawer that traps focus, closes on Escape and scrim click, and does not shift the thread.
- Demo chip visible on every panel, including on an empty repository.
- Light theme uses `var(--surface)`, `var(--line)`, `var(--text)`, `var(--faint)`; no white-alpha fill.

---

## 5. Out of scope

- URL routes, browser history, restored location — #311.
- The global command palette — #323.
- Phone-first shell, offline capture, touch gestures — #93.
- Full keyboard/screen-reader coverage of panel bodies — #92, #115.
- Vision panel content and persistence — #312.

---

## 6. Verification

```bash
npm --prefix apps/studio test -- --run
npm --prefix apps/studio run typecheck
npm --prefix apps/studio run lint
npm --prefix apps/studio run axe   # WCAG sweep (if present in package.json scripts)
```

Tests to add:
- `Sidebar.test.tsx` (moved from `WorkbenchRail.test.tsx`)
- count-parity tests per destination (empty/seeded/simulated)
- e2e test: open, close, collapse, drawer (`workspace.spec.ts` locator → sidebar)
- visual snapshots: light/dark × expanded/collapsed

## Context an implementing agent must read

- `apps/studio/src/components/workspace/WorkbenchRail.tsx` — the existing rail to extend (not replace)
- `apps/studio/src/components/workspace/panels.tsx:45-139` — the eight-destination registry
- `apps/studio/src/types.ts:236-244` — `WorkspacePanelId` union
- `apps/studio/src/state/StudioContext.tsx:448`, `:478-481`, `:1005` — `activePanel`, unread-notification rule, `openPanel`
- `apps/studio/src/components/canvas/SchedulePanel.tsx:39` — `scheduled_work.length`
- `apps/studio/src/lib/canvasProvenance.ts:26-33` — demo chip location to move
- `apps/studio/src/styles/theme.css:2046`, `:3845-3861`, `:3863-3906` — lens breakpoint + rail styles
- `apps/studio/src-tauri/tauri.conf.json:19` — desktop min width 1024
- `apps/studio/e2e/workspace.spec.ts:26` — e2e helper to retarget to sidebar
- #311 — routes (URL state, active row)
- #312 — Vision panel (ninth destination)
- #323 — global palette (don't claim `Cmd/Ctrl+K`)
- #92/#115 — accessibility (panel-body coverage, not this issue)
- #93 — mobile shell (not this issue)

## Open question for the human

#311 (routes) and #312 (Vision) are dependencies outside this batch. Confirm whether to sequence #310 after them, or ship eight rows now and add Vision when #312 lands. Also confirm the collapse breakpoint (1024px vs the existing lens breakpoint) matches the design system.
