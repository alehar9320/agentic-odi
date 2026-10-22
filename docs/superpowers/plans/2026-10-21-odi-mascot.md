# Odi the Otter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship Odi the Otter — a golden-ratio-derived pixel otter mascot — as a reproducible brand system across the CLI, the Studio SPA, the desktop app icon, the favicon, and the README.

**Architecture:** A single committed Python generator (`brand/src/odi_mascot.py`) owns the palette, the φ-derived geometry, and a tiny shape-and-outline rasterizer. Everything else is derived from it: the PNGs, the SVGs, the ICO, the inline studio React component, and the CLI's ASCII banner. `brand/tools/render.py` regenerates every artifact, and the brand tests assert that each committed artifact matches a fresh render, so the art can never drift from its source.

**Tech Stack:** Python 3.10+, Pillow 12.3.0 (already a root dev dependency), React 19 + TypeScript + Vite, Typer, Tauri 2, `@tauri-apps/cli` (already a studio dev dependency).

**Spec:** `docs/superpowers/specs/2026-10-21-odi-mascot-design.md`

## Global Constraints

- The mascot is **Odi the otter**. Species is fixed: otter, not cat, dog, bird, or robot.
- Master pixel grid is **32 × 32**. Head width `W` = 20 (bust) / 22 (icon). φ = 1.6180339887.
- Palette is fixed: `odi-ink #1B1410`, `odi-fur #B4794C`, `odi-fur-light #DCA871`, `odi-cream #F6EAD8`, `odi-accent #8B8CF8`, `odi-tile #131722`.
- **No new runtime dependencies.** No new entries in any `pyproject.toml`; no `npm install`.
- **No new CI job.** Brand tests run under the existing root `uv run pytest` by adding `"brand"` to `testpaths` in the root `pyproject.toml`.
- `website/` is **not touched** by this plan.
- Every generated file carries a `GENERATED — do not edit` header, and CI re-runs the generator and diffs the tree.
- Art comparison is **pixel parity**, not byte parity (encoder versions must not break CI).
- Python floor is `>=3.10`. Root ruff config: `line-length = 100`, `select = ["E4","E7","E9","F","I","UP","B","BLE"]`.
- Do not commit changes unless explicitly asked. Conventional commit messages.

## Review Focus

- **A fork re-running `render.py` must get byte-identical art** — no timestamps, no RNG, no dict-ordering dependence, no Pillow-version-sensitive output. A contributor on a different Pillow must not see a diff.
- **A 16-pixel favicon must still read as an animal** — if the head collapses into a brown blob with no eyes, the mascot has failed its smallest surface.
- **The CLI banner must never appear in a pipe or a CI log** — 16 lines of block-glyph art in a build log is a defect, not a feature.
- **The mascot must never be the only label of a control** — it is decorative; removing it must not remove meaning.
- **The mascot must not blur** — any non-integer scale of the 32-pixel grid (28 px, 24 px, 18 px) breaks pixel art. Every surface renders at an integer multiple or 1:1.

---

### Task 1: The generator core

**Files:**
- Create: `brand/src/odi_mascot.py`
- Create: `brand/tests/test_brand_assets.py`
- Modify: `pyproject.toml` (root — add `"brand"` to `testpaths`)

**Interfaces:**
- Consumes: nothing.
- Produces (the entire public API of `brand/src/odi_mascot.py`):
  - `PHI: float` — 1.6180339887
  - `GRID: int` — 32
  - `PALETTE: dict[str, str]` — the six hex tokens above, keyed `ink`, `fur`, `fur_light`, `cream`, `accent`, `tile`
  - `HEAD_W_BUST: int` — 20; `HEAD_W_ICON: int` — 22
  - `class Raster` — 2-D palette-index buffer. `Raster(grid: int)`, `.set(x: int, y: int, color: str)`, `.get(x: int, y: int) -> str | None`, `.fill_ellipse(cx: float, cy: float, rx: float, ry: float, color: str)`, `.fill_rect(x: int, y: int, w: int, h: int, color: str)`, `.fill_round_rect(x: int, y: int, w: int, h: int, r: int, color: str)`, `.outline(color: str) -> None` (adds a 1 px outline around the silhouette), `.to_rgba() -> list[list[tuple[int, int, int, int]]]`
  - `head_raster(head_w: int) -> Raster` — the head + ears, centered
  - `mark_raster() -> Raster` — the `odi-tile` rounded square with `head_raster(22)` composited on it
  - `bust_raster() -> Raster` — head + shoulders + chest + spark
  - `render_png(raster: Raster, size: int) -> bytes` — nearest-neighbour upscale to `size` × `size`, PNG bytes
  - `render_svg(raster: Raster, guides: bool = False) -> str` — one `<rect>` per pixel, `shape-rendering="crispEdges"`, optional golden guide layer
  - `render_svg_rle(raster: Raster) -> str` — the same art with horizontal runs merged into single `<rect>` elements
  - `render_ico(sizes: tuple[int, ...] = (16, 32, 48, 64)) -> bytes` — ICO with embedded PNG frames
  - `ascii_banner() -> str` — the plain (uncoloured) half-block banner
  - `ascii_banner_ansi() -> str` — the 24-bit ANSI-coloured banner
  - `contrast_ratio(hex_a: str, hex_b: str) -> float` — WCAG 2.1 relative-luminance ratio

