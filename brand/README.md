# Odi the Otter — brand guide

Odi is the mascot of **Agentic ODI**: a golden-ratio-derived pixel otter who
appears in the CLI, the Living Studio, the desktop app icon, the favicon, and
the README.

He is an otter because otters are the tool-using problem solvers of the animal
world — they take an ambiguous shell, a stone, and a current and *engineer* an
outcome from it. That is the product in one animal: turn messy human context
into a measurable customer outcome. No widely known developer tool uses an
otter, so the silhouette is unclaimed, and no other mascot in the category is
a feline, a penguin, a gopher, or an octopus.

**Odi is original work**, built from geometric primitives by the committed
generator in `brand/src/odi_mascot.py`, and covered by the repository's MIT
`LICENSE`. A mascot is a weak trademark; what this buys is *provenance* — a
fork that ships Odi has visibly forked Agentic ODI.

---

## Palette

| Token | Hex | Use |
|---|---|---|
| `odi-ink` | `#1B1410` | outline, nose, pupils |
| `odi-fur` | `#B4794C` | main coat |
| `odi-fur-light` | `#DCA871` | cheeks |
| `odi-cream` | `#F6EAD8` | muzzle, chest, eye highlight |
| `odi-accent` | `#8B8CF8` | the spark — the studio's existing accent |
| `odi-tile` | `#131722` | app-icon tile — matches the site mark tile |

The only new colours in the system are the coat browns. Everything else was
already in the product: `#8B8CF8` is the studio accent and `#131722` is the
tile the site mark sits on.

### Measured contrast

Every ratio below is measured, not asserted, and is pinned by
`brand/tests/test_brand_assets.py`.

| Pairing | Ratio | Reading |
|---|---|---|
| `odi-ink` on `odi-fur` | 5.01:1 | the outline that defines the face — passes AA for text |
| `odi-ink` on `odi-cream` | 15.32:1 | the nose and mouth on the muzzle |
| `odi-fur` on `odi-cream` | 3.06:1 | the coat against the muzzle — a non-text boundary, passes 3:1 |
| `odi-fur` on studio `#0a0b0e` | 5.42:1 | Odi on the app's near-black chrome |
| `odi-fur` on `odi-tile` | 4.93:1 | Odi on the app-icon tile |
| `odi-accent` on studio `#0a0b0e` | 6.75:1 | the spark |
| `odi-accent` on `odi-tile` | 6.14:1 | the spark on the tile |
| `odi-cream` on `odi-tile` | 15.07:1 | the muzzle on the tile |

`odi-ink` on the near-black chrome is 1.08:1 by design: the outline is never
meant to be read against the background, only against the fur it encloses.

---

## The golden-ratio construction

Every proportion of Odi's head comes from one constant, φ = 1.6180339887,
applied to the head width **W** (20 px in the bust, 22 px in the icon). The
head's internal proportions are scale-invariant, so the icon renders the same
animal at a different size.

| Feature | Rule | Value (px) |
|---|---|---|
| Canvas | — | 32 × 32 |
| Head width `W` | unit | 20 (bust) / 22 (icon) |
| Head height | `W / φ` | 12 |
| Eye separation | `W / φ` | 12 |
| Eye size | `W / φ²`, capped | 4 × 4 |
| Muzzle width | `W / φ²` | 8 |
| Muzzle height | `(W / φ²) / φ` | 5 |
| Nose width | `W / φ³` | 5 |
| Ear radius | `W / 4φ` | 3 |
| Body width | `0.85 × W` | 17 |

**The head is a golden rectangle** — 20 wide by 12 tall is 1.667, within 3% of
φ once the height is rounded to a whole pixel. **The face divides at the
golden section**: the eyes sit 0.618 of the head width apart, the muzzle is
0.382 of it, and the nose is 0.236 of it. **The body is 0.85 of the head** —
the chibi proportion, which is the same golden rule applied to mass, where
the smaller partner of a golden pair reads as "just right".

`brand/assets/odi-mascot.svg` carries the construction as a visible
`data-guides="true"` layer: the head rectangle, the eye-separation line, and
the muzzle box. Open it in a browser or an editor to see the grid the art was
drawn on.

---

## The three variants

| Variant | Contents | Where it is used |
|---|---|---|
| `head` | skull, ears, eyes, muzzle, nose, mouth | the base for the other two |
| `mark` | the head on the `odi-tile` rounded square | app icon, favicon, studio brand mark |
| `bust` | head, shoulders, chest, and the spark | README hero, brand guide |

The `mark` exists because operating-system icons want a filled shape (Windows
`StoreLogo`, macOS `.icns`) while a browser tab and a toolbar want the
character standing on its own. Both share the identical head.

---

## Files

```text
brand/
  assets/        the committed artwork (generated)
  src/           the generator — the single source of truth
  tests/         the asset contract and the drift check
  tools/render.py  regenerates everything
```

Regenerate every Odi artifact — the PNGs, the SVGs, the ICO, the studio
component, and the CLI banner — with one command:

```bash
uv run python brand/tools/render.py
```

Check that nothing has drifted:

```bash
uv run python brand/tools/render.py --check
```

CI runs that check, so the committed artwork can never silently disagree with
the code that made it.

---

## Usage rules

- **Never scale the art to a non-integer size.** The master grid is 32 × 32.
  Render it at 16, 32, 64, 128, 256, 512, or 1024 — a 28-pixel slot would
  scale the grid by 0.875 and blur it.
- **Never recolour `odi-ink`.** The outline is the character's structure.
- **Never place the head on a background other than `odi-tile`** in the `mark`
  variant. The bust is transparent and may sit on any dark surface.
- **Keep clear space of one head width** around the mark.
- **The mascot is decoration.** It is never the only label of a control, and
  it is always `aria-hidden` where it appears in the UI.
- **The spark is the signal.** It is the one element that carries the product's
  rising-outcome idea; do not remove it from the bust.
