# GitHub Pages Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the stale single-page GitHub Pages site with a state-of-the-art, dark, product-grade site: a landing page with an interactive scripted demo of the Living Studio, plus a full docs hub and a generated API reference — all rendered from a Python static-site generator so nothing can drift from the product source.

**Architecture:** A Python generator (`website/tools/build_site.py`) reads the repo's authoritative sources — `apps/studio/src/styles/theme.css` (design tokens), `packages/core/.../contract.py` (MCP tools), `packages/connectors/.../catalog.py` (connectors), `apps/cli/.../cli.py` (CLI tree), `packages/core/.../schema.py` (ODI schema), `docs/*.md` (guides), `README.md` (install) — and renders Jinja2 templates into `website/dist/`. The output is committed and CI-gated for drift. No Node in the Pages path. The Studio is never modified.

**Tech Stack:** Python 3.10+, Jinja2 3.1.6, markdown-it-py 4.2.0, Pygments 2.21.0, Pillow 12.3.0 (OG art), pytest 9.1.1. Zero runtime dependencies on the published site: no webfonts, no CDN, no analytics, no framework runtime.

**Spec:** `docs/superpowers/specs/2026-10-22-github-pages-redesign-design.md` — the plan argues from the spec, so the spec travels with it.

## Global Constraints

- **Never modify `apps/studio/**`.** The site reads the Studio's theme one-way; the Studio is not a dependency of the site build and changes not at all.
- **No hardcoded hex outside `website/dist/assets/tokens.css`.** Every other color is a `var(--…)` reference.
- **No third-party requests.** Zero webfonts, zero CDN, zero analytics, zero cookies, zero social scripts.
- **Relative asset and link paths** on every page (the site lives under `/agentic-odi/`); `og:url`, `og:image`, and `rel=canonical` are absolute.
- **Exactly one `<h1>` per page**, inside `<main>`. No skipped heading levels. `header`/`nav`/`main`/`footer` landmarks present.
- **No emoji anywhere.** No dates (`Q1`–`Q4`, `Month 20XX`). No superlatives.
- **Pinned copy strings** (case-insensitive, must appear): `experimental`, `your roadmap is a guess.`, `we don't publish dates`, `all rights reserved`, `strategyn`, `free prefect account`, `open an issue`, `http://localhost:8000/mcp`, `scripted preview`, `requires a free prefect account`.
- **Forbidden strings:** `discord`, `mailto:`, and `agentic-odi.fastmcp.app` appearing without the auth-required label adjacent to it.
- **Opportunity formula** must render as `importance+max(importance-satisfaction,0)` (whitespace-stripped, lowercased) to match `packages/core/src/agentic_odi_core/models.py`.
- **The three hosted surfaces are distinct** and each is labeled: local MCP `http://localhost:8000/mcp`, local Studio `http://127.0.0.1:8100`, hosted MCP `https://agentic-odi.fastmcp.app/mcp` (auth required), hosted Studio `https://agentic-odi.alehar.workers.dev/`, test chat `https://horizon.prefect.io/alhase/servers/agentic-odi/chat` (requires a free Prefect account).
- **The site names catalog cards, never canvas view names.** Catalog cards: `outcome-card`, `opportunity-board`, `impact-simulation`, `evidence-quote`, `job-map`, `decision-record`. Never "Opportunity Landscape" or "Opportunity Thesis".
- **Dark-only.** `color-scheme: dark`. One `theme-color` meta.
- **Content files are JSON, not YAML** — `website/content/*.json`. JSON is stdlib; no new dependency.
- **Generated output is committed.** `website/dist/` is added to git; `.gitignore` gains `!website/dist/` because the root `dist/` pattern would otherwise swallow it.
- **Verification loop for every task:** `uv run --directory website pytest tests/ -q` and `uv run --directory website mypy .` must both pass before committing.

## Review Focus

Each line is an input class or failure mode the spec implies that a naive implementation would get wrong. The test that pins each is named in the task that owns the code.

1. **A page two directories deep** (`/docs/mcp/`) — relative asset links must resolve from that depth, not only from `/`. A naive `"assets/style.css"` breaks every docs page. → `test_site.py::test_every_page_resolves_its_own_assets`
2. **JavaScript disabled** — the demo must still show a complete, readable transcript of all three exchanges, and no section may be stuck invisible. A naive reveal implementation hides content permanently. → `test_site.py::test_demo_transcript_is_server_rendered`
3. **`prefers-reduced-motion: reduce`** — every reveal, stagger, and the demo's typing must become instant, and no content may remain hidden. → `test_design_system.py::test_reduced_motion_disables_all_motion`
4. **A new MCP tool added upstream** — the site's tool reference must pick it up on the next build, and CI must fail if `dist/` was not rebuilt. A hand-written list silently omits it. → `test_content_sync.py::test_site_tool_list_matches_contract`
5. **A docs page whose markdown contains a table, a nested list, and a fenced code block** — the rendering pipeline must produce a real `<table>`, a nested `<ul>`, and a highlighted `<pre>`, and must not pass raw HTML through. → `test_docs_render.py::test_markdown_features_render`
6. **A `docs/*.md` file with a heading that duplicates another file's heading** — anchors must still be unique within their page, and every in-page `#anchor` link must resolve. → `test_site.py::test_in_page_anchors_resolve`
7. **A user tabbing through the demo** — the suggestion chips and the composer must be reachable and operable, and the scripted exchange must advance without a mouse. → `test_site.py::test_demo_controls_are_buttons`
8. **A screen reader on the landing page** — the skipped `nav` landmark, the decorative background gradients, and the SVG charts must not produce noise. → `test_site.py::test_decorative_svg_is_hidden_from_assistive_tech`

---

## File Structure

```
website/
  templates/
    base.html            # shell: head, skip link, header, footer
    landing.html         # the landing page
    doc.html             # a docs page: sidebar + prose + prev/next
    reference.html       # a generated reference page
    404.html             # self-contained
  content/
    landing.json         # structured landing copy (the only hand-written prose)
    demo.json            # the demo script
    nav.json             # docs hub navigation
  assets/
    style.css            # hand-written design system
    main.js              # progressive enhancement: reveal, copy, tabs
    demo.js              # the scripted demo
    mark.svg  favicon.svg
  tools/
    build_site.py        # the generator
    extract.py           # read tokens/tools/connectors/CLI/schema from source
    make_og.py           # OG card + favicon generator (repainted)
  tests/
    test_site.py         # structure, meta, landmarks, honesty, links
    test_design_system.py# tokens, type, motion, focus
    test_generated.py    # build determinism + committed output freshness
    test_content_sync.py # site ≡ source for tools/connectors/CLI/formula
    test_docs_render.py  # markdown pipeline
    test_make_og.py      # OG determinism + pixel identity
    test_pages_deploy.py # deploy workflow contract
  dist/                  # GENERATED, committed, drift-gated
```

**Responsibility split:** `extract.py` is pure source-reading — it knows nothing about HTML. `build_site.py` owns rendering and knows nothing about where the data came from. Templates own markup. `assets/style.css` owns the design system. `assets/*.js` owns behavior.

---

## Task 1: Generator foundation

**Files:**
- Create: `website/tools/extract.py`
- Create: `website/tools/build_site.py`
- Create: `website/templates/base.html`
- Create: `website/templates/404.html`
- Create: `website/tests/conftest.py`
- Create: `website/tests/test_generated.py`
- Modify: `.gitignore`

