# GitHub Pages Marketing Site Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the single-page GitHub Pages marketing site per the design spec — Jobsian one-pager, quickstart-first CTA, honest experimental framing, reproducible OG art, structural test suite, Actions deploy.

**Architecture:** Static sources in `website/` (`index.html`, `404.html`, `assets/{style.css,main.js,mark.svg,favicon.svg,og.png,favicon.png}`); generator `website/tools/make_og.py` (Pillow, pinned); structural tests in `website/tests/` run from the repo root with the workspace venv; deploy via `.github/workflows/pages.yml` (staged artifact → `deploy-pages`) with a new `website` job added to `ci.yml` and to `ci-green`'s `needs`.

**Tech Stack:** Hand-written HTML/CSS/vanilla JS (no framework, no build step); Python 3.10+ stdlib (`html.parser`, `xml.etree`, `struct`) + pytest for tests; new root dev deps `pillow==12.3.0` (Task 1) and `pyyaml==6.0.3` (Task 4); GitHub Actions `checkout@v7`, `configure-pages@v6`, `upload-pages-artifact@v5`, `deploy-pages@v5`, composite `./.github/actions/setup`; uv.

**Spec:** `docs/superpowers/specs/2026-10-18-github-pages-design.md` (copy, tokens, and honesty strings marked binding there are enforced by the tests below)

**Definition of Done:** PR pushed to `main` with **all** GitHub Actions checks green — lint (ruff), typecheck (mypy), security (bandit), tests (pytest ×6 packages + `website`), smoke, and the "CI green" aggregate — touching only files this plan names. Maintainer enables Pages (Source: GitHub Actions) **before merge**, or the post-merge deploy on `main` fails.

## Global Constraints

- Publishable artifact = `website/` minus `tests/` and `tools/`, staged by the workflow with `rsync --exclude tests/ --exclude tools/ website/ _site/`. `_site/` is CI-only; add `/_site` to `.gitignore`. Never commit `_site/`.
- **Paths:** all in-page refs relative (`assets/…`, `#anchor`); `rel=canonical`, `og:url`, `og:image`, `og:description` absolute to `https://alehar9320.github.io/agentic-odi/`. The 404 page is self-contained: zero `link`/`script`/`img` refs, absolute home link.
- **Root lint config (Task 1):** add to root `pyproject.toml` — `[tool.ruff] line-length = 100`, `target-version = "py310"`; `[tool.ruff.lint] select = ["E4", "E7", "E9", "F", "I", "UP", "B", "BLE"]` (mirrors `cli/pyproject.toml`). Verified: no root-level `.py` files exist besides the new `website/**`, so existing files keep their package configs. `ruff check .` / `ruff format --check .` (run in CI from root) now cover `website/**` — run both before every commit.
- **Dev deps:** root `[dependency-groups] dev` gains `pillow==12.3.0` (Task 1) and `pyyaml==6.0.3` (Task 4), each followed by `uv lock`; CI's `uv sync --all-packages --locked` must stay satisfiable. `website/**` stays **outside** mypy and bandit scopes — do not edit those CI commands.
- **Tests:** run from repo root as `uv run pytest website/tests -q`. No network in tests. Tests never write outside `tmp_path` — the committed PNGs are read-only; regenerate them only via `uv run python website/tools/make_og.py`.
- **Copy contract (enforced):** `Experimental`; `requires a free Prefect account`; `All rights reserved`; `as reported in ODI literature (Strategyn)`; `http://localhost:8000/mcp`; `http://localhost:8501`; quickstart verbatim from README (`uv sync --all-packages`, `python -m client.run`); headline `Your roadmap is a guess.`; opportunity formula exactly `Opportunity = Importance + max(Importance − Satisfaction, 0)`. No milestone dates (a © year is the only year allowed). No emoji. No `agentic-odi.fastmcp.app`, no Discord, no `mailto:`.
- **External link allowlist (closed set):** `https://github.com/alehar9320/agentic-odi`, `https://github.com/alehar9320/agentic-odi/issues`, `https://horizon.prefect.io/alhase/servers/agentic-odi/chat`, `https://docs.astral.sh/uv/`, `https://modelcontextprotocol.io`, canonical Pages URL.
- **Design system:** tokens per spec's color table (both schemes via `prefers-color-scheme`, all text pairs ≥ 4.5:1); system font stacks only — no webfonts; code blocks dark in both schemes. JS ≤ 100 non-blank lines, `defer`, progressive enhancement (content visible without JS), `prefers-reduced-motion` honored.
- Scope discipline: no changes to package source, no edits to `docs/` (this spec/plan excepted), README edited only in Task 5, no new workspace members.

## Review Focus