- [ ] **Step 1: Write the failing tests**

Create `brand/tests/test_brand_assets.py`. It must add `brand/src` to `sys.path` via a `conftest.py` at `brand/tests/conftest.py` containing:

```python
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
```

The test file must assert:

```python
def test_phi_constants_match_the_spec():
    assert odi_mascot.PHI == 1.6180339887
    assert odi_mascot.GRID == 32
    assert odi_mascot.HEAD_W_BUST == 20
    assert odi_mascot.HEAD_W_ICON == 22

def test_palette_matches_the_spec():
    assert odi_mascot.PALETTE == {
        "ink": "#1B1410", "fur": "#B4794C", "fur_light": "#DCA871",
        "cream": "#F6EAD8", "accent": "#8B8CF8", "tile": "#131722",
    }

def test_head_width_is_a_golden_ratio_of_its_own_height():
    # 20 / 12 = 1.667, within 2% of phi
    assert abs((odi_mascot.HEAD_W_BUST / round(odi_mascot.HEAD_W_BUST / odi_mascot.PHI)) - odi_mascot.PHI) < 0.02

def test_eye_separation_is_the_golden_section_of_the_head():
    head = odi_mascot.head_raster(odi_mascot.HEAD_W_BUST)
    xs = sorted({x for y in range(odi_mascot.GRID) for x in range(odi_mascot.GRID) if head.get(x, y) == "ink"})
    # the pupils' centres are 12 apart -> 12/20 = 0.618
    assert 12 in {b - a for a in xs for b in xs}

def test_raster_helpers_draw_within_bounds():
    r = odi_mascot.Raster(8)
    r.fill_ellipse(4, 4, 3, 3, "fur")
    r.fill_rect(0, 0, 2, 2, "ink")
    assert r.get(0, 0) == "ink"
    assert r.get(4, 4) == "fur"
    assert r.get(7, 7) is None

def test_outline_wraps_the_silhouette():
    r = odi_mascot.Raster(8)
    r.fill_ellipse(4, 4, 2, 2, "fur")
    r.outline("ink")
    assert r.get(0, 0) is None
    assert r.get(4, 2) == "ink"   # top edge of the blob
    assert r.get(4, 4) == "fur"   # interior untouched

def test_contrast_ratio_matches_wcag_reference_values():
    assert abs(odi_mascot.contrast_ratio("#000000", "#FFFFFF") - 21.0) < 0.01
    assert abs(odi_mascot.contrast_ratio("#FFFFFF", "#FFFFFF") - 1.0) < 0.01
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest brand/tests/test_brand_assets.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'odi_mascot'`.

- [ ] **Step 3: Implement `brand/src/odi_mascot.py`**

Module docstring: `"""Odi the Otter — the Agentic ODI mascot. Single source of truth for every Odi asset."""`

Implement in this order:

1. Constants: `PHI`, `GRID`, `PALETTE`, `HEAD_W_BUST`, `HEAD_W_ICON`.
2. `contrast_ratio(hex_a, hex_b) -> float` — sRGB relative luminance per WCAG 2.1, `(L1 + 0.05) / (L2 + 0.05)`.
3. `class Raster` — a `list[list[str | None]]` of size `grid × grid`. `set` ignores out-of-range coordinates. `fill_ellipse` fills pixels whose centre lies within `((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2 <= 1.0`. `fill_round_rect` fills the rect minus the four corner squares of radius `r`. `outline(color)` sets every transparent pixel that is 4-neighbour-adjacent to a non-transparent pixel to `color` (one pass, so the outline never doubles). `to_rgba()` maps palette names to `(r, g, b, 255)` and `None` to `(0, 0, 0, 0)`.
4. `head_raster(head_w)` — the head, ears, eyes, muzzle, nose, mouth, cheeks:
   - `rx = head_w / 2`, `ry = rx / PHI`
   - head ellipse centred at `(GRID / 2, head_centre_y)` where `head_centre_y = 15` for the bust and `16` for the icon
   - ears: radius `round(rx / PHI / 2)` at `cx = GRID / 2 ± (rx - ear_r)`, `cy = head_centre_y - ry + ear_r / 2`
   - eyes: 4 × 4 blocks of `ink` centred at `GRID / 2 ± round(head_w / PHI) / 2` and `head_centre_y - 1`, each with a 1 px `cream` highlight at its top-left
   - muzzle: cream ellipse of `rx = round(head_w / PHI ** 2) / 2` centred at `(GRID / 2, head_centre_y + round(head_w / PHI ** 2) / 2)`
   - nose: `ink` rect `round(head_w / PHI ** 3)` wide, 2 tall, sitting on the top of the muzzle
   - mouth: a 1 px `ink` smile under the nose
   - cheeks: 2 × 2 `fur_light` blocks either side of the muzzle
   - `outline("ink")` last
