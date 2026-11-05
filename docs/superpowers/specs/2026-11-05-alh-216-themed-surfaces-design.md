# ALH-216 (M5-01.2) — every surface on the palette, and a guard that keeps it there

## What this is

ALH-201 shipped the theme mechanism: one token block, a `light | dark | system` preference, a control in
Settings, a pre-paint resolution in `index.html`. What it deliberately left behind is this issue's whole
subject — *"the entire reading experience, including shared charts, stays legible and prints on a light
page."*

The mechanism is sound and the surfaces are not all inside it. Measured on `f6f6fe34`:

- **`html.theme-light` appears exactly once in `src/styles/theme.css` — at line 41, the token block.** The
  file is 6764 lines. Every rule below line 57 is theme-blind, which is fine while it reads `var(--token)`
  and a problem the moment it does not.
- **43 opaque colour declarations sit outside the token block** in that file: 39 `color:`, 3 `background:`,
  1 `border-color:`. Each one is a value that cannot change with the theme, so each is a light-theme defect
  waiting to be painted — `.notice { color: #d6c19b }`, `.evidence blockquote { color: #dfe1e7 }`,
  `.ui-card__evidence { color: #cbd5e1 }`, `.message__tag { color: #f0b45a }`,
  `.failure__icon { color: #f87171 }` are light ink on `--bg: #f5f6f8`. Several are near-duplicates of a
  token that already exists: `#f87171` *is* the dark `--red` byte for byte, and `#0b0c10` is within two of
  `--bg`.
- **194 `rgba(…)` literals sit outside the block too**, most of them white at 0.01–0.14 alpha. On the dark
  ground they are a whisper of paper; on `#f5f6f8` they are nothing at all. They are the same defect class
  at lower volume and they are *not* all fixed here — see *What stays*.
- `colors.test.ts` cannot see any of it. The gate's `TOKEN_FILE` is excluded from the scan by design
  ("it is where the tokens are defined"), so the file that is allowed to hold literals holds 237 of them
  outside its own token blocks, unmeasured. `theme.test.ts` measures the token *pairs*, which is exactly
  why these never appear in a contrast failure: the gate measures `--text` on `--bg`, not `#d6c19b` on `--bg`.
