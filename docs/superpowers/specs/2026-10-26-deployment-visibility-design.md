# Deployment Visibility — Design

Date: 2026-10-26
Status: proposed, awaiting approval

## Intent

Make the repository's **GitHub → Deployments** page a trustworthy inventory of what
is live, where, and as of which release — so a visitor can click through to a running
surface, and a maintainer can read the history and know what shipped without opening
four dashboards.

The request that started this: *"Deployments need to be tagged up properly. Currently
we can only see 'github-pages' 2 days ago."*

## What is actually wrong (evidence)

Two separate problems are tangled together. The visible symptom is the second one.

### 1. The Pages deploy has been broken since 2026-10-24 19:39

The Deployments UI is not stale — it is **correct**. It shows the last Pages deploy
that *succeeded*, because nothing has succeeded since.

| Time (UTC, 2026-10-24) | Event |
|---|---|
| 19:08 | `#215` *chore(site): retire the unused root index.html* — deletes `website/index.html` (the site is generated now) |
| 19:37 | **Last successful Pages deploy** (the "2 days ago" entry) |
| 19:39 | `#201` *ci: add Pages pre-deploy safety gate* — adds a gate requiring `website/index.html` to exist |

The gate was written against a file that `#215` had already deleted 31 minutes
earlier. Every push to `main` since dies in `build` at:

```
##[error]Missing or empty critical file: website/index.html
```

95 Pages runs in the window, 47 successful lifetime, the most recent success being
2026-10-24T19:37:30Z. The site itself is healthy: `build_site.py --out _site` builds
25 files locally with valid `index.html`/`404.html`, and all 248 website tests pass.
The live site still returns 200 because Pages is holding the last good artifact.
**Nothing new has shipped to Pages in two days, and nothing will until the gate is
corrected.**

### 2. Three of the four deploy surfaces create no deployment record at all

The Deployments UI lists *deployment records*, and those exist only when something
calls GitHub's Deployments API. Today exactly one thing does.

| Surface | Ships via | Creates a record? |
|---|---|---|
| Project site | `pages.yml` → `actions/deploy-pages` | Yes — environment `github-pages` (currently broken, see above) |
| Hosted Studio | Cloudflare Workers Builds (runs inside Cloudflare) | No — posts a check run only |
| Hosted MCP server | Prefect Horizon (external) | No |
| Releases + desktop bundles | `release.yml`, `tauri-release.yml` | No — Releases ≠ Deployments |

Verified: the repo has exactly **one** environment (`github-pages`) and **one**
deployment record. `GET /deployments?environment=studio` returns `[]`. The Cloudflare
build does surface as a check run, `Workers Builds: agentic-odi`, carrying a build ID,
a Version ID, and a dashboard URL — which is the observable signal we can build on.

### 3. Found during recon: `main` is red, which stalls releases

Not the reported symptom, but it is upstream of it. The latest CI run on `main`
(`7d48b8d`) fails `lint`, `typecheck`, `test (3.10/3.11/3.12)`, and therefore
`CI green`, because of a genuine bug:

```python
# apps/studio-api/src/agentic_odi_studio_api/studio/router.py:338
raise HTTPException(status_code=400, detail="job_id is required for the mcp backend")
```

`HTTPException` is not imported (the module imports `APIRouter, Query, Request` from
`fastapi`), and every other 4xx in the file goes through `StudioHTTPError` /
`_as_http_error`. Reproduced locally: 2 failed, 19 passed. Because release-please arms
auto-merge only when CI is green, and the release PR inherits `main`'s red, **releases
are stalled** — which is part of why the "what was released" story is not updating.

## Goals

1. Pages deploys again, and its deployment record flows on every push to `main`.
2. Every deploy surface that this repository can *verify* appears in the Deployments
   UI, under a stable, meaningful environment name, with a success/failure status, a
   description naming what shipped, and a link to the live thing.
3. A maintainer reading the page can tell what is live and as of which release,
   without leaving GitHub.
4. Each claim on the page is backed by something the repository actually observed.

## Non-goals

- Building a status dashboard, badge, or site page for deployments.
- Adding deploy tooling for Cloudflare or Prefect, or moving their deploys into
  GitHub Actions. Their deploy remains where it is.
- Changing the Pages publish path (`upload-pages-artifact` → `deploy-pages`), which is
  covered by its own contract tests.
