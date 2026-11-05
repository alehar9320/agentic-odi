# ALH-201 — Semantic themes and a persistent theme control: Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the Studio a *Light / Dark / Follow the system* control that survives a reload, and make the
palette track an OS change without one.

**Architecture:** One new preference value and one `matchMedia` subscription. `src/lib/theme.ts` owns the
vocabulary; `StudioProvider` resolves it and paints `<html>` from a single effect that already exists;
`AppearanceSection` writes the stored preference through the settings mechanism the other sections use.
`theme.css` stays the only place a colour literal appears.

**Tech Stack:** React 19 + TypeScript, Vitest + Testing Library, plain CSS custom properties. No new
dependency, no backend change.

**Spec:** `docs/superpowers/specs/2026-11-05-alh-201-theme-control-design.md` — read it before Task 1; the
twelve calls it names are why each task is shaped the way it is.

## Global Constraints

- Branch from `origin/main` (the parent epic ALH-121 requires it); PR base `main`.
- No CSS-in-JS, no theme provider package, no second colour vocabulary.
- `theme.css` and `index.html`'s inline `<style>` are the only files holding hex; `src/styles/colors.test.ts`
  fails otherwise, and its allow-list may only shrink.
- Token names do not change. `--chart-1..6` belongs to ALH-216, not here.
- The existing class contract stays: `html.theme-light` / `html.theme-dark` on `document.documentElement`,
  plus `root.style.colorScheme`.
- Labels read *Light*, *Dark*, *Follow the system*.
- From the repo root, `uv run pytest -q` currently reports **2227 passed** on `main` — it must stay green
  (this slice touches no Python, but every task ends with the whole gate set).
- In `apps/studio`: `npx tsc -b --noEmit` clean, `npx eslint .` zero errors (5 standing react-refresh
  warnings are pre-existing), `npx vitest run` currently **1090 passed / 115 files**.

---

### Task 1: The preference vocabulary in `src/lib/theme.ts`

**Files:**
- Modify: `apps/studio/src/lib/theme.ts`
- Modify: `apps/studio/src/types.ts` (`StudioConfig.theme`, line ~251)
- Test: `apps/studio/src/lib/theme.test.ts`

**Interfaces:**
- Consumes: nothing new.
- Produces:
  ```ts
  export type StudioTheme = "light" | "dark";
  export type StudioThemePreference = StudioTheme | "system";
  export function systemPrefersLight(): boolean;
  export function storedPreference(stored: StudioThemePreference | undefined): StudioThemePreference;
  export function resolveTheme(stored: StudioThemePreference | undefined, prefersLight?: boolean): StudioTheme;
  ```
  `StudioConfig.theme?: StudioThemePreference`. Task 2 adds `useSystemTheme()` to this module; Task 3 and
  Task 4 import these names.

- [ ] **Step 1: Write the failing tests** in `src/lib/theme.test.ts`, beside the three that exist:
  `resolveTheme("system", true) === "light"` and `resolveTheme("system", false) === "dark"`;
  `resolveTheme("light", false) === "light"` and `resolveTheme("dark", true) === "dark"` (a stored choice
  beats a disagreeing OS); `resolveTheme("neon" as StudioThemePreference, true) === "light"` (an
  unrecognised stored value is not a choice); `resolveTheme(undefined) === "dark"` when `matchMedia` is
  `undefined`, which is today's fallback and must stay; `storedPreference(undefined) === "system"` and
  `storedPreference("dark") === "dark"`.

- [ ] **Step 2: Run them and watch them fail** — `npx vitest run src/lib/theme` from `apps/studio`.
  Expected: the new cases fail on the second argument (`resolveTheme` takes one parameter today) and on
  `storedPreference` not being exported.

- [ ] **Step 3: Implement.** Move the `matchMedia("(prefers-color-scheme: light)")` read out of
  `resolveTheme`'s body into `systemPrefersLight()` (keep both `typeof` guards — jsdom has no
  `matchMedia`, and `theme.test.ts` deletes it outright in one case); `resolveTheme` takes the optional
  second argument and defaults it to `systemPrefersLight()`; add the two type aliases; widen the
  `stored` parameter to `StudioThemePreference | undefined` so `"system"` type-checks; add
  `storedPreference`. Keep the module's doc comment, and amend it to say that a stored `"system"` and an
  absent key mean the same thing — the bootstrap in `index.html` relies on accepting only `"light"` and
  `"dark"`.

- [ ] **Step 4: Verify** — `npx vitest run src/lib/theme` (all green, including the three pre-existing
  cases, unchanged) and `npx tsc -b --noEmit`.