Uncovered inputs/conditions most likely to bite a user — each has a test in the task that owns the code:

1. **Dead anchors or base-path breakage** — relative refs + closed allowlist + resource-existence checks; site must work under the `/agentic-odi/` base. (Task 2)
2. **Committed PNG drifting from its generator** — pixel-identity test fails until the art is regenerated (regenerate with the pinned Pillow in the project venv; FreeType ships inside Pillow wheels, so output matches across platforms). (Task 1)
3. **Dev files published to Pages** — artifact staging excludes `tests/` + `tools/`; workflow contract test pins it. (Task 4)
4. **Honesty regressions** — no milestone dates, required strings, formula ↔ `core/models.py`, README ↔ page command drift. (Tasks 2, 5)
5. **JS-off / reduced-motion / scheme failures** — reveal must never hide content without JS; both schemes legible. (Task 3)
6. **Root lint newly covers `website/**`** — ruff check + format parity before every commit. (Tasks 1–5)
7. **Pages source not enabled before merge** — deploy job on `main` fails until the manual toggle; must be done pre-merge. (Task 6)

---

### Task 1: OG image generator + committed social art

**Files:**
- Modify: `pyproject.toml` (root dev deps + `[tool.ruff]`), `uv.lock`
- Create: `website/tools/make_og.py`, `website/assets/og.png`, `website/assets/favicon.png`
- Test: `website/tests/test_make_og.py`

**Interfaces:**
- Consumes: `pillow==12.3.0` (new root dev dep); design tokens from the spec (canvas `#0b0d13`, surface `#131722`, text `#f1f5f9`, muted `#94a3b8`, accent `#409cff`, badge fg `#cbd5e1`).
- Produces (importable via `importlib.util` from the tests; also runnable as `uv run python website/tools/make_og.py`):
  - `make_og.OG_SIZE = (1200, 630)`, `make_og.FAVICON_SIZE = (32, 32)`
  - `make_og.DEFAULT_HEADLINE = "Your roadmap is a guess."`, `DEFAULT_SUBHEAD = "Verified customer outcomes, jobs, and opportunity scores — served over MCP."`, `DEFAULT_URL = "alehar9320.github.io/agentic-odi"`
  - `make_og.render(headline: str = DEFAULT_HEADLINE, subhead: str = DEFAULT_SUBHEAD, url: str = DEFAULT_URL) -> bytes` — PNG bytes of the 1200×630 card: dark canvas, hairline rounded frame, mark (rounded-square + ascending two-step polyline + apex dot) with "Agentic ODI" wordmark top-left, "Experimental" pill top-right, headline wrapped ≤ 2 lines, subhead muted beneath, URL bottom-left. Font: `ImageFont.load_default(size=…)` (Pillow-embedded Aileron — no font file). No timestamps, fixed positions, `compress_level=9, optimize=True` → deterministic bytes.
  - `make_og.render_favicon() -> bytes` — 32×32 dark tile with the mark only.
  - `make_og.write(out_dir: Path) -> list[Path]` — writes `og.png` + `favicon.png`, returns their paths.
  - `make_og.main(argv: list[str] | None = None) -> int` — argparse with `--out DIR` (default: `Path(__file__).resolve().parents[1] / "assets"`), writes both files, returns 0; `raise SystemExit(main())` under `__main__`.
- Design-system consequence of this task: root `pyproject.toml` also gains the `[tool.ruff]` / `[tool.ruff.lint]` config from Global Constraints.

- [ ] **Step 1: Write the failing tests**

```python
# website/tests/test_make_og.py
import importlib.util
import io
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "website" / "tools"
ASSETS = ROOT / "website" / "assets"


def _load():
    spec = importlib.util.spec_from_file_location("make_og", TOOLS / "make_og.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _dims(png: bytes) -> tuple[int, int]:
    assert png[:8] == b"\x89PNG\r\n\x1a\n", "not a PNG"
    w, h = struct.unpack(">II", png[16:24])  # IHDR: 8 sig + 4 len + 4 type, then width/height
    return w, h


def test_render_is_deterministic_and_sized():
    m = _load()
    a = m.render()
    b = m.render()
    assert _dims(a) == (1200, 630)
    assert a == b


def test_favicon_is_sized():
    m = _load()
    assert _dims(m.render_favicon()) == (32, 32)


def test_cli_writes_both_files_to_out_dir(tmp_path):
    m = _load()
    assert m.main(["--out", str(tmp_path)]) == 0
    assert _dims((tmp_path / "og.png").read_bytes()) == (1200, 630)
    assert _dims((tmp_path / "favicon.png").read_bytes()) == (32, 32)


def test_committed_art_matches_generator():
    """Regenerate committed PNGs (uv run python website/tools/make_og.py) whenever the script changes."""
    from PIL import Image

    m = _load()
    fresh = Image.open(io.BytesIO(m.render()))
    committed = Image.open(ASSETS / "og.png")
    assert committed.format == "PNG"
    assert fresh.size == committed.size == (1200, 630)
    assert fresh.tobytes() == committed.tobytes()
    fresh_fav = Image.open(io.BytesIO(m.render_favicon()))
    committed_fav = Image.open(ASSETS / "favicon.png")
    assert fresh_fav.tobytes() == committed_fav.tobytes()


def test_committed_og_size_budget():
    assert (ASSETS / "og.png").stat().st_size < 300_000
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest website/tests/test_make_og.py -v`
Expected: FAIL (`website/tools/make_og.py` not found; committed PNGs absent).

