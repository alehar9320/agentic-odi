# AI-Native PR Labeler — Design

Date: 2026-10-26
Status: awaiting approval

## Intent

A reviewer opening an agent-authored pull request should learn, at a glance, what
the agent delivered and how much attention it needs: who authored it, how big it
is, what part of the system it touches, whether it moved a dependency, and
whether the agent flagged it as breaking or low-confidence.

Today they learn nothing. Every pull request in this repository carries zero
labels, even though two labeler workflows run on every PR and report success.
That is the problem this work solves.

## What is actually broken (evidence)

Investigated from the live workflow logs of run `40385995135` (PR #254) and
`40385995138`, and the GitHub API.

### Root cause 1 — `pr-risk.yml` never passes its inputs

`.github/workflows/pr-risk.yml` sets step-level `env:` on the `uses:` step, but
the composite action declares `inputs:` (`BASE_SHA`, `HEAD_SHA`, `PR_NUMBER`,
`REPO`, `GITHUB_TOKEN`) and reads `${{ inputs.* }}`. A `uses:` step's `env:` does
not populate `inputs`. The inner step therefore runs with empty variables:

```
env:
  GITHUB_TOKEN:
  BASE_SHA:
  HEAD_SHA:
  PR_NUMBER:
  REPO:
...
fatal: ambiguous argument '': unknown revision or path not in the working tree.
PR risk score: 0/100 -> safe to merge
```

`git diff` fails on the empty SHAs, the script falls back to `0` lines, scores
`safe to merge`, and then every `gh pr edit` fails because that label does not
exist in the repository. All failures are swallowed by `|| true`, so the step
exits 0 and the workflow reports **success**.

### Root cause 2 — labels are never created

`label-merge-conflicts.yml` tries to create its labels with
`gh label create merge-conflict --force`, but the job has no `actions/checkout`
step and passes no `--repo`:

```
failed to run git: fatal: not a git repository (or any of the parent directories): .git
'merge-conflict' not found
'merge-ready' not found
```

The repository's 29 labels do not include `merge-conflict`, `merge-ready`,
`safe to merge`, `needs a look`, or `danger zone`. So even a correctly computed
label cannot be applied. Again hidden by `|| true`.

Net effect: silent failure at two layers. Fixing the trigger alone would not
have produced a visible label.

### Root cause 3 — the supplied spec does not match this repository

| Spec assumes | This repository has |
|---|---|
| `src/frontend/**`, `apps/web/**`, `components/**` | `apps/studio/**` (Vite/React) |
| `src/backend/**`, `apps/api/**`, `server/**` | `apps/studio-api/**`, `apps/mcp-server/**` |
| — | `packages/core`, `packages/connectors`, `website/`, `brand/` |

A `domain/frontend` label would never fire. The repository already ships
`area/ci`, `area/cli`, `area/core`, `area/docs`, `area/release`, `area/studio` —
labels that exist but that no workflow currently applies.

### Root cause 4 — the spec's provenance rule classifies nothing as an agent

The spec rule is `user.type === 'Bot' || login includes '[bot]' or 'agent'`.
Applied to the last 25 pull requests, it labels **0 of 25** as agent-authored:
every PR comes from `alehar9320` (type `User`). The agents in this repository push
branches on the owner's account, so authorship shows up in the branch name, not
the login:

```
jules/studio-whats-new-button-and-bff-fallback-14619777477577504070
slay/6538dc1a-promote-evidence
feat/elevate-pm-favicon-18122562874758321467   <- 20-digit agent suffix
docs/add-github-pages-badge-17204527713176226235
```

Without a branch-name signal, the provenance axis is dead on arrival.

### Root cause 5 — nothing emits `AGENT_METADATA`

`0 of 30` recent pull request bodies contain an `AGENT_METADATA` block, and
`.github/pull_request_template.md` does not ask for one. Metadata parsing would
be unreachable code until the template and the agents change.

## Decisions

### Mine (please check while reading)

- **Unify instead of adding a third labeler.** Fold the new axes into the
  existing `pr-risk` workflow and delete nothing. Three parallel labelers would
  leave `size/XL` sitting next to `danger zone` with no defined relationship.
- **Implement the label logic in Python, not `actions/github-script`.** The repo
  is Python-first with a `pytest` suite; a pure function over PR facts can be
  unit-tested with real fixtures, which is how this stops regressing. The spec's
  Node/`github-script` choice buys nothing here.
- **Drop `actions/labeler` and `.github/labeler.yml`.** Domain matching moves
  into the same tested Python function. One fewer third-party action, no second
  config file to drift, and the globs can be asserted in tests.
- **Reuse the existing `area/*` labels** rather than invent `domain/*`.
- **Fix the size ladder.** The spec jumps `S` (50–249) to `XL` (≥800) and never
  defines `L`. Use `XS <50`, `S 50–249`, `M 250–799`, `L 800–1999`,
  `XL ≥2000`.
- **Keep the `pull_request` trigger** (repo convention) rather than
  `pull_request_target`. We read PR metadata and file lists through the API and
  never check out or execute PR code. Trade-off: fork PRs get a read-only token
  and will not be labeled. Every current agent pushes to a same-repo branch.
- **Never swallow a failure again.** No `|| true` on the label-application path;
  a failed label write fails the step. That is the difference between this
  system and the one that is silently broken today.

### Yours (answered 2026-10-26)

1. **Provenance signal** — decided by measurement, not preference. Evaluated
   against the last 40 pull requests:

   | Rule | PRs marked agent |
   |---|---|
   | A: PR user `type`/login (the spec's rule) | **0 / 40** |
   | B: commit author identity | 6 / 40 |
   | C: branch-name prefix | 23 / 40 |
   | **B or C** | **28 / 40** |

   The spec's rule is dead: agents push on the owner's account, so `user` is
   always `alehar9320`. The signal lives in the commit identity
   (`google-labs-jules[bot]`, `opencode-agent@users.noreply.github.com`) and the
   branch name (`slay/` is 77% of all PRs). Chosen rule: agent if **any** of
   user-type/login, commit identity, branch prefix, or an explicit metadata
   declaration says so.

2. **Scope** — yes, repair `label-merge-conflicts.yml` too.

3. **Label vocabulary** — settled below.


## Design

### Managed label set

The naming rule: a label is an instruction to a reviewer, not a taxonomy entry.
No new label is created where an existing one already says the thing.

| Axis | Labels | Source |
|---|---|---|
| Provenance | `🤖 agent`, `👤 human` | author + commits + branch |
| Size | `size/XS`, `size/S`, `size/M`, `size/L`, `size/XL` | `additions + deletions` |
| Domain | `area/studio`, `area/cli`, `area/core`, `area/connectors`, `area/mcp`, `area/website`, `area/docs`, `area/ci`, `area/infra`, `area/brand`, `area/release` | changed paths |
| Supply chain | `dependencies` | lockfile / manifest paths |
| Telemetry | `breaking change`, `needs deep dive`, `telemetry invalid` | `AGENT_METADATA` block |
| Risk tier | `safe to merge`, `needs a look`, `danger zone` | existing scoring, unchanged |
| Merge state | `ready-for-merge`, `merge-conflict` | existing workflow, repaired |

Path → domain mapping, against the real tree. Six of these labels already exist;
only `area/connectors`, `area/mcp`, `area/website`, `area/brand`, and
`area/infra` are new.

| Path | Label | Exists |
|---|---|---|
| `apps/studio/**`, `apps/studio-api/**` | `area/studio` | yes |
| `apps/cli/**` | `area/cli` | yes |
| `apps/mcp-server/**` | `area/mcp` | new |
| `packages/core/**` | `area/core` | yes |
| `packages/connectors/**` | `area/connectors` | new |
| `website/**` | `area/website` | new |
| `brand/**` | `area/brand` | new |
| `packaging/**`, `scripts/**`, `release-please*` | `area/release` | yes |
| `infra/**`, `wrangler.jsonc` | `area/infra` | new |
| `.github/**` | `area/ci` | yes |
| `docs/**`, `**/*.md` | `area/docs` | yes |

`area/studio` deliberately absorbs `apps/studio-api`: its existing description
reads "Living Studio (apps/studio, apps/studio-api)", so a separate
`area/studio-api` would be a second name for one thing.

Provenance, size, and risk tier are mutually exclusive within their axis; the
others are additive.

Naming rationale:

- **Provenance is the only emoji axis.** Who wrote this is the first question a
  reviewer asks and the one they should answer without reading. Everything else
  is plain words, because emoji everywhere is clutter.
- **`dependencies` is reused, not invented.** The repository already has this
  label. The spec's `security/dependency-modified` is a longer name for the same
  fact, and a lockfile bump is a dependency change, not a security incident —
  calling it one trains reviewers to ignore the word "security".
- **Telemetry labels read as instructions.** `needs deep dive` tells the reviewer
  what to do; `review/needs-deep-dive` tells them which team owns the namespace.
- **`area/*` is reused** for domain. `domain/frontend` would have been a second
  vocabulary for a fact the repo already names.
- **Risk tiers keep their existing names**, including the spaces, so the README
  and the label list stay consistent.
- **`ready-for-merge` is reused, and `merge-ready` is dropped.** The repo already
  has `ready-for-merge`, but `label-merge-conflicts.yml` tries to create and
  apply `merge-ready` — a near-duplicate that never existed. Repair means
  pointing the workflow at the label the repo already has, not creating a second
  one that means the same thing.


### Shape

```
.github/workflows/pr-risk.yml        # one workflow, two jobs
  job: labels
    - checkout (needed for git diff)
    - ensure-labels      -> create every managed label via gh --repo (fixes RC2)
    - compute + apply    -> python scripts/pr_labels.py (fixes RC1, RC3-5)
  job: risk              -> existing score.sh, inputs passed via `with:` (RC1)
```

- `scripts/pr_labels.py` exposes `compute_labels(facts) -> set[str]` as a pure
  function plus a `main()` that reads a facts JSON on stdin and applies the
  result. Pure function = directly testable, no mocks, no network.
- Facts are gathered with `gh pr view --json` and `gh api .../pulls/N/files`
  (paginated, capped at 300 files — the risk scorer already saturates at 400
  lines, so a cap keeps latency bounded on huge PRs). No PR code is executed.
- Label application is idempotent: remove stale labels from the managed set,
  add the desired set. Re-running on `synchronize` converges, never duplicates.

### Permissions

The `labels` job needs `contents: read` (checkout), `pull-requests: write` (set
PR labels), and `issues: write`. The last one is not obvious and is easy to miss:
GitHub's label API lives under `issues`, so `gh label create` fails with a
permissions error without it — a third way to fail silently.

### Fork pull requests

Under `pull_request`, a fork's `GITHUB_TOKEN` is read-only, so neither label
creation nor application can succeed. The job detects this and prints a notice
instead of failing red on an unlabelable PR. Every current agent pushes to a
same-repo branch, so this affects contributors only.

### Telemetry contract

The block is an HTML comment, so it stays invisible in rendered PR bodies:

```html
<!-- AGENT_METADATA
{"has_breaking_changes": false, "agent_confidence": "high"}
-->
```

`compute_labels` reads `has_breaking_changes` (bool) and `agent_confidence`
(`high|medium|low`). Anything else is ignored; unparseable JSON yields
`agent/malformed-metadata`.

`.github/pull_request_template.md` gains this block as an optional, commented-out
snippet, so agents have a documented place to declare it. Without that, the
parsing path stays unreachable — see root cause 5.

### Failure behaviour

- Malformed `AGENT_METADATA` → `agent/malformed-metadata`, run continues.
- Missing metadata → no telemetry labels, run continues.
- A label write that genuinely fails → step fails loudly.
- Every computed label is echoed to the job summary so a reviewer can see why.

## Verification plan

- `tests/scripts/test_pr_labels.py` — unit tests over `compute_labels` for:
  size boundaries (49/50/249/250/799/800/1999/2000), dependency detection,
  valid/malformed/absent metadata, domain mapping for real repo paths,
  provenance for the branch patterns above.
- `tests/scripts/test_pr_labeler_workflow.py` — structural assertions that the
  workflow passes `with:` inputs to the composite action, declares the needed
  permissions, and creates labels with `--repo`. This is the regression guard
  for root causes 1 and 2.
- `uv run pytest` green.
- Live check after merge: open a PR and confirm labels appear.
