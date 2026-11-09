# ALH-238 · Audit artifact semantics and fix briefs and memos — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans (this harness exposes no subagent tool) to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** One shared structural audit of the HTML artifacts this repository produces — `audit_html(html) -> list[Violation]` — with a positive/negative fixture harness, a machine-checked renderer inventory, the rules written down where a new renderer's author meets them, and the defects it finds fixed.

**Architecture:** The audit is a stdlib-only `html.parser` walk in `scripts/`, the repo's home for tooling that ships with the checkout. It replaces the regex checks `website/tests/test_site.py` already maintains by hand, so there is one owner of the rules instead of two, and it reaches the standalone pages (`404.html`, `sample/index.html`) those checks deliberately skip. The decision brief is not HTML: it is Markdown serialised in TypeScript and previewed through React, so the brief's structural check belongs to the axe harness that already covers the app's surfaces, and that harness gains the brief as a surface.

**Tech Stack:** Python 3.10+ stdlib (`html.parser`, `dataclasses`, `pathlib`), pytest, Jinja2 + markdown-it-py (website build), Vitest + vitest-axe (Studio).

**Spec:** Linear `ALH-238` (M5-11.1, team ALH), parent epic `ALH-131` (M5-11 · Access · Shared artifacts pass a screen reader). Verbatim acceptance text is reproduced under "What the spec asks for" below; the ticket's premise about which artifacts exist is corrected under "What the code actually is".

---

## Global constraints

- No new third-party dependency. `website/` makes zero third-party requests; `scripts/*.py` is standard-library only. `packages/*/pyproject.toml` is unchanged by this plan.
- No axe dependency in Python (the ticket forbids it; axe stays the TypeScript-side gate).
- No duplicated audit logic per renderer: `website/tests/test_site.py` calls `audit_html` rather than keeping its own heading/id/svg regexes.
- No conformance claim: zero `audit_html` violations is a structural check, never "WCAG conformance" or "screen-reader certified". The screen-reader evidence belongs to ALH-252 and is not asserted here.
- Branch from `origin/main` as `qoder/ALH-238-artifact-semantics`. Never push to `main`, never merge; open a PR with `Reuses:` block and a `Closes #…`/Linear reference.
- Docs in the same task as the code: `docs/development.md` (rule set), `docs/architecture/testing.md`, `docs/architecture/reuse.md`, `README.md` if a capability line moves.
- Tests run from the repo root: `uv run pytest`. TypeScript: `npm --prefix apps/studio test -- --run <file>`.

## What the spec asks for

> Own the parent's `audit_html -> list[Violation]`, positive/negative fixture harness, renderer inventory, rules docs and brief/memo fixes. The sibling owns other renderers and cross-artifact assistive-technology verification. Do not cover the application's keyboard-navigation backlog or introduce an axe dependency into Python.

- One `h1`, ordered headings, captioned data tables with scoped headers, labelled charts and unique IDs pass for real brief/memo output; audit errors name element/rule.
- Negative fixtures separately fail skipped headings, missing table headers/caption, missing image/SVG label and duplicate IDs. Tests prove the detector, not merely that one happy fixture returns zero.
- Charts include textual bands/method/sample size and a data-equivalent table; missing values announced as missing, not zero. Reading order follows meaningful DOM order.
- Escape untrusted research text; semantic repairs do not remove citations, provenance or visible redaction disclosure.
- Inventory enumerates actual artifact renderers. Structural checks explicitly limited: zero custom-audit violations is not a WCAG conformance or screen-reader certification claim.

## What the code actually is

Reconnaissance against `origin/main` at `c403ba17`, recorded here because the plan's shape follows it:

- **There is no memo renderer, no one-pager renderer and no shared-page renderer** in first-party code. `grep` for `memo|one-pager|shared page` over `packages apps scripts website` finds one unrelated docstring (`apps/studio-api/.../studio/marketplace.py:23`, memoisation). Inventing them would be product work this ticket does not ask for, so they are **registered as absent** in the inventory and named in the docs, not mocked.
- **The decision brief is Markdown, produced in TypeScript.** `apps/studio/src/lib/brief.ts:150` builds the object, `apps/studio/src/lib/export.ts:362` `briefToMarkdown()` serialises it, `apps/studio/src/components/brief/BriefLens.tsx:117` previews it inside `<article aria-label="Decision brief">` and prints it through `styles/print.css`. The only Python-side `Brief` (`apps/studio-api/.../studio/schemas.py:137`) is onboarding context in a system prompt, not an artifact. A Python audit therefore has no brief HTML to run on; the brief's structural check is TypeScript-side.
- **Python emits HTML only in `website/`**: `website/tools/markdown_render.py:180` (docs guides), `website/tools/build_site.py` (Jinja shell: landing, doc, docs index, 404, references), `website/tools/build_sample.py:72` → `website/templates/sample.html` (the site sample). Today: docs tables render `<th>` with no `scope`; `sample.html` has four `<table>`s with no `<caption>` and no `scope`; `website/tests/test_site.py:143-204` already checks one-h1, heading skips, id resolution and decorative SVG by regex, and skips the standalone pages.
- `apps/studio/public/offline.html` is the one hand-authored HTML file inside the app that leaves the building (service-worker cache miss).

Consequence for scope: the brief/memo half of the ticket is delivered as **brief** coverage through the existing axe harness plus the inventory's honest record that the memo does not exist. That is the "missing surfaces must be recorded before claiming full coverage" rule, applied to this ticket's own premise.

## File structure

| Path | Responsibility |
| --- | --- |
| `scripts/artifact_a11y.py` | Create. `Violation`, `RULES`, `audit_html(html)` — the rules, nothing page-specific. |
| `scripts/artifact_renderers.py` | Create. The inventory: `Renderer`, `RENDERERS`, `discover_html_emitters(roots)`. |
| `tests/scripts/fixtures/artifact_audit/*.html` | Create. One conforming artifact, one per-rule negative, one empty artifact, one labelled-chart-plus-table positive. |
| `tests/scripts/test_artifact_a11y.py` | Create. Rule-by-rule detector tests and the parser-robustness cases. |
| `tests/scripts/test_artifact_inventory.py` | Create. Registration, staleness and absent-surface tests. |
| `website/tests/test_site.py` | Modify. Replace the four regex checks with `audit_html`, sweep standalone pages too. |
| `website/tools/markdown_render.py` | Modify. `scope="col"` on header cells of a markdown table. |
| `website/templates/sample.html` | Modify. `<caption>` + `scope` on the four data tables. |
| `apps/studio/src/test/a11y.test.tsx` | Modify. The decision brief joins the swept surfaces. |
| `docs/development.md` | Modify. The artifact rule set, its limits, and how to add a renderer. |
| `docs/architecture/testing.md`, `docs/architecture/reuse.md`, `docs/living-studio.md` | Modify. Where the audit lives, what owns the rules, what the brief check proves. |

## Interfaces

`scripts/artifact_a11y.py`

```python
RULES: tuple[str, ...] = (
    "single-h1", "heading-order", "table-caption", "table-header-scope",
    "image-label", "duplicate-id",
)

@dataclass(frozen=True)
class Violation:
    rule: str        # one of RULES
    detail: str      # what to change, naming the element
    snippet: str     # the offending start tag, or "" for a missing thing

def audit_html(html: str) -> list[Violation]: ...
```

`scripts/artifact_renderers.py`

```python
@dataclass(frozen=True)
class Renderer:
    name: str                    # "docs guide", "site sample", "decision brief" …
    path: str                    # repo-relative file, or "" when the artifact does not exist
    language: str                # "python" | "typescript" | "html"
    status: str                  # "emits-html" | "emits-markdown" | "absent"
    fixes_owned_by: str          # "ALH-238" | "ALH-252" | "—"

RENDERERS: tuple[Renderer, ...]
ARTIFACT_ROOTS: tuple[str, ...]  # directories a renderer may live in

def discover_html_emitters(root: Path = REPO_ROOT) -> set[str]: ...
```

Rule semantics every task depends on:

- `single-h1` — the document contains exactly one `<h1>`; zero and two are both violations, `detail` names the count.
- `heading-order` — the heading level sequence starts at 1 and never rises by more than one at a step (`<h2>` after `<h4>` is legal; `<h1>` then `<h3>` is not).
- `table-caption` / `table-header-scope` — every `<table>` has a `<caption>` as its first element child, and at least one `<th>` carrying a `scope` of `row`, `col`, `rowgroup` or `colgroup`. A table with no `<th>` fails `table-header-scope` with `snippet=""`.
- `image-label` — every `<img>` has an `alt` attribute (`alt=""` is a deliberate decoration and passes); every `<svg>` either has `aria-hidden="true"`, or is labelled by `role="img"` plus `aria-label`/`aria-labelledby`, or contains a `<title>` child.
- `duplicate-id` — no non-empty `id` value appears twice.
- Content inside `<script>`, `<style>`, `<textarea>` and `<!-- … -->` is data, not structure: headings, tables, ids and tags found there are never counted, and a `<textarea>`'s literal `<table>` must not raise a table rule.

---

## Review Focus

Failure modes the spec implies but no acceptance bullet names. Each line gets the test shown in the task that owns the code.

1. **Markup inside a non-structural element.** A guide page's `<style>` block or a research quote in a `<textarea>`/`<script>` that contains `<h1>` or `id="x"` must not be read as structure — otherwise the gate passes a broken page or fails a fine one. → Task 1.
2. **An artifact with nothing in it.** The brief prints "Not recorded." for an empty section; an empty or fully redacted artifact must still satisfy one `h1` and produce zero violations, so silence is not mistaken for a gap in the audit. → Task 1.
3. **A chart whose meaning is only in the picture.** A labelled `<svg role="img">` alone satisfies `image-label` while still excluding a blind reader; the bar is a label *plus* a data-equivalent table with caption and scope. → Task 1 fixture, Task 4 for the live chart.
4. **A defect the fix can hide.** Fixing sample/docs tables must not drop the citation, provenance or redaction text the tables also carry, and must not reorder the DOM the reading order depends on. → Task 2.
5. **An inventory that drifts silently.** A renderer added under an artifact root but never registered would keep the gate green — the exact failure the parent epic calls out ("a new renderer without an audit case fails the enumeration test"), so the discovery scan and its stale-entry check are tests, not comments. → Task 3.

---

## Task 1: The audit — `audit_html` and its fixture harness

**Files:**
- Create: `scripts/artifact_a11y.py`
- Create: `tests/scripts/fixtures/artifact_audit/conforming.html`
- Create: `tests/scripts/fixtures/artifact_audit/empty_artifact.html`
- Create: `tests/scripts/fixtures/artifact_audit/chart_with_table.html`
- Create: `tests/scripts/fixtures/artifact_audit/{no_h1,two_h1,skipped_heading,no_caption,no_th,bad_scope,img_no_alt,svg_no_label,duplicate_id}.html`
- Create: `tests/scripts/test_artifact_a11y.py`

**Interfaces:** Produces `Violation`, `RULES`, `audit_html` exactly as above; every later task consumes them.

- [ ] **Step 1: Write the positive fixture and the failing test.** `conforming.html` is a small artifact that reads like the brief: one `<h1>`, `<h2>` sections, one data `<table>` with `<caption>` and `<th scope="col">`, decorative svg with `aria-hidden`, no duplicate ids.

```python
def test_conforming_artifact_has_no_violations() -> None:
    assert audit_html(fixture("conforming.html")) == []
```

- [ ] **Step 2: Run it and watch it fail** — `uv run pytest tests/scripts/test_artifact_a11y.py -v`, expect `ModuleNotFoundError: scripts.artifact_a11y` (or an import error), not a pass.
- [ ] **Step 3: Implement `audit_html`** as an `HTMLParser` subclass: track a stack of open `<table>` elements, the heading level sequence, seen ids, and a suppression flag incremented on `<script|style|textarea>` start and cleared on its matching end (`convert_charrefs=True`; ignore `<img>`, `<br>`, `<meta>` as void). One pass, no regex over the whole document.
- [ ] **Step 4: Run Step 1's test to green**, then run the whole file.
- [ ] **Step 5: One negative fixture per rule, written and run before the rule's code is touched again.** Each fixture differs from `conforming.html` in exactly one way.