5. `mark_raster()` — `Raster(GRID)`, `fill_round_rect(0, 0, GRID, GRID, 7, "tile")`, then `head_raster(22)` composited on top (only where the head is not transparent).
6. `bust_raster()` — `head_raster(20)` at `head_centre_y = 10`, plus shoulders: a `fur` shape from `y = 15` to `y = 30`, widest (20) at `y = 21`, tapering to 12 at the bottom; a `cream` chest patch; the `accent` spark: a 3 × 3 diamond at `(GRID / 2, 1)`; `outline("ink")` last.
7. `render_png(raster, size)` — nearest-neighbour upscale of the RGBA buffer to `size × size`, encoded with Pillow: `Image.new("RGBA", (size, size))`, `putdata`, `save(buf, "PNG", optimize=True)`. Deterministic for a given Pillow version.
8. `render_svg(raster, guides=False)` — `<svg xmlns=... viewBox="0 0 32 32" shape-rendering="crispEdges">` with one `<rect x= y= width="1" height="1" fill=.../>` per non-transparent pixel. When `guides=True`, append a `<g data-guides="true">` containing the golden rectangles (head box, eye-separation line, muzzle box) drawn as `fill="none" stroke="#8B8CF8" stroke-width="0.25"`.
9. `render_svg_rle(raster)` — same, but merge horizontal runs of the same colour into one `<rect>`.
10. `render_ico(sizes)` — build each size with `render_png`, then assemble an ICO: `ICONDIR` (6 bytes: reserved 0, type 1, count) + one 16-byte `ICONDIRENTRY` per size (width, height, colour count 0, reserved 0, planes 1, bit count 32, bytes-in-resource, image offset) + the PNG payloads.
11. `ascii_banner()` — the bust raster converted to half blocks: 32 columns of text = 64 px wide, 16 rows of text = 32 px tall. Each text cell uses `▀` (upper half block) with the top pixel in the foreground and the bottom pixel in the background, or a space when both are transparent. The plain variant uses only `▀`, `█`, and ` `.
12. `ascii_banner_ansi()` — the same cells with 24-bit ANSI: `\x1b[38;2;R;G;Bm` for the foreground and `\x1b[48;2;R;G;Bm` for the background, `\x1b[39m` / `\x1b[49m` to reset to the terminal default for a transparent half.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest brand/tests/test_brand_assets.py -v`
Expected: PASS.

- [ ] **Step 5: Add `brand` to the root testpaths and re-run**

In the root `pyproject.toml`, change `testpaths = ["apps", "packages", "tests", "website"]` to `testpaths = ["apps", "brand", "packages", "tests", "website"]`.

Run: `uv run pytest brand -v` and `uv run ruff check brand && uv run ruff format --check brand`
Expected: PASS and clean.

- [ ] **Step 6: Commit**

```bash
git add brand pyproject.toml
git commit -m "feat(brand): add the Odi mascot generator with golden-ratio geometry"
```

---

### Task 2: Commit the rendered assets and the brand guide

**Files:**
- Create: `brand/tools/render.py`
- Create: `brand/assets/*` (generated)
- Create: `brand/README.md`

**Interfaces:**
- Consumes: everything from Task 1.
- Produces:
  - `brand/tools/render.py` — runnable as `uv run python brand/tools/render.py`; it adds `brand/src` to `sys.path`, renders every artifact, writes them to `brand/assets/`, and prints the list of files it wrote. It takes an optional `--check` flag: render into memory, compare with the committed bytes, and exit non-zero listing any file that differs (this is what CI runs).
  - `brand/assets/odi-mascot.svg` — the bust, vector, with the guide layer
  - `brand/assets/odi-mark.svg` — the mark, vector
  - `brand/assets/odi-mascot-256.png`, `odi-mascot-512.png`, `odi-mascot-1024.png` — the bust rasters
  - `brand/assets/odi-icon-1024.png` — the mark raster, the Tauri icon source
  - `brand/assets/favicon.svg` — the mark, vector
  - `brand/assets/favicon.ico` — 16/32/48/64
  - `brand/assets/apple-touch-icon.png` — 180 × 180
  - `brand/assets/odi-ascii.txt` — the plain banner

- [ ] **Step 1: Write the failing test**

Append to `brand/tests/test_brand_assets.py`:

```python
def test_every_committed_asset_matches_a_fresh_render():
    # render into a tmp dir and compare bytes with brand/assets
    ...

def test_brand_assets_exist():
    for name in ("odi-mascot.svg", "odi-mark.svg", "odi-mascot-256.png",
                 "odi-mascot-512.png", "odi-mascot-1024.png",
                 "odi-icon-1024.png", "favicon.svg", "favicon.ico",
                 "apple-touch-icon.png", "odi-ascii.txt"):
        assert (ASSETS / name).is_file(), name

def test_svg_assets_are_well_formed_and_script_free():
    # parse with xml.etree; assert root is svg, no <script>, viewBox is "0 0 32 32"

def test_png_assets_have_the_expected_dimensions():
    # PIL: odi-mascot-256.png is 256x256, odi-icon-1024.png is 1024x1024,
    # apple-touch-icon.png is 180x180

def test_ico_contains_the_expected_sizes():
    # parse the ICONDIR: count == 4, widths are 16/32/48/64

def test_ascii_banner_is_wide_enough_to_read_as_a_character():
    lines = (ASSETS / "odi-ascii.txt").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 16
    assert all(len(line) == 32 for line in lines)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest brand/tests/test_brand_assets.py -v`
Expected: FAIL — the asset files do not exist.

- [ ] **Step 3: Implement `brand/tools/render.py`**

```python
"""Regenerate every Odi mascot artifact. `uv run python brand/tools/render.py`."""
```

It must:
- insert `brand/src` at the front of `sys.path`
- import `odi_mascot`
- write each artifact to `brand/assets/` with `write_bytes`
- write `odi-ascii.txt` as UTF-8 with a trailing newline
- print `wrote <path>` per file
- support `--check`: compare rendered bytes against the committed files and `sys.exit(1)` with the list of differing paths if any

- [ ] **Step 4: Run the generator**

Run: `uv run python brand/tools/render.py`
Expected: prints one `wrote …` line per artifact.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest brand/tests/test_brand_assets.py -v`
Expected: PASS.

- [ ] **Step 6: Look at the art and iterate until it is cute**

Run: `uv run python brand/tools/render.py`, then open `brand/assets/odi-mascot-512.png` and `brand/assets/odi-icon-1024.png` and *look at them*. Iterate on the geometry in `brand/src/odi_mascot.py` until the otter reads as a friendly animal at 32 px, at 16 px, and at 512 px. Re-run the generator and the tests after every change. Do not proceed until the art is right — everything downstream inherits it.

**The 16-pixel check is a gate, not a formality.** Render the mark at 16 px and look at it: the eyes must still be visible as two dark pixels and the silhouette must still read as a head, not a brown blob. If the art fails at 16 px, fix it by simplifying the *head* geometry (fewer, larger features) — never by adding detail.

- [ ] **Step 7: Write `brand/README.md`**

The brand guide. It must contain:
- what Odi is (otter, "odee"), and the one-line rationale
- the palette table with the six hex values **and the measured contrast ratios**, produced by `odi_mascot.contrast_ratio` — ink on fur, fur on `--bg #0a0b0e`, accent on `--bg`, cream on fur. State them per pairing, with no blanket claim.
- the φ construction table (the same rows as the spec) and the statement that the head is a golden rectangle
- the three variants (head / mark / bust) and which surface uses which
- the file inventory and the one-line regeneration command
- usage rules: clear space of one head width, never recolour the ink, never add a background other than `odi-tile`, never place the head at a non-integer scale
- provenance: the artwork is original work by the project maintainers, built by the committed generator, covered by the repo's MIT `LICENSE`; and the honest note that a mascot is a weak trademark, offering provenance rather than legal protection

- [ ] **Step 8: Commit**

```bash
git add brand
git commit -m "feat(brand): add the rendered Odi assets and the brand guide"
```

---

### Task 3: Desktop app icon

**Files:**
- Modify: `apps/studio/src-tauri/icons/*` (all 18 files, regenerated)

**Interfaces:**
- Consumes: `brand/assets/odi-icon-1024.png` from Task 2.
- Produces: the canonical Tauri icon set.

- [ ] **Step 1: Regenerate the icon set**

Run: `cd apps/studio && npm ci && npm run tauri icon ../../brand/assets/odi-icon-1024.png`
Expected: the CLI writes `apps/studio/src-tauri/icons/` — `32x32.png`, `128x128.png`, `128x128@2x.png`, `icon.png`, `icon.icns`, `icon.ico`, `StoreLogo.png`, and every `Square*Logo.png`.

- [ ] **Step 2: Verify the set**

Run: `ls -la apps/studio/src-tauri/icons/` and confirm all 18 expected files are present and none is zero-length. Confirm `icon.png` is 1024 × 1024 and `icon.ico` contains 16/32/48/64/128/256 frames.

- [ ] **Step 3: Commit**

```bash
git add apps/studio/src-tauri/icons
git commit -m "feat(studio): replace the app icon with the Odi mascot"
```

---

### Task 4: Studio SPA — favicon, head, and brand mark

**Files:**
- Create: `apps/studio/public/favicon.svg` (generated)
- Create: `apps/studio/public/favicon.ico` (generated)
- Create: `apps/studio/public/apple-touch-icon.png` (generated)
- Create: `apps/studio/src/components/OdiMascot.tsx` (generated)
- Modify: `apps/studio/index.html`
- Modify: `apps/studio/src/components/layout/StudioBar.tsx`
- Modify: `apps/studio/src/styles/theme.css`
- Test: `apps/studio/src/components/OdiMascot.test.tsx`

**Interfaces:**
- Consumes: `odi_mascot.render_svg_rle`, `odi_mascot.render_ico`, `odi_mascot.render_png` (Task 1).
- Produces:
  - `OdiMascot` — a React component in `apps/studio/src/components/OdiMascot.tsx`:
    ```ts
    export function OdiMascot({ size = 32, className }: { size?: number; className?: string }): JSX.Element
    ```
    It renders the mark's inline SVG (run-length encoded), `width`/`height` = `size`, `role="presentation"`, `aria-hidden="true"`, `focusable="false"`, and `className` passed through.
  - `apps/studio/public/favicon.svg` — a copy of `brand/assets/favicon.svg`
  - `apps/studio/public/favicon.ico` — a copy of `brand/assets/favicon.ico`
  - `apps/studio/public/apple-touch-icon.png` — a copy of `brand/assets/apple-touch-icon.png`

- [ ] **Step 1: Extend the generator to emit the studio artifacts**

In `brand/tools/render.py`, additionally write:
- `apps/studio/public/favicon.svg` (the mark SVG)
- `apps/studio/public/favicon.ico`
- `apps/studio/public/apple-touch-icon.png` (180 × 180)
- `apps/studio/src/components/OdiMascot.tsx` — a generated file whose content is:

```tsx
// GENERATED by brand/tools/render.py — do not edit by hand.
// Run `uv run python brand/tools/render.py` to regenerate.
export function OdiMascot({ size = 32, className }: { size?: number; className?: string }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 32 32"
      shapeRendering="crispEdges"
      role="presentation"
      aria-hidden="true"
      focusable="false"
      className={className}
    >
      <rect ... />
      ...
    </svg>
  );
}
```

The `<rect>` elements come from `odi_mascot.render_svg_rle(mark_raster())`, with the inner SVG markup spliced in. The file must be valid TSX and pass `tsc --noEmit`.

- [ ] **Step 2: Write the failing test**

Create `apps/studio/src/components/OdiMascot.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { OdiMascot } from "./OdiMascot";

describe("OdiMascot", () => {
  it("renders a decorative pixel-art mark", () => {
    const { container } = render(<OdiMascot size={32} />);
    const svg = container.querySelector("svg");
    expect(svg).not.toBeNull();
    expect(svg?.getAttribute("viewBox")).toBe("0 0 32 32");
    expect(svg?.getAttribute("aria-hidden")).toBe("true");
    expect(svg?.getAttribute("width")).toBe("32");
    expect(svg?.querySelectorAll("rect").length).toBeGreaterThan(10);
  });

  it("is hidden from assistive technology", () => {
    render(<OdiMascot />);
    expect(screen.queryByRole("img")).toBeNull();
  });
});
```

Also add to `apps/studio/src/components/layout/StudioBar.test.tsx` (create it if it does not exist):

```tsx
it("shows the Odi mark at 32 pixels so the pixel art stays crisp", () => {
  const { container } = render(<StudioBar onHome={() => {}} onNew={() => {}} onChangelog={() => {}} />);
  const svg = container.querySelector(".brand__mark svg");
  expect(svg?.getAttribute("width")).toBe("32");
  expect(svg?.getAttribute("height")).toBe("32");
});
```

The `32` is load-bearing: a 28-pixel slot would scale the 32-pixel grid by 0.875 and blur it.

- [ ] **Step 3: Run the test to verify it fails**

Run: `npm --prefix apps/studio test -- --run src/components/OdiMascot.test.tsx`
Expected: FAIL — `OdiMascot` does not exist.

- [ ] **Step 4: Generate the component and the public assets**

Run: `uv run python brand/tools/render.py`
Expected: it writes the three files under `apps/studio/public/` and the component.

- [ ] **Step 5: Wire the SPA head**

In `apps/studio/index.html`, replace the dead favicon link with:

```html
<link rel="icon" type="image/svg+xml" href="/favicon.svg" />
<link rel="alternate icon" type="image/x-icon" href="/favicon.ico" />
<link rel="apple-touch-icon" href="/apple-touch-icon.png" />
```

Keep the existing `<title>`, viewport, and colour-scheme tags.

- [ ] **Step 6: Wire the studio brand mark**

In `apps/studio/src/components/layout/StudioBar.tsx`:
- import `OdiMascot` from `../OdiMascot`
- replace `<SparkIcon size={15} />` inside `brand__mark` with `<OdiMascot size={32} />`
- remove the now-unused `SparkIcon` import if nothing else uses it (check first — `grep -rn "SparkIcon" apps/studio/src`)

In `apps/studio/src/styles/theme.css`, change `.brand__mark` to:

```css
.brand__mark {
  display: grid;
  place-items: center;
  width: 32px;
  height: 32px;
  flex: none;
  border-radius: 9px;
  overflow: hidden;
  background: var(--odi-tile, #131722);
  border: 1px solid rgba(139, 140, 248, 0.35);
}
```

- [ ] **Step 7: Run the studio checks**

Run: `npm --prefix apps/studio run lint && npm --prefix apps/studio run typecheck && npm --prefix apps/studio test -- --run && npm --prefix apps/studio run build`
Expected: all four pass.

- [ ] **Step 8: Commit**

```bash
git add brand apps/studio
git commit -m "feat(studio): show the Odi mascot in the bar, favicon, and head"
```

---

### Task 5: CLI banner

**Files:**
- Create: `apps/cli/src/agentic_odi_cli/mascot.py` (generated)
- Modify: `apps/cli/src/agentic_odi_cli/chat.py`
- Test: `apps/cli/tests/test_mascot.py`

**Interfaces:**
- Consumes: `odi_mascot.ascii_banner`, `odi_mascot.ascii_banner_ansi` (Task 1).
- Produces, in `apps/cli/src/agentic_odi_cli/mascot.py`:
  - `MASCOT_ASCII: str` — the plain half-block banner
  - `MASCOT_ANSI: str` — the 24-bit ANSI banner
  - `def render_banner(color: bool = True) -> str` — returns `MASCOT_ANSI` when `color` else `MASCOT_ASCII`
  - `def should_show_banner(stream: TextIO) -> bool` — `True` only when `stream.isatty()` is true, the stream's encoding can represent `▀`, and `NO_COLOR` is unset in the environment

- [ ] **Step 1: Extend the generator to emit the CLI module**

In `brand/tools/render.py`, write `apps/cli/src/agentic_odi_cli/mascot.py`:

```python
"""Odi the Otter — the Agentic ODI CLI banner.

GENERATED by brand/tools/render.py — do not edit by hand.
Run `uv run python brand/tools/render.py` to regenerate.
"""

from __future__ import annotations

import os
import sys
from typing import TextIO

MASCOT_ASCII = """<the plain banner>"""

MASCOT_ANSI = """<the ansi banner>"""


def render_banner(color: bool = True) -> str:
    """Return the Odi banner, coloured when requested."""
    return MASCOT_ANSI if color else MASCOT_ASCII


def should_show_banner(stream: TextIO) -> bool:
    """Return True when the banner belongs on this stream."""
    if os.environ.get("NO_COLOR"):
        return True
    encoding = (getattr(stream, "encoding", "") or "").lower()
    return bool(stream.isatty()) and "utf" in encoding
```

The `NO_COLOR` branch returns `True` (show it, but without colour) — the caller picks the uncoloured variant.

- [ ] **Step 2: Write the failing test**

Create `apps/cli/tests/test_mascot.py`:

```python
from __future__ import annotations

import io

from agentic_odi_cli import mascot


class _NotATty(io.StringIO):
    def isatty(self) -> bool:
        return False


class _Tty(io.StringIO):
    def isatty(self) -> bool:
        return True

    @property
    def encoding(self) -> str:
        return "utf-8"


def test_banner_has_sixteen_rows_of_thirty_two_columns():
    lines = mascot.MASCOT_ASCII.splitlines()
    assert len(lines) == 16
    assert all(len(line) == 32 for line in lines)


def test_banner_is_not_empty_and_contains_the_otter():
    assert "█" in mascot.MASCOT_ASCII
    assert "▀" in mascot.MASCOT_ASCII


def test_ansi_banner_uses_24_bit_colour():
    assert "\x1b[38;2;" in mascot.MASCOT_ANSI
    assert "\x1b[48;2;" in mascot.MASCOT_ANSI


def test_banner_is_hidden_from_a_pipe():
    assert mascot.should_show_banner(_NotATty()) is False


def test_banner_is_shown_on_a_tty(monkeypatch):
    monkeypatch.delenv("NO_COLOR", raising=False)
    assert mascot.should_show_banner(_Tty()) is True


def test_banner_is_hidden_when_the_terminal_cannot_encode_it(monkeypatch):
    class _Latin1(_Tty):
        @property
        def encoding(self) -> str:
            return "latin-1"

    monkeypatch.delenv("NO_COLOR", raising=False)
    assert mascot.should_show_banner(_Latin1()) is False


def test_no_color_environment_keeps_the_banner_but_drops_the_colour(monkeypatch):
    monkeypatch.setenv("NO_COLOR", "1")
    assert mascot.should_show_banner(_Tty()) is True
    assert "\x1b[38;2;" not in mascot.render_banner(color=False)
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `uv run --directory apps/cli pytest tests/test_mascot.py -v`
Expected: FAIL — `agentic_odi_cli.mascot` does not exist.

- [ ] **Step 4: Generate the module**

Run: `uv run python brand/tools/render.py`
Expected: it writes `apps/cli/src/agentic_odi_cli/mascot.py`.

- [ ] **Step 5: Print the banner in chat**

In `apps/cli/src/agentic_odi_cli/chat.py`, inside `_run_chat`, replace:

```python
typer.echo("Agentic ODI · interactive")
```

with:

```python
if should_show_banner(sys.stdout):
    typer.echo(render_banner(color="NO_COLOR" not in os.environ))
typer.echo("Agentic ODI · interactive")
```

and add the imports `import os`, `import sys`, and
`from agentic_odi_cli.mascot import render_banner, should_show_banner`.

- [ ] **Step 6: Run the CLI checks**

Run: `uv run --directory apps/cli pytest -v` and `uv run mypy apps/cli` and `uv run ruff check apps/cli && uv run ruff format --check apps/cli`
Expected: all pass, including `test_startup_perf.py` (the banner module imports nothing heavy).

- [ ] **Step 7: Commit**

```bash
git add brand apps/cli
git commit -m "feat(cli): greet the ODI assistant with the Odi banner"
```

---

### Task 6: README hero and brand pointer

**Files:**
- Modify: `README.md`

**Interfaces:**
- Consumes: `brand/assets/odi-mascot-256.png` (Task 2).
- Produces: nothing new; the README is the entry point for the brand.

- [ ] **Step 1: Add the hero**

Inside the existing centred `<div align="center">` block, directly under the `# Agentic ODI` heading, add:

```html
<img src="brand/assets/odi-mascot-256.png" alt="" width="200" />
```

The line must start with `<` so `website/tools/sync-readme.py` skips it when deriving the site's meta description.

- [ ] **Step 2: Add a brand pointer**

Add a short section near the end of the README, before `## 📄 License`:

```markdown
## 🦦 Brand

Odi the Otter is the mascot of Agentic ODI — a golden-ratio-derived pixel otter
that appears in the CLI, the Living Studio, the desktop icon, and the favicon.
The artwork is original, generated by a committed script, and documented in
[brand/README.md](brand/README.md).

```bash
uv run python brand/tools/render.py   # regenerate every Odi asset
```
```

- [ ] **Step 3: Verify the website sync is unaffected**

Run: `uv run pytest website/tests -v` and `git status --porcelain website/`
Expected: the website tests pass and `website/` shows **no** changes — the hero line starts with `<`, so the derived description is unchanged.

- [ ] **Step 4: Commit**

```bash
git add README.md
git commit -m "docs: introduce Odi the Otter in the README"
```

---

### Task 7: CI parity, brand checks, and the pull request

**Files:**
- Modify: `.github/workflows/ci.yml`
- Modify: `pyproject.toml` (root — mypy scope)
- Create: `brand/tests/test_generated_sources.py`

**Interfaces:**
- Consumes: everything from Tasks 1–6.
- Produces: the CI wiring that keeps the art honest.

- [ ] **Step 1: Write the failing test**

Create `brand/tests/test_generated_sources.py`:

```python
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_generated_sources_match_a_fresh_render():
    """`render.py --check` must report no drift."""
    result = subprocess.run(
        [sys.executable, str(ROOT / "brand" / "tools" / "render.py"), "--check"],
        capture_output=True,
        text=True,
        cwd=ROOT,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_generated_files_carry_a_do_not_edit_header():
    for rel in (
        "apps/studio/src/components/OdiMascot.tsx",
        "apps/cli/src/agentic_odi_cli/mascot.py",
    ):
        head = (ROOT / rel).read_text(encoding="utf-8")[:400]
        assert "GENERATED" in head and "do not edit" in head.lower(), rel


def test_studio_component_and_cli_module_are_tracked():
    assert (ROOT / "apps/studio/src/components/OdiMascot.tsx").is_file()
    assert (ROOT / "apps/cli/src/agentic_odi_cli/mascot.py").is_file()
```

- [ ] **Step 2: Run the test to verify it passes (it should — the files exist)**

Run: `uv run pytest brand/tests/test_generated_sources.py -v`
Expected: PASS. If `--check` fails, re-run `uv run python brand/tools/render.py` and commit the result.

- [ ] **Step 3: Add `brand` to the mypy scope**

In `.github/workflows/ci.yml`, change the mypy step from:

```yaml
      - name: Run Mypy
        run: uv run mypy apps packages
```

to:

```yaml
      - name: Run Mypy
        run: uv run mypy apps brand packages
```

`brand/src/odi_mascot.py` must be fully annotated so this passes.

- [ ] **Step 4: Add the generator drift check to CI**

Add a step to the `lint` job, after the Ruff steps:

```yaml
      - name: Verify the mascot assets match the generator
        run: uv run python brand/tools/render.py --check
```

- [ ] **Step 5: Run the whole local CI parity suite**

Run, from the repo root:

```bash
uv run ruff check . && uv run ruff format --check .
uv run mypy apps brand packages
uv run bandit -c pyproject.toml -r apps packages
uv run pytest
uv run --directory website pytest tests/
npm --prefix apps/studio run lint
npm --prefix apps/studio run typecheck
npm --prefix apps/studio test -- --run
npm --prefix apps/studio run build
```

Expected: every command exits zero.

- [ ] **Step 6: Commit**

```bash
git add .github/workflows/ci.yml brand pyproject.toml
git commit -m "ci: verify the mascot assets match the generator"
```

- [ ] **Step 7: Push and open the pull request**

```bash
git push -u origin feat/odi-mascot
gh pr create --base main --head feat/odi-mascot --title "feat(brand): Odi the Otter — mascot, icon, favicon, and CLI banner" --body "$(cat <<'EOF'
## What

Odi the Otter — a golden-ratio-derived pixel otter — is the new mascot of
Agentic ODI. He appears in the CLI banner, the Living Studio brand mark, the
desktop app icon, the favicon, and the README.

## Why

A distinctive mascot is a weak trademark, but it is real provenance: a fork
can copy the README, but a fork that ships Odi has visibly copied Agentic ODI.
Odi is also an otter — tool-using, problem-solving, wide-headed, and not
currently used as a developer-tool mascot by anyone, so the silhouette is
unclaimed.

## How

- `brand/src/odi_mascot.py` is the single source of truth: palette, φ-derived
  geometry, and a small shape-and-outline rasterizer.
- `brand/tools/render.py` regenerates every artifact; CI runs it with
  `--check` and fails on drift.
- The studio component and the CLI module are generated too, so the icon and
  the artwork can never disagree.
- Contrast ratios are measured and published in `brand/README.md`.

## Not in this PR

`website/` is untouched: the marketing site is mid-redesign on
`feature/gh-pages-redesign`, which rewrites `website/` wholesale. The mascot
assets are ready in `brand/` for that branch to pick up.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

- [ ] **Step 8: Wait for CI and fix anything red**

Run: `gh pr checks --watch`
Expected: every check green — lint, typecheck, security, test, smoke, website, studio, tauri-check, tauri-build, and the `CI green` aggregate.

If the `tauri-build` job fails for an environment reason unrelated to this PR (missing WebKitGTK, no signing key), say so in the PR rather than weakening the change.
