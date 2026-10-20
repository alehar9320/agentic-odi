# GitHub Pages Marketing Site Design

**Date:** 2026-10-18
**Status:** Approved (design authority delegated to the session designer; all builder-check questions answered)
**Scope:** Single-page customer-facing site in `website/` + GitHub Actions deploy to GitHub Pages

## Intent & Why

`README.md` is the project's front door, and it reads like an engineering changelog — right for
contributors, wrong for the PM or eng lead who clicked a shared link asking "is this real, and is it
worth five minutes?" The site answers why/what/how/when in one scroll, with a Jobsian bar:
ruthless focus, one narrative, one obvious action, craft in type and motion, and honesty as the
brand — the project is an experimental testbed, and the page says so out loud.

The Jobsian constraint that shapes everything: **over-promising on an experimental product is the
one thing Jobs never did — the honest answer is the Jobsian answer.** No dates, no maturity theater,
no CTAs that dead-end behind auth, no screenshots of vaporware.

Definition of done for the build (see plan): PR pushed with all GitHub Actions checks green —
lint (ruff), typecheck (mypy), security (bandit), tests (pytest ×6 packages + `website`), smoke,
and the "CI green" aggregate.

## Audience & Jobs-to-be-Done

**Primary — product managers / innovation leads.** Landing cold from a shared link, a search, or a
referral. Skeptical of AI-tool marketing.
> When I open this page from a link in Slack, I want to know within one screen whether this is a
> real, runnable thing grounded in a method I respect, so I can decide to spend five minutes on it
> or leave without guilt.

**Secondary — AI/agent developers.** Evaluating whether to wire agents to an ODI data source.
> When I'm deciding what context to give my agents, I want the exact endpoint and a copy-paste
> quickstart that works locally, so I can try it without talking to anyone.

**Tertiary — the sharing PM (internal champion).** Forwarding the link to a team or a boss.
> When I forward this page, I want it to frame the thesis — evidence over opinion — credibly and
> soberly, so the conversation starts from the idea instead of from my credibility.

## Messaging Hierarchy

Binding copy contract (tests enforce the marked strings; micro-polish — punctuation-level tweaks —
is builder latitude).

| Level | Copy |
|---|---|
| Eyebrow pill | `Experimental` |
| H1 (hero) | **Your roadmap is a guess.** |
| Hero sub | An MCP server that hands your agents verified customer outcomes — and the evidence behind them. |
| Primary CTA | **Run it in 60 seconds** → `#run` (local quickstart) |
| Secondary CTA | View on GitHub → `https://github.com/alehar9320/agentic-odi` |
| Tertiary link | Hosted demo — requires a free Prefect account → Horizon chat URL |
| Footer tagline | Built with outcomes, not guesses. |

**Section 2 — `#problem`, "Opinion is expensive."** Three parallel beats, one line each, each with
a short support line:

1. "Roadmaps set by whoever talks loudest." — Decisions default to seniority, not evidence.
2. "Features for customers who never asked." — Nobody validated the outcome; only the idea.
3. "Agents fluent in everything, grounded in nothing." — A model will confidently invent your customer.

Section closer: "Add it up and the roadmap isn't a plan. It's a guess."

**Section 3 — `#insight`, "Ask for outcomes, not opinions."** Three plain sentences:
1. Outcome-Driven Innovation asks customers how much each desired outcome matters and how satisfied
   they are with it today.
2. The gap between importance and satisfaction is where products win or die.
3. Agentic ODI stores those outcomes, scores them, and serves them to any agent over MCP.

Then: a small CSS/inline-SVG bar visual (Importance vs Satisfaction, gap highlighted, labeled
"Illustrative outcome data"), the formula rendered exactly as the code computes it —
`Opportunity = Importance + max(Importance − Satisfaction, 0)` (source of truth:
`core/src/core/models.py:27`), and the stat callout: **86%** innovation success rate — *as reported
in ODI literature (Strategyn)*. Plain-text attribution only; no link to the in-repo PDF.

**Section 4 — `#how`, "How it works."** Three steps:
1. **Capture** — jobs, steps, and desired outcomes with importance/satisfaction scores, via CLI,
   connectors, or The Living Studio.