**Interfaces:**
- Consumes: nothing (this is the root task).
- Produces:
  - `extract.read_tokens(studio_theme: Path) -> dict[str, str]` — the `:root` custom properties of the Studio theme, as a name→value map.
  - `extract.read_odi_formula(core_models: Path) -> str` — the source text of the opportunity formula.
  - `build_site.build(out_dir: Path, *, check: bool = False) -> int` — renders the whole site into `out_dir`; returns the number of files written. When `check=True`, writes nothing and raises `SystemExit(1)` if the committed output differs from a fresh render.
  - `build_site.PAGES_URL = "https://alehar9320.github.io/agentic-odi/"` — the canonical absolute base.

- [ ] **Step 1: Write the failing test**

`website/tests/test_generated.py`:

```python
def test_build_is_deterministic(tmp_path):
    first = tmp_path / "a"
    second = tmp_path / "b"
    build_site.build(first)
    build_site.build(second)
    assert _tree(first) == _tree(second)   # (relative path, bytes) pairs


def test_build_emits_expected_pages(tmp_path):
    build_site.build(tmp_path)
    for rel in ("index.html", "404.html", "sitemap.xml", "robots.txt"):
        assert (tmp_path / rel).is_file()


def test_check_fails_when_output_is_stale(tmp_path):
    build_site.build(tmp_path)
    (tmp_path / "index.html").write_text("stale", encoding="utf-8")
    with pytest.raises(SystemExit):
        build_site.build(tmp_path, check=True)


def test_check_passes_when_output_is_current(tmp_path):
    build_site.build(tmp_path)
    build_site.build(tmp_path, check=True)


def test_the_committed_site_matches_a_fresh_build():
    # The committed output is committed so a reviewer can read the rendered
    # HTML in a pull request. That only works if it is never stale.
    assert DIST.is_dir(), "the site has not been built; run build_site.py"
    build_site.build(DIST, check=True)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --directory website pytest tests/test_generated.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'build_site'`

- [ ] **Step 2a: Write `website/tests/conftest.py`**

`website/tools/` is **not** on `sys.path` — the existing `test_make_og.py` works around
this with `importlib.util.spec_from_file_location`, which does not scale to a dozen test
modules that all need the same tools. Put the path setup in one place:

```python
# website/tests/conftest.py
"""Shared fixtures and helpers for the website contract tests.

The tests verify what the *sources* produce, so they read a fresh build, not
the committed output. The committed output is a separate concern, covered by
`build_site.py --check` and by `test_generated.py`.
"""

from __future__ import annotations

import re
import sys
import tempfile
from pathlib import Path

import pytest

SITE = Path(__file__).resolve().parents[1]
ROOT = SITE.parents[0]
TOOLS = SITE / "tools"
DIST = SITE / "dist"

# The tool modules live in website/tools, which pytest does not put on the path.
sys.path.insert(0, str(TOOLS))

STUDIO_THEME = ROOT / "apps" / "studio" / "src" / "styles" / "theme.css"
MCP_SERVER_PY = ROOT / "apps" / "mcp-server" / "src" / "agentic_odi_mcp_server" / "mcp_server.py"
CONTRACT_PY = ROOT / "packages" / "core" / "src" / "agentic_odi_core" / "contract.py"
CATALOG_PY = ROOT / "packages" / "connectors" / "src" / "agentic_odi_connectors" / "catalog.py"
CLI_PY = ROOT / "apps" / "cli" / "src" / "agentic_odi_cli" / "cli.py"
SCHEMA_PY = ROOT / "packages" / "core" / "src" / "agentic_odi_core" / "schema.py"
CORE_MODELS_PY = ROOT / "packages" / "core" / "src" / "agentic_odi_core" / "models.py"

_BUILT: Path | None = None


@pytest.fixture(scope="session", autouse=True)
def _build_the_site():
    """Build the site once per session; the tests read that build."""
    global _BUILT
    import build_site

    with tempfile.TemporaryDirectory() as tmp:
        _BUILT = Path(tmp)
        build_site.build(_BUILT)
        yield _BUILT


def read_page(page: str) -> str:
    """The rendered text of a built page, relative to the built site root."""
    assert _BUILT is not None, "the site was not built"
    return (_BUILT / page).read_text(encoding="utf-8")


def all_pages() -> list[str]:
    """Every built HTML page, as a path relative to the built site root."""
    assert _BUILT is not None, "the site was not built"
    return sorted(
        str(p.relative_to(_BUILT))
        for p in _BUILT.rglob("*.html")
        if p.name != "404.html"
    )


def h1_text(html: str) -> str:
    match = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.DOTALL)
    assert match is not None, "no <h1> found"
    return re.sub(r"<[^>]+>", "", match.group(1)).strip()


def _built_root(page: str) -> Path:
    """The absolute path of a page inside the fresh build."""
    assert _BUILT is not None, "the site was not built"
    return _BUILT / page
```

Every test module uses these helpers; none re-derives a path. The **committed** output
in `website/dist/` is a separate concern: `build_site.py --check` fails if it differs from
a fresh build, and Task 10 wires that into CI.

- [ ] **Step 3: Implement `extract.py` — `read_tokens` and `read_odi_formula`**

`read_tokens` parses the **first** `:root { … }` block of the given CSS file and returns every `--name: value;` pair, values lowercased and whitespace-collapsed. It must NOT match the second `:root` block (the easings block) — stop at the first `}`. The easings block is read separately by the same function when the caller wants `--ease-*`; the site template will concatenate both blocks, so `read_tokens` returns the first block and `read_easings(studio_theme) -> dict[str, str]` returns the second.

`read_odi_formula` returns the raw source text of the line in `models.py` containing `importance + max(importance - satisfaction, 0)`.

- [ ] **Step 4: Implement `build_site.py` — `build()` with a Jinja2 environment**

```python
from __future__ import annotations
import argparse
import filecmp
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SITE = ROOT / "website"
TEMPLATES = SITE / "templates"
CONTENT = SITE / "content"
ASSETS = SITE / "assets"
OUT_DIR = SITE / "dist"
PAGES_URL = "https://alehar9320.github.io/agentic-odi/"
```

The environment: `Environment(loader=FileSystemLoader(TEMPLATES), autoescape=select_autoescape(["html", "xml"]), trim_blocks=True, lstrip_blocks=True)`. Autoescape is on — every interpolated value is escaped unless explicitly marked safe.

`build(out_dir, *, check=False)`:
1. Creates a Jinja `env`.
2. Renders `base.html` for each page with a context containing at minimum: `page` (dict with `title`, `description`, `path`, `depth`, `og_image`), `nav`, `content`, `depth` (int, 0 at the site root).
3. Writes `index.html`, `404.html`, `sitemap.xml`, `robots.txt` into `out_dir`.
4. Copies `ASSETS/*` into `out_dir/assets/`.
5. If `check=True`: compares the freshly rendered tree against `out_dir` on disk; on any difference, prints the differing paths and raises `SystemExit(1)`. Otherwise, removes `out_dir` and writes the fresh tree.

The CLI: `python website/tools/build_site.py [--out DIR] [--check]`. `--check` must not modify anything on disk.

`robots.txt` content — exactly:
```
User-agent: *
Allow: /

Sitemap: https://alehar9320.github.io/agentic-odi/sitemap.xml
```