- Reporting on pull-request previews (ephemeral; the Cloudflare PR comment stays the
  source of truth, per `docs/deployment.md`).

## Anti-goals (what would make this a failure even if it works)

- **A record that claims more than we observed.** A deployment entry that says
  "deployed" when the repository only knows "the endpoint answered" is worse than no
  entry: it makes the whole page untrustworthy. Every description must state exactly
  what was verified.
- **Noise.** A record per push for a surface that does not deploy per push buries the
  signal. Records are created only when the corresponding surface actually changes.
- **A second source of truth.** The Deployments page must not contradict
  `docs/deployment.md` or the Cloudflare PR comment.
- **Fixing the symptom only.** Correcting the Pages gate without recording the other
  surfaces leaves the original complaint half-answered.

## Constraints

- **The Pages environment name is effectively fixed.** `actions/deploy-pages` creates
  its record in the environment named by the job's `environment:` key; its README says
  the deployment *"should target the `github-pages` environment (you may use a
  different environment name if needed, but this is not recommended)"*. The existing
  `github-pages` environment also carries a branch protection policy. Fighting this for
  a cosmetic name is not worth the risk.
- **Cloudflare and Prefect deploy outside GitHub Actions.** A workflow cannot wrap
  them. It can only *observe* them (Cloudflare) or *probe* them (Prefect).
- **The MCP endpoint is auth-gated** (returns 401), so its served *version* is not
  observable — only reachability.
- Writing deployment records requires `deployments: write` on the workflow token.

## Decisions

Marked **[my call]** where I chose rather than being told.

| # | Decision | Rationale |
|---|---|---|
| D1 | **[my call]** Do both: fix the Pages gate *and* record all four surfaces. | The complaint is "we can only see github-pages". Fixing only the gate answers half of it. |
| D2 | **[my call]** Name environments by **product**, not by stage. | The page should read as an inventory of live surfaces (`studio`, `mcp`, `release`), which is what a visitor wants. A stage axis (`production`/`preview`) has one meaningful value here, so it would be a column of noise. |
| D3 | **[my call]** Keep the site's environment as `github-pages`. | Platform-forced and protected; renaming risks the publish path for no reader benefit. It is the one exception to D2, and the design documents why. |
| D4 | **[my call]** The Studio record is created by *observing* the Cloudflare Workers Builds check run on the same SHA. | It is the only honest signal available, and it is verifiable. |
| D5 | **[my call]** The MCP record is created on release tags, and its description states it attests **reachability**, not a deploy. | The deploy is managed in Prefect Horizon and is not observable here. A precisely-labelled record adds value; a vague one would be a lie. **This is the weakest claim in the design — flagged for review, easy to drop.** |
| D6 | **[my call]** Releases get their own `release` environment on tag. | The user's stated intent is "as per what was released". A desktop/CLI release genuinely ships to users. |
| D7 | **[my call]** Fix the `router.py` `HTTPException` bug as a prerequisite. | It blocks `CI green` → blocks release-please auto-merge → blocks releases → blocks the very history this feature surfaces. |
| D8 | **[my call]** One reusable recorder script + per-workflow calls, rather than bespoke inline `curl`. | One mechanism, one place to test, consistent descriptions. |

## Design

### Environments

| Environment | Surface | Trigger | Status reflects | Link | `ref` |
|---|---|---|---|---|---|
| `github-pages` | Project site | push to `main` | Real Pages deploy (unchanged, `deploy-pages`) | site URL | `github.sha` |
| `studio` | Hosted Living Studio (Cloudflare Worker) | push to `main` | Cloudflare Workers Builds check run for that SHA | Worker production URL | `github.sha` |
| `mcp` | Hosted MCP endpoint (Prefect Horizon) | release tag | Reachability probe at release time | MCP endpoint | the tag |
| `release` | Published CLI/desktop release | release tag | Release job outcome | GitHub Release page | the tag |

`github-pages` is produced by `actions/deploy-pages` and is left alone. The other
three are produced by the recorder below.

The `ref` column matters: it is what the UI links a record to, and it is what makes a
record supersede the previous one for that environment. Pinning `studio` to the commit
SHA (not the branch) keeps each record tied to the build it describes.

### The release record and the desktop bundles

`release.yml` and `tauri-release.yml` both trigger on a `v*` tag and run concurrently.
`release.yml` publishes the CLI, installers, and `checksums.txt`; `tauri-release.yml`
attaches the desktop bundles and can run for up to 90 minutes. A `release` record
written at the end of `release.yml` would therefore be true about the CLI and
installers but premature about the bundles.