```python
@pytest.mark.parametrize("name,rule", [
    ("no_h1", "single-h1"), ("two_h1", "single-h1"),
    ("skipped_heading", "heading-order"), ("no_caption", "table-caption"),
    ("no_th", "table-header-scope"), ("bad_scope", "table-header-scope"),
    ("img_no_alt", "image-label"), ("svg_no_label", "image-label"),
    ("duplicate_id", "duplicate-id"),
])
def test_each_negative_fixture_reports_exactly_its_rule(name: str, rule: str) -> None:
    assert {v.rule for v in audit_html(fixture(name))} == {rule}
```

- [ ] **Step 6: Run, implement the missing branch, re-run to green.** A `detail` string must name the element and what is missing (`"table has no <caption>"`, `"<img> has no alt attribute"`), and `snippet` the start tag, so the error reads as a fix instruction.
- [ ] **Step 7: Robustness and completeness cases** (Review Focus 1-3):

```python
def test_markup_inside_script_style_and_textarea_is_not_structure() -> None: ...
def test_empty_artifact_produces_no_violations() -> None: ...   # one h1, "Nothing recorded."
def test_labelled_chart_alone_is_not_enough_without_a_data_table() -> None: ...
```

The last is asserted on `chart_with_table.html` (zero violations) and on a variant whose table is removed (a `table-*` rule fires), which is how "not colour-only" and "data-equivalent table" become testable rather than aspirational.
- [ ] **Step 8: `uv run pytest tests/scripts -q` green, `uv run mypy scripts/artifact_a11y.py` clean, commit** `git add scripts/artifact_a11y.py tests/scripts/…` → `feat(scripts): audit artifact HTML structure with one shared rule set (#ALH-238)`.

## Task 2: One owner for the rules — the website pages

**Files:**
- Modify: `website/tests/test_site.py` (`:143-204`, `all_pages()` usage)
- Modify: `website/tools/markdown_render.py`
- Modify: `website/templates/sample.html`
- Test: `website/tests/test_site.py` (existing parametrised sweep)

**Interfaces:** Consumes `audit_html`. Produces nothing new for later tasks except a green rule set over real output.

- [ ] **Step 1: Write the failing sweep.** Add a test over *every* built page including the standalone ones, and assert the sample's four data tables are captioned and scoped.

```python
@pytest.mark.parametrize("page", all_pages() + sorted(STANDALONE_PAGES))
def test_page_passes_the_artifact_audit(page: str) -> None:
    violations = audit_html(read_page(page))
    assert violations == [], f"{page}: {[v.rule for v in violations]}"
```