- **The two canvas components are still on the old inline palette.** `OpportunityLandscape.tsx` (13 literal
  sites: the plot's own `rgba(11, 13, 19, 0.6)`, the amber glow stops, `rgba(255, 255, 255, 0.05)` grid, the
  `#fbbf24`/`#f87171` score-band nodes, the `#0b0d13` node ring, the `rgba(255,255,255,0.2)` "Overserved
  Zone" label, the selected-row wash) and `JobMap.tsx` (6 sites, including the light-theme defect
  `color: … : "rgba(255,255,255,0.2)"` on an empty phase's step pill — invisible text on paper). Both are
  in `ALLOWED_FILES` with reason *"SVG chart colour encodes the score band; it is data, not theme."* That
  reasoning is half right: the band *is* data, and the fix is to name that role as a token, not to hide the
  colour in a component where neither theme nor print can reach it.
- **The e2e contrast gate owns the proof that this is a real defect.** `e2e/a11y/knownPairs.ts` carries two
  entries attributed to #335 — the matrix's SVG axis labels `rgb(21,23,28)` and captions `rgb(86,93,107)`
  measured over `rgb(109,110,113)`, which is the dark plot fill showing through in the *light* theme. They
  are on the known-failing list because the chart's own surface is a literal that does not flip.
- **The offline one-pager went stale the moment ALH-201 added a third value.** `public/offline.html:16`
  reads `if (JSON.parse(raw).theme === "light") theme = "light"` and everything else falls to dark. A
  reader with *Follow the system* on a light machine, opening the app while the network is down, gets a
  black sheet. Its token block also hand-copies `#0a0b0e`, `#f1f2f4`, `#a2a7b3`… from `theme.css`, so the
  two palettes drift the first time either changes.
- **`print.css` knows about the thread and the brief, and about nothing else.** It pins `#fff`/`#111` for
  `.message__*`, `.md`, `.card`, `.ui-card` — good — but it has no rule for `.opportunity-matrix`, the plot,
  the job map, the records table or a band pill, because those are inline styles a stylesheet cannot
  override without `!important`.

Linear: [ALH-216](https://linear.app/alhase-personal/issue/ALH-216) · M5-01.2 · epic Pillar 5 ·
parent [ALH-121](https://linear.app/alhase-personal/issue/ALH-121) · prerequisite
[ALH-201](https://linear.app/alhase-personal/issue/ALH-201) (PR #769) · coordinate with
[ALH-131](https://linear.app/alhase-personal/issue/ALH-131), whose screen-reader audit this does not take
over.

## Why this shape

The issue names its own boundary: *own the remaining canvas/tables/charts/shared-view conversion, SVG
token handling, the explicit light print palette, and the raw-colour scanning guard; do not rebuild
Settings/persistence or re-convert the thread.* So this slice is a **migration plus a lock**: move the
colour that is written as a value into the colour that is written as a role, then change the guard so the
value can never come back.

Two things make it smaller than it looks. First, the destination already exists for most of it — the
`--studio-*` alias layer (`theme.css:25-32`) is a thin set of names over the real tokens that the canvas
components were written against, so "convert the canvas" is mostly "delete the alias, read the token".
Second, the ratchets are self-enforcing: `colors.test.ts` fails on an `ALLOWED_FILES` entry whose file no
longer has a literal, and `a11y.spec.ts` fails on a `KNOWN_PAIRS` entry that no longer fails. Clearing a
surface *requires* removing its exemption, and the tests then forbid putting it back.

### The inventory premise, corrected and recorded

The issue says to inventory surfaces from `apps/studio/src/ui/catalog.ts`. That file is the **agent's wire
manifest** — the closed set of primitives and cards a model may ask for, whose `catalogPrompt()` is fed to
the LLM. It is not the surface inventory, and theming off it would miss every panel in the app. The two
real inventories are:

- `src/components/workspace/panels.tsx:51` — `WORKSPACE_PANELS`, **10** lenses (records, catch-up,
  landscape, brief, job map, segments, evidence, memory, schedule, capture), each with a `render()`. This is
  the list a screen-reader or theme audit should walk, and the list `e2e/a11y.spec.ts` currently walks only
  4 of (records, catch-up, landscape, brief).
- `src/ui/catalog.ts` — the card and primitive set the panels compose from (`ui-tone--*`, `ui-meter__fill`,
  `ui-card--urgent`), which is already token-driven.

The issue also requires that missing surfaces be **recorded before claiming full coverage**. Recorded, with
the acceptance line each one touches:

1. There is **no evidence chart.** `canvas/EvidenceStream.tsx` is a drag-reorderable list of quotes; it
   renders no plot. The parent's `--chart-1..6` series palette has no consumer anywhere in `src/`
   (`grep -rn -- --chart src/` is empty). So "Evidence chart labels, bands and sample size" is satisfied
   here for the only chart that exists — the opportunity map — and the named evidence chart is not claimed.
2. The a11y gate has **no print mode and no shared/offline screen** in its `SCREENS × THEMES` matrix.
3. `JobMap.tsx` is div-based, not SVG, despite its `ALLOWED_FILES` reason saying *"SVG job-map strokes"*.
   The reason is stale on its face; the entry goes.

What stays out of this slice, deliberately: the 194 alpha-blended surface literals in `theme.css`, the
`onboarding.css` scrim (a fixed dark intro is the design), and `OdiMascot.tsx` (brand artwork gated by
`brand/tools/render.py --check`). They are named, counted, and left under the new count baseline rather
than pretend-fixed.

## The calls I made (check these while reading)

1. **Colour moves out of inline `style` objects and SVG presentation attributes into class rules in
   `theme.css`.** A component's own `style={{ background: "rgba(11,13,19,0.6)" }}` cannot be overridden by
   `html.theme-light` or by `@media print` without `!important`, and the repo's own print sheet already
   leans on plain specificity. Class rules put every canvas colour where both the theme and the printer can
   reach it, and they are what lets the two `ALLOWED_FILES` entries be deleted. *My call.*
2. **Six new tokens, named by role, not the parent's `--chart-1..6`.** The map needs a ground, a band, a
   tint for "this row is the urgent one", two tints for selection, and ink for a filled control. It does not
   need six series colours, because the Studio has exactly one chart and it encodes *state*, not *series*.
   The proposed names: `--plot-surface`, `--plot-band`, `--tint-accent`, `--tint-accent-strong`,
   `--tint-amber`, `--accent-fill` with its paired ink `--on-accent`. Each gets a dark value and a light
   override in the token block and nothing else; every one is measured by `theme.test.ts` before it ships.
   *My call*, and the one a reviewer should push on hardest — it declines part of the parent epic's letter.
3. **Score-band colour comes from tokens the bands already own** — `--accent` for served, `--amber` for
   underserved, `--red` for a score of 15 or more — not from new chart hues. Those three are already the
   palette's semantic states, already measured at 4.5:1 in both themes, and already what the side table and
   the pills use. The `#fbbf24`/`#f87171` in the component are drift-duplicates of `--amber` and `--red`.
4. **A band is marked by shape as well as colour.** In the map, a served outcome stays a circle, an
   underserved one becomes a square, and a deep one a triangle; a legend names all three. The reason is the
   print line, not only the colour-blind line: a greyscale sheet cannot carry amber-versus-red, and today a
   printed map is an undifferentiated field of grey blobs. The pulse ring stays as a third cue where motion
   is allowed. *My call.*
5. **The guard splits into three rules, and the palette file is finally inside the scan.** (a) The existing
   whole-file rule for everything except `theme.css` is unchanged, minus the two canvas entries.
   (b) `theme.css` itself: an opaque literal (`#hex` or `rgb(` with alpha 1) in a `color`, `background`,
   `background-color`, `border-color`, `fill` or `stroke` declaration outside a token block fails at
   **zero tolerance** — reachable because I am clearing all 43 in this change. (c) The alpha-blended
   literals get a **count baseline** with the same one-way ratchet as `ALLOWED_FILES`: the test holds the
   measured number, fails when a run produces more, and fails when a run produces fewer, so the number can
   only move down and someone who improves it is told to bank the improvement. The two `html.theme-light`
   token-block ranges are the only place a literal is legal.
6. **The two #335 `KNOWN_PAIRS` entries are deleted in this change, not after it.** Once the plot's ground
   is `--plot-surface` and the axis text is `--text`, the light theme paints `#15171c` on a light ground and
   the pair stops failing; `a11y.spec.ts`'s staleness test is what proves I did not merely move the problem
   somewhere the gate does not look.
7. **The offline page resolves the theme the way the app does, and its palette is pinned against the app's
   by a test.** `light` means light, `dark` means dark, anything else — including the new `system` and a
   missing key — follows `matchMedia("(prefers-color-scheme: dark)")`. Still inline, still zero requests,
   still no settings API: the acceptance line says a shared snapshot must not depend on a live server, and
   `localStorage` plus a media query is what a cold cache has. A new jsdom test then compares each token
   name `offline.html` declares against the value in `theme.css`, so the copy cannot drift silently.
8. **Print gets rules for the surfaces that become reachable, in ink rather than tokens.** Paper is opaque;
   the print sheet keeps its own literals (that is `print.css`'s existing allow-list reason) and names the
   converted canvas classes, the records table, the band pills and the legend explicitly. The test asserts
   the print sheet reaches each converted surface and pins `#fff`/ink, so a future component cannot quietly
   print a black rectangle.
9. **The a11y screen list grows to the whole panel inventory, but stays contrast-only.** All 10 lenses × 2
   themes. The other axe rules still report violations on this repository's own markup (the banner dock's
   Radix `<ol>`, #625), and ALH-131 owns that audit; widening the screen list without widening the rule set
   keeps this issue's promise honest and costs CI time, nothing else. *My call.*

## What the change looks like

`theme.css` gains the six tokens with light overrides; the 43 opaque declarations are replaced one by one,
each by the token that names its role (`.composer__send` → `--accent-fill` + `--on-accent`; `.notice` →
`--amber`; `.ui-card__evidence` → `--text`; `.ui-tone-bg--neutral` → `--faint`; and so on — the plan carries
the full table). `OpportunityLandscape.tsx` and `JobMap.tsx` lose their colour `style` objects and SVG
literals in favour of classes (`opportunity-matrix__plot`, `__grid`, `__band`, `__node--served|underserved|deep`,
`jobmap__tile`, `jobmap__tile--selected`, `jobmap__tile--empty`, `jobmap__pill`), `ALLOWED_FILES` drops both
entries and the cap drops from 6 to 4, `print.css` gains a canvas and table block, `offline.html` gains the
`system` branch, `colors.test.ts` gains rules (b) and (c), `theme.test.ts` gains the `--on-accent` /
`--accent-fill` pair and the new tints measured against both grounds, `a11y.spec.ts` gains the lenses, and
`KNOWN_PAIRS` loses two.

No file outside `apps/studio` changes. No new dependency, no new framework, no rename of an existing token,
no second colour vocabulary — the parent's *Avoid* list is a constraint I hold.

## Acceptance lines and the test that holds each

| The issue's line | Where it is proved |
| --- | --- |
| Each inventoried remaining surface, including empty/error/focus/disabled states, uses semantic tokens; text pairs pass 4.5:1 in both themes. | `colors.test.ts` rule (b) at zero tolerance; `a11y.spec.ts` over 10 lenses × 2 themes; `theme.test.ts` for the new tokens. Job map empty-phase pill is the named empty state; the `JobMap` light-theme invisible-text defect is its regression test. |
| Evidence chart labels, bands and sample size readable and not colour-only; SVG uses `currentColor`/CSS variables without external resources. | The opportunity map: band shape + colour + legend, a text assertion that each band names its score in the side table, and a source-scan assertion that the SVG holds no literal and no `xlink:href`/`http` resource. Recorded above: there is no evidence chart, and this does not claim one. |
| Dark-screen print and offline one-pager fixtures use the light palette, not a black sheet; no dependency on a live settings API. | `print.test.ts` for the canvas/table/pill rules; a jsdom test that `offline.html`'s tokens equal `theme.css`'s and that its inline script branches on `system`; an e2e case with `theme: "system"` stored, `colorScheme: "light"` emulated, and the offline page measured — plus one that fails the request to `/api/config` and still paints. |
| Source scan fails on an injected component hex literal; legitimate literals have a narrow, justified allow-list. | The existing injected-hex test, plus a new injected-literal test aimed at `theme.css` outside the token block, plus the one-way count baseline. `ALLOWED_FILES` shrinks to 4 entries, each with a live reason. |
| Regression tests enumerate converted surfaces and theme/print modes. | A table-driven test that walks the 10 `WORKSPACE_PANELS` ids × {light, dark, print} and asserts each has no unresolved colour literal and is named in the inventory test — the enumeration itself is the artifact. |

## Verification

From the repo root: `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy apps brand packages`,
`uv run pytest -q`, `uv run python scripts/doc_check.py`, `uv run --directory website pytest tests/ -q`.
From `apps/studio`: `npx tsc -b --noEmit`, `npx eslint .`, `npx vitest run`, then
`npx playwright test e2e/a11y.spec.ts e2e/first-paint.spec.ts` in Chromium after `npm run build`.
By hand, in a browser, both themes and the print preview: the opportunity landscape with 12 seeded
outcomes spanning all three bands, the job map with an empty phase, the records table, and the offline
page with `theme: "system"` on a light OS.

Docs that move with the code: `docs/living-studio.md` (the canvas lenses gain their palette source, the
print rules, the offline page's third branch), `docs/roadmap.md`'s In-flight line for themed surfaces, and
`README.md`'s Studio capability bullet — the repo rule is that a capability change and its doc land in the
same task.
