# ALH-216 (M5-01.2) — Complete themed surfaces and prevent palette drift

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every colour the Studio paints comes from a named role in `theme.css`'s two token blocks, so both palettes and paper reach every surface — and the scan now watches the palette file itself.

**Architecture:** Seven role tokens land first (`theme.test.ts` measures them). The palette file's 48 opaque colour declarations are then replaced by those tokens and the raw-colour gate gains a rule it could never apply before: no opaque literal outside a token block, with a one-way count baseline for the alpha-blended remainder. The two canvas components move their colour out of inline `style` objects and SVG attributes into class rules, which is what makes `@media print` and `html.theme-light` able to reach them at all. Finally the a11y gate widens from 6 screens to all 10 lenses and the offline one-pager is pinned against the live palette.

**Tech Stack:** React 19 + TypeScript, Vite/Vitest (jsdom), Playwright + `@axe-core/playwright`, plain CSS custom properties. No new dependency.

**Spec:** `docs/superpowers/specs/2026-11-05-alh-216-themed-surfaces-design.md`

## Global Constraints

- No new CSS framework, no CSS-in-JS, no runtime colour library. Plain custom properties only (parent epic ALH-121, *Avoid*).
- No existing token is renamed. `--bg`, `--text`, `--muted`, `--faint`, `--accent`, `--accent-strong`, `--green`, `--amber`, `--red`, `--line`, `--line-strong`, `--surface`, `--surface-hover` and the `--studio-*` alias layer keep their names.
- An opaque colour literal (`#hex`, or `rgb()`/`rgba()` at full alpha) is legal in exactly two places: the `:root {` block and the `html.theme-light {` block of `src/styles/theme.css`.
- Text contrast threshold is WCAG AA 4.5:1; the focus ring 3:1. Both themes, measured from token values in `theme.test.ts` and from the painted page in `e2e/a11y.spec.ts`.
- SVG may not reference an external resource: no `xlink:href`, no `http(s)` URL inside the plot markup.
- Gates from the repo root: `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy apps brand packages`, `uv run pytest -q`, `uv run python scripts/doc_check.py`, `uv run --directory website pytest tests/ -q`.
- Gates from `apps/studio`: `npx tsc -b --noEmit`, `npx eslint .`, `npx vitest run`. Playwright only where a task names it (it needs `npm run build` first).
- Every task ends with the studio gate set green plus the root set if any non-studio file moved, then a commit.

---

## Review Focus

The spec states the vision; these are the input classes no task's happy-path test covers, and the task that
pins each.

1. **A stored *Follow the system* with no network and a light operating system.** A shared snapshot has no
   settings API to ask, so the offline page must resolve the third value from `localStorage` plus a media
   query — and must not fall through to dark. Pinned in Task 6, `it("resolves the third choice the way the app does")`.
2. **Two bands printed on a greyscale laser printer.** Amber and red become the same grey; only the shape
   carries the band. Pinned in Task 5, `it("prints the map as ink, not as a black sheet")`.
3. **A state encoded by colour alone.** `.status-dot.is-unknown` says "unknown" only by being a duller disc,
   and an empty job-map phase says it with text that is invisible on paper. Pinned in Task 2 (the dot becomes
   a ring) and Task 4 (the empty pill reads `--faint`).
4. **A role token that exists in one palette and not the other.** A token declared only in `:root` keeps its
   dark value in light, silently. Pinned in Task 1's two-block and two-pair tests, and in Task 2's staleness
   assertion.
5. **A class converted in a component but never named in `print.css`.** Its `var()` still resolves to the
   screen palette, so the sheet prints a dark rectangle. Pinned in Task 5's test that the canvas block
   contains no `var(--` and does name every converted selector.


---

## Task 1: The role tokens, measured before anything reads them

**Files:**
- Modify: `apps/studio/src/styles/theme.css` (the `:root` block at 3-34 and `html.theme-light` at 41-57 only)
- Test: `apps/studio/src/styles/theme.test.ts`

**Interfaces:**
- Consumes: nothing new.
- Produces: seven custom properties, all defined in `:root`, six of them overridden in `html.theme-light`:
  `--accent-fill` `#8b8cf8` / `#4f46e5`, `--on-accent` `#0b0c10` / `#ffffff`, `--plot-surface` `#0b0d13` / `#ffffff`,
  `--tint-accent` `rgba(139, 140, 248, 0.12)` / `rgba(79, 70, 229, 0.10)`,
  `--tint-accent-strong` `rgba(139, 140, 248, 0.2)` / `rgba(79, 70, 229, 0.18)`,
  `--tint-amber` `rgba(240, 179, 74, 0.15)` / `rgba(180, 83, 9, 0.12)`,
  `--brand-tile` `#131722` / *(not overridden — the mascot tile is brand, not a theme surface)*.