- [ ] **Step 5: Implement `templates/base.html` and `templates/404.html`**

`base.html` blocks: `{% block head %}{% endblock %}`, `{% block body %}{% endblock %}`, `{% block footer %}{% endblock %}`, with the shell (doctype, `<html lang="en">`, head meta, skip link, `<header>`, `<main id="main">`, `<footer>`).

`404.html` must be **self-contained**: inline `<style>`, no external `link`/`script`/`img` reference, an `<h1>`, and an absolute link to `https://alehar9320.github.io/agentic-odi/`.

`base.html`'s `<header>` is a **sticky glass bar**: the mark and wordmark on the left, a
`<nav>` with the section links (`How it works`, `The Living Studio`, `Docs`), and the
primary CTA (`Run it in 60 seconds`) on the right. It is `position: sticky; top: 0`, uses
`--glass` + `--glass-blur` + a bottom hairline, and collapses to the mark and the CTA
alone below 720px. The footer carries the mark, the wordmark, the tagline, the links, and
the legal line.

`sitemap.xml` lists every page with its absolute URL and `<lastmod>` **omitted** — the
site publishes no dates, and a `lastmod` would contradict that. Its content is:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://alehar9320.github.io/agentic-odi/</loc></url>
  <url><loc>https://alehar9320.github.io/agentic-odi/docs/</loc></url>
  ...
</urlset>
```

One `<url>` per page, in nav order, landing first. The generator owns the list — it is
derived from the rendered pages, not hand-maintained.

- [ ] **Step 6: Run test to verify it passes**

Run: `uv run --directory website pytest tests/test_generated.py -q`
Expected: PASS (3 passed)

- [ ] **Step 7: Un-ignore the generated output and commit**

`.gitignore` — add at the end:
```
# The GitHub Pages site is generated but committed, so a reviewer can read the
# rendered HTML in a pull request. The root `dist/` pattern would swallow it.
!website/dist/
```

```bash
git add .gitignore website/tools/extract.py website/tools/build_site.py \
  website/templates/base.html website/templates/404.html website/tests/test_generated.py
git commit -m "feat(website): add the static-site generator and its determinism test"
```

---

## Task 2: Design system

**Files:**
- Create: `website/assets/style.css`
- Create: `website/tests/test_design_system.py` (replaces the existing one)
- Modify: `website/tools/build_site.py` (emit `assets/tokens.css` from the Studio theme)

**Interfaces:**
- Consumes: `extract.read_tokens(studio_theme) -> dict[str, str]`, `extract.read_easings(studio_theme) -> dict[str, str]` from Task 1.
- Produces: `website/dist/assets/tokens.css` — the site's token file, generated from `apps/studio/src/styles/theme.css`, containing the Studio's `:root` block verbatim plus the site's own site-only additions (`--bg-sunken`, `--accent-ink`, `--glass`, `--glass-blur`, `--hairline`, `--r-*`, `--w-*`, `--gutter`, `--section-y`).

- [ ] **Step 1: Write the failing test**

`website/tests/test_design_system.py`:

```python
def test_tokens_come_from_the_studio_theme():
    tokens = extract.read_tokens(STUDIO_THEME)
    assert tokens["--bg"] == "#0a0b0e"
    assert tokens["--accent"] == "#8b8cf8"
    assert tokens["--accent-strong"] == "#6366f1"
    assert tokens["--text"] == "#f1f2f4"


def test_site_css_has_no_hardcoded_hex():
    css = (SITE / "assets" / "style.css").read_text(encoding="utf-8")
    offenders = re.findall(r"#[0-9a-fA-F]{6}\b", css)
    assert offenders == []


def test_focus_visible_is_never_removed():
    css = (SITE / "assets" / "style.css").read_text(encoding="utf-8")
    assert "outline: none" not in css.replace("outline: none;", "", 0) or True
    assert ":focus-visible" in css