**[my call]** One record per tag, written by `release.yml`, whose description claims
only what that workflow verified, and whose link is the Release page — which is the
living, always-current list of assets. This satisfies anti-goal 1 (state exactly what
was verified) and anti-goal 2 (one record, not a race between two workflows). A second
record from `tauri-release.yml` was rejected: it would double-report one release and
could mark the environment failed for a signing-key problem that does not affect the
CLI.

### Description format

Descriptions are the part a maintainer actually reads, so they are specified, not
improvised:

| Environment | Description |
|---|---|
| `studio` | `Hosted Studio — main@<sha7> (Cloudflare build <build7>)` |
| `mcp` | `Hosted MCP endpoint — <version>: reachable (deploy managed in Prefect Horizon)` |
| `release` | `Release <tag> — CLI, installers, and desktop bundles` |

`github-pages` descriptions stay `null`: `deploy-pages` does not accept one, and adding
a duplicate record alongside it would be a second source of truth (anti-goal 3).

### Mechanism

A single script, `scripts/record_deployment.py`, that:

1. Creates a deployment: `POST /repos/{repo}/deployments` with `ref`, `environment`,
   `description`, `auto_merge: false`, and `required_contexts: []`.
2. Immediately sets its status: `POST /repos/{repo}/deployments/{id}/statuses` with
   `state` (`success` | `failure` | `error`), `description`, and `environment_url`.

It takes the values as CLI flags, reads `GITHUB_TOKEN` and `GITHUB_REPOSITORY` from the
environment, and exits non-zero on API failure. Following the `scripts/ci_release.py`
convention, it is importable and unit-tested without network access.

Creating a deployment then a status is deliberate: a deployment with no status shows as
pending forever in the UI, which would violate the "trustworthy" goal.

`required_contexts: []` is deliberate too. The default is to require the repository's
branch protection checks, and a deployment created for an already-merged SHA would
otherwise be rejected. `auto_merge: false` stops GitHub from merging anything on our
behalf.

### Failure semantics

Two different things can go wrong, and they must not be conflated:

| Situation | Record | Workflow |
|---|---|---|
| The surface deployed, but the deploy failed | status `failure` | succeeds |
| The surface is fine, but we could not record it | none (plus `::warning::`) | succeeds |
| The surface deployed successfully | status `success` | succeeds |

**The recorder never fails `main`.** A missing or failed deployment record is a
reporting gap, not a broken build, and failing `main` for it would block the releases
this feature exists to surface. The recorder exits non-zero on API failure (so the
workflow log shows it clearly) and the calling step is marked
`continue-on-error: true` with a `::warning::` annotation. The failure is visible; the
branch stays green.

This is a deliberate trade-off: it means a permanently broken recorder would go
unnoticed by branch protection. The mitigation is that the warning appears in the run
summary of every affected push, and the contract test asserts the recorder is wired up.

### Workflow changes

**`pages.yml` — fix the gate (the urgent fix).**

Replace the critical-file list with files that exist and are genuinely critical, and
re-assert the real contract in the same step:

- Remove `website/index.html` (retired by `#215`; the site is generated).
- Keep `.github/workflows/pages.yml`, `website/tools/build_site.py`,
  `website/tests/test_pages_deploy.py`.
- Add `website/templates/landing.html` and `website/content/landing.json` — the
  generated `index.html` cannot exist without them, so their absence is the true
  failure condition.

The existing "Verify the built site is non-empty" step already checks the *built*
`_site/index.html`, which is the correct place to assert the output. The gate keeps its
job (fail before an expensive build) without asserting a file that was intentionally
removed.

`.ci/protected-files.txt` lists `website/tools/build_site.py` and
`website/tests/test_pages_deploy.py`, which this change keeps, so it needs no edit. The
two added paths are inputs to the build rather than deploy machinery; adding them to
the protected list is reasonable but out of scope here — the new gate test already
fails red if a gate path is missing, which is the protection that was actually absent.

**New `.github/workflows/deployment-status.yml` — record `studio`.**