**Amended as built.** Step 3's contrast test measured the pair this task shipped and refused it: white on
`#8b8cf8` is 2.90:1 and dark ink on it is 6.69, but nothing in the stylesheet fills with `#8b8cf8` — every
filled control uses `--accent-strong` (`#6366f1`) under white ink, which is **4.46:1** in both themes. So
`--accent-fill`/`--on-accent` are `#4f46e5`/`#ffffff`, declared once and *not* overridden in light; the
override list above drops to four names (`plot-surface`, `tint-accent`, `tint-accent-strong`, `tint-amber`),
and the test asserts the pair is absent from `html.theme-light` rather than present. Task 2 carries the
seven background re-points that follow from it.

- [ ] **Step 1: Write the failing tests** in `theme.test.ts`, in a new `describe("role tokens")`. Reuse the file's existing `readBlock`, `colorTokens`, `contrast` helpers; add one helper that sees through rgba values too:

```ts
function declaredNames(block: string): Set<string> {
  return new Set(Array.from(block.matchAll(/--([a-z0-9-]+)\s*:/g), (m) => m[1]));
}
```

Assertions:
- `it("defines every role token in the dark palette")` — `declaredNames(readBlock(":root {"))` contains all seven.
- `it("overrides every role token that changes with the theme, and only names it in one block when it does not")` — the light block contains `accent-fill`, `on-accent`, `plot-surface`, `tint-accent`, `tint-accent-strong`, `tint-amber`; and `expect(declaredNames(light).has("brand-tile")).toBe(false)` with the comment that a fixed value is declared once.
- The two measurable pairs, looped over both palettes the way the existing contrast tests loop:
  - `it("keeps the ink on a filled control at WCAG AA in the ${name} theme")` — `contrast(tokens["on-accent"], tokens["accent-fill"]) >= 4.5`.
  - `it("measures the canvas text on the ground the canvas actually paints, in the ${name} theme")` — `--text` and `--muted` both at ≥ 4.5 on `--plot-surface`.

- [ ] **Step 2: Run them to verify they fail** — `npx vitest run src/styles/theme.test.ts`. Expect failures naming the missing tokens (`tokens["on-accent"]` is `undefined`, so `contrast` yields `NaN`).

- [ ] **Step 3: Add the values.** Append the six dark values and the six light overrides to the two blocks, in the order listed in the Interfaces block, then `--brand-tile` in `:root` only. Keep the file's existing comment style: a short block comment above each group naming the role it serves, not the hex.

- [ ] **Step 4: Run the whole style suite** — `npx vitest run src/styles`. Expect green, including the existing `theme tokens` test, which now must still find every referenced `var()` defined (nothing references the new names yet).

- [ ] **Step 5: Commit**

```bash
git add apps/studio/src/styles/theme.css apps/studio/src/styles/theme.test.ts
git commit -m "feat(studio): name the roles the canvas and filled controls need (ALH-216)"
```

---

## Task 2: The palette file comes inside the scan, and its 48 opaque colours move to tokens

**Files:**
- Modify: `apps/studio/src/styles/colors.test.ts` (the gate)
- Modify: `apps/studio/src/styles/theme.css` (48 declarations, all below line 57; none inside the token blocks)
- Test: `apps/studio/src/styles/colors.test.ts`, `apps/studio/src/styles/theme.test.ts`

**Interfaces:**
- Consumes: the seven tokens from Task 1.
- Produces:
  - `opaqueOutsideTokens(source: string): Finding[]` — every declaration in `theme.css` outside a token block whose value contains an opaque colour literal.
  - `alphaOutsideTokens(source: string): Finding[]` — the same for literals that carry an alpha below 1.
  - `TOKEN_BLOCKS: number[][]` — the line ranges of `:root {`, `html.theme-light {` and the `@media` token block at 4502, derived by brace-depth walk, not hard-coded.
  - `OPAQUE_CEILING = 0` and `ALPHA_BASELINE = <measured>` as module constants.
- The 48 declarations' destinations, in full (this is the migration; nothing else may invent a value):

