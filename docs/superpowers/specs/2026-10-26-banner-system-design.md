# The Banner System — design

**Status:** approved for implementation
**Date:** 2026-10-26
**Scope:** `apps/studio` (React SPA + Tauri shell)

## Intent

The Studio tells the user things in five different ways, and each one was built
alone: `SidecarNotice` (red strip, sidecar down), `OfflineNotice` (amber strip,
no model), `Toasts` (bottom-right, transient), `FailurePanel` (in-place error),
and `.notice` in the transcript. Every new thing the studio needs to say — an
update is ready, a write was rejected, the model changed, a job finished — means
another bespoke component with its own markup, its own CSS, and its own
accessibility story.

This is the wrong shape for a product whose whole premise is that the studio is
always telling you where you are. The banner system replaces the one-off strips
with **one catalog, one store, and one renderer**, so a new banner is a data
entry, not a component.

The organizing idea: *a banner is a statement about the state of the studio.* It
has a severity, a life (persistent until resolved, or transient), optional
actions, and an identity that lets it be raised, updated, and resolved as its
condition changes. Everything else is a detail of that idea.

## Goals

1. **One system, any number of banners.** Raising ten banners degrades
   gracefully: they order by severity, cap at a visible limit, and the rest
   collapse behind a count. Nothing overlaps, nothing stacks off-screen.
2. **Modularized and reusable.** A new banner is one entry in a declarative
   catalog plus a `raise()` call. No new component, no new CSS class.
3. **Don't repeat ourselves.** Behavior that is expensive to get right —
   live-region semantics, focus management, keyboard dismissal, pause-on-hover,
   reduced-motion — comes from `@radix-ui/react-toast` (already vendored
   transitively at `1.3.1`), not from hand-rolled `setTimeout` and `role`
   guessing. The system is headless; the Studio owns every pixel.
4. **Consistent by construction.** Severity maps to one token set. Every banner
   is titled, described, and actioned the same way, in both themes.
5. **Two docks, one model.** A persistent banner docks as a page strip; a
   transient one docks in the corner. Both are the same `Banner` type.
6. **Resolvable, not just dismissible.** A banner raised for a condition is
   resolved when the condition clears (sidecar back → strip gone), so stale
   warnings cannot linger.

## Non-goals

- **Not a notification center.** The Catch Up feed stays where it is; banners
  are the live, on-screen layer, not a history.
- **Not a replacement for `FailurePanel`.** A failure shown *in place of the
  thing that failed* is a different idea. `FailurePanel` keeps its job.
- **No new styling system.** Banners use the existing CSS custom properties and
  the existing component vocabulary.
- **No banner authored by the model.** The catalog is owned by the client. The
  agent does not compose banners in v1; it raises them through named kinds.
- **No server round-trip.** Banners are client state.

## Architecture

Three layers and one type.

```
┌─────────────────────────── apps/studio/src/banners ─────────────────────────┐
│                                                                             │
│  catalog.ts            store.ts                BannerProvider.tsx           │
│  ┌────────────┐        ┌──────────────┐        ┌──────────────────┐         │
│  │ kinds +    │───────▶│ raise /      │───────▶│ context +        │         │
│  │ defaults   │        │ resolve /    │        │ useBanner()      │         │
│  │ + severity │        │ dismiss /    │        │ + raiseBanner()  │         │
│  │ + life     │        │ order / cap  │        └────────┬─────────┘         │
│  └────────────┘        └──────────────┘                 │                   │
│                                                          ▼                  │
│                                              BannerStack.tsx                 │
│                                       Radix Toast primitives + Banner        │
│                                       ┌─────────────────────────────┐        │
│                                       │ Toast.Provider / Region     │        │
│                                       │ Toast.Root (duration=∞ or N)│        │
│                                       │ Toast.Title / Description   │        │
│                                       │ Toast.Action / Toast.Close  │        │
│                                       └─────────────────────────────┘        │
└─────────────────────────────────────────────────────────────────────────────┘
```

### The type

