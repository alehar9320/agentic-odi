# Banner System Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Replace the hand-rolled "tell the user something" surfaces that state a condition *about the studio* — the sidecar strip, the offline strip, the toast stack — with one typed, modular banner system that renders any number of banners consistently. `FailurePanel` and the transcript `.notice` stay, by design (see the spec's non-goals).

**Architecture:** A dependency-free store module owns ordering, dedupe, and capping. A catalog module owns every banner kind's defaults. A provider bridges the store into React. A stack renders both docks through `@radix-ui/react-toast` (already vendored at `1.3.1`), so live-region semantics, timers, and dismissal come from the library, not hand-rolled code.

**Tech Stack:** React 19, TypeScript, Vite, Vitest + @testing-library/react, `@radix-ui/react-toast@1.3.1`, existing `theme.css` tokens.

**Spec:** `docs/superpowers/specs/2026-10-26-banner-system-design.md`

## Global Constraints

- React 19 + TypeScript, no new styling system — reuse the CSS custom properties in `apps/studio/src/styles/theme.css`.
- `@radix-ui/react-toast` is pinned to the version already in `package-lock.json` (`1.3.1`); it must be added to `dependencies` in `apps/studio/package.json`.
- Banner kinds are a closed set owned by the client; the agent never composes banners.
- Severity order is `critical > warning > info > success`; default `maxVisible` is 3.
- `pushToast(kind, message)` keeps its exact signature so its ~30 call sites in `StudioContext.tsx` do not change.
- All new unit tests run under the existing jsdom config (`npm test`); visual tests are `*.visual.test.tsx` only.
- Every comment earns its place: explain *why*, never narrate the diff.

## Review Focus

- **Same kind raised twice** — must update in place, not duplicate (a retry loop must not paint ten copies).
- **More banners than `maxVisible`** — the lowest-severity ones must collapse into an overflow count, never overlap or push off-screen.
- **A `critical` banner alongside a `success` banner** — severity ordering must keep `critical` visible.
- **A persistent banner left alone** — it must not auto-expire; only `transient` banners get a duration.
- **A dismissed kind raised again** — dismissing is per-instance; a newly raised banner must reappear.

---

### Task 1: Banner types and catalog

**Files:**
- Create: `apps/studio/src/banners/types.ts`
- Create: `apps/studio/src/banners/catalog.ts`
- Test: `apps/studio/src/banners/catalog.test.ts`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `type BannerSeverity = "info" | "success" | "warning" | "critical"`
  - `type BannerLife = "persistent" | "transient"`
  - `type BannerDock = "top" | "corner"`
  - `interface BannerAction { label: string; intent: string; tone: "primary" | "ghost" }`
  - `type BannerKind` — the eight kind strings
  - `interface BannerSpec` — caller input (see spec)
  - `interface Banner` — resolved banner with `id`, `kind`, `severity`, `life`, `dock`, `title`, `body`, `durationMs`, `actions`, `dismissible`, `raisedAt`
  - `interface BannerDefaults` — the catalog entry shape
  - `const BANNER_CATALOG: Record<BannerKind, BannerDefaults>`
  - `function severityWeight(severity: BannerSeverity): number`
  - `function resolveSpec(spec: BannerSpec): Omit<Banner, "id" | "raisedAt">`

- [x] **Step 1: Write the failing test** in `catalog.test.ts` — assert every `BannerKind` has a complete entry, that `sidecar-down` is `critical`/`persistent`/`top` and dismissible, that `model-offline` is `warning`/`persistent` and not dismissible, and that `severityWeight` orders critical above warning above info above success.
- [x] **Step 2: Run `npm test -- banners/catalog` and watch it fail** (module missing).
- [x] **Step 3: Implement `types.ts` and `catalog.ts`.**
- [x] **Step 4: Run `npm test -- banners/catalog`** — PASS.
- [x] **Step 5: Commit.**

### Task 2: The store (pure)

**Files:**
- Create: `apps/studio/src/banners/store.ts`
- Test: `apps/studio/src/banners/store.test.ts`

**Interfaces:**
- Consumes: `Banner`, `BannerSpec`, `resolveSpec`, `severityWeight` from Task 1.
- Produces:
  - `interface BannerState { banners: Banner[]; dismissed: Set<string> }`
  - `const EMPTY_BANNER_STATE: BannerState`
  - `function raiseBanner(state, spec, now?): BannerState` — upsert by `kind`
  - `function resolveBanner(state, kind): BannerState`
  - `function dismissBanner(state, id): BannerState`
  - `function selectBanners(state, maxVisible?): { visible: Banner[]; overflow: number }`

- [x] **Step 1: Write failing tests** — dedupe by kind; resolve removes; dismiss removes; `selectBanners` orders `critical` before `success`; cap at 3 with overflow counted; a later raise of a dismissed kind reappears.
- [x] **Step 2: Run `npm test -- banners/store` and watch it fail.**
- [x] **Step 3: Implement `store.ts` as pure functions.**
- [x] **Step 4: Run `npm test -- banners/store`** — PASS.
- [x] **Step 5: Commit.**