- [ ] **Step 3: Add Pillow + root ruff config, implement the generator, generate the art**

1. Root `pyproject.toml`: append `pillow==12.3.0` to `[dependency-groups] dev`; add the `[tool.ruff]` / `[tool.ruff.lint]` blocks from Global Constraints. Run `uv lock` from the repo root.
2. Implement `website/tools/make_og.py` per Interfaces (module docstring, `from __future__ import annotations`, argparse, `IO[bytes]` via `io.BytesIO`, PIL draws: `rounded_rectangle` frame, polyline steps, ellipse apex dot, word-wrapped headline via `draw.textlength`). Keep lines ≤ 100 chars.
3. Generate art: `uv run python website/tools/make_og.py`
4. Lint the new Python the way CI will: `uv run ruff check website pyproject.toml` then `uv run ruff format website/` then parity `uv run ruff check . && uv run ruff format --check .`
   Expected: clean (root config applies to `website/**` only — re-verify no other file got reformatted via `git status`).

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest website/tests -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml uv.lock website/tools/make_og.py website/tests/test_make_og.py website/assets/og.png website/assets/favicon.png
git commit -m "feat(website): reproducible OG image generator with committed art"
```

---

### Task 2: Page structure, copy, and social meta

**Files:**
- Create: `website/index.html`, `website/404.html`, `website/assets/mark.svg`, `website/assets/favicon.svg`,
  `website/assets/style.css` (**base layer only**: custom-property tokens from the spec's color table, CSS reset, base typography, single-column flow, section spacing — Task 3 completes the design system)
- Test: `website/tests/test_site.py`

**Interfaces:**
- Consumes: `og.png` / `favicon.png` (Task 1); copy contract + section copy from the spec's *Messaging Hierarchy* (binding strings verbatim; micro-polish is builder latitude).
- Produces — `index.html` contract:
  - `<html lang="en">`; `charset=utf-8`; `name=viewport` (`width=device-width, initial-scale=1`); `title` = `Agentic ODI — Ground agents in verified customer outcomes` (≤ 60 chars); `name=description` ≤ 160 chars; `rel=canonical` = Pages URL.
  - Social: `og:type=website`, `og:site_name=Agentic ODI`, `og:title` (`Your roadmap is a guess. — Agentic ODI`), `og:description`, `og:url` (Pages URL), `og:image` (absolute `…/assets/og.png`); `twitter:card=summary_large_image`, `twitter:title`, `twitter:description`, `twitter:image` (absolute); two `theme-color` metas with `prefers-color-scheme: light|dark`.
  - Icons/head: `assets/favicon.svg` (`type=image/svg+xml`), `assets/favicon.png` (`sizes=32x32`), `assets/style.css`. **No script tag yet** (Task 3 adds it with `main.js`).
  - Body: sticky header (mark + wordmark, CTA → `#run`) → `main` with sections `#problem` (#opinion… title "Opinion is expensive." + 3 beats + closer), `#insight` (3 sentences + formula `Opportunity = Importance + max(Importance − Satisfaction, 0)` + bars figure labeled "Illustrative outcome data" + 86% callout with "as reported in ODI literature (Strategyn)"), `#how` (Capture/Query/Steer + Studio figure `role="img"` aria-labeled illustrative, marked "Illustrative"), `#run` (quickstart block, endpoint chips, MCP config snippet, hosted note), `#status` (Experimental badge, What works today / What's next curated from the README roadmap **re-read at build time**, "We don't publish dates…", "Questions? Open an issue.") → `footer` (tagline, GitHub/Issues/Hosted links, `© 2026 Agentic ODI maintainers · All rights reserved`). Exactly one `h1`: `Your roadmap is a guess.`; no skipped heading levels; decorative SVG `aria-hidden="true"`.
  - No emoji anywhere in `index.html`. Linked external URLs only from the allowlist; local refs only `assets/*` and `#*`.