```ts
type BannerSeverity = "info" | "success" | "warning" | "critical";
type BannerLife = "persistent" | "transient";
type BannerDock = "top" | "corner";

interface BannerAction { label: string; intent: string; tone: "primary" | "ghost"; }

interface BannerSpec {
  kind: BannerKind;          // key into the catalog — the identity, and the dedupe key
  title?: string;            // overrides the kind's default
  body?: string;
  severity?: BannerSeverity;
  life?: BannerLife;
  durationMs?: number;       // transient only
  actions?: BannerAction[];
  dismissible?: boolean;
}

interface Banner extends Required<...> { id: string; kind: BannerKind; raisedAt: number; }
```

`kind` is the identity. Raising the same kind twice **updates** the existing
banner rather than adding a second — so a retry loop cannot paint ten copies of
the same warning.

### The catalog

A flat record of kinds. Each entry supplies the defaults a caller may override:

| kind | severity | life | dock | dismissible | actions |
|---|---|---|---|---|---|
| `sidecar-down` | critical | persistent | top | yes | Recheck, Start the sidecar |
| `model-offline` | warning | persistent | top | no | Capture an outcome, Map the job, Set your context |
| `update-available` | info | persistent | top | yes | Install, Later |
| `update-ready` | success | persistent | top | yes | Restart |
| `write-rejected` | critical | persistent | top | yes | — |
| `info` | info | transient | corner | yes | — |
| `success` | success | transient | corner | yes | — |
| `error` | critical | transient | corner | yes | — |

`info` / `success` / `error` are the kinds that absorb today's `pushToast`, which
keeps the existing call sites working unchanged.

### The store

A pure module — no React — so the ordering and capping rules are testable in
isolation:

- `raise(state, spec, now)` → upsert by `kind`, stamp `id` and `raisedAt`.
- `resolve(state, kind)` → remove (condition cleared).
- `dismiss(state, id)` → remove and remember the kind as dismissed.
- `select(state)` → order by severity weight, then `raisedAt`; split into
  `visible` (first `maxVisible`) and `overflow` (the count behind "+N more").

Severity weight: `critical > warning > info > success` — a "success" banner never
pushes a "critical" one off the cap.

`BannerProvider` wraps the store in React, exposes `raiseBanner`, `resolveBanner`,
`dismissBanner`, and the selected view. It composes *inside* `StudioProvider` so
`useStudio().pushToast` delegates to it, and `useBanner()` is available to any
component without going through the studio god-object.

### The renderer

`BannerStack` renders the two docks. It maps each `Banner` to a `Banner`
component, which wraps Radix `Toast.Root`:

- `duration={life === "persistent" ? Infinity : durationMs}` — a persistent
  banner never auto-expires.
- `type` maps to Radix's `foreground`/`background` for correct politeness
  (`critical`/`warning` interrupt; `info`/`success` wait their turn).
- `role="status"` for quiet severities, `role="alert"` for `critical`.
- Actions render through `Toast.Action`; dismiss through `Toast.Close`.
- Severity drives one class: `banner--{severity}`.

## Migration

| Today | Becomes |
|---|---|
| `SidecarNotice.tsx` | `raiseBanner({ kind: "sidecar-down" })` on unreachable; `resolveBanner` on recovery |
| `OfflineNotice.tsx` | `raiseBanner({ kind: "model-offline" })` |
| `Toasts.tsx` | the corner dock of `BannerStack` |
| `.sidecar-notice`, `.offline`, `.toast*` CSS | one `.banner*` token block |

`pushToast(kind, message)` keeps its signature and maps to the matching
transient kind, so its ~30 call sites in `StudioContext` are untouched.

## Testing

- `store.test.ts` — upsert dedupe, resolve, dismiss, severity ordering, cap and
  overflow. Pure, fast, no DOM.
- `catalog.test.ts` — every kind has complete defaults; kinds referenced by the
  migration exist.
- `BannerStack.test.tsx` — renders multiple banners, orders them, collapses
  overflow, fires actions, dismisses, and asserts the live-region roles.
- `Banner.visual.test.tsx` — one Chromatic snapshot per severity in both docks.

## What is left to the builder

- Exact corner-vs-top offsets and the collapse affordance's wording.
- Whether `update-available` wires to `useUpdater` in this change or the next.
- The precise animation, kept inside the existing reduced-motion guard.
