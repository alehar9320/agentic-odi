# ALH-163 (M2-01.2) — a theme tree that carries its own counts

## What this is

A theme is today a name in a list. `odi themes list` shows which groups exist, the landscape's
facet shows how many outcomes sit directly under each, and nothing answers the question a person
with 150 outcomes actually asks: *how much of my research is in this branch of the tree, how much
of it is measured, and what is the biggest opportunity in it?*

ALH-163 makes the tree readable. One read-only rollup — `{outcomes, measured, top_opportunity,
top_statement}` — computed from memberships that already exist, reached by a parent theme and its
children together, counted **once per outcome** when a membership overlaps. It surfaces from the
terminal (`odi themes rollup`), over MCP (`get_theme_rollup`, `list_theme_rollups`), and on the
board as a `theme_tree` card. The landscape's theme facet gains the same rule: choosing a theme
with children can filter to that theme *and its subtree*, so the count on the card and the list on
the board agree by construction rather than by luck.

Linear: [ALH-163](https://linear.app/agentic-odi/issue/ALH-163) · M2-01.2 · epic Pillar 1 ·
areas core, mcp, cli, studio · size S. Depends on M2-01 (themes, PR in this stack) and M2-02.1
(`OutcomeQuery`, PR in this stack).

## Why this shape

The issue's own boundary: *deliver the read-only rollup, the CLI/MCP adapter and the existing
tree/facet; no second hierarchy, no membership editor, no stored aggregate*. So everything here is
a **read over data that already exists** — the union is computed at call time from
`repo.themes` and `repo.outcomes`, nothing is written, and a second call returns the same answer.
Two consequences drive the design:

- The rollup and the facet must be **one rule**. Today nothing in the codebase expands a theme to
  its children: `OutcomeQuery._passes` treats `theme_ids` as a flat OR, `list_themes` returns an
  unstructured list, and the landscape maps facet ids straight through. If the Studio and the
  rollup each grew their own expansion, the card's number and the board's list would drift — the
  exact failure this issue exists to prevent ("a tree you cannot read is a taxonomy you will not
  maintain").
- The depth bound already exists as prose. `ODIService._validate_theme_placement` refuses a third
  level with *"themes go two levels deep at most"*. The rollup walker must use that number rather
  than recurse freely, because the model itself only forbids a theme being its own parent.

## Goals

- `theme_rollup(theme_id)` returning the four values plus the theme's identity, counting a
  parent's own direct memberships and its children's as a union of outcome ids — an outcome filed
  in the parent and in two children counts **once**.
- `measured` reported separately from `outcomes`: a theme full of unscored outcomes is not
  progress, and the two numbers must never be conflated into one.
- `top_opportunity`/`top_statement` chosen by the same ordering every other outcome read uses, and
  **absent** (`None`, never `0.0`) when nothing in the subtree is scored.
- A deterministic tie: equal top scores resolve the way `odi top` and search already resolve them.
- `odi themes rollup <id>`, and `odi themes rollup --job <id>` for the whole tree in one read.
- MCP `get_theme_rollup` and `list_theme_rollups`, both read-effect, both auto-ungated in chat.
- A `theme_tree` catalog card that renders a theme, its children, and each one's counts.
- A landscape facet that filters to a theme and its subtree when asked, through `OutcomeQuery`
  itself — not through a calculation in the browser.
- Empty, missing and failed are three different answers, and each surface says so.

## Non-goals

- No membership editor, no drag-and-drop re-filing, no second hierarchy. `assign`/`unassign` and
  `add`/`rename`/`delete` already own writes.
- No stored or cached aggregate: no new event, no new table, no field on `Theme` or `Outcome`,
  nothing in `_apply_event`, nothing in `odi_schema()`'s entity registry.
- No arithmetic sum of children's counts. Overlapping memberships make a sum a lie; the union is
  the only honest count.
- No third level, and no unbounded recursive walk to defend against one.
- No new REST route. The board already fetches the themes it needs and the rollup reaches the
  agent-rendered card through the tool; the studio-api change is the facet's one new parameter.
- No change to what a facet count means: `facets.theme` stays each theme's own direct memberships,
  which is what a facet list is for.

## The calls

Anything below marked *my call* is mine, made because the issue names the boundary and not the
mechanism. ALH-163's readiness blockers — define `measured` and the tie/no-score behaviour
consistently with ALH-21/search, use the theme depth bound rather than an unbounded walker, no
local per-client aggregate calculation — are answered by calls 2, 3, 4 and 8.

### 1. One module holds the rule, and both doors call it (*my call*)

New `packages/core/src/agentic_odi_core/theme_tree.py`, next to `query.py` and `outcome_import.py`
rather than inside a 1,550-line `services.py`:

```python
THEME_DEPTH = 2  # in models.py, next to Theme


class ThemeRollup(BaseModel):
    ...  # theme_id, name, parent_id, outcomes,
    # measured, top_opportunity, top_statement


def subtree_ids(
    themes: Mapping[str, Theme], theme_id: str, depth: int = THEME_DEPTH
) -> list[str]: ...
def build_rollup(
    theme: Theme, themes: Mapping[str, Theme], outcomes: Sequence[Outcome]
) -> ThemeRollup: ...
```

`ThemeRollup` is a **read result, not an entity**: it lives here and is deliberately *not* added to
`schema._SCHEMA_MODELS`, whose docstring is "the JSON schema for each ODI entity". Its shape
travels to agents in the `ToolSpec.returns` sentence, the way `search_outcomes`'s
`{items, total, facets}` does.

### 2. `measured` is the search's own `scored`, lifted out of the private (*my call*)

`query.py::_is_scored(outcome)` — `importance is not None and satisfaction is not None` — is
already the definition the confidence facet, the score bands and the Studio's `isUnderserved`
agree on. It becomes public `is_scored(outcome)` in the same file and is the *only* measure of
measured here. No new rule, no `scored_only` flag inventing a second one. `measured` counts the
same included ids as `outcomes`, never a wider set.

### 3. The top is the first scored outcome of the ordering we already ship (*my call*)

`top_opportunity`/`top_statement` come from
`rank_outcomes([o for o in included if is_scored(o)])[0]` — the very function
`sort_outcomes(..., "opportunity_score")` uses for `get_outcomes`, `odi top` and search. It is a
stable sort on `(unscored last, −score)`, so a tie keeps store order: the same winner the terminal
prints at the top of a list, and no invented tie-break like "lowest id wins" that would disagree
with `odi top` on the same data. When no included outcome is scored, both fields are `None`, and
`measured` is `0` — a theme of three unscored outcomes reads `3 outcomes · nothing measured yet`,
not `top 0.0`.

### 4. The walk is bounded and cycle-safe because the model does not guarantee it

`Theme` only validates "a theme is not its own parent", so a two-theme cycle is reachable on a
store written before the service's two-level check, or through a hand-edited event log. The walker
therefore takes at most `THEME_DEPTH − 1 = 1` descent below the named theme, and carries a `visited`
set so a corrupt parent chain returns what it has instead of spinning.

The bound is one constant, `models.THEME_DEPTH = 2`, that the walk reads. The write that refuses a
third level already states the same fact structurally — it refuses a parent that has a parent of
its own — and carries a comment naming the constant rather than interpolating it into the sentence,
because that sentence is pinned word for word by two existing tests and "themes go 2 levels deep"
is worse copy than "themes go two levels deep" for the sake of one number.

### 5. The union is by outcome id, and only live outcomes (*my call*)

`outcomes` is `len({outcome.id for outcome in store if set(outcome.theme_ids) & subtree})` — a
set, so the fixture the issue names (one outcome directly in the parent *and* in two children)
counts once. Deleting a theme strips its id from live outcomes and deletes no outcome, so a
membership that pointed at a removed outcome is simply absent from `repo.outcomes`. No count ever
includes a ghost.

### 6. Two tools, because two questions are being asked

- `get_theme_rollup(theme_id)` — one theme's rollup, the shape the issue names. Unknown id →
  `ThemeNotFoundError`, which is a 404 at the HTTP door and exit 1 at the terminal, distinct from
  a malformed request.
- `list_theme_rollups(job_id=None)` — every theme in scope, one pass over the memberships, ordered
  `(job_id, ordinal, name)` so a tree prints top-down. The tree card and `odi themes rollup --job`
  need all of them; looping `get_theme_rollup` per theme would be an N-read for a single screen,
  and the issue forbids a per-client aggregate calculation.

Both are `get_`/`list_` prefixed, so `ToolSpec._derive_effect` makes them READ and chat never
prompts — deliberately *not* given an explicit `effect=`, which the capability-manifest test
reserves for the three declared reads (`evaluate_outcome`, `compute_opportunity`,
`search_outcomes`).

### 7. The CLI is one command with an optional argument

`odi themes rollup [THEME_ID] [--job <id>] [--json]`:

- a `THEME_ID` prints that theme's rollup block and nothing else;
- no `THEME_ID` prints the whole tree's table for `--job` (or for the workspace when `--job` is
  also absent), which is what `odi themes list` should have been able to say;
- neither → the tool's own complaint, printed and exit 1:
  `'rollup wants a theme: name one with THEME_ID or list a scope with --job'`.

Rendering never fabricates a zero. `outcomes == 0` → `no outcomes yet`; `outcomes > 0,
measured == 0` → `nothing measured yet`; a top of `None` prints no score column value at all.

### 8. The facet's subtree rule lives in `OutcomeQuery`, not in the browser

`OutcomeQuery.include_children: bool = False`. When true and `theme_ids` is non-empty,
`search_outcomes` expands the list through the same `subtree_ids` before matching, after the
existing unknown-theme validation. The thread is one boolean end to end: MCP `search_outcomes`'s
twelfth argument, `GET /api/outcomes/search?include_children=`, `BulkQuery.include_children` so
the bulk dialog cannot quietly narrow a different set from the visible search, and the Studio's
theme facet, whose chip for a theme that has children offers *incl. subthemes* and shows it on the
active-filter row. Facet counts keep their present meaning; a `skip="theme"` recount is untouched
by an id the theme dimension is not filtering on.

## Interface the builder must not reinvent

- `ODIService.theme_rollup(theme_id: str) -> ThemeRollup` — raises `ThemeNotFoundError`.
- `ODIService.list_theme_rollups(job_id: str | None = None) -> list[ThemeRollup]`.
- `ThemeRollup.as_dict()` → `model_dump(mode="json")`, the same shape both MCP handlers return.
- `theme_tree.subtree_ids(themes, theme_id, depth=THEME_DEPTH) -> list[str]` — includes the
  theme itself first.
- `query.is_scored(outcome: Outcome) -> bool` — the one measured rule.
- No repository, schema, event, or SQLite change. `test_persistence_parity.py` must stay green
  *without* an edit, which is the proof that nothing was stored.

## Test plan

- **core** `packages/core/tests/test_theme_rollup.py`: the overlap fixture counts once; a parent's
  rollup equals the union of itself and children, never their sum; `measured` excludes unscored and
  agrees with `facets.confidence.scored` over the same ids; the tie picks the store-order winner and
  matches `sort_outcomes`'s first item; an all-unscored subtree gives `top_* = None` with `0`
  measured; an empty theme gives two zeros and two `None`s; `subtree_ids` stops at depth 2 and
  survives a parent cycle; a deleted child's outcomes stop counting; workspace themes roll up
  job-scoped children only when the scopes match (`list_themes`'s existing rule).
- **core** `test_outcome_query.py` (or the existing search test file): `include_children=True`
  returns the subtree's items and `False` returns the selected ids' own; counts stay
  dimension-removed; an unknown theme in `theme_ids` is still `Unknown theme: …`.
- **core** reads write nothing: two `theme_rollup` calls leave the event table and every outcome
  byte-identical.
- **mcp** `apps/mcp-server/tests/test_theme_tools.py`: both handlers answer JSON, `validate_tool_specs`
  stays empty, the two names appear in `TOOL_NAMES`, capability manifest, and the summary, and the
  `get_theme_rollup` of an unknown id reports the not-found sentence.
- **cli** `apps/cli/tests/test_themes_cli.py`: `themes rollup <id>` block, `--json`, `--job` table,
  neither-argument exit 1 with its sentence, an unknown id exit 1, and no fabricated `0.0` for a
  theme with no scores.
- **contract** `tests/contract/`: `set(_LOCAL_HANDLERS) == set(TOOL_NAMES)` still passes, and
  `tests/contract/test_outcome_search_parity.py` gains an `include_children` case proving the
  terminal and `GET /api/outcomes/search` return the same ids and total.
- **studio-api** `apps/studio-api/tests/test_studio_themes.py`: a missing theme is a 404 and a bad
  request is a 422 (never both the same envelope), and `include_children` reaches the local service
  and the MCP branch alike.
- **studio**: catalog/registry parity for `theme_tree` (the existing loops catch a missing
  renderer, a missing `actions` prop, or a description under 20 chars), a card test that renders
  parent-plus-child counts, and `OpportunityLandscape.search.test.tsx` that selecting a parent with
  the toggle sends `include_children=true` and the chip says *incl. subthemes*.

## What is left to the builder

Field order in the rollup table's columns, the card's DOM and class names (it must match the
existing cards' conventions, not a new one), the exact placement of the *incl. subthemes* control
in `FacetGroup`, and whether `render_theme_rollup` is one function with a flag or two. None of it
changes a contract. If the website's MCP reference page breaks its 110 KB ceiling with two
one-argument tools, the record moves the ceiling the way the comment in
`website/tests/test_site.py` says it has moved five times before; splitting that page is a separate
issue and not this one's work.
