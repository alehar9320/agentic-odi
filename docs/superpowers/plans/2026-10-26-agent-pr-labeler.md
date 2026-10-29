# AI-Native PR Labeler Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make pull-request labels actually appear, and make them tell a reviewer what an agent delivered and how much attention it needs.

**Architecture:** Two pure Python modules hold all labeling logic — `pr_provenance.py` (who wrote this) and `pr_labels.py` (size, domain, supply chain, telemetry) — each unit-tested with real fixtures and no network. A new `labels` job in the existing `pr-risk.yml` gathers PR facts with `gh`, pipes them to `pr_labels.py`, and applies the result. The existing `risk` job keeps its scoring and gets its inputs passed correctly. `label-merge-conflicts.yml` is repaired to create and apply the label the repo already has.

**Tech Stack:** Python 3.11 (stdlib only), pytest, `gh` CLI, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-10-26-agent-pr-labeler-design.md`

## Global Constraints

- Python 3.10+ syntax; `from __future__ import annotations` at the top of every new module.
- No third-party dependencies in `scripts/*.py`. Stdlib only.
- No `actions/github-script`, no `actions/labeler`, no `.github/labeler.yml`.
- Never `|| true` a label write. A failed label write fails the step.
- Trigger stays `pull_request` (never `pull_request_target`); never check out or execute PR code.
- Label names are exact, including spaces and emoji:
  `🤖 agent`, `👤 human`, `size/XS`, `size/S`, `size/M`, `size/L`, `size/XL`,
  `area/studio`, `area/cli`, `area/mcp`, `area/core`, `area/connectors`,
  `area/website`, `area/brand`, `area/release`, `area/infra`, `area/ci`,
  `area/docs`, `dependencies`, `breaking change`, `needs deep dive`,
  `telemetry invalid`, `safe to merge`, `needs a look`, `danger zone`,
  `ready-for-merge`, `merge-conflict`.
- Do not rename or remove the `ci-green` job in `ci.yml`; the `main-requires-ci-green`
  ruleset requires the status check `CI green`.
- Size thresholds: `XS` <50, `S` 50–249, `M` 250–799, `L` 800–1999, `XL` >=2000.
- Provenance labels are mutually exclusive; size labels are mutually exclusive;
  risk tiers are mutually exclusive. All other axes are additive.

## Review Focus

Inputs and conditions the spec implies but its rules do not cover. Each is pinned
to a test in the task that owns the code.

1. **A PR with zero changed files** (empty diff, or the file list API returns
   nothing) — a reviewer expects a size label and no crash, not a missing label.
2. **`AGENT_METADATA` present but not a JSON object** (e.g. `true`, a bare
   string, a truncated `{`) — expects `telemetry invalid`, not a traceback.
3. **`agent_confidence` or `has_breaking_changes` of the wrong type** (e.g.
   `"yes"`, `1`, `null`) — expects the value ignored, no label, run continues.
4. **A path matching two domains** (e.g. `docs/readme.md` and `website/docs/x.md`)
   — expects both `area/docs` and `area/website`, additively, not one winning.
5. **A fork PR under `pull_request`** where the token is read-only — expects a
   printed notice and no red failure, not an unhandled permissions error.

---

### Task 1: Provenance classifier

**Files:**
- Create: `scripts/pr_provenance.py`
- Test: `tests/scripts/test_pr_provenance.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `AGENT_BRANCH_PREFIXES: frozenset[str]`
  - `classify(pr_user_login: str, pr_user_type: str, branch: str, commit_identities: list[str]) -> str` returning `"🤖 agent"` or `"👤 human"`

- [ ] **Step 1: Write the failing test**

```python
from __future__ import annotations

import pytest

from pr_provenance import classify

HUMAN = "👤 human"
AGENT = "🤖 agent"


@pytest.mark.parametrize(
    "login,user_type,branch,commits,expected",
    [
        # The spec's own rule, which marks nothing in this repo.
        ("some-bot[bot]", "Bot", "feat/thing", [], AGENT),
        # What this repo actually looks like: owner's account, agent branch.
        ("alehar9320", "User", "slay/6538dc1a-promote-evidence", [], AGENT),
        ("alehar9320", "User", "jules/fix-the-thing", [], AGENT),
        # Agent identity visible only in the commit, not the branch.
        ("alehar9320", "User", "fix/release", ["opencode-agent <opencode-agent@users.noreply.github.com>"], AGENT),
        ("alehar9320", "User", "fix/release", ["google-labs-jules[bot] <161369871+google-labs-jules[bot]@users.noreply.github.com>"], AGENT),
        # A genuine human branch with a human commit.
        ("alehar9320", "User", "fix/studio-api-outcomes-errors", ["Alexander <alehar9320@users.noreply.github.com>"], HUMAN),
        # Unknown prefix + human commit stays human.
        ("contributor", "User", "patch-1", ["Contributor <c@example.com>"], HUMAN),
    ],
)
def test_classify(login, user_type, branch, commits, expected):
    assert classify(login, user_type, branch, commits) == expected


def test_a_human_branch_never_overrides_a_bot_commit():
    assert classify("alehar9320", "User", "fix/x", ["dependabot[bot] <x@y>"]) == AGENT


def test_the_numeric_suffix_alone_is_not_enough():
    """A 20-digit suffix on an unknown prefix is not a provenance signal."""
    assert classify("contributor", "User", "patch-1-18122562874758321467", []) == HUMAN
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/scripts/test_pr_provenance.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'pr_provenance'`

- [ ] **Step 3: Implement `scripts/pr_provenance.py`**

Match on: `user_type == "Bot"`, `[bot]` or `agent` in the login (lowercased),
branch's first `/`-segment in `AGENT_BRANCH_PREFIXES`, or any commit identity
containing `[bot]` or `agent` (lowercased, matched against the full
`Name <email>` string).

`AGENT_BRANCH_PREFIXES` is a `frozenset` of the agent branch prefixes observed
in this repo plus common tools:
`{"slay", "jules", "cursor", "devin", "codex", "claude", "copilot", "openhands",
"aider", "sweep", "otto", "factory", "goose", "amp"}`.

A branch with no `/` yields the whole branch name as its prefix, so
`stop-having-to-approve-runs` matches nothing. The 20-digit numeric suffix is
deliberately *not* a signal on its own — see the third test.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/scripts/test_pr_provenance.py -v`
Expected: PASS (10 tests)

- [ ] **Step 5: Commit**

```bash
git add scripts/pr_provenance.py tests/scripts/test_pr_provenance.py
git commit -m "feat(ci): classify PR provenance from commits and branch names"
```

---

### Task 2: Size, domain, and supply-chain labels

**Files:**
- Create: `scripts/pr_labels.py`
- Test: `tests/scripts/test_pr_labels.py`

**Interfaces:**
- Consumes: nothing.
- Produces (in `pr_labels.py`):
  - `size_label(additions: int, deletions: int) -> str`
  - `domain_labels(filenames: list[str]) -> set[str]`
  - `DEPENDENCY_FILES: frozenset[str]`
  - `is_dependency_change(filenames: list[str]) -> bool`
  - `MANAGED_LABELS: frozenset[str]` (every label this system may add or remove)

- [ ] **Step 1: Write the failing test**

```python
from __future__ import annotations

import pytest

from pr_labels import (
    MANAGED_LABELS,
    domain_labels,
    is_dependency_change,
    size_label,
)


@pytest.mark.parametrize(
    "additions,deletions,expected",
    [
        (0, 0, "size/XS"),
        (49, 0, "size/XS"),
        (50, 0, "size/S"),
        (249, 0, "size/S"),
        (250, 0, "size/M"),
        (799, 0, "size/M"),
        (800, 0, "size/L"),
        (1999, 0, "size/L"),
        (2000, 0, "size/XL"),
        (400, 400, "size/L"),
    ],
)
def test_size_label_boundaries(additions, deletions, expected):
    assert size_label(additions, deletions) == expected


@pytest.mark.parametrize(
    "paths,expected",
    [
        (["apps/studio/src/App.tsx"], {"area/studio"}),
        (["apps/studio-api/main.py"], {"area/studio"}),
        (["apps/cli/main.py"], {"area/cli"}),
        (["apps/mcp-server/server.py"], {"area/mcp"}),
        (["packages/core/src/x.py"], {"area/core"}),
        (["packages/connectors/slack.py"], {"area/connectors"}),
        (["website/tools/build_site.py"], {"area/website"}),
        (["brand/src/otter.py"], {"area/brand"}),
        (["packaging/build.sh"], {"area/release"}),
        (["scripts/dev.py"], {"area/release"}),
        (["infra/cloudflare/worker.js"], {"area/infra"}),
        (["wrangler.jsonc"], {"area/infra"}),
        ([".github/workflows/ci.yml"], {"area/ci"}),
        (["README.md"], {"area/docs"}),
        (["docs/development.md"], {"area/docs"}),
        # Additive, not exclusive.
        (["docs/readme.md", "website/index.html"], {"area/docs", "area/website"}),
        # Unknown paths produce nothing rather than a bogus label.
        (["Makefile"], set()),
    ],
)
def test_domain_labels(paths, expected):
    assert domain_labels(paths) == expected


@pytest.mark.parametrize(
    "paths",
    [
        ["package.json"],
        ["package-lock.json"],
        ["pnpm-lock.yaml"],
        ["yarn.lock"],
        ["requirements.txt"],
        ["pyproject.toml"],
        ["uv.lock"],
        ["Cargo.toml"],
        ["go.sum"],
        ["apps/studio/package-lock.json"],
    ],
)
def test_dependency_changes_are_detected(paths):
    assert is_dependency_change(paths) is True


def test_source_only_changes_are_not_dependency_changes():
    assert is_dependency_change(["apps/studio/src/App.tsx", "README.md"]) is False


def test_managed_labels_never_include_labels_another_job_owns():
    """The labels job must not remove the risk tier the risk job just applied."""
    assert not MANAGED_LABELS & {"safe to merge", "needs a look", "danger zone"}
    assert not MANAGED_LABELS & {"ready-for-merge", "merge-conflict"}


def test_managed_labels_cover_every_axis_this_system_owns():
    assert {
        "🤖 agent", "👤 human",
        "size/XS", "size/S", "size/M", "size/L", "size/XL",
        "dependencies", "breaking change", "needs deep dive", "telemetry invalid",
        "area/studio", "area/cli", "area/mcp", "area/core", "area/connectors",
        "area/website", "area/brand", "area/release", "area/infra", "area/ci",
        "area/docs",
    } == MANAGED_LABELS
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/scripts/test_pr_labels.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'pr_labels'`

- [ ] **Step 3: Implement the three functions in `scripts/pr_labels.py`**

- `size_label`: sum the two arguments, then walk the threshold ladder
  (`XS` <50, `S` <250, `M` <800, `L` <2000, else `XL`). A sum of 0 is `XS`.
- `domain_labels`: return the union of labels whose rule matches any path.
  Match on the **first path segment** (`path.split("/", 1)[0]`) so
  `apps/studio-api/` maps to `area/studio` and is not caught by an
  `apps/studio` prefix test. Bare filenames (`README.md`, `wrangler.jsonc`) are
  matched by exact name; `*.md` anywhere maps to `area/docs`.
- `is_dependency_change`: true if any path's basename is in `DEPENDENCY_FILES`
  (`package.json`, `package-lock.json`, `pnpm-lock.yaml`, `yarn.lock`,
  `requirements.txt`, `pyproject.toml`, `uv.lock`, `Cargo.toml`, `Cargo.lock`,
  `go.mod`, `go.sum`).
- `MANAGED_LABELS`: the union of the domain labels, the five size labels, the
  dependency label, and the telemetry/provenance labels added in Task 3 — **22
  labels**. Define it here as the base set and let Task 3 extend it.

  It deliberately **excludes** the three risk tiers (`safe to merge`,
  `needs a look`, `danger zone`) and the two merge-state labels
  (`ready-for-merge`, `merge-conflict`). Those are owned by `score.sh` and by
  `label-merge-conflicts.yml`. If this set included them, the `labels` job would
  remove a risk tier that the `risk` job had just applied, and the two jobs would
  fight on every run.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/scripts/test_pr_labels.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/pr_labels.py tests/scripts/test_pr_labels.py
git commit -m "feat(ci): compute PR size, domain, and supply-chain labels"
```

---

### Task 3: Telemetry parsing and the label entrypoint

**Files:**
- Modify: `scripts/pr_labels.py`
- Test: `tests/scripts/test_pr_labels.py` (append)

**Interfaces:**
- Consumes: `size_label`, `domain_labels`, `is_dependency_change`, `MANAGED_LABELS` from Task 2; `classify` from Task 1.
- Produces:
  - `telemetry_labels(body: str | None) -> set[str]`
  - `compute_labels(facts: dict) -> set[str]`
  - `main(argv: list[str] | None = None) -> int` — with no arguments, reads a
    facts JSON document on stdin and prints the computed labels, one per line.
    With `--managed`, prints `MANAGED_LABELS` one per line instead, so the
    workflow can ask for the label set it must remove rather than duplicating the
    list in YAML.

`facts` has exactly this shape, and `compute_labels` tolerates missing keys:

```json
{
  "author": {"login": "alehar9320", "type": "User"},
  "branch": "slay/6538dc1a-promote-evidence",
  "commits": ["google-labs-jules[bot] <161369871+google-labs-jules[bot]@users.noreply.github.com>"],
  "body": "<!-- AGENT_METADATA {\"has_breaking_changes\": true} -->",
  "files": [{"filename": "apps/studio/src/App.tsx", "additions": 10, "deletions": 2}]
}
```

- [ ] **Step 1: Write the failing test**

```python
from pr_labels import compute_labels, telemetry_labels

BREAKING = '<!-- AGENT_METADATA {"has_breaking_changes": true} -->'
LOW_CONF = '<!-- AGENT_METADATA {"agent_confidence": "low"} -->'
MULTILINE = '<!-- AGENT_METADATA\n{"has_breaking_changes": true, "agent_confidence": "low"}\n-->'


def test_a_breaking_change_is_flagged():
    assert telemetry_labels(BREAKING) == {"breaking change"}


def test_low_confidence_asks_for_a_deep_dive():
    assert telemetry_labels(LOW_CONF) == {"needs deep dive"}


def test_a_multiline_block_parses():
    assert telemetry_labels(MULTILINE) == {"breaking change", "needs deep dive"}


def test_a_false_breaking_change_is_not_flagged():
    assert telemetry_labels('<!-- AGENT_METADATA {"has_breaking_changes": false} -->') == set()


def test_absent_metadata_is_not_an_error():
    assert telemetry_labels(None) == set()
    assert telemetry_labels("") == set()
    assert telemetry_labels("Just a normal PR body.") == set()


@pytest.mark.parametrize(
    "body",
    [
        "<!-- AGENT_METADATA {not json} -->",
        "<!-- AGENT_METADATA { -->",
        "<!-- AGENT_METADATA true -->",
        '<!-- AGENT_METADATA "a string" -->',
    ],
)
def test_malformed_metadata_is_flagged_and_never_raises(body):
    assert telemetry_labels(body) == {"telemetry invalid"}


@pytest.mark.parametrize(
    "payload",
    [
        '{"agent_confidence": "yes"}',
        '{"has_breaking_changes": 1}',
        '{"has_breaking_changes": null}',
        '{"agent_confidence": null}',
        '{"unrelated": true}',
    ],
)
def test_wrongly_typed_values_are_ignored(payload):
    assert telemetry_labels(f"<!-- AGENT_METADATA {payload} -->") == set()


def test_compute_labels_combines_every_axis():
    facts = {
        "author": {"login": "alehar9320", "type": "User"},
        "branch": "slay/abc-promote-evidence",
        "commits": [],
        "body": BREAKING,
        "files": [{"filename": "package-lock.json", "additions": 20, "deletions": 5}],
    }
    assert compute_labels(facts) == {"🤖 agent", "size/XS", "dependencies", "breaking change"}


def test_compute_labels_survives_an_empty_pr():
    facts = {"author": {"login": "x", "type": "User"}, "branch": "fix/y", "files": []}
    assert compute_labels(facts) == {"👤 human", "size/XS"}


def test_compute_labels_tolerates_missing_keys():
    assert compute_labels({}) == {"👤 human", "size/XS"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/scripts/test_pr_labels.py -v`
Expected: FAIL — `ImportError: cannot import name 'telemetry_labels'`

- [ ] **Step 3: Implement `telemetry_labels`, `compute_labels`, and `main`**

- `telemetry_labels` finds `<!-- AGENT_METADATA ... -->` with a non-greedy regex
  (`re.DOTALL`), takes the captured text, and `json.loads` it. A regex match with
  unparseable JSON, or JSON that is not a `dict`, returns `{"telemetry invalid"}`.
  No match at all returns `set()`. Read `has_breaking_changes` only when it is
  exactly a `bool` (`is True`), and `agent_confidence` only when it is exactly
  the string `"low"`. Any other type is ignored, so `1` and `"yes"` add nothing.
- `compute_labels` unions the provenance label, `size_label` over summed
  additions/deletions, `domain_labels` over filenames, `dependencies` when
  `is_dependency_change`, and `telemetry_labels` over the body. Use
  `.get(...)` with defaults throughout so a missing key cannot raise.
- `main` parses `argv` with `argparse`. With `--managed`, print every name in
  `MANAGED_LABELS` sorted and return 0. Otherwise read stdin, call
  `compute_labels`, print each label on its own line sorted, and return 0. Any
  exception prints to stderr and returns 1, so the workflow fails loudly rather
  than labeling nothing.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/scripts/test_pr_labels.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/pr_labels.py tests/scripts/test_pr_labels.py
git commit -m "feat(ci): parse agent telemetry into PR labels"
```

---

### Task 4: Repair the `pr-risk` workflow

**Files:**
- Modify: `.github/workflows/pr-risk.yml`
- Modify: `.github/actions/pr-risk/action.yml` (only if input wiring requires it)
- Test: `tests/scripts/test_pr_labeler_workflow.py`

**Interfaces:**
- Consumes: `scripts/pr_labels.py` from Tasks 2–3.
- Produces: nothing other tasks import.

**Root causes fixed:** inputs never passed to the composite action (RC1); labels
never created (RC2).

- [ ] **Step 1: Write the failing test**

```python
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "pr-risk.yml"


def test_inputs_are_passed_with_with_not_env():
    """RC1: a uses: step's env does not populate the action's inputs."""
    text = WORKFLOW.read_text(encoding="utf-8")
    risk_job = text.split("\n  risk:\n", 1)[1]
    assert "with:" in risk_job
    for key in ("BASE_SHA", "HEAD_SHA", "PR_NUMBER", "REPO"):
        assert f"{key}: ${{{{ github.event.pull_request" in risk_job, key


def test_the_labels_job_creates_labels_with_an_explicit_repo():
    """RC2: gh label create needs --repo outside a checkout, and issues:write."""
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "gh label create" in text
    assert "--repo" in text


def test_permissions_include_issues_write():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "issues: write" in text
    assert "pull-requests: write" in text


def test_no_failure_is_swallowed_on_the_label_path():
    """RC1/RC2 were hidden by || true. Removal may be tolerant; addition must not."""
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "pr_labels.py" in text
    for line in text.splitlines():
        if "--add-label" in line:
            assert "|| true" not in line, f"swallowed add-label failure: {line.strip()}"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/scripts/test_pr_labeler_workflow.py -v`
Expected: FAIL on the first assertion (no `with:` block today)

- [ ] **Step 3: Rewrite `.github/workflows/pr-risk.yml`**

Keep the name `PR Risk Classification`, the `pull_request` trigger with
`[opened, synchronize, reopened]` on `main`, the `concurrency` block, and
`timeout-minutes`. Two jobs:

**Job `labels`** (new) — `contents: read`, `pull-requests: write`, `issues: write`:
1. `actions/checkout@v7` with `fetch-depth: 0`.
2. **Ensure labels exist** — for each of the 22 labels in `MANAGED_LABELS`, run
   `gh label create "<name>" --color <hex> --description "<text>" --repo "$GITHUB_REPOSITORY" --force`.
   Pass `GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}`. This is the RC2 fix: `--repo`
   removes the need for a git checkout, and `--force` makes re-runs idempotent.
   Do not append `|| true` to the whole loop; let a genuine failure surface.

   Colors and descriptions, so the new labels match the existing palette:

   | Label | Color | Description |
   |---|---|---|
   | `🤖 agent` | `8250df` | Authored by a coding agent |
   | `👤 human` | `0e8a16` | Authored by a human |
   | `size/XS` | `c2e0c6` | Under 50 lines changed |
   | `size/S` | `bfd4f2` | 50-249 lines changed |
   | `size/M` | `fbca04` | 250-799 lines changed |
   | `size/L` | `d93f0b` | 800-1999 lines changed |
   | `size/XL` | `b60205` | 2000 or more lines changed |
   | `dependencies` | `0366d6` | (exists — skip if present) |
   | `breaking change` | `b60205` | Agent declared breaking changes |
   | `needs deep dive` | `fbca04` | Agent reported low confidence |
   | `telemetry invalid` | `ededed` | AGENT_METADATA block could not be parsed |
   | `area/mcp` | `006b75` | MCP server (apps/mcp-server) |
   | `area/connectors` | `006b75` | External connectors (packages/connectors) |
   | `area/website` | `c2e0c6` | Published website (website) |
   | `area/brand` | `d4c5f9` | Brand assets and mascot (brand) |
   | `area/infra` | `0052cc` | Infrastructure (infra, wrangler) |

   The six `area/*` labels that already exist (`area/ci`, `area/cli`,
   `area/core`, `area/docs`, `area/release`, `area/studio`) and the existing
   `dependencies` are also passed to `gh label create --force`, which is a no-op
   for an unchanged label and keeps one code path.
3. **Gather facts and apply labels** — pipe a JSON document built with
   `gh pr view "$PR_NUMBER" --repo "$REPO" --json author,body,commits,headRefName`
   (mapped into the `facts` shape from Task 3; `commits` becomes a list of
   `"<name> <email>"` strings) and
   `gh api "repos/$REPO/pulls/$PR_NUMBER/files?per_page=100" --paginate` (capped
   at 300 files) into `uv run python scripts/pr_labels.py`.
4. Remove every stale label, then add the computed set. Get the removal list from
   the script itself — `uv run python scripts/pr_labels.py --managed` — rather
   than repeating the label names in YAML, so there is one source of truth.
   Removal first makes re-runs converge instead of accumulating stale sizes.

   ```bash
   computed="$(printf '%s' "$facts" | uv run python scripts/pr_labels.py)"
   while IFS= read -r label; do
     [ -z "$label" ] && continue
     if ! printf '%s\n' "$computed" | grep -Fxq "$label"; then
       gh pr edit "$PR_NUMBER" --repo "$REPO" --remove-label "$label" || true
     fi
   done < <(uv run python scripts/pr_labels.py --managed)
   while IFS= read -r label; do
     [ -z "$label" ] && continue
     gh pr edit "$PR_NUMBER" --repo "$REPO" --add-label "$label"
   done <<< "$computed"
   ```

   Note the asymmetry, and that it is deliberate: removing a label that is
   already absent is a harmless no-op that `gh` may still report as an error, so
   that one removal is tolerant. The `--add-label` call is the one that must not
   be swallowed — that is the failure the old workflow hid.
5. Write `$computed` to `$GITHUB_STEP_SUMMARY` so a reviewer can see which labels
   were chosen and why the run behaved as it did.

Add a guard at the top of the job: if
`github.event.pull_request.head.repo.fork` is true, print
`::notice::Skipping labels for a fork PR (read-only token)` and skip the steps.

**Job `risk`** (existing) — fix RC1 by moving the values from step-level `env:`
into a `with:` block:

```yaml
      - name: Score PR diff and apply risk label
        uses: ./.github/actions/pr-risk
        with:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          BASE_SHA: ${{ github.event.pull_request.base.sha }}
          HEAD_SHA: ${{ github.event.pull_request.head.sha }}
          PR_NUMBER: ${{ github.event.pull_request.number }}
          REPO: ${{ github.repository }}
```

Also change `score.sh` so a failed label write is not swallowed: keep the
stale-label removal tolerant, but let the final
`gh pr edit --add-label "${tier}"` fail the step when it genuinely fails.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/scripts/test_pr_labeler_workflow.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add .github/workflows/pr-risk.yml .github/actions/pr-risk/score.sh tests/scripts/test_pr_labeler_workflow.py
git commit -m "fix(ci): pass action inputs and create labels so PR labels appear"
```

---

### Task 5: Repair `label-merge-conflicts`

**Files:**
- Modify: `.github/workflows/label-merge-conflicts.yml`
- Test: `tests/scripts/test_pr_labeler_workflow.py` (append)

**Interfaces:**
- Consumes: nothing.
- Produces: nothing.

**Root causes fixed:** `gh label create` runs outside a checkout without
`--repo` (RC2), and the workflow targets `merge-ready`, a near-duplicate of the
existing `ready-for-merge`.

- [ ] **Step 1: Write the failing test**

```python
CONFLICTS = ROOT / ".github" / "workflows" / "label-merge-conflicts.yml"


def test_conflict_labels_are_created_with_an_explicit_repo():
    text = CONFLICTS.read_text(encoding="utf-8")
    assert "gh label create" in text
    assert "--repo" in text


def test_the_existing_ready_for_merge_label_is_reused():
    text = CONFLICTS.read_text(encoding="utf-8")
    assert "ready-for-merge" in text
    assert "merge-ready" not in text


def test_conflicts_workflow_declares_issues_write():
    text = CONFLICTS.read_text(encoding="utf-8")
    assert "issues: write" in text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/scripts/test_pr_labeler_workflow.py -v`
Expected: FAIL — no `--repo` on the `gh label create` lines

- [ ] **Step 3: Edit `.github/workflows/label-merge-conflicts.yml`**

- Add `--repo "$GITHUB_REPOSITORY"` to both `gh label create` calls, keeping
  `--force`.
- Add `issues: write` to `permissions`.
- Replace every `merge-ready` with `ready-for-merge` — in the create step, both
  `--add-label`/`--remove-label` calls, and the `case` branches.
- Add a checkout step only if `gh` still needs one; with `--repo` it should not.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/scripts/test_pr_labeler_workflow.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add .github/workflows/label-merge-conflicts.yml tests/scripts/test_pr_labeler_workflow.py
git commit -m "fix(ci): create merge labels with --repo and reuse ready-for-merge"
```

---

### Task 6: PR template, README, and full verification

**Files:**
- Modify: `.github/pull_request_template.md`
- Modify: `README.md:246-267`
- Test: `tests/scripts/test_pr_labels.py` (append)

**Interfaces:**
- Consumes: `telemetry_labels` from Task 3.
- Produces: nothing.

- [ ] **Step 1: Write the failing test**

```python
TEMPLATE = ROOT / ".github" / "pull_request_template.md"


def test_the_template_offers_the_metadata_block():
    assert "AGENT_METADATA" in TEMPLATE.read_text(encoding="utf-8")


def test_the_documented_example_is_valid():
    """The snippet in the template must parse, or agents will copy a broken one."""
    from pr_labels import telemetry_labels

    text = TEMPLATE.read_text(encoding="utf-8")
    start = text.index("<!-- AGENT_METADATA")
    end = text.index("-->", start) + 3
    assert telemetry_labels(text[start:end]) != {"telemetry invalid"}
    assert telemetry_labels(text[start:end]) == set(), "the placeholder must add no label"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/scripts/test_pr_labels.py -v`
Expected: FAIL — `ValueError: substring not found`

- [ ] **Step 3: Add the block to the template and update the README**

Add to `.github/pull_request_template.md`, after `## Summary`, a visible
heading, a guidance comment, and the live block:

```markdown
## Agent metadata

<!-- Agents: replace these values with your own, or delete this block. -->

<!-- AGENT_METADATA
{"has_breaking_changes": false, "agent_confidence": "high"}
-->
```

Two things matter here. The guidance comment and the live block must be
**separate** HTML comments — HTML comments do not nest, so wrapping the block in
another comment truncates it at the first `-->` and the block never parses. And
the values must be real, parseable JSON: the placeholder is the safe default
(`false` / `high`), which adds no label, so a PR that leaves it untouched is
unaffected while a PR that edits it is believed.

Do **not** make the block unreachable by commenting it out — the test below
parses it, and an agent copying a commented-out example produces nothing.

- Rewrite the README's `## PR Risk Classification` section to document both
  label axes, the label table, and the fact that provenance, size, domain,
  supply chain, and telemetry labels now apply alongside the risk tier.
- Keep the section's existing tone and its "silent: never posts PR comments"
  note.

- [ ] **Step 4: Run the full suite**

Run: `uv run pytest`
Expected: PASS, no regressions. Also run
`uv run ruff check scripts/pr_labels.py scripts/pr_provenance.py tests/scripts/`
and expect no findings.

- [ ] **Step 5: Commit**

```bash
git add .github/pull_request_template.md README.md tests/scripts/test_pr_labels.py
git commit -m "docs: document PR labels and the agent metadata block"
```

---

### Task 7: Verify on a live pull request

**Files:** none (verification only).

- [ ] **Step 1: Push the branch and open a PR**

Push the branch and open a PR against `main`. Wait for the
`PR Risk Classification` run to finish.

- [ ] **Step 2: Confirm the labels actually appear**

```bash
gh pr view <PR_NUMBER> --repo alehar9320/agentic-odi --json labels \
  --jq '.labels[].name'
```

Expected: a provenance label, a `size/*` label, at least one `area/*` label,
`dependencies` (this PR changes `package.json`/`uv.lock`-adjacent files if it
touches them), and a risk tier. At minimum: `👤 human` or `🤖 agent`, `size/*`,
`area/ci`, and a risk tier.

- [ ] **Step 3: Confirm idempotency**

Push an empty commit to trigger `synchronize`, then re-run Step 2. Expected:
the same label set, no duplicates, and no error in the run log. Then confirm the
run log contains no `fatal: ambiguous argument ''` and no `not found`.

- [ ] **Step 4: Confirm the risk score is real**

In the `risk` job log, confirm the printed score is non-zero for a non-trivial
diff. A `PR risk score: 0/100` on a PR with changed files means RC1 has
regressed.