### Task 3: The provider and hook

**Files:**
- Create: `apps/studio/src/banners/BannerProvider.tsx`
- Test: `apps/studio/src/banners/BannerProvider.test.tsx`

**Interfaces:**
- Consumes: the store (Task 2).
- Produces:
  - `interface BannerApi { raise(spec): void; resolve(kind): void; dismiss(id): void; view: { visible; overflow } }`
  - `function BannerProvider({ children, maxVisible? })`
  - `function useBanner(): BannerApi`

- [x] **Step 1: Write failing tests** — `renderHook` wrapped in `BannerProvider`; raise then read `view.visible`; raise same kind twice yields one; resolve clears it.
- [x] **Step 2: Run `npm test -- banners/BannerProvider` and watch it fail.**
- [x] **Step 3: Implement the provider with `useReducer` over the store.**
- [x] **Step 4: Run the test** — PASS.
- [x] **Step 5: Commit.**

### Task 4: `Banner` and `BannerStack` renderer

**Files:**
- Create: `apps/studio/src/banners/Banner.tsx`
- Create: `apps/studio/src/banners/BannerStack.tsx`
- Modify: `apps/studio/src/styles/theme.css`
- Test: `apps/studio/src/banners/BannerStack.test.tsx`

**Interfaces:**
- Consumes: `Banner` type (Task 1), `BannerApi` (Task 3).
- Produces: `function Banner({ banner, onDismiss })`, `function BannerStack({ dock })`.

- [x] **Step 1: Write failing tests** — renders one banner's title and body; `critical` gets `role="alert"`, `info` gets `role="status"`; an action button calls its `intent`; overflow renders a "+N" affordance.
- [x] **Step 2: Run `npm test -- banners/BannerStack` and watch it fail.**
- [x] **Step 3: Implement `Banner.tsx` on Radix `Toast.Root` and `BannerStack.tsx` on `Toast.Provider`/`Toast.Viewport`; add the `.banner*` token block to `theme.css`.**
- [x] **Step 4: Run the test** — PASS.
- [x] **Step 5: Commit.**

### Task 5: Migrate the existing notices and toasts

**Files:**
- Modify: `apps/studio/src/App.tsx` — mount `BannerProvider` and `BannerStack`; delete `Toasts`/`SidecarNotice` mounts
- Add: `apps/studio/src/banners/BannerBridge.tsx` — raise/resolve `sidecar-down` and `model-offline` from studio state, route actions and dismissal
- Add: `apps/studio/src/banners/BannerToasts.tsx` — turn each `pushToast` into a keyed banner
- Delete: `apps/studio/src/components/notices/SidecarNotice.tsx` and `apps/studio/src/components/chat/OfflineNotice.tsx` (now kinds, not components)
- Delete: `apps/studio/src/components/Toasts.tsx` and its test
- Note: `pushToast` keeps its signature, so `StudioContext.tsx` did not change.

- [x] **Step 1: Write/adjust failing tests** proving the sidecar strip appears and disappears via the banner system, and that `pushToast` produces a corner banner.
- [x] **Step 2: Run the affected tests and watch them fail.**
- [x] **Step 3: Rewire the components and the context.**
- [x] **Step 4: Run the full suite `npm test`** — PASS.
- [x] **Step 5: Commit.**

### Task 6: Docs and verification

**Files:**
- Modify: `README.md`, `docs/architecture/notifications.md`
- Add: `apps/studio/src/banners/BannerStack.visual.test.tsx`

- [x] **Step 1: Add the visual snapshot test** covering each severity.
- [x] **Step 2: Run `npm run typecheck` and `npm test`** — both clean.
- [x] **Step 3: Update `README.md` and the architecture note.**
- [x] **Step 4: Commit.**

---

## Outcome

All six tasks landed on `feat/banner-system`. Every surface that states a
condition *about the studio* — the sidecar strip, the offline strip, the toast
stack — now goes through one system. `FailurePanel` (a failure in place of the
thing that failed) and the transcript `.notice` (a line in history) stay as they
are, by design.

- Unit suite: 52 files, 441 tests, green (banner tests stress-run 6×, full suite 4×).
- Visual suite: 2 files, 6 snapshots, green (`BannerStack.visual.test.tsx` covers
  each severity, both docks, and the overflow affordance).
- `tsc -b`, `vite build`, and `eslint` are clean (the only warnings are the
  project's existing `react-refresh/only-export-components` idiom, shared with
  `StudioRuntime.tsx` and `composerParts.tsx`).
- Superseded: `Toasts.tsx`, `notices/SidecarNotice.tsx`,
  `chat/OfflineNotice.tsx`, and their CSS blocks.
- Docs: `docs/architecture/banners.md` (new), `notifications.md` (distinguishes
  the feed from banners), `architecture/README.md`, and the root `README.md`.