- [ ] **Step 5: Commit** — `git add apps/studio/src/lib/theme.ts apps/studio/src/types.ts apps/studio/src/lib/theme.test.ts`
  then `git commit -m "feat(studio): name the three theme choices a reader can make (ALH-201)"`.

---

### Task 2: The subscription that follows the system

**Files:**
- Modify: `apps/studio/src/lib/theme.ts`
- Test: `apps/studio/src/lib/theme.test.ts`

**Interfaces:**
- Consumes: `systemPrefersLight()` from Task 1.
- Produces: `export function useSystemTheme(): StudioTheme` — the live OS palette, re-rendering its caller
  when it changes, and `dark` when `matchMedia` is unavailable. Task 3 calls it exactly once.

- [ ] **Step 1: Write the failing test.** In `src/lib/theme.test.ts` import `renderHook` from
  `@testing-library/react` and `act`. Build a stub `matchMedia` factory that returns an object with a
  mutable `matches`, records the `(event, handler)` pairs passed to `addEventListener` and removes them in
  `removeEventListener`, and installs itself with `Object.defineProperty(window, "matchMedia", …)` the way
  `stubMatchMedia` in this file already does. Then: `renderHook(() => useSystemTheme())` reports the
  palette the stub advertises; setting `matches` and invoking the recorded `change` handler inside `act`
  flips `result.current`; `unmount()` clears the recorded handler list to empty. Add a case where
  `window.matchMedia` is `undefined`: the hook returns `"dark"`, `result.all` has length 1, and nothing
  throws.

- [ ] **Step 2: Run it, expect a failure** — `npx vitest run src/lib/theme`; `useSystemTheme` is not
  exported.

- [ ] **Step 3: Implement** with `useState(() => resolveTheme(undefined))` for the initial value and a
  `useEffect` that subscribes to `matchMedia("(prefers-color-scheme: light)")`'s `change` event and
  unsubscribes on cleanup. Guard the whole effect on `typeof window.matchMedia === "function"`; return
  `"dark"` when absent. The query string is the same one `systemPrefersLight` reads and `index.html`
  uses — put that in a module-level `const LIGHT_QUERY` and use it in all three places the code can reach.
  One `useEffect`, no `useSyncExternalStore` (the repo has no store to adapt), no context.

- [ ] **Step 4: Verify** — `npx vitest run src/lib/theme` green; `npx eslint .` clean.

- [ ] **Step 5: Commit** — `git commit -m "feat(studio): follow the system palette as it moves (ALH-201)"`.

---

### Task 3: Resolve it once, in the provider, and let the bar see it

**Files:**
- Modify: `apps/studio/src/state/StudioContext.tsx` (`:583` resolution, `:919-925` effect,
  `StudioContextValue` at `:315`, the `useMemo` at `:2422`)
- Modify: `apps/studio/src/components/layout/StudioBar.tsx` (`:7` import, `:52-53`, `:254-258`)
- Test: `apps/studio/src/state/StudioContext.test.tsx`
- Test: `apps/studio/src/components/layout/StudioBar.test.tsx`

**Interfaces:**
- Consumes: `useSystemTheme`, `resolveTheme` from Tasks 1-2.
- Produces: `StudioContextValue.theme: StudioTheme` — the palette the app is painting, which any surface
  may now read instead of resolving the preference itself.

- [ ] **Step 1: Write the failing provider tests** in `StudioContext.test.tsx`, which already renders with
  `renderHook(() => useStudio(), { wrapper: StudioProvider })`. Stub `matchMedia` as in Task 2 and set
  `localStorage` directly under the settings key the file already uses: with `{"theme":"system"}`, `result.current.theme`
  is the OS palette, `document.documentElement` carries `theme-dark` or `theme-light` to match, and firing
  `change` moves both; with `{"theme":"light"}` and a dark OS, the class stays `theme-light` and the change
  event does nothing. Assert the same `theme` value the painted class implies — that pairing is the
  contract Task 4 and the bar depend on.

- [ ] **Step 2: Run, expect failure** — `npx vitest run src/state/StudioContext`; `result.current.theme` is
  `undefined`, since the context value does not carry it.

- [ ] **Step 3: Implement.** In `StudioProvider`: `const systemTheme = useSystemTheme();` and
  `const theme = resolveTheme(settings.theme, systemTheme);` replacing line 583's local resolution; add
  `theme: StudioTheme` to `StudioContextValue` next to `settings`, with a one-line comment saying it is the
  palette actually painted, not the stored preference; add `theme` to the object in the `useMemo` at
  `:2422` **and to its dependency array** (omitting it there is how a stale palette gets shipped).
  The effect at `:919-925` does not change — it already depends on `theme`, and now `theme` can move.

