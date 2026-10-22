# Odi the Otter — mascot and brand identity — design

**Status:** approved for implementation
**Date:** 2026-10-21
**Scope:** `brand/` (new, source of truth), `apps/studio` (SPA + Tauri),
`apps/cli`, `README.md`. Deliberately excludes `website/` (see Non-goals).

## Intent

The project is public and forkable. Its name, its README, and its UI are all
copyable, but a *character* is much harder to copy credibly: it carries taste,
history, and a recognizable silhouette that, once people meet it, they expect
to see again. Odi is that character — the friendly face of Outcome-Driven
Innovation, present in the terminal, in the studio, in the app icon, and in the
favicon.

Odi is also a defensive asset. A distinctive mascot is a weak trademark: a
fork can copy the README, but a fork that ships Odi has visibly copied
Agentic ODI, and the provenance story ("the one with the otter") compounds.

The mascot must be **cute** (people should smile at it) and **professional**
(nobody should be embarrassed to see it in a professional product). It must be
**legible at 16 pixels** and **honest at 1024**.

## Goals

1. One character, one silhouette, recognizable at 16 px, on every surface.
2. A construction that is mathematically deliberate — golden-ratio derived
   proportions — so the character reads as designed rather than doodled.
3. Assets that are **reproducible from source**: a committed generator, not
   hand-exported binaries, so a fork can see exactly how every pixel was made.
4. Zero new runtime dependencies. The generator uses only what the repo already
   declares.
5. A brand guide that a third party can follow without asking us.

## Non-goals

- **No change to `website/`.** The marketing site is mid-redesign on
  `feature/gh-pages-redesign`, which rewrites `website/` wholesale. Touching
  `website/assets/mark.svg` or `favicon.svg` here guarantees a conflict on that
  branch. The mascot lands in `brand/` and the site swap is a documented
  two-line follow-up on the redesign branch.
- **No wordmark lockup.** `odi-lockup.svg` was considered and dropped: no
  surface in this iteration consumes it, and hand-authoring letterforms is a
  drawing project with no payoff. A `<text>`-based lockup would render
  differently per machine and would break the "committed art matches a fresh
  render" guarantee. The lockup is a follow-up, when a surface needs it.
- **No new licensing terms.** The repo already ships an MIT `LICENSE`. The
  mascot is covered by it. What we add is a *provenance* note, not a legal
  claim.
- **No animation, no sprite sheet, no 3D.** First iteration is static art.
- **No mascot in every surface.** A mascot on every pixel is noise. It goes
  where a human would look for the product's face: the app icon, the favicon,
  the studio's brand mark, the terminal banner, and the README.
- **No emoji.** The repo's own website test suite bans emoji; the CLI already
  uses a few, but the mascot must not depend on them.

## The character

**Name:** Odi. Spelled exactly like the `odi` binary, pronounced "odee".

**Species:** otter (sea otter).

**Why an otter.** The name is the hook — "Odi the Otter" is alliterative,
memorable, and rhymes with the product without impersonating anything. The
species carries the semantics: otters are the tool-using problem solvers of
the animal world. They take an ambiguous shell, a stone, and a current, and
they *engineer* an outcome from it. That is the product thesis in one animal:
take messy human context, find the tool that turns it into a measurable
customer outcome. Otters are also wide-headed, round-eyed, and warm brown —
cute without being saccharine, and visually distinct from every other
developer mascot in wide use.