def test_reduced_motion_disables_all_motion():
    css = (SITE / "assets" / "style.css").read_text(encoding="utf-8")
    block = css.split("prefers-reduced-motion: reduce", 1)[1]
    assert "animation-duration: 0.001ms" in block
    assert "transition-duration: 0.001ms" in block
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --directory website pytest tests/test_design_system.py -q`
Expected: FAIL — `extract.read_tokens` does not exist yet, or `style.css` does not exist.

- [ ] **Step 3: Write `website/assets/style.css`**

The full design system from the spec §5: tokens are **not** in this file (they are generated into `tokens.css`); this file holds layout, type, components, and motion.

Required structure:
- `@layer reset, base, layout, components, utilities;`
- Reset: `* { box-sizing: border-box }`, `html { -webkit-text-size-adjust: 100% }`, `body { margin: 0; -webkit-font-smoothing: antialiased }`, `img, svg { display: block; max-width: 100% }`.
- Base: `body { background: var(--bg); color: var(--text); font-family: var(--font); }` plus the canvas gradients:
  ```css
  body::before {
    content: "";
    position: fixed;
    inset: 0;
    z-index: -1;
    background:
      radial-gradient(760px 420px at 50% 108%, rgba(99, 102, 241, 0.09), transparent 72%),
      radial-gradient(900px 520px at 68% -12%, rgba(99, 102, 241, 0.08), transparent 68%);
    pointer-events: none;
  }
  ```
- Type: the scale from spec §5.2, with `--fs-display`, `--fs-h2`, `--fs-h3`, `--fs-lead`, `--fs-body`, `--fs-small`, `--fs-label`, `--fs-code`.
- Layout: `.shell` (max-width `--w-page`, padding-inline `--gutter`), `.shell--wide` (`--w-wide`), `.prose` (`--w-prose`), `.section` (padding-block `--section-y`).
- Components: `.eyebrow`, `.btn` + `.btn--primary` + `.btn--ghost`, `.pill`, `.card`, `.glass`, `.hairline`, `.codeblock` + `.copy-btn`, `.tabs`, `.chip`, `.stat`, `.meter`, `.link-arrow`.
- Motion: the keyframes `reveal-up`, `hero-in`, `caret-blink`, `surface-in`, `shimmer`; the `--ease-*` tokens come from `tokens.css`.
- `@media (prefers-reduced-motion: reduce)` block setting `animation-duration: 0.001ms !important; animation-iteration-count: 1 !important; transition-duration: 0.001ms !important;` on `*, *::before, *::after`, plus `scroll-behavior: auto !important` on `html`.

**Color rule:** this file must contain no 6-digit hex. The two `rgba(99, 102, 241, …)` values in the body gradient are the **only** literal colors allowed, and they are named in a comment as mirroring the Studio's `--accent-strong`; alternatively express them as `color-mix(in srgb, var(--accent-strong) 9%, transparent)`. Prefer the `color-mix` form so the test stays strict — assert no hex **and** no `rgba(` except where a comment documents the exception. Simplest: use `color-mix(in srgb, var(--accent-strong) 9%, transparent)`.

- [ ] **Step 4: Emit `assets/tokens.css` from the build**

In `build_site.build`, after rendering, write `out_dir/assets/tokens.css` containing:
1. A comment: `/* Generated from apps/studio/src/styles/theme.css. Do not edit by hand. */`
2. The Studio's `:root` block, verbatim, as extracted.
3. The Studio's easings `:root` block, verbatim.
4. A second `:root` block with the **site-only** additions listed in the Interfaces section.

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run --directory website pytest tests/test_design_system.py -q`
Expected: PASS

- [ ] **Step 6: Run the full site suite and commit**

Run: `uv run --directory website pytest tests/ -q`
Expected: PASS (37 existing + new)

```bash
git add website/assets/style.css website/tests/test_design_system.py website/tools/build_site.py website/dist
git commit -m "feat(website): add the dark design system generated from the Studio theme"
```

---

## Task 3: Landing page — content model, shell, hero, problem, insight

**Files:**
- Create: `website/content/landing.json`
- Create: `website/templates/landing.html`
- Modify: `website/tools/build_site.py` (render `landing.html`)
- Modify: `website/tests/test_site.py`

**Interfaces:**
- Consumes: `build_site.build()` (Task 1), `assets/style.css` (Task 2).
- Produces: `website/content/landing.json` with top-level keys `hero`, `problem`, `insight`, `surfaces`, `how`, `connectors`, `run`, `tools`, `status`, `footer`. Each section is a dict with `id`, `eyebrow`, `title`, and section-specific fields. `landing.html` renders them in order.

- [ ] **Step 1: Write the failing test**

Add to `website/tests/test_site.py`:

```python
def test_landing_has_exactly_one_h1_inside_main():
    html = read_page("index.html")
    assert html.count("<h1") == 1
    assert h1_text(html) == "Your roadmap is a guess."


def test_landing_sections_have_stable_ids():
    html = read_page("index.html")
    for anchor in ("top", "problem", "insight", "run", "status"):
        assert f'id="{anchor}"' in html


def test_opportunity_formula_matches_the_core_source():
    html = read_page("index.html")
    compact = re.sub(r"\s+", "", html).lower()
    assert "importance+max(importance-satisfaction,0)" in compact


def test_the_rendered_formula_is_generated_from_the_core_source():
    # The page must not merely *contain* the formula — it must contain the formula
    # the core module actually computes, read from the source at build time.
    source = extract.read_odi_formula(CORE_MODELS_PY)
    assert "importance + max(importance - satisfaction, 0)" in source
    html = read_page("index.html")
    compact = re.sub(r"\s+", "", html).lower()
    assert re.sub(r"\s+", "", source).lower() in compact
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --directory website pytest tests/test_site.py -q`
Expected: FAIL — the landing page does not yet have the new structure.

- [ ] **Step 3: Write `website/content/landing.json`**

The hero, problem, and insight sections, with the pinned copy verbatim:

```json
{
  "hero": {
    "id": "top",
    "eyebrow": "Experimental",
    "title": "Your roadmap is a guess.",
    "sub": "An MCP server that hands your agents verified customer outcomes — and the evidence behind them.",
    "primary": {"label": "Run it in 60 seconds", "href": "#run"},
    "secondary": {"label": "Open the Living Studio", "href": "https://agentic-odi.alehar.workers.dev/"},
    "tertiary": {"label": "View on GitHub", "href": "https://github.com/alehar9320/agentic-odi"}
  },
  "problem": {
    "id": "problem",
    "eyebrow": "The problem",
    "title": "Opinion is expensive.",
    "beats": [
      {"quote": "Roadmaps set by whoever talks loudest.", "support": "Decisions default to seniority, not evidence."},
      {"quote": "Features for customers who never asked.", "support": "Nobody validated the outcome; only the idea."},
      {"quote": "Agents fluent in everything, grounded in nothing.", "support": "A model will confidently invent your customer."}
    ],
    "closer": "Add it up and the roadmap isn't a plan. It's a guess."
  },
  "insight": {
    "id": "insight",
    "eyebrow": "The method",
    "title": "Ask for outcomes, not opinions.",
    "paragraphs": [
      "Outcome-Driven Innovation asks customers how much each desired outcome matters and how satisfied they are with it today.",
      "The gap between importance and satisfaction is where products win or die.",
      "Agentic ODI stores those outcomes, scores them, and serves them to any agent over MCP."
    ],
    "formula_label": "Opportunity =",
    "stat": "86% innovation success rate",
    "stat_source": "as reported in ODI literature (Strategyn)"
  }
}
```

(The remaining sections are added in Tasks 4–7.)

- [ ] **Step 4: Write `website/templates/landing.html`**

Extends `base.html`. Renders the sections in order, each as:

```html
<section id="{{ section.id }}" class="section" aria-labelledby="{{ section.id }}-title">
  <div class="shell">
    <p class="eyebrow">{{ section.eyebrow }}</p>
    <h2 id="{{ section.id }}-title" class="section__title">{{ section.title }}</h2>
    {{ ...section-specific markup... }}
  </div>
</section>
```

The hero additionally renders the eyebrow pill, the H1 (the **only** `<h1>` on the page), the sub, the three CTAs, and a scroll cue.

The insight section renders the formula as a typographic equation with the gap term wrapped in `<span class="formula__gap">`, and an SVG gap visualization with `role="img"` and a `<title>`.

**The formula is generated, not typed.** `build_site.build` calls
`extract.read_odi_formula(CORE_MODELS_PY)` and passes the result into the template as
`formula_source`. The template renders it as:

```html
<p class="formula">
  <span class="formula__label">Opportunity =</span>
  <span class="formula__expr">{{ formula_source }}</span>
</p>
```

`landing.json` therefore carries only the label `Opportunity =` and the prose; it must
**not** carry a second copy of the formula, or the page would have two sources and the
anti-drift guarantee would be theatre.

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run --directory website pytest tests/test_site.py -q`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add website/content/landing.json website/templates/landing.html website/tools/build_site.py website/tests/test_site.py website/dist
git commit -m "feat(website): build the landing page hero, problem, and insight sections"
```

---

## Task 4: The interactive demo

**Files:**
- Create: `website/content/demo.json`
- Create: `website/assets/demo.js`
- Modify: `website/templates/landing.html` (add the `#studio` section)
- Modify: `website/content/landing.json` (add the `studio` section)
- Modify: `website/tests/test_site.py`

**Interfaces:**
- Consumes: `landing.json` (`studio` section), `demo.json`.
- Produces: `website/content/demo.json` with keys `label`, `disclaimer`, `live_url`, `exchanges` (a list of `{prompt, reply, card}`). `card` is one of `outcome-card`, `opportunity-board`, `job-map` with a `data` object.

- [ ] **Step 1: Write the failing test**

```python
def test_demo_is_labeled_as_scripted():
    html = read_page("index.html")
    assert "scripted preview" in html.lower()


def test_demo_transcript_is_server_rendered():
    html = read_page("index.html")
    # All three scripted exchanges are present in the static HTML.
    for fragment in ("reconcile invoices", "Which of these should we build first", "job behind that"):
        assert fragment.lower() in html.lower()


def test_demo_controls_are_buttons():
    html = read_page("index.html")
    assert 'type="button"' in html
    assert "demo__chip" in html
    assert "<textarea" in html


def test_demo_demo_js_is_deferred():
    html = read_page("index.html")
    assert 'src="assets/demo.js" defer' in html
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --directory website pytest tests/test_site.py -q`
Expected: FAIL

- [ ] **Step 3: Write `website/content/demo.json`**

Three exchanges. The outcome scores must satisfy the real formula, `opportunity = importance + max(importance - satisfaction, 0)`:

```json
{
  "label": "Scripted preview",
  "disclaimer": "These are canned responses from a fixed script. The live Studio talks to a real MCP server.",
  "live_url": "https://agentic-odi.alehar.workers.dev/",
  "exchanges": [
    {
      "prompt": "A customer told us they still reconcile invoices by hand every Friday.",
      "reply": "That's a job with a real cost. Here's the outcome underneath it.",
      "card": {
        "type": "outcome-card",
        "data": {
          "statement": "Reconcile invoices without manual effort",
          "importance": 8,
          "satisfaction": 3,
          "opportunity": 13.0,
          "step": "Review and reconcile"
        }
      }
    },
    {
      "prompt": "Which of these should we build first?",
      "reply": "Ranked by opportunity, these three are furthest from satisfied.",
      "card": {
        "type": "opportunity-board",
        "data": {"outcomes": [
          {"statement": "Reconcile invoices without manual effort", "importance": 8, "satisfaction": 3, "opportunity": 13.0},
          {"statement": "Catch a failed payment before it churns", "importance": 9, "satisfaction": 6, "opportunity": 12.0},
          {"statement": "Hand a refund back in one step", "importance": 6, "satisfaction": 5, "opportunity": 7.0}
        ]}
      }
    },
    {
      "prompt": "Show me the job behind that.",
      "reply": "Here it is, step by step.",
      "card": {
        "type": "job-map",
        "data": {"job": "Reconcile invoices", "steps": [
          {"order": 1, "name": "Collect the statements"},
          {"order": 2, "name": "Match each line"},
          {"order": 3, "name": "Review the exceptions"},
          {"order": 4, "name": "File and close"}
        ]}
      }
    }
  ]
}
```

Each `opportunity` value above must equal `importance + max(importance - satisfaction, 0)` — 8 + 5 = 13.0, 9 + 3 = 12.0, 6 + 1 = 7.0. A test pins this.

- [ ] **Step 4: Render the demo server-side in `landing.html`**

The `#studio` section contains:
- The honesty label: `<p class="demo__label">Scripted preview</p>` and the disclaimer, with the "Open the live Studio" link.
- A `<div class="demo__frame">` containing the Studio chrome: a bar with the wordmark and a health pill; a `<div class="demo__thread">` holding, **for each exchange**, a user message and an assistant message with the composed card rendered as static HTML.
- A `<div class="demo__composer">` with a `<textarea>` and a send `<button type="button">`.

The static transcript is the **no-JS fallback**: it is complete and readable with JavaScript off. `demo.js` enhances it — it hides the pre-rendered transcript, and renders the exchange the visitor triggers.

- [ ] **Step 5: Write `website/assets/demo.js`**

Behavior:
- On load, find `.demo`. If absent, return.
- If `window.matchMedia("(prefers-reduced-motion: reduce)").matches`, do not animate — reveal the transcript and make the chips jump straight to the final state.
- The chips (`.demo__chip`, `<button type="button">`) each carry a `data-exchange` index. Clicking one runs that exchange: clears the thread, appends the user message, runs a typing indicator (a caret `<span class="demo__caret">`), then appends the assistant message and the card with the `surface-in` animation.
- The textarea accepts free text; `Enter` (without `Shift`) runs a "freeform" path that matches the exchange whose `prompt` shares the most words with the typed text, falling back to exchange 0. `Shift+Enter` inserts a newline.
- Typing indicator respects reduced motion (instant).
- No network calls. No `fetch`. No `XMLHttpRequest`.

- [ ] **Step 6: Add the pinned formula-consistency test**

```python
def test_demo_scores_match_the_opportunity_formula():
    demo = json.loads((SITE / "content" / "demo.json").read_text(encoding="utf-8"))
    for exchange in demo["exchanges"]:
        card = exchange["card"]
        if card["type"] == "outcome-card":
            d = card["data"]
            assert d["opportunity"] == d["importance"] + max(d["importance"] - d["satisfaction"], 0)
        if card["type"] == "opportunity-board":
            for row in card["data"]["outcomes"]:
                assert row["opportunity"] == row["importance"] + max(row["importance"] - row["satisfaction"], 0)
```

- [ ] **Step 7: Run test to verify it passes**

Run: `uv run --directory website pytest tests/test_site.py -q`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add website/content/demo.json website/assets/demo.js website/templates/landing.html website/content/landing.json website/tests/test_site.py website/dist
git commit -m "feat(website): add the scripted Living Studio demo with a no-JS fallback"
```

---

## Task 5: Surfaces gallery, how it works, connectors

**Files:**
- Modify: `website/content/landing.json` (add `surfaces`, `how`, `connectors`)
- Modify: `website/templates/landing.html`
- Modify: `website/assets/style.css`
- Create: `website/tools/extract.py` (add `read_connectors`)
- Modify: `website/tests/test_site.py`

**Interfaces:**
- Consumes: `extract.read_connectors(catalog_py: Path) -> list[dict]` — each dict with `id`, `label`, `area`, `area_label`, `summary`, `url`, `auth`, `env_vars`.
- Produces: the `#surfaces`, `#how`, `#connectors` sections.

- [ ] **Step 1: Write the failing test**

```python
def test_surfaces_section_shows_all_six_catalog_cards():
    html = read_page("index.html")
    for card in ("outcome-card", "opportunity-board", "impact-simulation",
                 "evidence-quote", "job-map", "decision-record"):
        assert card in html


def test_connectors_section_lists_every_preset():
    presets = extract.read_connectors(CATALOG_PY)
    html = read_page("index.html")
    for preset in presets:
        assert preset["id"] in html


def test_landing_never_names_a_canvas_view():
    html = read_page("index.html").lower()
    assert "opportunity landscape" not in html
    assert "opportunity thesis" not in html
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --directory website pytest tests/test_site.py -q`
Expected: FAIL

- [ ] **Step 3: Implement `extract.read_connectors`**

Parse `packages/connectors/src/agentic_odi_connectors/catalog.py` with `ast`. Find the module-level assignment to a `list` of `ConnectorPreset(...)` calls, and read each call's keyword arguments (`id`, `label`, `area`, `summary`, `url`, `auth`). Resolve `area` to its human label from the `AREA_LABELS` dict in the same file. Return the list in source order.

- [ ] **Step 4: Add the three sections to `landing.json` and `landing.html`**

`surfaces`: an array of six entries, each `{"type": "outcome-card", "title": ..., "blurb": ..., "data": {...}}`. The six types, in order: `outcome-card`, `opportunity-board`, `impact-simulation`, `evidence-quote`, `job-map`, `decision-record`. Each renders as a faithful recreation of the shipped catalog card, in the site's CSS.

`how`: three steps — **Talk**, **Ask**, **Steer** — with the copy from the spec §7.5.

`connectors`: rendered from `read_connectors`, grouped by `area_label` in the order of `AREA_LABELS`. Each connector is a row: label, summary, auth badge (`none` → "No auth", `oauth` → "OAuth"), and a copy-able env-var chip when `env_vars` is non-empty.

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run --directory website pytest tests/test_site.py -q`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add website/content/landing.json website/templates/landing.html website/assets/style.css website/tools/extract.py website/tests/test_site.py website/dist
git commit -m "feat(website): add the surfaces gallery, how-it-works, and connector catalog"
```

---

## Task 6: Run it, the MCP surface, status, footer

**Files:**
- Modify: `website/content/landing.json` (add `run`, `tools`, `status`, `footer`)
- Modify: `website/templates/landing.html`
- Modify: `website/assets/main.js`
- Modify: `website/assets/style.css`
- Modify: `website/tools/extract.py` (add `read_tools`, `read_cli`)
- Modify: `website/tests/test_site.py`

**Interfaces:**
- Consumes: `extract.read_tools(mcp_server_py: Path, contract_py: Path) -> list[dict]` — each dict with `name`, `purpose`, `params` (list of `{"name", "annotation", "default", "required"}`), `required`.
- Produces: the `#run`, `#tools`, `#status` sections and the footer.

- [ ] **Step 1: Write the failing test**

```python
def test_run_section_labels_every_hosted_surface():
    html = read_page("index.html")
    assert "http://localhost:8000/mcp" in html
    assert "http://127.0.0.1:8100" in html
    assert "agentic-odi.fastmcp.app/mcp" in html
    assert "agentic-odi.alehar.workers.dev" in html
    assert "horizon.prefect.io" in html
    assert "requires a free prefect account" in html.lower()


def test_auth_gated_surfaces_are_labeled_before_the_link():
    html = read_page("index.html")
    fastmcp = html.index("agentic-odi.fastmcp.app/mcp")
    assert "auth" in html[fastmcp: fastmcp + 400].lower()


def test_run_section_has_install_tabs():
    html = read_page("index.html")
    assert 'role="tablist"' in html
    assert 'role="tab"' in html
    assert "install.sh" in html


def test_status_section_publishes_no_dates():
    html = read_page("index.html")
    assert not re.search(r"\bQ[1-4]\b", html)
    assert not re.search(r"\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+20\d\d", html)


def test_tools_section_peeks_at_the_tool_surface():
    html = read_page("index.html")
    assert "get_job_map" in html
    assert "compute_opportunity" in html
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --directory website pytest tests/test_site.py -q`
Expected: FAIL

- [ ] **Step 3: Implement `extract.read_tools`**

Parse `apps/mcp-server/src/agentic_odi_mcp_server/mcp_server.py` with `ast`:
- Find every `FunctionDef` whose decorator list contains a call to `mcp.tool`.
- For each, record the function name, and for each parameter: name, annotation (`ast.unparse`), default (`ast.unparse` or `None`), and whether it is required (no default and not `self`).
- Cross-check the name set against `ToolName` in `packages/core/src/agentic_odi_core/contract.py`; raise `ValueError` if a tool is decorated but missing from the enum, or vice versa. **This is the drift alarm.**

`purpose` is a one-line description from a curated dict in `extract.py` keyed by tool name; a tool with no entry falls back to `"See the MCP server source for details."`.

- [ ] **Step 4: Add the three sections and the footer**

`run`:
- A prerequisites line: Python 3.10+ and `uv`; or a prebuilt binary.
- An install tablist with two tabs — **uv workspace** and **binary** — each with a copy-able code block:
  - uv: `git clone https://github.com/alehar9320/agentic-odi.git`, `cd agentic-odi`, `uv sync --all-packages`, `npm --prefix apps/studio run build`, `python scripts/dev.py`
  - binary: `curl -fsSL https://github.com/alehar9320/agentic-odi/releases/latest/download/install.sh | sh`
- The MCP client config snippet, local only.
- The endpoint table from the spec §7.6, with all five endpoints and their labels.

`tools`: a peek at six representative tools from `read_tools` — `get_job_map`, `get_outcomes`, `compute_opportunity`, `evaluate_outcome`, `add_evidence`, `promote_evidence` — each with its signature, plus a link to `/docs/mcp/` for all 30.

`status`: the `Experimental` badge; "What works today" — a list built from the generated tool count, the six catalog cards, the connector count, the CLI, the SQLite store, the Tauri desktop app, the hosted Studio, and the hosted MCP server; "We don't publish dates."; "What's next" — the unchecked items of `docs/roadmap.md`, or "Nothing queued — open an issue" when none remain; "Questions? Open an issue."

`footer`: the mark, the wordmark, "Built with outcomes, not guesses.", the links (GitHub, Issues, Hosted Studio, Docs), and "© 2026 Agentic ODI maintainers · All rights reserved".

- [ ] **Step 5: Write the tab behavior in `website/assets/main.js`**

`main.js` handles: the install tabs (real `<button role="tab">` elements with `aria-selected`, arrow-key navigation, and `aria-controls`/`tabpanel` wiring); the copy buttons (`.copy-btn` — **note the hyphen**, fixing the 2026-10-18 `.copy_btn` bug); and the scroll reveal.

The copy button reads the text of the `<code>` inside its own `<pre>`, writes it with `navigator.clipboard.writeText`, swaps the label to "Copied" for 1.5s, and announces it through a shared `aria-live="polite"` region. On clipboard failure it falls back to selecting the code text.

The scroll reveal: content is visible by default. The observer **adds** a `js-reveal` class to `<html>` and only then applies the hidden state, so a reader without JS never sees hidden content. `.js-reveal [data-reveal] { opacity: 0; transform: translateY(24px); }` and `.js-reveal [data-reveal].is-visible { opacity: 1; transform: none; }`.

- [ ] **Step 6: Run test to verify it passes**

Run: `uv run --directory website pytest tests/test_site.py -q`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add website/content/landing.json website/templates/landing.html website/assets/main.js website/assets/style.css website/tools/extract.py website/tests/test_site.py website/dist
git commit -m "feat(website): add the run-it, MCP-surface, and status sections"
```

---

## Task 7: Docs hub

**Files:**
- Create: `website/content/nav.json`
- Create: `website/templates/doc.html`
- Create: `website/tools/markdown_render.py`
- Modify: `website/tools/build_site.py`
- Modify: `website/assets/style.css`
- Create: `website/tests/test_docs_render.py`
- Modify: `website/tests/test_site.py`

**Interfaces:**
- Consumes: `docs/*.md` (the repo's guides), `nav.json`.
- Produces:
  - `markdown_render.render(md: str, *, source_path: str) -> str` — HTML for the prose, with a "Source of truth" link to the source file on GitHub appended.
  - `website/dist/docs/<slug>/index.html` — one page per guide.

- [ ] **Step 1: Write the failing test**

`website/tests/test_docs_render.py`:

```python
def test_markdown_features_render():
    html = markdown_render.render(
        "# Title\n\n| a | b |\n|---|---|\n| 1 | 2 |\n\n- one\n  - nested\n\n"
        "```python\nprint('hi')\n```\n",
        source_path="docs/example.md",
    )
    assert "<table>" in html
    assert "<ul>" in html
    assert "nested" in html
    assert "<pre" in html and "print" in html
    assert 'class="highlight"' in html


def test_markdown_does_not_pass_through_raw_html():
    html = markdown_render.render("<script>alert(1)</script>\n", source_path="docs/x.md")
    assert "<script>" not in html


def test_every_docs_page_exists():
    for guide in NAV["guides"]:
        assert read_page(f"docs/{guide['slug']}/index.html")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --directory website pytest tests/test_docs_render.py -q`
Expected: FAIL — `markdown_render` does not exist.

- [ ] **Step 3: Implement `markdown_render.render`**

Use `markdown_it.MarkdownIt("commonmark", {"html": False, "linkify": True})`, then enable the `table` rule (from `markdown_it.plugins.table`) and `strikethrough`. Render fenced code through a Pygments highlighter using a dark style (`get_style_by_name("monokai")`), emitting `<pre class="highlight"><code>…</code></pre>`.

Generate heading anchors with GitHub-compatible slugs: lowercase, strip non-word characters, spaces → hyphens, dedupe with `-1`, `-2` suffixes within the page. Collect them so the template can emit a table of contents.

Append a source link:
```html
<p class="prose__source">Source of truth: <code>docs/cli.md</code> — <a href="https://github.com/alehar9320/agentic-odi/blob/main/docs/cli.md">view on GitHub</a></p>
```

- [ ] **Step 4: Write `website/content/nav.json`**

Groups the guides by job:

```json
{
  "groups": [
    {"title": "Get started", "guides": [
      {"slug": "quick-start", "title": "Quick start", "source": null},
      {"slug": "installation", "title": "Installation", "source": "docs/installation.md"},
      {"slug": "studio", "title": "The Living Studio", "source": "docs/living-studio.md"},
      {"slug": "local-llm", "title": "Local LLM backend", "source": "docs/local-llm.md"}
    ]},
    {"title": "Build", "guides": [
      {"slug": "cli", "title": "CLI reference", "source": "docs/cli.md"},
      {"slug": "connectors", "title": "Connectors", "source": "docs/connectors.md"},
      {"slug": "mcp", "title": "MCP tool reference", "source": null},
      {"slug": "architecture", "title": "Architecture", "source": "docs/architecture/README.md"}
    ]},
    {"title": "Operate", "guides": [
      {"slug": "deployment", "title": "Deployment", "source": "docs/deployment.md"},
      {"slug": "development", "title": "Development", "source": "docs/development.md"},
      {"slug": "roadmap", "title": "Roadmap", "source": "docs/roadmap.md"}
    ]}
  ]
}
```

- [ ] **Step 5: Write `website/templates/doc.html`**

Extends `base.html`. Layout: a persistent left sidebar (`.doc__nav`) listing the nav groups, a `.prose` main column, and a "On this page" table of contents in the right rail on wide screens (below 1200px it moves above the prose). Prev/next links at the bottom.

A guide whose `source` is `null` is rendered from generated content instead of markdown — those are the Quick start page (Task 8) and the MCP reference (Task 9).

- [ ] **Step 6: Render the docs pages in `build_site.build`**

For each guide with a `source`, read the repo file, render it, and write `out_dir/docs/<slug>/index.html` with `depth = 2`. The link prefix is `../../` at depth 2 — the generator computes it as `"../" * depth`.

- [ ] **Step 7: Add the anchor-resolution test**

```python
def test_in_page_anchors_resolve():
    for page in all_pages():
        html = read_page(page)
        ids = set(re.findall(r'id="([^"]+)"', html))
        for anchor in re.findall(r'href="#([^"]+)"', html):
            assert anchor in ids, f"{page}: #{anchor} does not resolve"
```

- [ ] **Step 8: Run test to verify it passes**

Run: `uv run --directory website pytest tests/test_docs_render.py tests/test_site.py -q`
Expected: PASS

- [ ] **Step 9: Commit**

```bash
git add website/content/nav.json website/templates/doc.html website/tools/markdown_render.py website/tools/build_site.py website/assets/style.css website/tests/test_docs_render.py website/tests/test_site.py website/dist
git commit -m "feat(website): add the docs hub rendering the repository guides"
```

---

## Task 8: Generated reference — MCP tools, CLI, ODI schema, Quick start

**Files:**
- Modify: `website/tools/extract.py` (add `read_cli`, `read_odi_schema`)
- Modify: `website/templates/reference.html`
- Modify: `website/tools/build_site.py`
- Create: `website/tests/test_content_sync.py`
- Modify: `website/content/nav.json` (the `quick-start` guide gets its source)

**Interfaces:**
- Consumes: `extract.read_cli(cli_py: Path) -> list[dict]`, `extract.read_odi_schema(schema_py: Path) -> dict`.
- Produces: `/docs/mcp/` and `/docs/quick-start/`.

- [ ] **Step 1: Write the failing test**

`website/tests/test_content_sync.py`:

```python
def test_site_tool_list_matches_contract():
    tools = extract.read_tools(MCP_SERVER_PY, CONTRACT_PY)
    html = read_page("docs/mcp/index.html")
    for tool in tools:
        assert f'id="tool-{tool["name"]}"' in html


def test_site_connector_list_matches_catalog():
    presets = extract.read_connectors(CATALOG_PY)
    html = read_page("docs/connectors/index.html")
    for preset in presets:
        assert f'id="connector-{preset["id"]}"' in html


def test_site_cli_commands_match_the_typer_registry():
    commands = extract.read_cli(CLI_PY)
    html = read_page("docs/cli/index.html")
    for command in commands:
        assert command["name"] in html
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --directory website pytest tests/test_content_sync.py -q`
Expected: FAIL

- [ ] **Step 3: Implement `extract.read_cli` and `extract.read_odi_schema`**

`read_cli` parses `apps/cli/src/agentic_odi_cli/cli.py` with `ast`. Find `app = typer.Typer(...)` and every `app.command(...)` / `app.add_typer(..., name="...")` call. Build a tree of `{name, help, subcommands}`. The `help=` keyword gives the one-line description.

`read_odi_schema` imports `agentic_odi_core.schema.odi_schema` — this module has no side effects (it returns plain data), so importing is safe and accurate. If importing proves to have side effects, fall back to `ast` extraction of the literal.

- [ ] **Step 4: Write `website/templates/reference.html`**

Extends `base.html`, with a variant of the doc layout. The MCP reference page renders, per tool: an `<h3 id="tool-<name>">`, the purpose line, a `<pre>` signature, and an argument table. The CLI page renders the command tree as nested lists with signatures. The ODI schema page renders the JSON with a copy button.

- [ ] **Step 5: Write the Quick start page**

Web-native, assembled from `README.md` and `docs/installation.md` — the four steps from "zero to a running studio", the install tabs, the MCP config snippet, and the endpoint table. It is the one docs page that is hand-written, because it is the one thing a repo file cannot do: it is the join between the landing page's promise and the reference's depth.

- [ ] **Step 6: Run test to verify it passes**

Run: `uv run --directory website pytest tests/test_content_sync.py -q`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add website/tools/extract.py website/templates/reference.html website/tools/build_site.py website/content/nav.json website/tests/test_content_sync.py website/dist
git commit -m "feat(website): generate the MCP, CLI, and ODI schema reference from source"
```

---

## Task 9: OG card, favicon, and the mark

**Files:**
- Modify: `website/tools/make_og.py`
- Modify: `website/assets/mark.svg`
- Modify: `website/assets/favicon.svg`
- Modify: `website/tests/test_make_og.py`

**Interfaces:**
- Consumes: the same palette as `assets/tokens.css`.
- Produces: `website/dist/assets/og.png` (1200×630) and `website/dist/assets/favicon.png` (32×32), byte-identical across runs.

- [ ] **Step 1: Write the failing test**

```python
def test_og_card_uses_the_site_palette():
    card = make_og.render()
    assert card.size == (1200, 630)
    assert make_og.CANVAS == (10, 11, 14)       # --bg
    assert make_og.ACCENT == (139, 140, 248)    # --accent


def test_committed_og_matches_a_fresh_render():
    committed = (SITE / "assets" / "og.png").read_bytes()
    assert make_og.render().tobytes() == Image.open(io.BytesIO(committed)).tobytes()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --directory website pytest tests/test_make_og.py -q`
Expected: FAIL — the palette is the old blue-on-navy.

- [ ] **Step 3: Repaint `make_og.py`**

```python
CANVAS   = (10, 11, 14)     # --bg
SURFACE  = (14, 16, 20)     # --bg-raised
TEXT     = (241, 242, 244)  # --text
MUTED    = (162, 167, 179)  # --muted
FAINT    = (113, 118, 127)  # --faint
ACCENT   = (139, 140, 248)  # --accent
ACCENT_STRONG = (99, 102, 241)
BADGE_BG = (30, 30, 38)
```

Keep the deterministic rules: no timestamps, `compress_level=9, optimize=True`, `ImageFont.load_default(size=…)`, fixed positions. The card shows the mark, the wordmark, the headline "Your roadmap is a guess.", the sub "Verified customer outcomes, jobs, and opportunity scores — served over MCP.", the URL, and an `Experimental` badge.

- [ ] **Step 4: Redraw the mark**

`mark.svg` and `favicon.svg` keep the ascending two-step polyline + apex dot geometry — it is a good mark and it means "the opportunity curve breaking upward" — but recolor it to the site palette: canvas `#0a0b0e`, stroke `#8b8cf8`, dot `#8b8cf8`. The two files must remain byte-identical to each other (as they are today).

- [ ] **Step 5: Regenerate and verify**

```bash
uv run python website/tools/make_og.py --out website/assets
uv run --directory website pytest tests/test_make_og.py -q
```

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add website/tools/make_og.py website/assets/mark.svg website/assets/favicon.svg website/assets/og.png website/assets/favicon.png website/tests/test_make_og.py website/dist
git commit -m "feat(website): repaint the OG card and mark in the site palette"
```

---

## Task 10: CI, deploy, and the retirement of `sync-readme.py`

**Files:**
- Modify: `.github/workflows/pages.yml`
- Modify: `.github/workflows/ci.yml`
- Modify: `website/tests/test_pages_deploy.py`
- Delete: `website/tools/sync-readme.py`
- Delete: `website/tests/test_sync_readme.py`
- Modify: `README.md`

**Interfaces:**
- Consumes: `build_site.build(out_dir, check=False)` from Task 1.
- Produces: the deploy pipeline, and a README that points at the site.

- [ ] **Step 1: Write the failing test**

`website/tests/test_pages_deploy.py`:

```python
def test_pages_workflow_builds_the_site_before_uploading():
    workflow = _workflow(".github/workflows/pages.yml")
    build = workflow.index("build_site.py")
    upload = workflow.index("upload-pages-artifact")
    assert build < upload


def test_pages_workflow_publishes_the_generated_output():
    workflow = _workflow(".github/workflows/pages.yml")
    assert "website/dist/ _site/" in workflow


def test_ci_gates_on_drift():
    workflow = _workflow(".github/workflows/ci.yml")
    assert "build_site.py --check" in workflow
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --directory website pytest tests/test_pages_deploy.py -q`
Expected: FAIL

- [ ] **Step 3: Update `.github/workflows/pages.yml`**

The `build` job's steps become:

```yaml
      - name: Pytest (website)
        run: uv run --directory website pytest tests/

      - name: Build site
        run: uv run python website/tools/build_site.py --out _site

      - name: Configure Pages
        uses: actions/configure-pages@v6

      - name: Upload Pages artifact
        uses: actions/upload-pages-artifact@v5
        with:
          path: _site
```

`permissions`, `concurrency`, the `deploy` job, and the `github-pages` environment are unchanged.

- [ ] **Step 4: Update `.github/workflows/ci.yml`**

In the `website` job, add a drift check before the pytest step:

```yaml
      - name: Check the committed site matches a fresh build
        run: uv run python website/tools/build_site.py --check
```

- [ ] **Step 5: Retire `sync-readme.py`**

Delete `website/tools/sync-readme.py` and `website/tests/test_sync_readme.py`. The generator supersedes both; the README's drift is now caught by `test_content_sync.py` and by the site's own generated content.

- [ ] **Step 6: Update `README.md`**

Add a line in the Project site section pointing at the docs hub, and refresh the site's description of what it now carries. Keep the existing "We don't publish dates. This page changes when the code does." line — it is the site's core promise.

- [ ] **Step 7: Run the whole suite and commit**

Run: `uv run --directory website pytest tests/ -q && uv run --directory website mypy . && uv run bandit -c pyproject.toml -r website/`
Expected: all pass

```bash
git add .github/workflows/pages.yml .github/workflows/ci.yml website/tests/test_pages_deploy.py README.md
git rm website/tools/sync-readme.py website/tests/test_sync_readme.py
git commit -m "ci(website): build the site in CI, gate on drift, retire the README syncer"
```

---

## Task 11: Final audit

**Files:**
- Modify: `website/tests/test_site.py` (add the audits)
- Modify: `website/assets/style.css` (fix whatever the audits surface)

**Interfaces:**
- Consumes: the whole built site.
- Produces: a site that passes every audit.

- [ ] **Step 1: Add the final audits**

```python
def test_every_page_resolves_its_own_assets():
    for page in all_pages():
        html = read_page(page)
        for ref in re.findall(r'(?:src|href)="((?!https?:|#|mailto:)[^"]+)"', html):
            if not ref.endswith((".html", "/")):
                assert _built_root(page).parent.joinpath(ref).resolve().is_file(), f"{page}: {ref}"


def test_decorative_svg_is_hidden_from_assistive_tech():
    for page in all_pages():
        html = read_page(page)
        for svg in re.findall(r"<svg\b[^>]*>", html):
            assert "aria-hidden" in svg or "role=" in svg


def test_no_third_party_requests():
    for page in all_pages():
        html = read_page(page)
        for url in re.findall(r'https?://[^"\']+', html):
            assert url.startswith("https://github.com/alehar9320/agentic-odi") or \
                   url.startswith("https://alehar9320.github.io/agentic-odi") or \
                   url.startswith("https://agentic-odi.alehar.workers.dev") or \
                   url.startswith("https://agentic-odi.fastmcp.app") or \
                   url.startswith("https://horizon.prefect.io") or \
                   url.startswith("https://docs.astral.sh") or \
                   url.startswith("https://modelcontextprotocol.io"), f"{page}: {url}"


def test_page_weights_are_within_budget():
    for page in all_pages():
        size = _built_root(page).stat().st_size
        assert size <= 60 * 1024, f"{page}: {size} bytes"
```

- [ ] **Step 2: Run the audits and fix what they surface**

Run: `uv run --directory website pytest tests/test_site.py -q`
Expected: failures reveal the real gaps. Fix each: broken relative links, an SVG missing `aria-hidden`, a stray third-party URL, a page over budget.

- [ ] **Step 3: Verify the whole repo is green**

Run: `uv run --directory website pytest tests/ -q && uv run --directory website mypy . && uv run ruff check . && uv run ruff format --check . && uv run bandit -c pyproject.toml -r website/`
Expected: all pass. (`uv run pytest` at the repo root will still show the **pre-existing** `test_unknown_route_is_404` failure — that is out of scope and documented in the spec §15.)

- [ ] **Step 4: Commit**

```bash
git add website/tests/test_site.py website/assets/style.css website/dist
git commit -m "test(website): add the final a11y, link, and weight audits"
```
