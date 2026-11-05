# ALH-201 (M5-01.1) — a theme you can choose, and one that follows the system

## What this is

The Studio already has two palettes. `src/styles/theme.css` defines every colour once, `:root` holds the
dark values and `html.theme-light` overrides them under the same token names; `src/lib/theme.ts` reads
the stored choice and falls back to the operating system; `index.html` resolves and paints that class
before React runs; `src/styles/colors.test.ts` fails the build on a raw hex in a component;
`src/styles/theme.test.ts` measures the token pairs against WCAG AA in both palettes. That is most of
what the parent epic, ALH-121, asked for, and it is on `main`.

Two of its acceptance lines are not met, and they are the two a reader actually feels:

- **There is no way to go back.** The Settings panel has no theme control at all — a `ModelSection` and
  a `ConnectionsSection` exist, and neither touches `theme`. The only door is the sun/moon button in the
  studio bar, which writes `light` or `dark` and nothing else. Once a person has pressed it, the app is
  pinned: the OS can move to the other palette and the Studio will not follow.
- **Nothing listens to the system.** `resolveTheme(settings.theme)` is called during render
  (`state/StudioContext.tsx:583`) and its result is painted by an effect that depends on that value
  (`:919-925`). No `matchMedia` change subscription exists anywhere in `src/`, so choosing "follow the
  system" — even if it were expressible — would only take effect on the next reload. A person who flips
  their OS to dark at 23:00 keeps a bright window until they reopen the app.