| Selector / site | Today | Becomes |
| --- | --- | --- |
| `.composer__send` 866, `.bell-badge` 2978, `.studio-button--primary` 3293, `.ui-action--primary` 3780, `.pill-changelog:hover` 4200, `.changelog-modal__unread` 4260, `.approval__allow` 5436, `.banner__action--primary` 5907, `.suggestion-modal__primary` 6435, `.message__avatar` 1366 | `#0b0c10`, `#fff`/`#ffffff`, `#f8f8ff` | `var(--on-accent)` |
| `.ui-action--primary:hover` 3784 | `background: #7c7ff5` | `background: var(--accent-fill)` plus `box-shadow: 0 0 0 3px var(--tint-accent-strong)` — hover rings, it does not deepen, because a second fill value would need a second ink value to measure |
| `.pill-changelog:hover` 4199 | `border-color: #818cf8` | `border-color: var(--accent-fill)` |
| `.message__avatar` 1365 | `linear-gradient(140deg, #6366f1, #8b5cf6)` | `linear-gradient(140deg, var(--accent-strong), var(--accent))` |
| `.brand__mark` 4724 | `var(--odi-tile, #131722)` | `var(--brand-tile)` |
| `.message__body` 1374, `.evidence blockquote` 2354, `.failure__suggestion` 2664, `.ui-card__evidence` 3559, `.ui-pill--neutral` 3578, `.ui-meter__value` 3615, `.ui-action--ghost` 3790, `.ui-table__statement` 3857, `.ui-bet__value` 3885, `.ui-phase__items` 3920, `.ui-quote` 3931, `.ui-field dd` 4012, `.changelog-category__item` 4367 | `#e8e9ed`, `#dfe1e7`, `#e7e5e4`, `#cbd5e1`, `#e2e8f0` | `var(--text)` |
| `.failure__detail` 2618 | `#d6d3d1` | `var(--muted)` |
| `.palette__name` 749, `.pill-changelog` 4191, `.changelog-category__title` 4352, `.changelog-modal__badge` 4250, `.changelog-release__new` 4271, `.changelog-release__version` 4333 | `#c7c8ff`, `#a5b4fc`, `#818cf8` | `var(--accent)` |
| `.notice` 2302, `.message__tag` 2562, `button.message__tag:hover` 2583, `.canvas-warnings` 3333, keyframe 4607, keyframe 4611 | `#d6c19b`, `#f0b45a`, `#f5c67a`, `#f59e0b`, `#fbbf24` | `var(--amber)` |
| `.failure__icon` 2602, `.failure__message` 2611, `.quiet-action--danger:hover` 2906, `.panel-failure__message` 3315, `.banner--critical` 5928 | `#f87171`, `#fca5a5`, `#ef4444` | `var(--red)` |
| `.composer__input::placeholder` 836, `.ui-tone-bg--neutral` 3634, `.status-dot.is-unknown` 4766 | `#6f7480`, `#94a3b8`, `#5b616c` | `var(--faint)` |

- [ ] **Step 1: Write the failing gate tests** in `colors.test.ts`, inside the existing `describe("raw colours")`, after adding the two scan helpers:
  - Declare `const OPAQUE_CEILING = 0` and `const ALPHA_BASELINE = 194` (the measured counts) at module level, then: `it("refuses an opaque colour literal in the palette file's own rules")` — `expect(opaqueOutsideTokens(themeSource).map(f => \`\${f.file}:\${f.line} \${f.literal}\`)).toEqual([])`, and `OPAQUE_CEILING` is what the helper compares each finding against, so a ceiling of 0 makes the failure name all 48 rows at once and the run output is Step 3's checklist.
  - `it("keeps the palette file's alpha washes at a baseline that can only shrink")` — assert `expect(alphaOutsideTokens(themeSource).length).toBe(ALPHA_BASELINE)`, exactly the one-way ratchet the `ALLOWED_FILES` staleness test uses: a higher count is new drift, a lower count means someone improved it and must bank the new number here.
  - `it("names the line for an opaque literal injected into the palette file")` — the issue's own requirement, aimed at the file the old gate could not see: `expect(opaqueOutsideTokens(".card {\n  color: #ff00ff;\n}\n").map((f) => f.line)).toEqual([2])`.
  - `it("reads a literal nested in a gradient or hiding in a var() fallback")` — both shapes are findings, so a future edit cannot smuggle one past a property-name check.
  - `it("does not treat a token block's own values as drift")` — the seven Task 1 tokens and the existing palette values are not findings.