**Deliberate exclusions.** No cats (Mistral's Le Chat, and the feline trope is
crowded). No octocat (GitHub trademark). No penguin (Tux). No dog (reads as
Garfield's Odie). No bee (Honeycomb). An otter is not currently a
developer-tool mascot, which is exactly the point: the silhouette is
unclaimed.

**Personality:** curious, competent, a little bit pleased with itself. Not a
robot, not an anthropomorph in a hard hat, not a "smart" creature with a
visor. Just a friendly otter who has clearly read the manual.

## Golden-ratio construction

Every proportion below is derived from a single constant, φ = 1.6180339887,
applied to a **32 × 32 master pixel grid**. The numbers in the table are the
literal pixel values the generator uses, so the construction is checkable, not
decorative.

The construction unit is the head width **W**. Every other dimension is W
divided by a power of φ, rounded to the nearest whole pixel (φ¹ = 1.618,
φ² = 2.618, φ³ = 4.236, φ⁴ = 6.854). The head's *internal* proportions are
scale-invariant, so the same head renders at W = 20 in the bust and W = 22 in
the icon without changing its character.

| Feature | Rule | Value (px) | Golden point |
|---|---|---|---|
| Canvas | — | 32 × 32 | — |
| Head width `W` | unit | 20 (bust) / 22 (icon) | — |
| Head height | `W / φ` | 12 | head **is** a golden rectangle (20:12 = 1.667, within 3% of φ) |
| Eye separation (centre-to-centre) | `W / φ` | 12 | eyes at x = 16 ± 6 → 1 : 0.618 : 1 across the face |
| Eye size | `W / φ²` | 8 → 4 × 4 rendered | capped for legibility |
| Muzzle width | `W / φ²` | 8 | golden section of the lower face |
| Muzzle height | `(W / φ²) / φ` | 5 | — |
| Nose width | `W / φ³` | 5 | rounded: 2 px on top, 5 px below |
| Ear radius | `W / 4φ` | 3 → 6 px across | the head's outer edges |
| Body width | `0.85 × W` | 17 | shoulders narrower than the head |
| Spark | — | 3 px plus | a highlight, not a proportional element |

**The two-ladder composition.** The head is a golden rectangle. The face
divides it at the golden section: eye separation is 0.618 of the head width,
the muzzle is 0.382 of it, and the nose is 0.236 of it. The body is 0.85 of
the head — the classic chibi "small body, large head" proportion, which is
the golden rule applied to mass, where the smaller partner of a golden pair
is the one that reads as "just right". Read as a silhouette the head is a
golden rectangle; read as a face, every feature sits at a golden point. That
is the whole claim, and the generator computes it, so it is checkable.

**The spark.** The existing site mark is an ascending two-step polyline with
an apex dot — a rising opportunity curve. Odi carries that dot: a single
accent-coloured spark floating above the head. It is the one element that
ties the character to the product's existing visual language, and it is the
character's *signal*: the outcome Odi is looking for. It is a highlight
rather than a proportional element, so it is the one dimension the golden
ladder does not govern.

## Palette

The mascot must work on the studio's near-black chrome (`--bg: #0a0b0e`) and
on the website's light pages. A warm subject on a cool ground does both.

| Token | Hex | Use |
|---|---|---|
| `odi-ink` | `#1B1410` | outline, nose, pupils |
| `odi-fur` | `#B4794C` | main coat |
| `odi-fur-light` | `#DCA871` | cheeks, brow, chest edge |
| `odi-cream` | `#F6EAD8` | muzzle, chest, eye highlight |
| `odi-accent` | `#8B8CF8` | the spark (studio `--accent`) |
| `odi-tile` | `#131722` | app-icon tile (matches the site mark tile) |

`odi-accent` is the studio's existing accent, so the mascot is already on
brand. The coat browns are the only new colours in the system, and they are
warm enough to read as "character" against the cool indigo/blue chrome.

Measured contrast ratios (WCAG 2.1) are published in `brand/README.md` and
asserted by the brand tests. They are stated per pairing, not as a blanket
claim: the ink-on-fur outline and the fur-on-chrome pairings are the ones
that carry legibility, and the guide says so.

## Variants

Three renders of one character, all from the same head geometry.

| Variant | Contents | Used for |
|---|---|---|
| `head` | head + ears, transparent background | nothing on its own — the base for the others |
| `mark` | `head` on the `odi-tile` rounded square | app icon, favicon, studio bar |
| `bust` | head + shoulders + chest + spark, transparent | README hero, brand guide |

The `mark` variant exists because operating-system icons want a filled shape
(Windows `StoreLogo`, macOS `.icns`), while a browser tab and a toolbar want
the character standing on its own. Both share the identical head, so they are
the same animal.

## Asset inventory

Everything lives under `brand/`, generated by a committed script, and
committed to the repo. Files marked **generated** are written by
`brand/tools/render.py` and must never be hand-edited.

```text
brand/
  README.md                     # the brand guide (public, standalone)
  assets/
    odi-mascot.svg              # bust, vector, with a φ guide layer   [generated]
    odi-mark.svg                # mark, vector                          [generated]
    odi-mascot-256.png          # bust raster (README hero)            [generated]
    odi-mascot-512.png          #                                       [generated]
    odi-mascot-1024.png         #                                       [generated]
    odi-icon-1024.png           # mark raster, the Tauri icon source    [generated]
    favicon.ico                 # 16/32/48/64, embedded PNG frames      [generated]
    favicon.svg                 # mark, vector                          [generated]
    apple-touch-icon.png        # 180 × 180 mark                        [generated]
    odi-ascii.txt               # the terminal banner, plain text       [generated]
  src/
    odi_mascot.py               # the generator: geometry, palette, raster, vector
  tests/
    test_brand_assets.py        # asset contract + generator parity
  tools/
    render.py                   # regenerate everything: `uv run python brand/tools/render.py`
```

Copies land where they are consumed:

```text
apps/studio/public/favicon.svg        [generated]  # copy of brand/assets/favicon.svg
apps/studio/public/favicon.ico        [generated]
apps/studio/public/apple-touch-icon.png [generated]
apps/studio/src/components/OdiMascot.tsx [generated]  # inline SVG, run-length encoded
apps/cli/src/agentic_odi_cli/mascot.py  [generated]  # the ASCII banner constant
apps/studio/src-tauri/icons/*           [generated]  # via `tauri icon`
```

**One source of truth.** `brand/src/odi_mascot.py` holds the palette, the φ
constants, and the raster geometry. The PNGs, the SVGs, the ICO, the studio
component, the CLI module, and the ASCII banner are all derived from it. The
brand tests assert that every committed artifact matches a fresh render, so
the art can never silently drift from its source. CI re-runs the generator and
diffs the tree, the same way `apps/studio` already re-runs `gen:api-types`.

**Rasterizer.** A tiny shape-and-outline rasterizer, not hand-placed pixels:
the generator draws ellipses and rounded rects onto the 32 × 32 grid, then
adds a 1 px `odi-ink` outline around the silhouette — the standard pixel-art
technique that produces clean, symmetric, professional edges. Features
(eyes, nose, muzzle, cheeks, spark) are stamped on top, and a 1 px `odi-cream`
highlight is added to each eye.

**The SVG** is emitted as a `<rect>` per pixel with
`shape-rendering="crispEdges"`, so it stays pixel-exact at any size. The bust
SVG also carries a `data-guides="true"` group that draws the golden
rectangles over the art for documentation.

**The ICO** is written by Pillow (already a root dev dependency) with embedded
PNG frames. The **Tauri icon set** (`apps/studio/src-tauri/icons/*`) is
regenerated by the already-declared `@tauri-apps/cli` from `odi-icon-1024.png`,
so `.icns`, `.ico`, and every `Square*Logo.png` stay canonical.

## Surfaces

| Surface | Change | File |
|---|---|---|
| App icon | Replace the purple gradient placeholder with Odi's mark | `apps/studio/src-tauri/icons/*` |
| Studio favicon | `favicon.svg` + `favicon.ico` + `apple-touch-icon.png` | `apps/studio/public/` |
| SPA `<head>` | Replace the dead `/vite.svg` reference | `apps/studio/index.html` |
| Studio brand mark | Odi's mark replaces the generic `SparkIcon` in the bar's brand slot | `apps/studio/src/components/layout/StudioBar.tsx` |
| Studio mascot component | Inline SVG component, size-prop, no dependency | `apps/studio/src/components/OdiMascot.tsx` |
| CLI banner | Odi's ASCII bust printed on chat start | `apps/cli/src/agentic_odi_cli/mascot.py`, `chat.py` |
| README | Hero image in the centred title block | `README.md` |
| Brand guide | Palette, φ construction, usage, provenance | `brand/README.md` |

**Studio mark slot.** `StudioBar.tsx` already has a `brand__mark` span
holding a `SparkIcon` inside a 28 × 28 gradient tile. The slot becomes
**32 × 32** so the 32-pixel master grid renders 1:1 and stays perfectly crisp
— a non-integer scale would blur pixel art. The tile's gradient is replaced
by the flat `odi-tile` fill with the existing 9 px radius, so the mark reads
as a small app icon in the bar. The 56 px bar height absorbs the 4 px growth
with no other layout change, and the `brand__wordmark` text is untouched.

**Studio mascot component.** `OdiMascot.tsx` is generated: the SVG is
run-length encoded (horizontal runs of identical pixels merge into one
`<rect>`), which turns ~700 rects into ~90 elements — small enough to inline
in JSX with no extra request and no image asset. The component takes a `size`
prop and is always `aria-hidden`, because it is decorative.

**CLI banner.** The banner is a generated constant in
`apps/cli/src/agentic_odi_cli/mascot.py`, printed at chat start (`chat.py`,
alongside the existing "Agentic ODI · interactive" line). It uses the Unicode
half-block technique (▀/█) so the 32 × 32 grid maps to a 64 × 32-pixel
art block in 16 text rows, and 24-bit ANSI colour for the fur. It is printed
**only** when stdout is a TTY that can encode UTF-8; in a pipe or a CI log the
banner is omitted entirely rather than dumped, and `NO_COLOR` drops the
colour while keeping the shape. The module imports nothing heavy, so the
`--version` / `--help` fast path (guarded by
`apps/cli/tests/test_startup_perf.py`) is unaffected. The art lives in Python
source, not a data file, so the PyInstaller-frozen binary needs no extra
bundling.

**README hero.** A centred `<img>` pointing at `brand/assets/odi-mascot-256.png`
inside the existing centred title block. The line starts with `<`, so
`website/tools/sync-readme.py` skips it when deriving the site's meta
description — the site's description is unchanged and `website/index.html`
stays untouched.

## Originality and provenance

The point of a mascot is that it is *ours*. The design doc and the generator
are the evidence:

- Odi is an original character built from geometric primitives by a committed
  script. No traced, generated-from-prompt, or third-party art.
- The species (otter) is not used as a developer-tool mascot by any widely
  known product, so there is no crowd to blend into.
- The construction is published in `brand/README.md`, including the φ table, so
  a reviewer can verify the character was designed rather than copied.
- The repo's MIT `LICENSE` covers the artwork. The brand guide states the
  artwork is original work by the project maintainers.

**Honest limitation.** A mascot is a weak trademark and no part of this design
should be read as a legal opinion. What it does provide is *provenance*: a
fork that ships Odi is visibly a fork of Agentic ODI, which is the practical
protection the maintainer asked for.

## Accessibility

- The mascot is decorative everywhere it appears: `aria-hidden="true"` in the
  studio, `alt=""` in the README, and never the only label of a control.
- The CLI banner is decorative text; it carries no information that is not
  also in the lines beside it.
- Measured contrast ratios for every meaningful pairing (ink on fur, fur on
  the bar, accent on the bar) are published in `brand/README.md` and asserted
  by the brand tests, so the claim is a measured fact rather than a slogan.
- Nothing about the mascot's meaning is conveyed by color alone; the spark is
  a shape, not just a hue.

## What's left for the builder

1. Build the generator, get the raster looking cute, iterate.
2. Emit the SVG, ICO, PNGs, the studio component, the CLI module, and the
   ASCII banner.
3. Regenerate the Tauri icon set.
4. Wire the studio, the CLI, and the README.
5. Write `brand/README.md` and the brand tests.
6. Keep CI green: root `ruff check .` / `ruff format --check .` must pass for
   the new Python, `mypy brand` must pass, and the new `brand/tests` must run
   under the root `uv run pytest` run.