Linear: [ALH-201](https://linear.app/agentic-odi/issue/ALH-201) · M5-01.1 · epic Pillar 5 ·
area `area/studio` · parent [ALH-121](https://linear.app/agentic-odi/issue/ALH-121) ·
sibling [ALH-216](https://linear.app/agentic-odi/issue/ALH-216) (remaining surfaces, chart/print
conversion, palette-drift guard).

## Why this shape

The issue's own boundary: this slice *owns* the tokens, the Settings control, persistence, the
pre-paint choice, and the conversion of **two** surfaces — the thread and Settings. The sibling owns
everything past that seam. So the change is deliberately narrow: one new preference value, one
subscription, one section of Settings, and tests. No core, contract, CLI or studio-api file moves —
the theme preference is browser state in `localStorage`, exactly as `StudioConfig.theme` is today, and
`/api/config` carries no `theme` key.

The parent's technical decisions name `tokens.css`, `--surface-raised`, `--danger`, `--chart-1..6` and
a `data-theme` attribute. Those names were written before `theme.css` shipped. This design builds on
what exists rather than re-labelling it, for the reason the parent itself gives under *Avoid*: a second
colour vocabulary. Details and the cost of each call are below.

## The calls I made (check these while reading)

1. **`theme.css` stays the single palette source; no `tokens.css`.** The file already is that thing —
   the parent's requirement was "extract every colour into a semantic token", and `colors.test.ts` is
   the enforcement that keeps it true, with an allow-list that can only shrink. Renaming `--bg` →
   `--surface` and `--red` → `--danger` across the studio would touch every stylesheet for zero
   user-visible change. What the sibling needs that does not exist — `--chart-1..6` — is *its* scope,
   and inventing unused tokens here is the failure mode this repository's rules call out. *My call.*
2. **The class contract stays `html.theme-light` / `html.theme-dark`.** The bootstrap, the painting
   effect, and both existing stylesheet tests are written against those classes. `data-theme` buys
   nothing the class does not already buy: the requirement is *a value set before first paint*, and
   `index.html` already sets it. *My call.*
3. **A three-state preference, stored explicitly.** `StudioThemePreference = "light" | "dark" |
   "system"`, and `StudioConfig.theme?: StudioThemePreference`. `undefined` (never chosen) and
   `"system"` (chosen) both mean follow the OS; `"light"`/`"dark"` pin. `"system"` is stored rather
   than deleted because it is a decision the reader made: deleting the key would make the pick
   indistinguishable from never having visited Settings, and a refresh would appear to undo it.
   Backwards compatible by construction — `resolveTheme` already treats any value that is not
   `"light"`/`"dark"` as "no stored choice", and the bootstrap in `index.html` checks exactly those two
   strings, so a stored `"system"` falls through to the OS branch with no edit to that script. *My call.*
4. **One subscription, and the resolved palette becomes context.** `useSystemTheme()` in
   `src/lib/theme.ts` returns the OS's current preference and re-renders its caller when it changes;
   `StudioProvider` calls it once, computes `theme = resolveTheme(settings.theme, systemLight)`, and
   puts `theme` in its context value. The existing effect that depends on `theme` stays the only place
   that paints `<html>`. The context field is not a second store — it is the value the provider already
   resolves and today keeps to itself, and without it the studio bar cannot know the palette moved:
   `StudioBar.tsx:52-53` calls `resolveTheme(settings.theme)` at render, so a live OS change would
   repaint the window while the sun/moon icon stayed put and the next press pinned the palette you are
   already looking at. That is the same defect this slice exists to remove, so the bar reads
   `useStudio().theme` instead of resolving its own copy. *My call.*
5. **`resolveTheme` keeps its callers working.** New signature
   `resolveTheme(stored: StudioThemePreference | undefined, prefersLight?: boolean)`. When
   `prefersLight` is omitted it reads `matchMedia` itself, which is what the function does today —
   `SettingsPanel.tsx:64` (the diagnostics bundle's palette) stays as it is, and the three existing
   tests in `src/lib/theme.test.ts` keep passing unchanged.
6. **The control is a radiogroup, not a cycling button.** Three labelled radio inputs — *Light*,
   *Dark*, *Follow the system* — in one `<fieldset>` with a `<legend>`, inside a new
   `AppearanceSection` under `src/components/settings/sections/`, following `ModelSection` and
   `ConnectionsSection`, saved through the existing `saveSettings` path. A cycling button hides which of
   three states you are in and gives no non-colour cue; native radios bring the label, the keyboard, the
   group semantics, and the focus ring from `theme.css`'s `:focus-visible` for free.
7. **`undefined` reads as *Follow the system* in the control.** With no stored choice, none of three
   native radios would be checked — an arrow-key group with no landing point, and every first-time
   visitor sits in that state. So the checked value is `settings.theme ?? "system"`: still the stored
   preference, not the resolved palette (the group says *Follow the system* while the OS shows dark),
   just normalised where "never chosen" and "chose system" mean the same behaviour. The first click
   writes the value explicitly.
8. **The bar toggle stays and keeps its meaning.** It pins the palette opposite to the one on screen —
   including when that palette came from the system, where pressing it moves you off *Follow the
   system* onto the other explicit palette. *My call.*
9. **Contrast is measured by the tests that exist, widened to this slice's pairs.** `theme.test.ts`
   gains `--red`, the text token this product paints and does not check today — measured at the values
   on `main`, `#f87171` is 7.11:1 on `--bg` and 6.88:1 on `--bg-raised`, `#b91c1c` is 5.98:1 and 6.47:1,
   so widening the list documents a pass rather than forcing a palette edit. The failing assertion
   already names the pair and its ratio, which is what the acceptance line asks for. What a token-level
   check structurally *cannot* measure stays with the rendered walker: `colorTokens` reads only 6-digit
   hex properties, so the rgba surfaces (`--surface`, `--line`) and a browser-drawn radio fill are
   carried by `src/test/contrast.ts` in jsdom and by `e2e/a11y.spec.ts`, whose known-pairs list is a
   deliberately non-blocking CI job. A new entry there is added only if running it produces a finding,
   with the output in hand. *My call.*
10. **No `prefers-color-scheme` block in `theme.css`.** The parent lists it as a technical decision, but
    with an explicit class painted before first paint, a media-query default either loses to that class
    or has to beat it with `!important` — and then a stored *Light* on a dark-mode OS prints dark. The
    bootstrap already implements "OS unless stored", and `index.html`'s own boot media block stays
    because `bootShell.test.ts` requires it. *My call.*
11. **Storage that is corrupt, absent, or refuses a write is a default, never a crash — and a refused
    write is not this slice's API change.** `loadSettings` (`state/StudioContext.tsx:474`) and
    `saveSettings` (`:927-934`) already try/catch. This design pins that with tests: a corrupt stored
    object, a `getItem` that throws, and a `setItem` that throws all resolve to the existing default,
    apply the choice for the session, and leave the app usable. It does **not** turn `saveSettings` into
    a call that reports whether the write landed. `saveSettings` returns `void` today and every sibling
    section (`ModelSection.tsx:36`) already saves fire-and-forget, so the per-field "Saved" line means
    *your choice is in effect*, not *this survived a browser restart* — for theme as for the API key
    beside it. Making storage failures visible is a change to the settings mechanism, not to one field
    of it, and it is called out in the PR body as the limitation it is. *My call.*
12. **The `AboutSection` extraction in #716 is a rebase, not a blocker.** Open PR #716 splits
    `SettingsPanel.tsx` into five section modules and moves that file's diagnostics call into
    `sections/AboutSection.tsx`; its tests live flat at `src/components/settings/<Name>Section.test.tsx`.
    This issue branches from `origin/main` as the parent instructs, puts the component in
    `sections/AppearanceSection.tsx` and its test at `settings/AppearanceSection.test.tsx` so #716's
    conventions are already satisfied, and takes the conflict on `SettingsPanel.tsx` (three lines:
    import, mount, nothing else) whenever #716 lands first. *My call.*

## Goals

- A person can pick *Light*, *Dark* or *Follow the system* in Settings, by keyboard, with every control
  labelled and its focus visible, and the pick survives a reload.
- Picking *Follow the system* makes the Studio change palette when the OS does, **without a reload**,
  and picking *Light* or *Dark* makes an OS change do nothing at all.
- The studio bar's toggle is never a half-truth: its icon and its next press both track the palette that
  is actually on screen, including after a live OS change.
- A cold load is painted with the chosen theme before any content is visible — asserted by reading the
  shipped document, not by running an effect.
- Every hex text/background token pair this product paints text with clears 4.5:1 in both palettes, and
  the failing assertion names the pair.
- A stored value that is not a theme (`"neon"`), a `localStorage` that throws on read, and one that
  throws on write all resolve to the existing default and leave the app usable.
- *Thread* and *Settings* stay legible in both palettes — including the empty, loading, error and
  disabled states of the Settings panel and the focus state of the new control.

## Non-goals

- The rest of the surface catalogue, the SVG evidence chart, and the print stylesheet: ALH-216.
- New tokens for consumers that do not exist yet, including `--chart-1..6`.
- Renaming `theme.css` or any token in it.
- Any change to core, the MCP contract, the CLI, or studio-api. This is browser state.
- A theme framework, CSS-in-JS, or a provider dependency.
- Changing `saveSettings` into a status-returning API, or adding a storage-failure banner.
- Locale work, branding, or a palette editor.
- Claiming that passing a contrast gate proves a surface accessible. The control gets an accessible
  name and a visible focus ring, and that is all the tests here can assert.

## The interface this leaves the builder

`src/lib/theme.ts`

```ts
export type StudioTheme = "light" | "dark";                    // unchanged
export type StudioThemePreference = StudioTheme | "system";    // new

/** The operating system's answer right now; false when it cannot answer. */
export function systemPrefersLight(): boolean;                 // extracted from resolveTheme's body
/** The live OS palette, re-rendering the caller when it changes. */
export function useSystemTheme(): StudioTheme;                 // new — the only subscription
/** What the Settings control shows as checked. */
export function storedPreference(stored: StudioThemePreference | undefined): StudioThemePreference;

export function resolveTheme(
  stored: StudioThemePreference | undefined,
  prefersLight?: boolean,     // omitted = read matchMedia, which is today's behaviour
): StudioTheme;
```

`src/types.ts` — `StudioConfig.theme?: StudioThemePreference`.

`src/state/StudioContext.tsx` — provider holds `const systemTheme = useSystemTheme()`, resolves
`theme` with it, and adds `theme` to the context value (and to the memo's dependency list).
`src/components/layout/StudioBar.tsx` — reads `theme` from context; `nextTheme` follows from it.

`src/components/settings/sections/AppearanceSection.tsx` —
`({ settings, saveSettings }: { settings: StudioConfig; saveSettings: (config: StudioConfig) => void })`,
mounted in `SettingsPanel.tsx` beside `ModelSection`, rendering one `<fieldset>` with a `<legend>` and
three radio inputs sharing one `name`, checked from `storedPreference(settings.theme)`.

## Test plan

- `src/lib/theme.test.ts` — `"system"` and `undefined` both follow `prefersLight`; `"light"`/`"dark"`
  win over a disagreeing `prefersLight`; an unrecognised string follows the system; the
  omitted-second-argument path keeps its three existing behaviours; `storedPreference` maps
  `undefined` to `"system"` and passes everything else through.
- New: `useSystemTheme` subscribes. A stubbed `matchMedia` whose `addEventListener` captures the
  handler; flipping `matches` and firing `change` re-renders with the other palette; the listener is
  removed on unmount; a `matchMedia` that is `undefined` yields the dark default and never throws.
- `src/state/StudioContext.test.tsx` — an OS change repaints `<html>` (class and `style.colorScheme`)
  while the preference is *system*, and does not while it is pinned; the context's `theme` moves with
  it; `resolveTheme` and the bootstrap agree on the same inputs for the same stored value.
- `src/components/layout/StudioBar.test.tsx` — after a live OS change the icon matches the painted
  palette and a press pins the other one.
- `src/components/settings/AppearanceSection.test.tsx` — one group label, three radios, the checked
  option is the stored preference with `undefined` read as *Follow the system*, choosing one calls
  `saveSettings` with that value, arrow keys move within the group, and the section still renders when
  the panel is in its error or loading state.
- `src/styles/theme.test.ts` — `--red` joins the text tokens checked against both surfaces in both
  palettes.
- `src/styles/bootShell.test.ts` — a stored `"system"` is not accepted as a literal theme, so the
  bootstrap falls through to the OS branch, and the class it sets is the one the app later keeps.
- Storage failures — corrupt JSON, a throwing `getItem`, a throwing `setItem`: the app boots on the
  default, the choice still applies for the session, and nothing crashes.

## What is left to the builder

Where the section sits in the panel's order; whether the group also shows the resolved palette as a
caption; the exact copy of the three labels, beyond *Light* / *Dark* / *Follow the system*; whether
`systemPrefersLight` is exported or module-private (export it only if a test needs it); how the
StudioBar toggle's `aria-label` wording changes now that a pin is a choice rather than the only state;
and whether any `knownPairs` entry is needed in the e2e job, decided from the walker's actual output.