- `404.html` contract: `lang="en"`, one `h1`, absolute link to the Pages URL, **zero** `link`/`script`/`img` tags (inline styles only).

- [ ] **Step 1: Write the failing tests**

```python
# website/tests/test_site.py
import re
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SITE = ROOT / "website"
PAGES_URL = "https://alehar9320.github.io/agentic-odi/"

ALLOWED_EXTERNAL = {
    "https://github.com/alehar9320/agentic-odi",
    "https://github.com/alehar9320/agentic-odi/issues",
    "https://horizon.prefect.io/alhase/servers/agentic-odi/chat",
    "https://docs.astral.sh/uv/",
    "https://modelcontextprotocol.io",
    PAGES_URL,
}

MILESTONE_DATE = re.compile(
    r"\b(Q[1-4]|Jan(uary)?|Feb(ruary)?|Mar(ch)?|Apr(il)?|May|Jun(e)?|"
    r"Jul(y)?|Aug(ust)?|Sep(t(ember)?)?|Oct(ober)?|Nov(ember)?|Dec(ember)?)[ -]20\d\d\b"
)
EMOJI = re.compile("[\u2600-\u27bf\U0001f300-\U0001faff]")


class Doc(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.lang = None
        self.charset = False
        self.viewport = False
        self.title = ""
        self.ids: set[str] = set()
        self.hrefs: list[str] = []
        self.refs: list[str] = []
        self.headings: list[tuple[int, str]] = []
        self.tags: list[str] = []
        self.metas: dict[str, str] = {}
        self.theme_colors: list[tuple[str, str]] = []
        self.text: list[str] = []
        self._in_title = False
        self._heading: tuple[int, list[str]] | None = None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        self.tags.append(tag)
        if tag == "html":
            self.lang = a.get("lang")
        elif tag == "title":
            self._in_title = True
        elif tag == "meta":
            if a.get("charset"):
                self.charset = True
            if a.get("name") == "viewport":
                self.viewport = True
            if a.get("name") == "theme-color":
                self.theme_colors.append((a.get("content", ""), a.get("media", "")))
            key = a.get("property") or a.get("name")
            if key:
                self.metas[key] = a.get("content", "")
        elif tag == "a" and a.get("href"):
            self.hrefs.append(a["href"])
        elif tag in ("link", "script", "img"):
            ref = a.get("href") or a.get("src")
            if ref:
                self.refs.append(ref)
        if a.get("id"):
            self.ids.add(a["id"])
        if re.fullmatch(r"h[1-6]", tag):
            self._heading = (int(tag[1]), [])

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False
        elif self._heading and tag == f"h{self._heading[0]}":
            level, parts = self._heading
            self.headings.append((level, " ".join("".join(parts).split())))
            self._heading = None

    def handle_data(self, data):
        self.text.append(data)
        if self._in_title:
            self.title += data
        if self._heading:
            self._heading[1].append(data)


def parse(name: str) -> Doc:
    doc = Doc()
    doc.feed((SITE / name).read_text(encoding="utf-8"))
    return doc


def test_lang_charset_viewport():
    doc = parse("index.html")
    assert doc.lang == "en"
    assert doc.charset
    assert doc.viewport


def test_title_and_description():
    doc = parse("index.html")
    assert "Agentic ODI" in doc.title
    assert len(doc.title.strip()) <= 60
    desc = doc.metas.get("description", "")
    assert 0 < len(desc) <= 160


def test_single_h1_and_ordered_headings():
    levels = [lv for lv, _ in parse("index.html").headings]
    assert levels.count(1) == 1
    assert levels[0] == 1
    for prev, cur in zip(levels, levels[1:]):
        assert cur <= prev + 1


def test_landmarks_and_section_ids():
    doc = parse("index.html")
    for landmark in ("header", "main", "footer"):
        assert landmark in doc.tags
    assert {"problem", "insight", "how", "run", "status"} <= doc.ids


def test_no_dead_internal_anchors():
    doc = parse("index.html")
    internal = [h[1:] for h in doc.hrefs if h.startswith("#")]
    assert internal, "expected in-page anchors"
    assert set(internal) <= doc.ids


def test_local_resources_exist_and_stylesheet_present():
    doc = parse("index.html")
    local = [r for r in doc.refs if not r.startswith(("http://", "https://"))]
    assert local
    for ref in local:
        assert (SITE / ref).is_file(), f"missing resource: {ref}"
    assert "assets/style.css" in local
    assert "assets/favicon.svg" in local
    assert "assets/favicon.png" in local


def test_no_third_party_resources():
    for ref in parse("index.html").refs:
        if ref.startswith(("http://", "https://")):
            assert ref in ALLOWED_EXTERNAL, f"off-allowlist resource: {ref}"
        else:
            assert ref.startswith("assets/"), f"unexpected resource: {ref}"


def test_external_links_https_and_allowlisted():
    for href in parse("index.html").hrefs:
        if href.startswith("#"):
            continue
        assert href.startswith("https://"), href
        assert href in ALLOWED_EXTERNAL, href


def test_social_cards_and_theme_colors():
    doc = parse("index.html")
    m = doc.metas
    assert m.get("og:type") == "website"
    assert m.get("og:site_name") == "Agentic ODI"
    assert m.get("og:title") and m.get("og:description")
    assert m.get("og:url") == PAGES_URL
    assert m.get("og:image") == PAGES_URL + "assets/og.png"
    assert m.get("twitter:card") == "summary_large_image"
    assert m.get("twitter:title") and m.get("twitter:description")
    assert m.get("twitter:image") == PAGES_URL + "assets/og.png"
    assert PAGES_URL in doc.refs  # rel=canonical
    media = [m_ for _, m_ in doc.theme_colors]
    assert len(doc.theme_colors) == 2
    assert any("prefers-color-scheme: light" in x for x in media)
    assert any("prefers-color-scheme: dark" in x for x in media)


def test_honesty_contract():
    text = (SITE / "index.html").read_text(encoding="utf-8")
    low = text.lower()
    assert "experimental" in low
    assert "free prefect account" in low
    assert "all rights reserved" in low
    assert "strategyn" in low
    assert "your roadmap is a guess." in low
    assert "we don't publish dates" in low
    assert "open an issue" in low
    assert "http://localhost:8000/mcp" in text
    assert "agentic-odi.fastmcp.app" not in text
    assert "discord" not in low
    assert "mailto:" not in low


def test_no_milestone_dates():
    text = (SITE / "index.html").read_text(encoding="utf-8")
    assert not MILESTONE_DATE.search(text), "no dated milestones on an experimental product"


def test_no_emoji_on_site():
    text = (SITE / "index.html").read_text(encoding="utf-8")
    assert not EMOJI.search(text)


def test_opportunity_formula_matches_core():
    core = (ROOT / "core" / "src" / "core" / "models.py").read_text(encoding="utf-8")
    assert "importance + max(importance - satisfaction, 0)" in core  # repo truth guard
    page = (SITE / "index.html").read_text(encoding="utf-8")
    normalized = page.lower().replace("\u2212", "-").replace(" ", "")
    assert "importance+max(importance-satisfaction,0)" in normalized


def test_404_is_self_contained():
    doc = parse("404.html")
    assert doc.lang == "en"
    assert any(lv == 1 for lv, _ in doc.headings)
    assert PAGES_URL in doc.hrefs
    assert not doc.refs, "404.html must not depend on relative assets"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest website/tests/test_site.py -v`
