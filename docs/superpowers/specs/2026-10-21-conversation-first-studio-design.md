# A conversation-first Living Studio — design

**Status:** approved for implementation
**Date:** 2026-10-21
**Scope:** `apps/studio` shell and workspace views; one paragraph of the
sidecar's agent prompt.

## Intent

The Studio is an agent. Today the agent is good at talking, but the room it
talks in does not know that. A permanent 264px drawer lists seven
destinations, and opening any of them **replaces the conversation**: the
composer disappears, the transcript disappears, and the user is left in a
form. That is a dashboard with a chat box bolted to the side. It asks the user
to translate their intent into a place, and it makes the conversation the
smallest thing on screen.

The Studio should feel like one intelligence in one room:

- **The conversation is the room.** It owns the stage at every moment,
  including while the user is looking at something the conversation produced.
- **Artifacts are items in the thread.** A thesis, an outcome, a simulation,
  a quote arrives *in* the conversation, at the point the agent produced it.
  The drawer is a lens on those items, never a destination that hides them.
- **Every step is spoken.** Capture, score, simulate, decide, confirm: the
  normal path is a sentence to the agent. A form is the degraded, offline path,
  not the product.
- **Chrome stays at a whisper.** One 52px bar. One quiet rail of artifacts,
  visible only once there is work to look at. Everything else is whitespace.

The test for every decision: *does the conversation still feel like the thing
you are using?* If a surface can answer yes only by occupying a separate
screen, it is designed wrong.

## Goals

1. Opening a workspace view never removes the transcript or the composer.
   The conversation keeps the stage; the view makes room for itself.
2. Navigation shrinks from a seven-item drawer to a single, data-driven rail
   above the conversation. Nothing appears in it before the conversation
   produces something.
3. Capture and impact simulation stop being forms. They become intents the
   agent handles, rendering their results as inline surfaces.
4. Every workspace view ends in a conversational exit: one sentence that takes
   the user back to the thread with the right question already asked.
5. The offline path stays honest: with no model, direct capture remains
   reachable, and the UI says why.

## Non-goals

- No new runtime dependencies.
- No redesign of the generative UI catalog, the cards, or the protocol.
- No change to the ODI domain model, the MCP tools, or the persistence layer.
- No new animations that fight `prefers-reduced-motion`.
- No mobile-specific rewrite: the existing 1023px breakpoint is the seam.

## Experience

```
┌──────────────────────────────────────────────────────────────────────┐
│ ◍ Living Studio                       ＋   ● Live   ⚙   🔔           │  52px
│                                                                      │
│   Landscape · 6      Job map · 8      Evidence · 3                   │  rail
│                                                                      │
│                    ┌───────────────────────────────┐                 │
│                    │  the conversation, 720px       │   ┌───────────┐ │
│                    │  prose, cards, traces          │   │  a lens   │ │
│                    │                                │   │  (520px)  │ │
│                    └───────────────────────────────┘   │           │ │
│                    ┌───────────────────────────────┐   │  Talk ↗   │ │
│                    │  Ask about a job, an outcome…  │   └───────────┘ │
│                    └───────────────────────────────┘                 │
└──────────────────────────────────────────────────────────────────────┘
```

### The bar

Brand (home), new conversation, connection status, settings, catch-up. It is
the only persistent chrome, and it holds no navigation. The old left drawer is
deleted: a drawer that competes with the thread for width is a second product.

### The rail

Three to four chips, derived from real state rather than a fixed menu:

| Chip | Appears when | Opens |
|---|---|---|
| `Landscape · N` | outcomes exist | opportunity landscape |
| `Job map · N` | steps exist | universal job map |
| `Evidence · N` | outcomes carry evidence | evidence |

The rail is centered on the same 720px column as the thread, so it reads as a
label above the conversation rather than a toolbar beside it. Before the first
artifact, it renders nothing — the first screen is a greeting and a composer.
Chip labels must start with the view name so `Landscape · 6` is still findable
as "landscape".

### The lens

`WorkspacePanel` becomes a docked sheet on screens ≥1024px: 520px wide, full
height, on the right edge, with the conversation still live to its left. It is
not modal; the composer keeps focus and the user can keep typing. On narrow
screens it becomes a full-height overlay with a scrim and a close control.

The sheet keeps a header (title, one-line purpose), a scrolling body, and a
footer that is the point of the whole design:

> A lens on the conversation.
> **[ Ask about this ]**

The button closes the lens and sends a panel-specific question — "Looking at
my landscape, which opportunity should I chase first, and why?" — so leaving a
view is always a return to the thread, not a return to a menu.

### The steps

| Was | Now |
|---|---|
| Capture: job select, statement field, two sliders, submit | `/capture` or "I heard something from a customer…" → the agent asks, scores, and renders the card. The form survives only in offline mode, reachable from the offline notice and `/capture` when no model answers. |
| Impact: outcome select, bet field, example panel | "Simulate…" on a card or `/impact` sends the bet to the agent, which renders an `impact-simulation` surface inline. |
| Job map: add-step form | "Walk me through the job" is the footer action; steps still edit and delete in place. |
| Sidebar: seven destinations | Rail: the three artifacts that exist. Settings, catch-up, context live in the bar or the setup conversation. |

### Motion

One gesture, everywhere: the lens slides in 12px and fades over 220ms; the rail
fades in once. Reduced motion removes both. No spring, no bounce, no stagger
inside a view.

## Constraints

- React 19 + Vite + vitest; no new packages.
- State stays in `StudioContext`; no new store.
- Slash commands are still local and still work offline.
- Tests must assert the new invariant directly: opening a view leaves the
  composer and transcript in the document.
- README and `docs/living-studio.md` change in the same commit.

## Left to the builder

Exact spacing, the rail's icon set, the panel transition curve, and the
wording of each panel's conversational exit. Craft, not contract.

## Calls made in this design

- **Delete the left drawer instead of shrinking it.** The rail already carries
  every artifact that exists, and Settings/catch-up are controls, not places.
- **Dock the lens instead of overlaying it.** An overlay would cover the
  conversation it is supposed to serve; a dock makes room and keeps both true.
- **Keep direct capture, offline only.** Removing it would break the promise in
  the offline notice; making it primary would break the conversational rule.