- [ ] **Step 4: Move the bar onto the context.** In `StudioBar.tsx`, delete the `resolveTheme` import and
  read `theme` from `useStudio()` (its `stubContext()` in `StudioBar.test.tsx` gains
  `theme: "dark"`), so `nextTheme` derives from the painted palette. Behaviour to pin in
  `StudioBar.test.tsx`: with `theme: "dark"` the button's `aria-label` names *light* and a press calls
  `saveSettings` with `theme: "light"`. The toggle keeps its meaning from design call 8 — from *Follow the
  system* it pins the opposite palette.

- [ ] **Step 5: Verify** — `npx vitest run src/state src/components/layout` and the whole suite
  `npx vitest run`; `npx tsc -b --noEmit`. Any test that mocks `useStudio` needs `theme` in its stub —
  that is the change's blast radius, and it is a compile error, not a guess.

- [ ] **Step 6: Commit** — `git commit -m "feat(studio): paint one resolved theme and let every surface read it (ALH-201)"`.

---

### Task 4: The control in Settings

**Files:**
- Create: `apps/studio/src/components/settings/sections/AppearanceSection.tsx`
- Create: `apps/studio/src/components/settings/AppearanceSection.test.tsx` (flat, the convention open PR
  #716's section tests follow)
- Modify: `apps/studio/src/components/SettingsPanel.tsx` (import + mount beside `ModelSection`)
- Modify: `apps/studio/src/styles/theme.css` (the group's own rules, tokens only)

**Interfaces:**
- Consumes: `StudioThemePreference`, `storedPreference`, `theme` from context (Task 3), `saveSettings`.
- Produces: `export function AppearanceSection({ settings, saveSettings }: { settings: StudioConfig;
  saveSettings: (config: StudioConfig) => void }): JSX.Element`.

- [ ] **Step 1: Write the failing component test.** Render the section with a `useStudio` stub the way
  `SettingsPanel.perFieldSave.test.tsx` does. Assert: one `role="radiogroup"` whose name is the legend;
  exactly three radios named *Light*, *Dark*, *Follow the system*; with `settings.theme` absent the
  **Follow the system** radio is checked (design call 7 — a group with nothing checked has no arrow-key
  landing point); with `{"theme":"light"}` on a dark OS **Light** is checked and the resolved palette does
  not change which radio is checked; firing a change on *Dark* calls `saveSettings` with
  `theme: "dark"` and leaves the other settings fields untouched; with `settings.theme === "system"`,
  choosing *Light* then re-rendering with the new settings shows *Light* checked.

- [ ] **Step 2: Run, expect failure** — `npx vitest run src/components/settings/AppearanceSection`; the
  module does not exist.

- [ ] **Step 3: Implement the component** as a `<section aria-labelledby>` holding a `<fieldset>` with a
  `<legend>`, three `<label>`-wrapped `<input type="radio" name="studio-theme">` whose `checked` is
  `storedPreference(settings.theme) === option`, and `onChange` calling
  `saveSettings({ ...settings, theme: option })`. No local state: the stored preference is the answer, so
  the control cannot disagree with what persistence did. Add a caption line, only if it reads well after
  the radios, naming the palette currently painted from `useStudio().theme` — that is the design's
  builder's-choice item, and the test above must not depend on it.

- [ ] **Step 4: Style it in `theme.css`** near the existing `.settings__` rules, reading only
  `var(--…)`. Do not add a hex value: `colors.test.ts` fails the build otherwise. Both palettes must show
  the checked state without relying on colour — the native radio fill and the `:focus-visible` outline
  already in `theme.css` do that; say so in the PR rather than inventing an indicator.

- [ ] **Step 5: Mount it** in `SettingsPanel.tsx`, and extend `SettingsPanel.perFieldSave.test.tsx` with
  the one assertion that matters there: opening Settings on a corrupt stored `theme` renders the group with
  *Follow the system* checked rather than throwing.

- [ ] **Step 6: Verify** — `npx vitest run src/components` , `npx tsc -b --noEmit`, `npx eslint .`.

- [ ] **Step 7: Commit** — `git commit -m "feat(studio): a Settings control for light, dark, and the system (ALH-201)"`.

---

### Task 5: The claims that must not be inherited from `main` untested

**Files:**
- Modify: `apps/studio/src/styles/theme.test.ts`
- Modify: `apps/studio/src/styles/bootShell.test.ts`
- Test: `apps/studio/src/state/StudioContext.test.tsx`

**Interfaces:**
- Consumes: everything above.
- Produces: nothing new — this task's output is evidence.

- [ ] **Step 1: Widen the token gate.** Add `"red"` to `TEXT_TOKENS` in `src/styles/theme.test.ts`. Run
  `npx vitest run src/styles/theme` and report the measured ratios in the PR body; design call 9 records
  the values read off `main` (`#f87171` at 7.11:1 / 6.88:1, `#b91c1c` at 5.98:1 / 6.47:1), so a pass here
  is a pass already measured, and a failure means the palette — not the test — is wrong and must be
  corrected in `theme.css`.

- [ ] **Step 2: Pin the bootstrap against a stored `"system"`.** In `bootShell.test.ts`, add to the
  existing inline-script assertions that `index.html` accepts only the literal strings `"light"` and
  `"dark"` from storage, so a stored `"system"` falls through to the media query — and state in the test
  name that this is why the app and the bootstrap cannot disagree. Read the shipped document as the file
  already does; do not evaluate the script in jsdom.

- [ ] **Step 3: Pin the storage-failure trio** in `StudioContext.test.tsx`: a corrupt JSON value at the
  settings key; `localStorage.getItem` throwing; `localStorage.setItem` throwing. Each must leave the app
  on the default palette with the provider usable, and in the third case a theme chosen in the session
  still repaints `<html>` even though the write was refused. Restore whatever the stub replaced. This is
  design call 11: the behaviour is asserted, and the limitation (a refused write is invisible, as it is
  for every other settings field today) is stated, not papered over.

- [ ] **Step 4: Verify** — `npx vitest run` from `apps/studio`, then the whole repo gate set:
  `npx tsc -b --noEmit`, `npx eslint .`, and from the root `uv run ruff check .`,
  `uv run ruff format --check .`, `uv run mypy apps brand packages`, `uv run pytest -q`,
  `uv run python scripts/doc_check.py`, `uv run --directory website pytest tests/ -q`.

- [ ] **Step 5: Commit** — `git commit -m "test(studio): the theme gate covers red, the bootstrap, and a refusing store (ALH-201)"`.

---

### Task 6: Say what changed, in the documents that carry it

**Files:**
- Modify: `README.md` (the capability line about the Studio's appearance)
- Modify: `docs/living-studio.md` (the Settings surface inventory gains the appearance control; the
  theme-follows-the-system behaviour is stated where the shell is described)
- Modify: `docs/roadmap.md` (an In-flight line for this change)
- Create: this plan at `docs/superpowers/plans/2026-11-05-alh-201-theme-control.md`

**Interfaces:**
- Consumes: the shipped behaviour.
- Produces: the PR body's *Verification* numbers and the roadmap line.

- [ ] **Step 1: Write the roadmap line** in the In-flight list, in the existing style: **Choose light, dark,
  or the system** — a Settings control, the bar's toggle reading the palette actually painted, an OS flip
  applied without a reload, and the contrast gate widened to the token it skipped (this change).

- [ ] **Step 2: Update `docs/living-studio.md` and `README.md`** to the extent they describe Settings or the
  theme today. `uv run python scripts/doc_check.py` must exit 0.

- [ ] **Step 3: Commit** — `git commit -m "docs: the theme control and system-follow are shipped behaviour (ALH-201)"`.

---

## Review Focus

The parent epic's completion text names inputs no task above exercises in passing. Each of these is a line
in the PR body's *Known limitations* if the test says something else:

- **A stored `theme` that is neither of the three values** (an old build's value, a hand-edited
  `localStorage`, a tampered one): it must resolve to the OS and render *Follow the system* checked, never
  throw and never pin. Owned by Task 1 Step 1 and Task 4 Step 5.
- **`window.matchMedia` missing** (older browsers; every jsdom test that deletes it): `useSystemTheme`
  returns `"dark"` and subscribes to nothing. Owned by Task 2 Step 1.
- **A refused `localStorage` write**: the session honours the choice, the reload loses it, and no surface
  claims otherwise. Owned by Task 5 Step 3.
- **An OS flip while the reader has pinned a palette**: the painted class, `result.current.theme`, and the
  bar's icon all stay put. Owned by Task 3 Step 1.
- **A keyboard-only reader** reaching the group: one tab stop into the radiogroup, arrows move between the
  three, and the focus ring is the token one in both palettes. Owned by Task 4 Steps 1-4.