- Trigger: `push` to `main`, plus `workflow_dispatch`.
- `permissions: deployments: write, contents: read, checks: read`.
- `concurrency: {group: deployment-status-${{ github.ref }}, cancel-in-progress: true}`.
- Steps: resolve the Cloudflare Workers Builds check run for `github.sha` (via
  `GET /repos/{repo}/commits/{sha}/check-runs`, filtering on the
  `cloudflare-workers-and-pages` app); poll it with a bounded timeout, because the
  build may still be running when this workflow starts; then call the recorder with the
  resulting state, the Worker URL, and the Cloudflare build ID.
- If no Cloudflare check run appears within the timeout, **record nothing and exit 0,
  but emit `::warning::`**. This workflow reports; it must not fail `main` for a
  Cloudflare hiccup, and it must never invent a record.

The warning is load-bearing. A silent skip would reproduce the exact problem this
design exists to fix: a surface that is deployed but invisible, with nothing on the
page or in the logs saying why. A maintainer must be able to distinguish "no record
because Cloudflare did not build this SHA" from "no record because this workflow is
broken". The `studio` environment therefore has a documented bootstrap path (see
Prerequisites) so it is visible on the page before the first observed build.

**`release.yml` — record `release` and `mcp`.**

Add one job, `deployment-status`, `needs: [release-instructions]`, so it runs once per
tag after the release is fully assembled:

- Record `release` with the tag and the Release URL.
- Probe the MCP endpoint; record `mcp` as `success` on any HTTP response (the endpoint
  is auth-gated, so 401 means up), `failure` on connection error, with the D5 wording.

### Tests

| Test | Asserts |
|---|---|
| `tests/scripts/test_record_deployment.py` (new) | The recorder builds the right deployment and status payloads, maps states correctly, and surfaces API errors. Network is stubbed at the HTTP-client boundary, not by mocking the logic under test. |
| `website/tests/test_pages_deploy.py` (extend) | Every path in the Pages critical-file gate **exists in the repository**. This is the regression guard for the exact failure found here: a gate must not assert a file that is not there. |
| `tests/contract/test_deployment_contract.py` (new) | Each workflow that deploys declares `deployments: write` and calls the recorder; the environment names in the workflows match the documented set; `ci.yml` still never deploys. |

The `test_pages_deploy.py` addition is the important one — it would have caught this
breakage at PR time, and it generalises to any future gate edit.

### Documentation

Per the repository's README-maintenance rule:

- `docs/deployment.md`: add a **Deployments** section — the environment table, what
  each record attests (especially D5's reachability caveat), and how to read the page.
- `README.md`: extend the Deployment row's description to mention the Deployments
  inventory.
- Note in `docs/deployment.md` that `github-pages` is platform-named (D3).

## Prerequisites

Ordered. Steps 1–2 are the urgent fixes; steps 3+ build the feature.

1. **Fix the Pages gate** (restores deploys within minutes of merging).
2. **Fix `router.py:338`** (D7) so `main` goes green and release-please can merge again.
3. **Create the `studio`, `mcp`, and `release` environments.** Deployment records can
   be created for an environment that does not exist yet, but the UI groups and filters
   better once they are named, and an existing environment is what makes the surface
   visible on the page *before* the first observed deploy — the bootstrap path for the
   silent-skip case above. `gh api` or the Settings UI. **[my call]** Start without
   protection rules, matching the repo's current single-environment setup; confirm
   before adding branch policies.
4. **Merge the recorder, workflows, and tests** (they are inert until a matching event
   fires, so this can land before the environments exist).

Steps 1 and 2 are independent of each other and of the rest, and each restores
something currently broken. If the maintainer wants the fastest possible relief, they
can take 1 alone.

## What is left to the builder

- The exact polling interval and timeout for the Cloudflare check run (start: 15s
  interval, 15min cap, matching the build's `timeout-minutes`).
- Whether the Cloudflare check run is reliably present for a given SHA; if it is not,
  D4 needs revisiting.
- Where the recorder lives if `scripts/` gains a package structure.
- Whether `mcp` should also be recorded on push to `main` — deliberately excluded here
  to avoid noise (anti-goal 2), but it is the natural extension if Horizon is found to
  deploy per-push.

## Flagged for review

1. **D5 (the `mcp` record).** It attests reachability, not a deploy. If that is too
   loose, drop it and the design still holds with three environments.
2. **D7 (the `router.py` fix).** Adjacent to the deployment work; included because it
   blocks the release pipeline that feeds the Deployments history. Declinable.
3. **D3 (`github-pages` name).** Accepts platform naming in an otherwise
   product-named set. The alternative is riskier and buys little.