2. **Query** — agents call MCP tools for job maps and opportunity scores at decision time, local or
   hosted.
3. **Steer** — The Living Studio shows the Opportunity Landscape, Universal Job Map, and Impact
   Simulation so the team decides from the same picture.

Accompanies: a stylized Studio illustration (real shipped surfaces, marked "Illustrative"), never a
fake screenshot.

**Section 5 — `#run`, "Run it in 60 seconds."** Prerequisites line (Python 3.10+, uv), terminal
block with copy button:

```bash
git clone https://github.com/alehar9320/agentic-odi.git
cd agentic-odi
uv sync --all-packages
python -m client.run
```

Endpoint chips with copy buttons: MCP `http://localhost:8000/mcp` · Studio `http://localhost:8501`.
MCP client config snippet (local only):

```json
{
  "mcpServers": {
    "agentic-odi": { "url": "http://localhost:8000/mcp" }
  }
}
```

Prose note: hosted credentials come from the maintainers — open an issue. Never invent an auth
scheme we cannot document.

**Section 6 — `#status`, "Honest status."** `Experimental` badge; **What works today** (MCP server
tools for jobs/steps/outcomes/customer outcomes with opportunity scoring; The Living Studio —
Opportunity Landscape, Universal Job Map, Impact Simulation, Causal Lineage; CLI `outcomes` +
`connectors`; MCP ingest connector; hosted test endpoints requiring auth) and **What's next**
(curated from the README roadmap at build time: map ingested evidence onto ODI artifacts, more
connector kinds, ODI schema definition, context tooling, persistence layer, agentic integration).
Standing line: "We don't publish dates. This page changes when the code does." Closer: "Questions?
Open an issue." → Issues link.

**Footer.** Mark + wordmark, tagline, links (GitHub, Issues, Hosted demo), legal line:
`© 2026 Agentic ODI maintainers · All rights reserved` + one-line experimental reminder.

**Voice rules:** warm, direct, second person; plain language; no jargon dumps; **no emoji anywhere
on the site** (house copy rule from the first-run onboarding spec — README's emoji style stays in
README); no superlatives ("revolutionary", "seamless", "enterprise-grade"); English only.

## Information Architecture / Sitemap

| Route | File | Notes |
|---|---|---|
| `/` | `website/index.html` | The entire site. One scroll, seven sections. |
| `/404.html` | `website/404.html` | On-brand, **self-contained** (inline styles, absolute link home) so it renders at any depth on project Pages. |

- Sticky compact header: mark + wordmark (left), single CTA "Run it in 60 seconds" (right). No nav
  links — one page needs no navigation, but the one obvious action must stay reachable.
- In-page anchors: `#problem`, `#insight`, `#how`, `#run`, `#status`.
- No sitemap.xml, no robots.txt, no blog, no docs pages, no search.

## Visual Direction

**Type.** No webfonts, zero downloads:
- `--font-sans: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif`
  (same stack The Living Studio ships, `client/src/client/app.py:36`)
- `--font-mono: ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, monospace`

| Role | Size | Weight / tracking |
|---|---|---|
| H1 | `clamp(2.75rem, 6.5vw, 4.75rem)` | 700, `-0.02em`, lh 1.05 |
| H2 | `clamp(1.75rem, 3.2vw, 2.5rem)` | 700, `-0.015em`, lh 1.15 |
| H3 / beats | `1.25rem` | 600, lh 1.3 |
| Body / lead | `1.0625rem` (17px) / `1.1875rem` | 400, lh 1.6 |
| Eyebrow, badges | `0.75rem` | 600, `0.08em`, uppercase |
| Code | `0.9375rem` mono | lh 1.55 |

**Color.** Tokens as CSS custom properties; `:root` = light, `@media (prefers-color-scheme: dark)`
overrides. Palette echoes the shipped Studio dark-glass theme (`#0B0D13` / `#131722` / `#F1F5F9`
straight from `app.py`). All ratios measured, WCAG 2.1 AA (text ≥ 4.5:1):