- [ ] **Step 2: Run it** — `npx vitest run src/styles/colors.test.ts`. Expect the first test to fail listing 48 `theme.css:line literal` rows. Keep that output; it is the checklist.
- [ ] **Step 3: Migrate the 48** by the table above. Change nothing else in the file. Where the table says a token is a byte-identical match (`#f87171` → `--red`, `#6366f1` → `--accent-strong`) the rule's rendered appearance is unchanged in dark and fixed in light; where the table replaces a light-on-dark value with a themed one (`.notice`, `.ui-card__evidence`), the light theme is deliberately changing, which is the defect being closed.
- [ ] **Step 4: Pin the roles that moved** in `theme.test.ts`, `describe("theme tokens")`: `it("paints a notice, an evidence quote and a neutral meter from the palette, not from a stray hex")` — a small `declaration(selector, prop)` helper that reads a rule body out of `themeCss`, asserting `.notice` `color: var(--amber)`, `.ui-card__evidence` `color: var(--text)`, `.ui-tone-bg--neutral` `background: var(--faint)`, `.composer__send` `color: var(--on-accent)` and `background: var(--accent-fill)`, `.brand__mark` `background: var(--brand-tile)`.
- [ ] **Step 5: Give the unknown status a shape, not a duller colour.** Step 3 left `.status-dot.is-unknown` as `background: var(--faint)`, which is still only a colour. Turn it into a square ring — `background: transparent; border-radius: 2px; box-shadow: inset 0 0 0 1.5px var(--faint)` — so *unknown* is a shape while *known* and *warn* stay filled discs. Add the assertion to `theme.test.ts`: `it("makes an unknown status a shape, not only a colour")`.
- [ ] **Step 6: Run the suite** — `npx vitest run src/styles`. Green.
- [ ] **Step 7: Commit** — `feat(studio): hold the palette file to its own tokens (ALH-216)`

**As built.** The gate counts literals, so 48 declarations hold **49** of them (`.message__avatar`'s
gradient has two stops) and `OPAQUE_CEILING = 0` names all 49 at once. The wash count measured **208**, not
194: the earlier figure was per line, and a few lines carry two. Beyond the table, seven controls moved
from `background: var(--accent-strong)` to `var(--accent-fill)` so the ink shipped above them has a fill the
pair test can measure (`.bell-badge`, `.ui-action--primary`, `.changelog-modal__unread`, `.approval__allow`,
`.banner__action--primary`, `.suggestion-modal__primary`, and `.studio-button--primary`, whose
`--studio-indigo → --studio-indigo-strong` gradient flattened to the fill: white on its light stop was
2.90:1), and `.composer__send` went from `background: var(--text)` — ink on ink in the light theme — to the
pair. Three destinations differ from the table, each because the table read a value without reading the
rule: `.pill-changelog:hover`'s `#ffffff` is `var(--text)`, not `--on-accent`, because the hover ground is a
30%-alpha wash rather than a fill and white ink on a light theme's wash is invisible; its `border-color` is
`var(--accent)`, the same hue the pill already tints with; `.ui-action--primary:hover` keeps a lift by
ringing (`box-shadow: 0 0 0 3px var(--tint-accent-strong)`) once its fill stops changing; and
`.message__avatar`'s gradient starts on `--accent-fill` so its glyph sits on ink the pair test measured.
Step 4 gained a fourth pin beyond the plan: **a rule may read `color: var(--on-accent)` only if the same
rule paints with `--accent-fill`** — the invariant that would have caught the 4.46:1 defect, held open-ended
rather than by selector list.

**Review Focus 4 lives here:** a role token declared only in `:root` keeps its dark value in the light theme; the two-palette tests in Step 1 of Task 1 and the staleness assertions in Step 1 above are what catch it.

---

## Task 3: The opportunity map reads the palette, and a band is a shape as well as a colour