Expected: FAIL (no `index.html` / `404.html`).

- [ ] **Step 3: Build the page, the 404, the SVGs, and the base stylesheet**

1. Write `website/index.html` to the Interfaces contract and the spec's *Messaging Hierarchy* — every binding string verbatim; status lists curated from the README roadmap **as it reads right now**; opportunity figure and Studio figure as HTML/CSS compositions (`figure role="img"` with an aria-label; inner decoration `aria-hidden`); quickstart/endpoint/MCP snippets inside `<pre><code>` with copy-button `<button>` placeholders (wire-up comes in Task 3).
2. Write `website/404.html` self-contained (inline styles, absolute home link).
3. Hand-author `website/assets/mark.svg` and `website/assets/favicon.svg`: `viewBox="0 0 32 32"`, rounded-square + ascending two-step polyline + apex dot, no `<script>`.
4. Write the **base layer** of `website/assets/style.css`: `:root` light tokens and `prefers-color-scheme: dark` overrides exactly from the spec's color table, reset, system font stacks, base typography, single-column flow with the spec's max-widths/paddings, legible default focus styles. (Components, motion, responsive grids land in Task 3.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest website/tests -v`
Expected: PASS.

- [ ] **Step 5: Lint, then commit**

Run: `uv run ruff check . && uv run ruff format --check .`
Expected: clean.

```bash
git add website/index.html website/404.html website/assets/mark.svg website/assets/favicon.svg website/assets/style.css website/tests/test_site.py
git commit -m "feat(website): one-page structure, copy, and social meta tags"
```

---

### Task 3: Design system, dark mode, and progressive motion

**Files:**
- Modify: `website/assets/style.css` (complete it), `website/index.html` (add the deferred script tag)
- Create: `website/assets/main.js`
- Test: `website/tests/test_assets.py`

**Interfaces:**
- Consumes: base layer from Task 2; motion/token spec (curves, stagger, breakpoints, radii).
- Produces:
  - `style.css` completes: sticky header; hero with CSS-only staggered load animation; beats/steps two-column at `min-width: 720px`; insight bars; code blocks + chips + copy-button states; badges; status lists; footer; all component styling in both schemes; `@media (prefers-reduced-motion: reduce)` disabling transforms/reveals; `:focus-visible` rings ≥ 3:1 against adjacent colors.
  - `main.js` (≤ 100 non-blank lines, no imports/fetch): (1) reveal — default CSS shows content; JS adds a `data-reveal` opt-in only when `IntersectionObserver` exists, then reveals once at 15% visibility; (2) copy buttons — `navigator.clipboard.writeText` from the sibling `<code>`, label swaps to "Copied" for 1.5s, announced by a shared `aria-live="polite"` span. No network APIs, no external URLs.
  - `index.html` gains `<script defer src="assets/main.js"></script>`.

- [ ] **Step 1: Write the failing tests**

```python
# website/tests/test_assets.py
import re
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SITE = ROOT / "website"


def test_stylesheet_has_tokens_both_schemes_and_reduced_motion():
    css = (SITE / "assets" / "style.css").read_text(encoding="utf-8")
    assert ":root" in css
    assert "@media (prefers-color-scheme: dark)" in css
    assert "@media (prefers-reduced-motion: reduce)" in css
    low = css.lower()
    for token in ("#0b0d13", "#131722", "#f1f5f9", "#0071e3", "#409cff"):
        assert token in low, f"missing design token {token}"
    assert "@import" not in css
    assert not re.search(r"https?://", css), "CSS must load nothing off-origin"


def test_js_budget_and_progressive_enhancement():
    lines = [
        ln
        for ln in (SITE / "assets" / "main.js").read_text(encoding="utf-8").splitlines()
        if ln.strip()
    ]
    assert 0 < len(lines) <= 100
    src = "\n".join(lines)
    assert not re.search(r"https?://", src)
    assert "fetch(" not in src and "XMLHttpRequest" not in src
    html = (SITE / "index.html").read_text(encoding="utf-8")
    assert re.search(
        r'<script[^>]*defer[^>]*src="assets/main\.js"[^>]*>|<script[^>]*src="assets/main\.js"[^>]*defer[^>]*>',
        html,
    )


def test_svgs_well_formed_and_safe():
    for name in ("mark.svg", "favicon.svg"):
        root = ET.parse(SITE / "assets" / name).getroot()
        assert root.tag.endswith("svg")
        assert root.get("viewBox") == "0 0 32 32"
        assert not any(el.tag.endswith("script") for el in root.iter())
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest website/tests/test_assets.py -v`
Expected: FAIL (base CSS lacks media queries/tokens; no `main.js`).

- [ ] **Step 3: Implement the design system and the script**

Per Interfaces: complete `style.css` (components, both schemes, reduced-motion, focus-visible, ≥720px grids, no external URLs); write `main.js` (reveal opt-in + copy buttons + `aria-live`); add the deferred script tag to `index.html`. Behavior requirement: with JS disabled every section is fully visible; with `prefers-reduced-motion: reduce` there are no transforms or staggered animations.

- [ ] **Step 4: Run the whole site suite**

Run: `uv run pytest website/tests -v`
Expected: ALL PASS (including Task 1–2 tests).

- [ ] **Step 5: Lint, then commit**

Run: `uv run ruff check . && uv run ruff format --check .`
Expected: clean.

```bash
git add website/assets/style.css website/assets/main.js website/index.html website/tests/test_assets.py
git commit -m "feat(website): design system, dark mode, and progressive motion"
```

---

### Task 4: Deploy pipeline (Pages workflow + CI website job)

**Files:**
- Create: `.github/workflows/pages.yml`
- Modify: `.github/workflows/ci.yml`, `pyproject.toml` (dev += `pyyaml==6.0.3`), `uv.lock`, `.gitignore` (add `/_site`)
- Test: `website/tests/test_workflows.py`

**Interfaces:**
- Consumes: `website/tests` (the deploy gate), composite `./.github/actions/setup`.
- Produces — `pages.yml`:
  - `on`: `push` with `branches: [main]`, `paths: ["website/**", ".github/workflows/pages.yml"]`, plus `workflow_dispatch`.
  - Workflow-level `permissions: {contents: read, pages: write, id-token: write}`; `concurrency: {group: pages, cancel-in-progress: false}`.
  - One job `deploy`: `runs-on: ubuntu-latest`, `environment: {name: github-pages}`, steps in order —
    `actions/checkout@v7` → `./.github/actions/setup` → run `uv run pytest website/tests -q` →
    `actions/configure-pages@v6` → stage: `mkdir -p _site && rsync -a --exclude tests/ --exclude tools/ website/ _site/` →
    `actions/upload-pages-artifact@v5` with `with: {path: _site}` → `actions/deploy-pages@v5` (`id: deployment`).
- Produces — `ci.yml` edits: new job `website` (checkout → setup → `uv run pytest website/tests -q`, `timeout-minutes: 10`), placed after `smoke`; `"website"` appended to `ci-green`'s `needs`.
- PyYAML note for the test: YAML 1.1 parses the bare key `on:` as boolean `True` — read it with `wf.get("on") or wf.get(True)`.

- [ ] **Step 1: Write the failing tests**

```python
# website/tests/test_workflows.py
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
WF = ROOT / ".github" / "workflows"


def _load(name: str) -> dict:
    return yaml.safe_load((WF / name).read_text(encoding="utf-8"))


def _on(wf: dict):
    return wf.get("on") or wf.get(True)  # PyYAML parses `on:` as boolean True (YAML 1.1)


def test_pages_workflow_triggers_only_for_main_website_paths():
    on = _on(_load("pages.yml"))
    assert on["push"]["branches"] == ["main"]
    assert "website/**" in on["push"]["paths"]
    assert ".github/workflows/pages.yml" in on["push"]["paths"]
    assert "workflow_dispatch" in on


def test_pages_deploy_verifies_before_publishing():
    wf = _load("pages.yml")
    assert wf["permissions"]["pages"] == "write"
    assert wf["permissions"]["id-token"] == "write"
    job = wf["jobs"]["deploy"]
    assert job["environment"]["name"] == "github-pages"
    runs = [str(s.get("run", "")) for s in job["steps"]]
    uses = [str(s.get("uses", "")) for s in job["steps"]]
    assert any("pytest website/tests" in r for r in runs), "gate deploy on site tests"
    assert any(
        "rsync" in r and "--exclude tests/" in r and "--exclude tools/" in r for r in runs
    ), "artifact must exclude dev files"
    upload = next(s for s in job["steps"] if "upload-pages-artifact@v5" in str(s.get("uses", "")))
    assert upload["with"]["path"] == "_site"
    assert any("deploy-pages@v5" in u for u in uses)
    assert any("./.github/actions/setup" in u for u in uses)


def test_ci_runs_website_job_and_aggregate_needs_it():
    ci = _load("ci.yml")
    assert "website" in ci["jobs"], "site tests must run on every PR"
    assert "website" in ci["jobs"]["ci-green"]["needs"]
    runs = [str(s.get("run", "")) for s in ci["jobs"]["website"]["steps"]]
    assert any("pytest website/tests" in r for r in runs)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest website/tests/test_workflows.py -v`
Expected: FAIL (`pages.yml` missing; `website` job absent from `ci.yml`).

- [ ] **Step 3: Declare PyYAML, write the workflows, gitignore `_site`**

1. Root `pyproject.toml`: append `pyyaml==6.0.3` to `[dependency-groups] dev`; run `uv lock`.
2. Write `.github/workflows/pages.yml` per Interfaces (structure above; step names human-readable).
3. Edit `.github/workflows/ci.yml`: add the `website` job after `smoke`; append `"website"` to `ci-green` `needs`. Do not touch other jobs or the existing `ci-green` logic.
4. Add `/_site` to `.gitignore`.

- [ ] **Step 4: Run tests to verify they pass, then the whole suite**

Run: `uv run pytest website/tests -v`
Expected: ALL PASS.

- [ ] **Step 5: Lint, then commit**

Run: `uv run ruff check . && uv run ruff format --check .`
Expected: clean.

```bash
git add .github/workflows/pages.yml .github/workflows/ci.yml pyproject.toml uv.lock .gitignore website/tests/test_workflows.py
git commit -m "ci: add Pages deploy workflow and website test job"
```

---

### Task 5: README Website section + README↔page sync test

**Files:**
- Modify: `README.md` (one new section + one TOC entry)
- Test: `website/tests/test_readme_sync.py`

**Interfaces:**
- Consumes: the live site URL, preview/test commands.
- Produces:
  - README gains `- [Website](#-website)` in the TOC (immediately after the Deployment entry) and a `## 🌐 Website` section immediately after `## ☁️ Deployment`, containing: the live URL `https://alehar9320.github.io/agentic-odi/`; source location (`website/`, one page, no build step); local preview `python3 -m http.server 8080 --directory website`; site checks `uv run pytest website/tests`; one line noting the site carries the same experimental framing and links Issues for questions.
  - Sync tests pin the README↔page contract (README stays source of truth for commands/URLs).

- [ ] **Step 1: Write the failing tests**

```python
# website/tests/test_readme_sync.py
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PAGES_URL = "https://alehar9320.github.io/agentic-odi/"


def _pair() -> tuple[str, str]:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    page = (ROOT / "website" / "index.html").read_text(encoding="utf-8")
    return readme, page


def test_quickstart_commands_stay_in_sync():
    readme, page = _pair()
    for cmd in ("uv sync --all-packages", "python -m client.run"):
        assert cmd in readme, f"README lost {cmd}"
        assert cmd in page, f"page lost {cmd}"


def test_local_endpoints_stay_in_sync():
    readme, page = _pair()
    for url in ("http://localhost:8000/mcp", "http://localhost:8501"):
        assert url in readme and url in page, url


def test_hosted_entry_stays_in_sync():
    readme, page = _pair()
    url = "https://horizon.prefect.io/alhase/servers/agentic-odi/chat"
    assert url in readme and url in page


def test_readme_links_the_live_site():
    readme, _ = _pair()
    assert PAGES_URL in readme
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest website/tests/test_readme_sync.py -v`
Expected: FAIL (`README.md` does not mention the Pages URL yet).

- [ ] **Step 3: Add the README Website section and TOC entry**

Per Interfaces (place section after Deployment; keep README's existing emoji/heading style).

- [ ] **Step 4: Run tests to verify they pass, then the whole suite**

Run: `uv run pytest website/tests -v`
Expected: ALL PASS.

- [ ] **Step 5: Lint, then commit**

Run: `uv run ruff check . && uv run ruff format --check .`
Expected: clean.

```bash
git add README.md website/tests/test_readme_sync.py
git commit -m "docs: link the GitHub Pages site from README"
```

---

### Task 6: Final verification and PR

**Files:**
- Modify: none planned (commit only fixes surfaced below, conventional messages, e.g. `fix(website): …`)

**Interfaces:**
- Consumes: Tasks 1–5 output.
- Produces: a PR to `main` with all GitHub Actions checks green; the Pages-source toggle done before merge.

- [ ] **Step 1: Full local CI parity**

Run, exactly as CI does (from repo root):

```bash
uv run ruff check . && uv run ruff format --check .
uv run --directory core mypy . && uv run --directory mcp_server mypy . && uv run --directory local_server mypy . && uv run --directory cli mypy . && uv run --directory client mypy . && uv run --directory connectors mypy .
uv run bandit -c pyproject.toml -r core/src mcp_server/src local_server/src cli/src client/src connectors/src
uv run --directory core pytest && uv run --directory mcp_server pytest && uv run --directory local_server pytest && uv run --directory cli pytest && uv run --directory client pytest && uv run --directory connectors pytest
uv run pytest website/tests -v
```

Expected: ALL GREEN (any fix → commit first, re-run).

- [ ] **Step 2: Local preview + manual checklist**

Run: `python3 -m http.server 8080 --directory website`, open `http://localhost:8080/` (and `/404.html` directly — `http.server` serves its own 404).
Check: 360px and 1280px widths, no horizontal scroll; light and dark scheme both legible; every section visible with JS disabled; `prefers-reduced-motion: reduce` removes motion; keyboard reaches header CTA, all links, both copy buttons (visible focus ring); copy button shows "Copied"; all five anchors scroll to their sections; header CTA scrolls to `#run`. If a Chrome/Chromium is available, run Lighthouse mobile — expect ≥ 95 on all four categories; otherwise note "Lighthouse deferred (no browser)" in the PR description.

- [ ] **Step 3: Pre-merge Pages toggle (manual gate — do before opening/updating the PR)**

The maintainer sets repository **Settings → Pages → Source: GitHub Actions** (API alternative:
`gh api -X POST /repos/alehar9320/agentic-odi/pages -f source=workflow`). Without this, the deploy
job fails on `main` immediately after merge. The PR itself stays green either way — `pages.yml` has
no `pull_request` trigger.

- [ ] **Step 4: Push and confirm all checks green**

Push the branch, open the PR to `main`, and confirm every check is green: **lint**, **typecheck**,
**security**, **test**, **smoke**, **website**, and the **CI green** aggregate. Confirm the PR
diff touches only files this plan names (no package code, no stray docs).

- [ ] **Step 5: Post-merge spot check (not PR-blocking)**

After merge + successful Pages deploy: `curl -sI https://alehar9320.github.io/agentic-odi/` → 200;
`curl -sI https://alehar9320.github.io/agentic-odi/assets/og.png` → 200; run any social-preview
debugger (X/LinkedIn) once to confirm the card renders. If the deploy job failed only because the
Pages source was not enabled, toggle it and re-run the workflow (`workflow_dispatch`).