| Token | Light | Dark | Contrast (light / dark) |
|---|---|---|---|
| `--bg` | `#ffffff` | `#0b0d13` | — |
| `--surface` | `#f5f5f7` | `#131722` | — |
| `--text` | `#1d1d1f` | `#f1f5f9` | 16.8 on bg / 17.7 on bg |
| `--muted` | `#6e6e73` | `#94a3b8` | 5.07 bg, 4.66 surface / 7.58 bg, 6.98 surface |
| `--accent` (button fill, white label) | `#0071e3` | `#0071e3` | white on it: 4.70 (both) |
| `--accent-text` (link text) | `#0062c4` | `#409cff` | 5.93 bg, 5.44 surface / 6.86 bg, 6.32 surface |
| `--accent-hover` | `#0059b8` | `#0059b8` | white on it: 6.73 |
| `--badge` (fg on bg) | `#475569` on `#e2e8f0` | `#cbd5e1` on `#1e293b` | 6.15 / 9.85 |
| `--border` | `rgba(0,0,0,.08)` | `rgba(148,163,184,.16)` | decorative only |

Code blocks are dark (`#0b0d13`) in both schemes — a terminal is a terminal (17.7:1 either way).
OG card is fixed dark, self-contained.

**Layout & spacing.** Mobile-first; content max-width 1080px, prose max-width 68ch; inline padding
`clamp(20px, 5vw, 40px)`; section padding-block `clamp(72px, 12vw, 140px)`; 8px spacing scale as
custom properties; radius 12px cards / 999px pills (echoing the Studio's own radii); 1px hairline
borders. Beats and steps go two-column at ≥720px.

**Motion.** Restrained, explanatory, never load-bearing:
- Hero stagger on load: eyebrow → H1 → sub → CTAs, 12px fade-up, 60ms stagger, 400ms,
  `cubic-bezier(.22,1,.36,1)` — pure CSS, no JS.
- Scroll reveal: sections fade-up once when 15% visible (IntersectionObserver). Default state is
  **visible**; JS opts content into the hidden-then-reveal state only after it loads, so no-JS
  readers never see hidden content.
- Buttons: 150ms `background-color`/`transform`, hover `translateY(-1px)`, active `scale(.98)`.
- Copy button swaps its label to "Copied" for 1.5s, announced via an `aria-live="polite"` span.
- `@media (prefers-reduced-motion: reduce)`: all transforms/stagger removed, reveals off, content
  immediate.

**Imagery & assets (none exist in the repo — all created):**
- **Mark** (`mark.svg`, hand-authored, viewBox `0 0 32 32`): rounded-square canvas with an
  ascending two-step polyline and a filled dot at the apex — the opportunity curve breaking
  upward. Accent stroke `#0071e3`, hairline frame. Works at 16px, single color-safe.
- **Favicon:** `favicon.svg` (same geometry) + `favicon.png` 32×32 (generated, dark tile, for
  browsers that ignore SVG icons).
- **Opportunity visual:** pure CSS/inline SVG bars in `#insight`, `aria`-labeled, marked
  "Illustrative outcome data".
- **Studio illustration:** stylized abstraction of shipped surfaces only (Opportunity Landscape,
  Universal Job Map, Impact Simulation — verified in `client/src/client/app.py:683-838`), marked
  "Illustrative". Depicting vaporware on a page whose thesis is "no guesses" would self-destruct.
- All decorative SVGs `aria-hidden="true"`; no stock photos, no icon fonts, no emoji.

## Content Sources

| Content | Source | Enforcement |
|---|---|---|
| Quickstart commands (`uv sync --all-packages`, `python -m client.run`) | README §Getting Started — **verbatim** | `test_readme_sync.py` |
| Local endpoints (`http://localhost:8000/mcp`, `http://localhost:8501`) | README One-Command Launch — **verbatim** | `test_readme_sync.py` |
| Hosted chat URL | README §Deployment — **verbatim**; the label "requires a free Prefect account" is fresh | `test_readme_sync.py` + allowlist |
| Experimental framing, maturity claims | README banner — adapted, no new claims | review + honesty tests |
| What works today / What's next | README roadmap checkboxes, curated at build time (re-read README in Task 2 of the plan) | review focus |
| License/legal line | README §License — adapted ("All rights reserved") | honesty test |
| 86% stat + "as reported in ODI literature (Strategyn)" | Session decision (no link to `knowledge/*.pdf`) | honesty test |
| Opportunity formula | `core/src/core/models.py:27-29` | formula test |
| Headline, subhead, beats, section titles, CTA labels, tagline, OG copy | **Written fresh** — binding in this spec | structural tests |
| Mark, favicon, illustrations, OG art | Created per this spec | asset tests |

Rule: README is the source of truth for every command, URL, and status claim. If the page and
README disagree, the page is wrong.

## Technical Approach

Hand-crafted static HTML + one CSS file + ≤100 lines of vanilla JS. **No framework** (no
Astro/Next/React): one page with no routing, no state, no data, no components shared across
views — a framework buys a toolchain, a lockfile, hydration, and an upgrade treadmill, and charges
rent on every one of them. Consequence of no framework: deploy is "copy files", the review diff is
readable HTML, Lighthouse is high by construction, and there is zero supply chain on the page.

```
website/
  index.html            # the site
  404.html              # self-contained fallback
  assets/
    style.css           # tokens + full design system (no external URLs)
    main.js             # ≤100 lines: reveal + copy buttons, defer, progressive enhancement
    mark.svg  favicon.svg
    og.png    favicon.png   # committed, generated (see OG strategy)
  tools/
    make_og.py          # regenerates og.png + favicon.png (Pillow, pinned)
  tests/
    test_site.py  test_assets.py  test_make_og.py
    test_workflows.py  test_readme_sync.py
```

- **Paths:** every in-page URL is **relative** (`assets/…`, `#anchor`) so the site works under the
  project-Pages base `/agentic-odi/`, on a local static server, and on any future custom domain.
  `og:url` / `og:image` / `rel=canonical` are **absolute**.
- Local preview: `python3 -m http.server 8080 --directory website` (preview the 404 by opening
  `/404.html` directly — `http.server` serves its own 404).
- JS is `defer`'d and additive: the page is complete, styled, and readable with JS disabled.
- Python tooling lives only in `tools/` + `tests/`, run from the repo root with the workspace venv.

## OG / Social Strategy

Social previews are the main earned-distribution artifact — one committed raster, no mystery binary.

- `website/assets/og.png`: **1200×630**, fixed dark card — mark + "Agentic ODI" wordmark,
  headline "Your roadmap is a guess.", sub "Verified customer outcomes, jobs, and opportunity
  scores — served over MCP.", bottom row `alehar9320.github.io/agentic-odi` + Experimental badge.
- `website/tools/make_og.py`: the committed, runnable generator (stdlib argparse + Pillow). Writes
  `og.png` and `favicon.png`; defaults embed the canonical card copy above. Deterministic output —
  fixed palette/positions, no timestamps, `compress_level=9`, font via
  `ImageFont.load_default(size=…)` (Pillow's embedded Aileron, SIL OFL — no font file in the repo).
  Run: `uv run python website/tools/make_og.py`.
- **Regenerability is enforced:** `test_make_og.py` renders fresh bytes and asserts they are
  pixel-identical to the committed PNGs. Change the script → the test fails until you regenerate.
  Change the card copy → defaults in the script are the source.
- Meta contract on `index.html`: `og:type=website`, `og:site_name`, `og:title`
  ("Your roadmap is a guess. — Agentic ODI"), `og:description`, `og:url` (canonical Pages URL),
  `og:image` (absolute PNG URL), `twitter:card=summary_large_image` + title/description/image,
  `rel=canonical`, `theme-color` per color scheme, both favicons. Title tag ≤ 60 chars:
  `Agentic ODI — Ground agents in verified customer outcomes`.
- og:image is never loaded by the page itself (page weight unaffected).
- No OpenGraph on SVG: scrapers (X, LinkedIn, Slack, iMessage) need raster — hence exactly one PNG.

## Deploy Pipeline

**`.github/workflows/pages.yml`** (deploy only — its contract is tested in `ci.yml` via
`test_workflows.py`, so PRs validate it without triggering a deploy):

- `on: push branches [main] paths [website/**, .github/workflows/pages.yml]`, plus
  `workflow_dispatch`.
- Workflow permissions: `contents: read`, `pages: write`, `id-token: write`. Concurrency:
  `group: pages`, `cancel-in-progress: false`. Environment: `github-pages` (URL from the
  deployment step).
- Job `deploy`, steps: checkout@v7 → `./.github/actions/setup` → **run
  `uv run pytest website/tests -q` (verify before publish)** → `actions/configure-pages@v6` →
  stage the artifact with
  `mkdir -p _site && rsync -a --exclude tests/ --exclude tools/ website/ _site/` →
  `actions/upload-pages-artifact@v5` (`path: _site`) → `actions/deploy-pages@v5`.
  Only the site publishes — tests and generator never do; `_site/` is CI-only and gitignored.
- **Manual gate:** repository Settings → Pages → Source = "GitHub Actions" must be set **before
  this workflow first runs on `main`**, or the deploy job fails. (One-time toggle; flag before
  merge.)

**`.github/workflows/ci.yml`**: add a `website` job (setup + `uv run pytest website/tests -q`,
timeout 10m) and add `website` to `ci-green`'s `needs`. Root `ruff check .` / `ruff format --check .`
already cover `website/**` once root ruff config exists (below).

## Accessibility & Performance Budget

**Accessibility (WCAG 2.1 AA):**
- Semantic landmarks (`header`/`main`/`footer`), one `h1`, no skipped heading levels, `lang="en"`.
- Contrast: measured pairs in the color table — every text pair ≥ 4.5:1 in both schemes.
- Full keyboard operability; visible focus ring (≥ 3:1 against adjacent colors); copy controls are
  real `<button>`s with accessible names; `aria-live` for "Copied".
- Decorative SVG `aria-hidden="true"`; meaningful links (no "click here"); `prefers-reduced-motion`
  respected; viewport meta; tested at 360px width with no horizontal scroll.

**Performance:**
- Zero third-party requests, zero webfonts, zero analytics, zero cookies — the page talks only to
  its own origin.
- Weights (raw, committed): HTML ≤ 60 KB, CSS ≤ 30 KB, JS ≤ 4 KB (≤ 100 non-blank lines), each SVG
  ≤ 10 KB, `favicon.png` ≤ 5 KB, total transferred ≤ 150 KB; `og.png` ≤ 300 KB (test-enforced;
  expected ~15–40 KB).
- Lighthouse ≥ 95 on Performance / Accessibility / Best Practices / SEO (mobile emulation,
  manual run before merge — CI has no browser).

## Non-Goals / Anti-Goals

- **Not a docs site, not a blog.** No MkDocs/Docusaurus, no nav maze, no search, no sitemap.
- **No framework, no build step, no dependencies on the deployed artifact.**
- **No claims the repo can't back:** no dates or milestones; no "open source" or license claim
  (repo is all-rights-reserved); no maturity language beyond the Experimental framing; no invented
  testimonials, logos, customer counts, or benchmark numbers; no emoji.
- **No dead ends:** no CTAs behind auth (hosted is tertiary, labeled); no personal emails, no
  invented Discord/Slack; access channel = GitHub Issues only.
- **No auth fiction:** local MCP config only; never link the 401 `agentic-odi.fastmcp.app`
  endpoint as something a visitor can try; no invented header/token scheme.
- **No vaporware imagery:** Studio illustration is abstraction-of-shipped-surfaces, labeled
  "Illustrative"; no fake screenshots.
- **No hotlinking `knowledge/Strategyn_*.pdf`** — attribution text only.
- **No analytics/cookies/CDN/fonts/i18n** — scope is English, one page, two schemes.
- **No publishing dev files:** `website/tests/` and `website/tools/` never reach the Pages artifact.

## Risks & Mitigations

1. **Pages not enabled before first merge** → deploy job red on `main`. Mitigation: manual toggle
   flagged as a pre-merge gate in the plan's final task.
2. **README drift** (commands/URLs change, page rots) → `test_readme_sync.py` fails CI.
3. **Committed PNG drifts from generator** → pixel-identity test fails CI until regeneration.
4. **Scope creep** (nav items, extra pages, webfonts) → anti-goals + structural tests (allowlisted
   links, weight budgets) push back mechanically.
5. **Ruff newly covers `website/**`** → root config added at repo-consistent line length; commit
   steps run root lint/format parity before every commit.

## Resolved Questions (builder-check × session — all settled)

1. **Primary CTA** → local quickstart ("Run it in 60 seconds"). Verified live: Horizon chat 302s
   to `auth.horizon.prefect.io`, hosted MCP returns 401 — a hero CTA that dead-ends anonymous
   visitors in auth is malpractice. Hosted is tertiary, labeled "requires a free Prefect account."
2. **Access channel** → GitHub Issues (footer + status section). No personal email, no invented
   Discord.
3. **MCP snippet** → local config only (`http://localhost:8000/mcp`); hosted credentials are
   requested via issues. Never document an auth scheme we don't have.
4. **OG image** → one committed PNG, regenerated by committed `website/tools/make_og.py`
   (deterministic, tested pixel-identical). SVG-only cards render poorly on X/LinkedIn/iMessage.
5. **"When"** → no dates. "What works today / What's next" under an explicit Experimental badge,
   mirroring the README roadmap.
6. **Living Studio visual** → stylized abstraction grounded in real shipped surfaces, labeled
   "Illustrative" — never a fake screenshot.
7. **86% stat** → plain-text attribution "as reported in ODI literature (Strategyn)"; no link to
   the copyrighted in-repo PDF.

## Builder Calls (design authority — beyond the session's settled six)

1. **Formula corrected to repo truth:** the session sketch showed `Opportunity = Importance −
   Satisfaction`; the code computes `importance + max(importance − satisfaction, 0)`
   (`core/src/core/models.py:28`). The page shows the real formula, and a test pins page ↔ code.
2. **OG renderer = Pillow, pinned in root dev deps** (`pillow==12.3.0`, `uv.lock` updated):
   `ImageFont.load_default(size=…)` ships the Aileron font inside Pillow — real typography, no font
   binary, deterministic bytes, zero deploy-time dependency (Pillow never ships to Pages).
   Generator also emits `favicon.png`.
3. **Full color/type/motion system specified with measured contrast ratios** (table above); palette
   lifted from the shipped Studio theme for brand continuity.
4. **Sticky compact header** (wordmark + one CTA), no nav links.
5. **`404.html` included, self-contained** — absolute home link + inline styles, because relative
   assets break when Pages serves 404.html at arbitrary depths under the `/agentic-odi/` base.
6. **Relative assets + absolute canonical/OG URLs** — required by GitHub project-Pages base path.
7. **Test/CI architecture:** `website/tests/` run by a new `website` job in `ci.yml` (added to
   `ci-green` needs) *and* as a verify-before-publish step inside the Pages deploy job; workflow
   YAML itself is contract-tested with PyYAML (`pyyaml==6.0.3` declared in root dev deps).
8. **Artifact staging** via `rsync --exclude tests/ --exclude tools/` → `_site/` (CI-only,
   gitignored): the published site is the site, nothing else.
9. **Root `[tool.ruff]` added** (line-length 100, target py310, select `E4,E7,E9,F,I,UP,B,BLE`,
   mirroring `cli/pyproject.toml`) so `website/**` Python is linted at repo standards — verified
   impact is website-only (no other root-level `.py` files exist).
10. **Hosted link = Horizon chat only**; the `agentic-odi.fastmcp.app` endpoint is never linked
    (401) — it is mentioned only as "credentials via an issue."
11. **Closed external-link allowlist** (repo, Issues, Horizon chat, uv docs, MCP docs, canonical);
    no analytics, no sitemap/robots/JSON-LD — SEO comes from meta + structure alone.
12. **No emoji on the site** (README's emoji vocabulary stays in README).
13. **Pages source toggle is a pre-merge gate**, not a post-merge note — without it `main` goes red.

## What's Left to the Builder

Exact micro-copy polish within the binding strings above; section/illustration composition and grid
details; animation timing fine-tuning within the stated curves; favicon/mark geometry drafting within
the stated concept; breakpoint tuning; workflow YAML details not specified (names, step ordering).