**Files:**
- Modify: `apps/studio/src/components/canvas/OpportunityLandscape.tsx` (colour sites at 142, 531, 561-562, 577, 582, 595, 599, 602, 613-614, 625, 650, 659, 770, 802-804, 826, 835-836)
- Modify: `apps/studio/src/lib/odi.ts` (add the band helper beside `isUnderserved`)
- Modify: `apps/studio/src/styles/theme.css` (a new `/* Opportunity landscape */` section: the classes below)
- Modify: `apps/studio/src/styles/colors.test.ts` (drop the file's `ALLOWED_FILES` entry, `ALLOWED_CAP` 6 → 5)
- Modify: `apps/studio/e2e/a11y/knownPairs.ts` (delete both #335 matrix entries)
- Test: `apps/studio/src/lib/odi.test.ts`, `apps/studio/src/components/canvas/OpportunityLandscape.test.tsx`, `apps/studio/src/styles/theme.test.ts`

**Interfaces:**
- Consumes: `--plot-surface`, `--tint-accent`, `--tint-amber`, `--accent`, `--amber`, `--red`, `--text`, `--muted`, `--faint`, `--line` from the palette.
- Produces, in `src/lib/odi.ts`:

```ts
export type ScoreBand = "served" | "underserved" | "deep";
export const DEEP_SCORE = 15;
export function bandOf(score: number | null): ScoreBand;
```

and these class names, emitted by the component and declared in `theme.css`:
`opportunity-matrix__toggle`, `__plot`, `__grid`, `__axis`, `__band`, `__zone-label--underserved`,
`__zone-label--overserved`, `__node` + `__node--served|underserved|deep`, `__node-edge`, `__label` +
`__label--active`, `__row--selected`, `__header-row`, `__pill` + `__pill--underserved`, `__legend`.
`bandOf` is the only place the 15 threshold appears; the component imports it, `theme.css` reads no number.

- [ ] **Step 1: Write the failing band tests** in `src/lib/odi.test.ts`: `it("splits the score range into the three bands the map draws")` — `bandOf(null) === "served"`, `bandOf(4) === "served"`, `bandOf(10.5) === "underserved"`, `bandOf(14.9) === "underserved"`, `bandOf(15) === "deep"`, and that `underserved` agrees with `isUnderserved` across `0…20` in 0.1 steps for every non-deep value. Run — fails on the missing export.
- [ ] **Step 2: Implement `bandOf`** in `odi.ts`: `null` → `"served"`; `score >= DEEP_SCORE` → `"deep"`; else `isUnderserved(score) ? "underserved" : "served"`. Green.
- [ ] **Step 3: Write the failing component tests** in `OpportunityLandscape.test.tsx`:
  - `it("marks a band by shape as well as colour")` — seed three outcomes scoring served, underserved and deep; assert the plot contains exactly one `circle.opportunity-matrix__node--served`, one `rect.opportunity-matrix__node--underserved` and one `polygon.opportunity-matrix__node--deep`.
  - `it("names every band shape in a legend the reader can read")` — the rendered legend text contains `circle`, `square`, `triangle` and the three band words.
  - `it("paints the map only from the palette")` — for the rendered plot container and the header row, assert the colour-bearing properties arrive through classes: `expect(container.querySelector(".opportunity-matrix__plot")).toHaveClass(...)` plus a source-level assertion that the component no longer writes a colour: `expect(landscapeSource).not.toMatch(/(fill|stroke|background|color)\s*[:=]\s*["'{][^"'}]*#[0-9a-fA-F]{3}/)`. (Read the component text with `?raw`, the way `colors.test.ts` does.)
  - `it("keeps the decorative gradient out of the plot")` — `expect(container.querySelector("linearGradient")).toBeNull()` and the underserved zone polygon carries `opportunity-matrix__band`.
  - `it("holds still under reduced motion and still shows the band")` — the shape assertion re-run with the pulse ring absent, mirroring how `theme.css` collapses animations; assert no `animate` element is required for a band to be identifiable.
  - `it("draws the map without referencing an outside resource")` — `expect(container.innerHTML).not.toMatch(/xlink:href|https?:\/\//)`.
  - Update the existing tests that assert on the removed inline styles (the selected-row wash, the amber pill) to the class names instead.
- [ ] **Step 4: Run them — expect failures.** `npx vitest run src/components/canvas/OpportunityLandscape.test.tsx`
- [ ] **Step 5: Convert the component.** Replace each colour-bearing inline style and SVG presentation attribute with the class above; keep layout (`display`, `width`, `padding`, `position`) exactly where it is. The node glyph becomes a `switch` on `bandOf(plot.score)` returning `circle` / `rect` (centred, `width = height = 2r`) / `polygon` (an equilateral triangle on the same centre), each carrying `className={\`opportunity-matrix__node opportunity-matrix__node--${band}\`}`. The node ring reads `--plot-surface` through `__node-edge` rather than a hex. The pulse `<animate>` stays where motion is allowed — it is a third cue, not the second.
- [ ] **Step 6: Declare the classes** in `theme.css`: `__plot { background: var(--plot-surface); border-color: var(--line) }`, `__grid { stroke: var(--line) }`, `__axis, __label { fill: var(--muted) }`, `__label--active { fill: var(--text) }`, `__band { fill: var(--tint-amber); stroke: var(--amber) }`, `__zone-label--underserved { fill: var(--amber) }`, `__zone-label--overserved { fill: var(--faint) }`, `__node--served { fill: var(--accent) }`, `__node--underserved { fill: var(--amber) }`, `__node--deep { fill: var(--red) }`, `__row--selected { background: var(--tint-accent) }`, `__header-row { background: var(--surface); color: var(--muted) }`, `__pill { background: var(--surface); color: var(--muted) }`, `__pill--underserved { background: var(--tint-amber); color: var(--amber) }`, `__toggle { background: var(--surface) }`, and `__legend` as muted body text. No literal in any of them.
- [ ] **Step 7: Delete the exemption and the two known pairs.** Remove `src/components/canvas/OpportunityLandscape.tsx` from `ALLOWED_FILES`, set `ALLOWED_CAP = 5`, and delete both #335-owned entries from `e2e/a11y/knownPairs.ts` (the axis-label `rgb(21,23,28)` and caption `rgb(86,93,107)` pairs measured over `rgb(109,110,113)`). `npx vitest run src/styles src/test` — the stale-entry test and `contrast.test.ts` must both be green.
- [ ] **Step 8: Prove it in the browser.** `npm run build && npx playwright test e2e/a11y.spec.ts -g "landscape"` in Chromium, both themes. Expect the six landscape/records cases green with the two exemptions gone — this is the measurement that says the light-theme plot ground is now light.
- [ ] **Step 9: Commit** — `feat(studio): put the opportunity map on the palette, and give each band a shape (ALH-216)`

---

## Task 4: The job map follows, and an empty phase stops being invisible

**Files:**
- Modify: `apps/studio/src/components/canvas/JobMap.tsx` (colour sites at 229, 231-232, 237, 279-280)
- Modify: `apps/studio/src/styles/theme.css` (a `/* Job map */` section)
- Modify: `apps/studio/src/styles/colors.test.ts` (drop the file's `ALLOWED_FILES` entry, `ALLOWED_CAP` 5 → 4)
- Test: `apps/studio/src/components/canvas/JobMap.test.tsx`, `apps/studio/src/styles/theme.test.ts`

**Interfaces:**
- Consumes: `--surface`, `--line`, `--tint-accent`, `--tint-accent-strong`, `--accent`, `--faint`, `--text`, `--muted`.
- Produces: `jobmap__tile`, `jobmap__tile--selected`, `jobmap__tile--empty`, `jobmap__pill`, `jobmap__pill--filled`, `jobmap__pill--empty`.

- [ ] **Step 1: Write the failing tests** in `JobMap.test.tsx`:
  - `it("marks a phase with no steps as empty, in a class and not a colour")` — render a job with one empty phase; assert its tile carries `jobmap__tile--empty` and its count pill carries `jobmap__pill--empty`.
  - `it("keeps the empty phase's count legible in both palettes")` — the defect this closes is `color: rgba(255,255,255,0.2)`, white ink that vanishes on paper. Assert the pill's colour arrives from a token, by reading the class rule out of `theme.css`: `expect(jobMapRules(".jobmap__pill--empty")).toMatch(/color:\s*var\(--faint\)/)`. Add `it("never paints the job map with a literal")` mirroring Task 3's source-level assertion.
  - `it("selects a phase through a class")` — the selected tile carries `jobmap__tile--selected`, and `onClick`/`aria-pressed` behaviour is unchanged.
- [ ] **Step 2: Run — expect failures.** `npx vitest run src/components/canvas/JobMap.test.tsx`
- [ ] **Step 3: Convert `JobMap.tsx`** to the six classes, layout styles untouched.
- [ ] **Step 4: Declare the classes** in `theme.css`: tile default `background: var(--surface); border: 1px solid var(--line)`; `--selected { background: var(--tint-accent-strong); border-color: var(--accent) }`; `--empty { background: transparent; border-style: dashed }`; `__pill--filled { background: var(--tint-accent); color: var(--accent) }`; `__pill--empty { background: transparent; color: var(--faint) }`.
- [ ] **Step 5: Delete the exemption**, `ALLOWED_CAP = 4`, run `npx vitest run src/styles src/components/canvas` — the stale-entry test is what proves the file really has no literals left.
- [ ] **Step 6: Report the alias layer's remaining reach.** Run `grep -rn -- "--studio-" apps/studio/src | wc -l`. If it is zero outside `theme.css`, delete the alias block at `theme.css:25-32` and fix whatever the token-name test then names; otherwise leave it and record the count in the PR body as an outstanding naming cleanup (it is not a theming defect — every alias already resolves to a themed token). Say which branch happened in the commit message.
- [ ] **Step 7: Commit** — `feat(studio): theme the job map, and make an empty phase readable on paper (ALH-216)`

---

## Task 5: Paper reaches the converted surfaces

**Files:**
- Modify: `apps/studio/src/styles/print.css` (a canvas and table block inside `@media print`)
- Create: `apps/studio/e2e/print.spec.ts`
- Test: `apps/studio/src/styles/print.test.ts`

**Interfaces:**
- Consumes: every `opportunity-matrix__*` and `jobmap__*` class from Tasks 3-4.
- Produces: no new selector. The print sheet must name each converted class, because `var(--plot-surface)` still resolves to the *screen* palette's dark value in print — the reason a token is not enough for paper.

- [ ] **Step 1: Write the failing test** in `print.test.ts`: `it("reaches every converted canvas surface with ink on paper")` — one array of selectors (the Task 3/4 class list) and for each, assert print.css contains it with a paper value; also `it("does not leave a canvas rule on a screen token")` — within the canvas block, assert no `var(--` appears, so paper cannot inherit a dark palette. Run — fails.
- [ ] **Step 2: Write the browser test** in `e2e/print.spec.ts`: open Studio in the dark theme, seed outcomes spanning the three bands, open the Landscape lens, `await page.emulateMedia({ media: "print" })`, then assert `getComputedStyle` gives `.opportunity-matrix__plot` the white ground (`rgb(255, 255, 255)`) and the axis text a dark ink, and assert the three band shapes are still distinct. Name it `it("prints the map as ink, not as a black sheet")`.
- [ ] **Step 3: Add the print rules.** Ink for text (`#111`, `#444`), paper for grounds (`#fff`, `#f4f4f5`), grey for rules (`#ccc`, `#bbb`), and three separable greys for the bands (`#444` served, `#888` underserved, `#111` deep) — the shape is what carries the band, so the greys only have to be distinct. Cover the records table rows, the band pill, the legend, and the job map tile and pill states, including the dashed empty tile.
- [ ] **Step 4: Run the print gates** — `npx vitest run src/styles` then `npx playwright test e2e/print.spec.ts` after `npm run build`.
- [ ] **Step 5: Commit** — `feat(studio): print the canvas in ink, with the bands still distinct in grey (ALH-216)`

**Review Focus 1 and 5 live here:** a shared snapshot that no one can theme (an unstyled dark rectangle on paper), and two bands that collapse into one grey.

---

## Task 6: The offline one-pager follows the system and cannot drift from the palette

**Files:**
- Modify: `apps/studio/public/offline.html` (the inline resolver at 14-23; the `:root` / `html[data-theme="light"]` token blocks)
- Create: `apps/studio/src/styles/offlinePalette.test.ts`

**Interfaces:**
- Consumes: `theme.css`'s token values, read from disk.
- Produces: `data-theme="light" | "dark"` on the offline document element, resolved by the same three-branch rule as `resolveTheme` in `src/lib/theme.ts` — `light`, `dark`, and anything else (including `system` and no stored key) following `matchMedia("(prefers-color-scheme: dark)")`.

- [ ] **Step 1: Write the failing tests** in `offlinePalette.test.ts`, reading `public/offline.html` with `readFileSync(new URL("../../public/offline.html", import.meta.url), "utf8")`:
  - `it("copies the palette rather than inventing one")` — every colour-valued custom property declared in the offline `:root` and light blocks equals the same name in `theme.css`'s dark and light blocks. This test also catches the `--line` mismatch that already exists (`0.14` against the theme's `0.07`).
  - `it("resolves the third choice the way the app does")` — extract the inline script, run it in jsdom with `localStorage` and `matchMedia` stubbed, and assert `document.documentElement.dataset.theme` for the five cases: stored `light`, stored `dark`, stored `system` with a light system, stored `system` with a dark system, and nothing stored with a dark system.
  - `it("needs no server to paint")` — assert the file contains no `fetch(`, no `http(s)://` resource reference, and no `src=` on an element; the acceptance line is about a snapshot with no live settings API.
- [ ] **Step 2: Run — expect failures** naming the `--line` drift and the `system` case.
- [ ] **Step 3: Fix the resolver and the values.** The inline script becomes the three-branch rule (still ES5, still wrapped in the existing `try/catch`, still setting `dataset.theme` before any paint); align `--line` to the token. Keep `color-scheme` per block, and leave `--font` out of the colour comparison by name.
- [ ] **Step 4: Run the suite** — `npx vitest run src/styles`.
- [ ] **Step 5: Commit** — `fix(studio): the offline page follows the system, and its palette is pinned to the app's (ALH-216)`

**Review Focus 1 (first line) lives here:** a reader with *Follow the system* on a light machine, offline, must not get a black sheet.

---

## Task 7: The gate walks every lens, and the docs say what changed

**Files:**
- Modify: `apps/studio/e2e/a11y.spec.ts` (`SCREENS`, `goto`)
- Modify: `apps/studio/e2e/a11y/knownPairs.ts` (whatever the widened run proves stale)
- Modify: `apps/studio/src/components/workspace/panels.test.ts` (or create it if absent) — the enumeration test
- Modify: `README.md`, `docs/living-studio.md`, `docs/roadmap.md`
- Test: `apps/studio/e2e/a11y.spec.ts`

**Interfaces:**
- Consumes: `WORKSPACE_PANELS` from `src/components/workspace/panels.tsx` (10 entries, each with a `label`).
- Produces: an a11y matrix over `{home, settings} ∪ every panel label` × `{dark, light}`.

- [ ] **Step 1: Enumerate the surfaces** in `src/components/workspace/panels.test.ts`: `it("the a11y gate walks every lens the workspace can open")` — import the panel ids and assert the e2e screen list (read from `e2e/a11y.spec.ts` via `?raw`, or from a shared `e2e/a11y/screens.ts` const both files import) contains every `WORKSPACE_PANELS` label. Prefer the shared const: create `e2e/a11y/screens.ts` exporting `PANEL_SCREENS` and `HOME_SCREENS`, import it from the spec, and assert against it here. Run — fails while the spec still lists six.
- [ ] **Step 2: Widen the spec.** `SCREENS` becomes `["home", ...HOME_SCREENS]`; `goto` opens a lens through the rail button the existing helper already targets (`rail(page).getByRole("button", { name: new RegExp(`^${label},`) })`), so all ten lenses are reached the way a person reaches them. Seed one scored outcome so a lens has content rather than only an empty state.
- [ ] **Step 3: Run the widened matrix and fix what it names.** `npm run build && npx playwright test e2e/a11y.spec.ts`. Expect new unlisted pairs from segments, evidence, memory, schedule and capture. For each: the fix is a token in `theme.css` or a class on the component — never a new `KNOWN_PAIRS` entry, unless the pair is genuinely owed to another issue, in which case it gets that issue's number and a line in the PR body's *Known limitations*. The suite's own staleness test then deletes what you fixed; keep deleting until both directions are green.
- [ ] **Step 4: Docs.** `docs/living-studio.md`: the Appearance row gains that the canvas and the print sheet read the same tokens; a new **Print** row for what paper gets (ink, not the screen palette) and one for the offline page's three-branch resolution. `docs/roadmap.md`: move the In-flight line to *Every surface reads the palette*, naming the shape-coded bands and the drift guard. `README.md`: extend the Studio capability sentence — the map marks each band by shape as well as colour, and a printed page is ink.
- [ ] **Step 5: Full gate set.** Root: `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy apps brand packages`, `uv run pytest -q`, `uv run python scripts/doc_check.py`, `uv run --directory website pytest tests/ -q`. Studio: `npx tsc -b --noEmit`, `npx eslint .`, `npx vitest run`, `npx playwright test e2e/a11y.spec.ts e2e/print.spec.ts e2e/first-paint.spec.ts`.
- [ ] **Step 6: Commit** — `test(studio): every lens is measured in both palettes, and the docs say so (ALH-216)`

---

## What stays, and is said out loud

- **194 alpha-blended literals** in `theme.css` remain under the `ALPHA_BASELINE` count. They are the same defect class at lower severity — a white wash is invisible on a light page — and the honest statement is that they are counted, one-way, and not yet zeroed.
- **`onboarding.css`** (a fixed dark scrim) and **`OdiMascot.tsx`** (brand art gated by `brand/tools/render.py --check`) keep their `ALLOWED_FILES` entries with their existing reasons.
- **The parent's `--chart-1..6` series palette has no consumer.** There is no evidence chart in the app; `canvas/EvidenceStream.tsx` is a list. Recorded in the PR body as a surface this change does not claim, per the issue's own instruction that missing surfaces be recorded before full coverage is claimed.
- **The `--studio-*` alias layer** survives wherever Task 4 Step 6 found it still referenced; it resolves to themed tokens, so it is a naming cleanup, not a defect.
- **ALH-131's screen-reader audit** is not touched. This change only widens the contrast rule's screen list; the other axe rules stay out of the gate, exactly as they were.
