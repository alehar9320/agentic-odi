# Issue #612 — prove the first run on the URL visitors actually open

Branch `qoder/612-hosted-first-run`, worktree `qoder-612-hosted-run`, claim label
`qoder/2026-11-04-612`.

## Baseline, measured 2026-11-04T20:51Z

```
git show origin/main:infra/cloudflare/worker.ts | grep -c sidecar_unavailable  → 0
GET  /api/capabilities   local-data / local-memory / deterministic-assistant available: true
POST /api/jobs           502 {"error":{"code":"mcp_unreachable", ...}}      ← promise 2 FAILS today
GET  /api/canvas         502 {"error":{"code":"mcp_unreachable", ...}}      ← promise 2 FAILS today
GET  /                   serves assets/index-BttJPD52.js
GET  /api/build          200 {"version":"0.14.0"}
GET  /api/deploy         502 mcp_unreachable  (route does not exist yet)
```

`#492`/`#609` are still not on `main`, so the probe cannot be green today. Step 6 of the
issue makes that the finding: the PR carries the failing run, never a pass.

## Design decisions (and why)

1. **`/api/deploy` extends, not duplicates, `/api/build`.** The Worker already answers
   `GET /api/build` with `env.RELEASE_VERSION` before the sidecar proxy
   (`infra/cloudflare/worker.ts:204`, pinned by `tests/test_worker_build_route.py`), and
   `docs/deployment.md:234` deliberately says that value is a tag and *never* a deploy
   timestamp. A tag cannot answer "did the merge reach the deploy?", so the new route adds
   the two facts the build route omits — `build_id`, `commit` — plus `entry`, the asset file
   the Worker's own bundle serves, which is what step 3 compares against `GET /`.
   Reuse ladder: rung 1 reuses the existing route's position (before the proxy), its
   GET-only 405 handling, its `no-store`, and its source-inspection test style.
2. **Commit identity comes from the deploy command, not from a platform guess.** No code in
   this repository currently reads a Cloudflare-provided commit variable, and there is no
   evidence in the docs that Workers Builds exposes one. `wrangler.jsonc` therefore declares
   `BUILD_ID` and `COMMIT_SHA` as `"unknown"` vars, and `docs/deployment.md` states the
   dashboard deploy command that fills them:
   `npx wrangler deploy --var COMMIT_SHA:$(git rev-parse HEAD) --var BUILD_ID:$(git rev-parse --short HEAD)`.
   The route is real and tested; the wiring is one dashboard edit the owner controls. Until
   it is set, the probe reports production's believed commit as `unknown` and the comparison
   fails with both values shown — a failure with a date and a name, which is the point.
3. **The script takes the expected commit as an argument instead of running git.** Keeps the
   bash script testable from Python without a repository, and makes the CI job state
   explicitly which SHA it believes it is comparing against.
4. **A non-production target is never a pass.** The base URL defaults to
   `https://agentic-odi.alehar.workers.dev`; `--base-url` exists for the test's stub server
   and, when it is not the production host, the script prints a `NON-PRODUCTION TARGET`
   banner and labels every line `informational`. The string of a preview host never appears
   in the script or in the job.

## Steps, in TDD order

1. `tests/scripts/test_verify_hosted_first_run.py` (RED first, then the script).
   The test runs `bash scripts/verify-hosted-first_run.sh` against a stub `http.server` with
   canned production-shaped responses and asserts: one dated `PASS` line per named promise
   and exit 0 on the good fixture; a `FAIL` line naming the promise, the offending body
   printed, and exit 1 when `/api/jobs` answers `mcp_unreachable`; `FAIL` with both commits
   shown when the reported commit disagrees with `--commit`; `FAIL` when the asset named by
   `GET /` is not the asset the deploy reports; refusal of a capability that reports
   `available: false`; the `NON-PRODUCTION TARGET` banner for a stub host; and a source guard
   that the script names only the production host and uses `set -euo pipefail` with `curl`
   and `jq`.
2. `tests/test_worker_deploy_route.py` (RED), then `infra/cloudflare/worker.ts` +
   `wrangler.jsonc` (GREEN): route answered before the sidecar proxy, GET-only, `no-store`,
   `BUILD_ID`/`COMMIT_SHA` declared on `Env`, and the vars present in `wrangler.jsonc` so the
   `--var` override has something to override.
3. The bundle comparison check folded into the script from step 1's assertions (no second
   pass over the file).
4. `.github/workflows/ci.yml`: a `hosted-first-run` job on
   `if: github.event_name == 'schedule' || github.event_name == 'workflow_dispatch'`, kept
   out of `ci-green`'s `needs:` beside `pr-body` and `updater-e2e`, with `curl`/`jq` from the
   runner image, the job failing loudly (`::error::` lines and the run log uploaded as an
   artifact on failure), and the `schedule` comment at line 11 corrected — it currently
   claims `updater-e2e` is the only job that reacts to the event.
5. `docs/deployment.md`: name the probe, what each check protects, where its output lives,
   and the deploy-command edit that fills the identity. `scripts/doc_check.py` must pass.
6. Record the real run against production in the PR body — expected red, and that is the
   finding.

## Out of scope (the issue says so)

Browser→sidecar reconciliation (#306), capability copy (#326/#507), any model key, and
promoting a preview URL into documentation.