- [ ] **Step 2: Run it and read the real violation list** — `uv run pytest website/tests/test_site.py -k artifact_audit -v`. Expect `table-caption`/`table-header-scope` on `sample/index.html` and docs pages with markdown tables. That output is the fix list; do not guess it.
- [ ] **Step 3: Fix `markdown_render.py`** so a markdown table's header cells render `<th scope="col">` (a `th_open` renderer rule in markdown-it-py; nothing else changes).
- [ ] **Step 4: Fix `website/templates/sample.html`** — one `<caption>` per data table, wording that names the table's subject the way the surrounding `<h2>` does, `scope="col"` on every header cell. Keep every existing cell's text, citation and origin column verbatim (Review Focus 4).
- [ ] **Step 5: Re-run the sweep to green, then delete the four regex checks** `test_site.py` now duplicates (`test_page_has_exactly_one_h1`, `test_page_headings_never_skip_a_level`, `test_in_page_anchors_resolve`'s id half, `test_decorative_svg_is_hidden_from_assistive_tech`), keeping any assertion they carry that `audit_html` does not (the `<header>/<main>/<footer>` landmarks, `lang`, no-third-party-requests).
- [ ] **Step 6: `uv run pytest website -q` green, `uv run python website/tools/build_sample.py --check` and `…/build_site.py --check` clean, commit** `test(website): audit every built page with the shared rule set (#ALH-238)`.

## Task 3: The renderer inventory and its enumeration gate

**Files:**
- Create: `scripts/artifact_renderers.py`
- Create: `tests/scripts/test_artifact_inventory.py`

**Interfaces:** Consumes nothing from Tasks 1-2 except `RULES` names in docstrings. Produces `RENDERERS`, `ARTIFACT_ROOTS`, `discover_html_emitters`.

- [ ] **Step 1: Write the failing tests.**

```python
def test_every_registered_renderer_exists_or_is_marked_absent() -> None: ...
def test_no_emitter_under_an_artifact_root_is_unregistered() -> None:
    unregistered = discover_html_emitters() - {r.path for r in RENDERERS if r.path}
    assert unregistered == set()
def test_the_inventory_has_no_stale_paths() -> None: ...
def test_absent_artifacts_are_recorded_not_claimed() -> None:
    absent = {r.name for r in RENDERERS if r.status == "absent"}
    assert absent == {"memo", "one-pager", "shared page"}
```

- [ ] **Step 2: Run to confirm failure** (module missing).
- [ ] **Step 3: Implement `RENDERERS`** with one row per real surface from "What the code actually is": docs guide (`website/tools/markdown_render.py`), site shell (`website/tools/build_site.py`), site sample (`website/templates/sample.html`), offline shell (`apps/studio/public/offline.html`), decision brief (`apps/studio/src/lib/export.ts`, `emits-markdown`), brief preview (`…/brief/BriefLens.tsx`), evidence chart (`…/canvas/OpportunityLandscape.tsx`), plus the three `absent` rows whose `fixes_owned_by` is `ALH-252`.
- [ ] **Step 4: Implement `discover_html_emitters`** — walk `ARTIFACT_ROOTS` only (`website/tools`, `website/templates`, `apps/studio/public`, `apps/studio/src/lib`, `apps/studio/src/components/brief`, `apps/studio/src/components/canvas`, `brand/tools`), skipping `dist`, `node_modules`, `__pycache__`, `.test.*`, `*.snap`, and matching `<h1|<table|<!DOCTYPE|role="img"` as a start-tag-shaped string. Narrow roots, so the SPA's own markup is not mistaken for an artifact.
- [ ] **Step 5: Run to green; then prove the gate** by adding a scratch `website/tools/_probe.html` containing `<h1>x</h1>`, re-running to see it fail naming the path, and deleting the file. Record the failure output in the PR.
- [ ] **Step 6: Commit** `feat(scripts): inventory the artifact renderers and fail on an unregistered one (#ALH-238)`.

## Task 4: The brief, where the brief actually is

**Files:**
- Modify: `apps/studio/src/test/a11y.test.tsx`
- Modify: whatever the run identifies under `apps/studio/src/components/brief/`, `apps/studio/src/lib/export.ts`, `apps/studio/src/lib/markdown.ts`, `apps/studio/src/components/chat/Markdown.tsx`
- Test: `apps/studio/src/lib/export.test.ts` (extend)

**Interfaces:** Consumes the existing `renderSurface`/`expectAccessible` harness (`src/test/axe.ts:16`, `src/test/a11y.test.tsx:165`).

- [ ] **Step 1: Write the failing surface test** — the brief joins the swept surfaces, rendered from a real `DecisionBrief` fixture with a populated decision, an empty section, and research text carrying `<script>alert(1)</script>` and `"`/`<h1>` so escaping is asserted while it is being checked (Review Focus 4).

```tsx
it("passes the decision brief, empty sections included", async () => {
  await renderSurface(<BriefLens … />);
  await expectAccessible();
});
```

- [ ] **Step 2: Run it and watch it fail** — `npm --prefix apps/studio test -- --run src/test/a11y.test.tsx`. Read axe's reported nodes; fix the component, not the rule. If axe reports nothing, the test still earns its place as the regression the epic asked for ("the brief is not in this list").
- [ ] **Step 3: Add the structural assertion the Python audit cannot make here:** serialise the rendered brief DOM and assert one `<h1>` inside the article, no heading-level skip across the article, every `<svg>` in it labelled, and no duplicate `id` in the article subtree. Keep it in the brief's own test file so it is found with the artifact, and state in a comment that the authoritative rule set is `scripts/artifact_a11y.py` so the two do not drift into different rules.
- [ ] **Step 4: Assert the printed page keeps its text**: extend `src/styles/print.test.ts` or the brief test to confirm the "Not recorded." lines and citation/provenance/redaction lines survive in the print path, so a redacted artifact stays understandable.
- [ ] **Step 5: `npm --prefix apps/studio test -- --run src/test/a11y.test.tsx src/lib/export.test.ts src/styles/print.test.ts` green, `npm --prefix apps/studio run typecheck` clean, commit** `test(studio): pass the decision brief through the accessibility gate (#ALH-238)`.

## Task 5: Write the rules down, and their limits

**Files:**
- Modify: `docs/development.md` (artifact/accessibility rows, `:124`, `:381`, `:410-412`)
- Modify: `docs/architecture/testing.md#accessibility`
- Modify: `docs/architecture/reuse.md` (canonical owner)
- Modify: `docs/living-studio.md` (the decision brief row), `README.md` if a capability line moves

- [ ] **Step 1: Add the rule set to `docs/development.md`** — the six rules with their exact ids, the two commands that run them (`uv run pytest website/tests/test_site.py -k artifact_audit`, `uv run pytest tests/scripts/test_artifact_a11y.py`), how to register a new renderer, and the sentence the ticket demands: zero violations is a structural check, not WCAG conformance and not a screen-reader certification, and no memo/one-pager/shared-page renderer exists to audit yet.
- [ ] **Step 2: Add the audit's owner to `docs/architecture/reuse.md`** as a Canonical owner row ("Structural rules for artifact HTML | `scripts/artifact_a11y.py` | the ad-hoc regexes it replaced in `website/tests/test_site.py`"), and update `docs/architecture/testing.md#accessibility` to list the Python audit + inventory as a fourth check beside the three existing ones.
- [ ] **Step 3: `uv run python scripts/doc_check.py` clean** (or the repo's documented docs gate), commit `docs: state the artifact accessibility rules and what they do not prove (#ALH-238)`.

## Task 6: Verify, ship, hand off

- [ ] **Step 1: Reconcile with `main`** — `git fetch origin && git merge --ff-only origin/main` (or a merge commit if the branch moved), resolving conflicts in the tree rather than discarding either side.
- [ ] **Step 2: Full suites, output inspected not skimmed:** `uv run pytest` (expect the website + scripts additions green, zero errors), `npm --prefix apps/studio test -- --run`, `npm --prefix apps/studio run typecheck`, `npm --prefix apps/studio run lint`, `uv run mypy <touched packages>`, `uv run ruff check .`, `python3 -m pytest website -q`.
- [ ] **Step 3: Prove the gates can fail**, and keep the transcripts: mutate a fixture (drop a `<caption>`), mutate a shipped page (delete a `scope`), add an unregistered emitter file, remove the brief from the axe sweep. Each must turn exactly the intended test red.
- [ ] **Step 4: Run the app** — open `/brief` with a real canvas, read the heading structure with the browser's accessibility tree (or a Playwright a11y snapshot), confirm the sample page built by `build_sample.py` prints captioned tables. Anything not observed is reported as not observed.
- [ ] **Step 5: PR** against `main`: template filled, the four-line `Reuses:` block (`Reuses: scripts/ … , src/test/axe.ts, html.parser; Near-duplicates considered: website/tests/test_site.py regexes — refactor-to-share, done in Task 2; New code and why: no rung-1/2/3 audit existed; Provenance: n/a`), the ```json summary block matching `git diff --stat base...HEAD```, `Closes` wording, and `agent-handoff` only once CI is green.
- [ ] **Step 6: Linear:** move ALH-238 to In Review with the note that names what shipped, the absent memo/one-pager/shared-page renderers, what ALH-252 inherits, and the observed-vs-claimed line. Do not merge.
