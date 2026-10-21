# First-run wizard for The Living Studio — design

**Status:** approved for implementation
**Date:** 2026-10-21
**Scope:** `apps/studio` (React SPA + Tauri shell). No sidecar, MCP, or API changes.

## Intent

A new user reaches The Living Studio and immediately meets a context
conversation: four good questions about their product, customer, job, and
friction. What nothing explains first is the product they are answering inside —
that a job map, a scored opportunity landscape, an impact simulation, and a
direct capture surface exist, and which one to start with.

The first-run wizard answers that in under a minute, then gets out of the way.
It is a short, skippable tour that ends in a real destination, not a slideshow.
The context conversation remains the deeper first step; the tour is the front
door that leads to it or to the surface the user picked.

## Goals

1. Orient a first-time user: the job-to-be-done premise, the four starting
   points, and the live state of their instruments.
2. End on a **first move**: open the chosen surface, or hand the job path to the
   context conversation that creates the job.
3. Be resumable, skippable, and replayable. Never trap a user, never nag.
4. Arrive as an isolated module with a feature flag. `App.tsx` gains two lines;
   the chat, canvas, and sidecar code do not know the wizard exists.
5. Behave like a first-class dialog: focus trap, Escape to skip, focus returned
   on close, reduced-motion support, mobile layout, no layout shift.

## Non-goals

- **No second context conversation.** The existing `SetupConversation` remains
  the place where product, customer, job, and friction are captured.
- **No backend onboarding state.** A local-first studio remembers locally.
- **No product tour with spotlight overlays.** The wizard is the orientation;
  the surfaces are the reveal.
- **No second settings panel.** The readiness step surfaces only the three model
  fields a blocked user needs, through the same `saveSettings` path.

## The flow

Four steps, one progress rail, never more than two actions on screen.

| Step | Question | What it does |
|---|---|---|
| 1. Welcome | *What is this?* | The JTBD premise, plus the three moves: map the job, score the outcomes, test the bet. |
| 2. Starting point | *Where do I begin?* | Four goal cards: name the job, read the landscape, simulate a bet, capture an outcome. |
| 3. Instruments | *Will it work?* | Live sidecar, MCP, and model status. If the model is down, the three config fields are inline with **Save & test**. |
| 4. First move | *What happens next?* | The chosen destination and what the user walks away with. One primary action. |

The tour opens over the shell on the first visit. The context conversation is
already waiting behind it, so skipping the tour lands exactly where the studio
used to start.

### Destinations

- **Name the job** → `openSetup()`: the context conversation asks its four
  questions, then creates the job and brief.
- **Read the landscape** / **Simulate a bet** / **Capture an outcome** →
  `openPanel(panel)`. Opening a surface already dismisses the setup conversation
  by design, leaving the sidebar's **Your context** nudge in place.

Skip is a quiet footer action on steps 1–3; `Escape` exits from any step.
Skipping and finishing are remembered. The tour is replayable from
**Settings → Replay the welcome tour**.

Progress is persisted after every transition, so a user who closes the app on
step 3 resumes on step 3.

## Architecture

```
apps/studio/src/
├── features/
│   ├── flags.ts            ← generic feature-flag resolution (query → storage → env)
│   └── flags.test.ts
├── onboarding/
│   ├── content.ts          ← steps + goals, the only place copy lives
│   ├── machine.ts          ← pure state transitions (no React, no DOM)
│   ├── storage.ts          ← versioned localStorage read/write, defensive
│   ├── context.ts          ← context + useOnboarding hook
│   ├── OnboardingProvider.tsx  ← auto-open, persistence, replay
│   ├── FirstRunWizard.tsx  ← the dialog (reads StudioContext for health + actions)
│   ├── steps.tsx           ← presentational step content
│   └── onboarding.css      ← colocated styles, same tokens as theme.css
└── App.tsx                 ← <OnboardingProvider><StudioShell/><FirstRunWizard/></…>
```

Three separations keep this from becoming spaghetti:

- **Content is data.** `content.ts` exports typed steps and goals. Changing copy
  or adding a goal is a data edit, not a JSX edit.
- **State is pure.** `machine.ts` has no React import and no storage access, so
  the flow is unit-tested as plain functions. Persistence sits behind
  `storage.ts`; the provider only wires them together.
- **The UI is one component.** It reads the studio context but writes through
  existing actions (`openPanel`, `openSetup`, `saveSettings`,
  `checkConnections`). No new global state for the canvas.

### Supporting change

`StudioContext` gains `sidecarReachable` and `checkConnections()` so the
readiness step can re-probe after a repair. `checkConnections` is the same
probe boot already runs, callable against unsaved config.

### Feature flag

`firstRunWizard` defaults **on** so the MVP is visible, and is resolved in this
order:

1. URL: `?flags=firstRunWizard:off` (QA without a rebuild)
2. `localStorage["studio.flags.firstRunWizard"]` (`on`/`off`)
3. `VITE_STUDIO_FIRST_RUN_WIZARD` (`1`/`0`, `true`/`false`, `on`/`off`)
4. Default: on

When the flag is off the provider still mounts but is inert: no dialog, no
replay entry in Settings, no storage writes.

## Design language

The wizard inherits the studio's dark surface and indigo accent and adds only
what a modal needs: a blurred backdrop, a soft top glow, 20px radius, and a
single accent. One idea per screen, generous whitespace, sentence-case copy with
no exclamation marks. Numbers (`1 / 4`) and a segmented hairline rail replace a
decorative stepper.

Motion is 220–320ms with an ease-out curve, and fully removed under
`prefers-reduced-motion`. Under 640px the panel becomes full-height, goal cards
stack, and controls grow to 44px.

Accessibility: `role="dialog"` + `aria-modal`, labelled by the step heading,
focus moved to the heading on every step, Tab trapped inside the panel, Escape
skips, focus restored to the opener on close, status rows announce state as text
rather than colour alone.

## Trade-offs

- **Auto-open vs. discovery.** Auto-opening is right for a first run and wrong
  forever after; the flag plus stored completion handles both. Settings replay
  covers "I closed it too fast."
- **Tour then context.** Asking for a product and job before explaining the tool
  is putting the cart first. The tour explains, then the context conversation
  personalizes; a user who picks a surface can still set context later from the
  sidebar.
- **Versioned completion.** `ONBOARDING_VERSION` is stored with the state. A
  future content revision can deliberately re-introduce the tour by bumping it.

## Acceptance criteria

- With no stored onboarding state and the flag on, the dialog appears once.
- All four steps are reachable without a mouse; Escape skips; focus stays inside.
- Finishing sends the user to the selected destination and records completion.
- Replaying from Settings restarts at step 1 regardless of completion.
- With the flag off, nothing renders and Settings shows no replay entry.
- `npm --prefix apps/studio run typecheck`, `run lint`, `test -- --run`, and
  `run build` all pass.
