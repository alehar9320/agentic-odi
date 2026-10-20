# User-Facing Auto-Generated Changelog — Design

**Date:** 2026-10-18
**Status:** Approved (design session `ses_ebea76e4dffeNzxhwoqkB40AW5`, user decisions binding)
**Scope:** Release-time AI changelog generation with grounding guardrails, GitHub Release delivery, `odi changelog` CLI surface, commit/branch/semver standard + enforcement

## Intent & Why

When a user updates agentic-odi — or decides whether to — they need one thing: a complete, plain-language account of what changed **since the version they last ran**, so they can judge the value and act. Today there is no changelog at all: no tags, no release notes, and PR #8's release-please config would commit a developer-facing `CHANGELOG.md` that (a) is written in commit-speak, not user language, and (b) is a merge-conflict magnet.

Jobsian bar: the user never reads a commit. They type one command (`odi changelog`) — or see one hint line after an upgrade — and get professionally written, value-focused entries that cover **every user-visible change** in their gap, each provably grounded in the actual release commits (no hallucination), with an honest AI disclaimer. Fully automated end to end; the guardrails, not a human gate, are the safety mechanism.

## User-Facing Audience & Voice

- **Audience:** the person who installs/uses agentic-odi (not contributors, not release engineers).
- **Voice:** professionally written, value-focused, second person, no developer-speak. Never show branch names, scopes, PR numbers, raw commit subjects, or SHAs in the default view (SHAs exist only as machine-readable citations in `changelog.json`).
- **Example of the rewrite we expect:**
  - Commit: `fix(cli): require Python 3.11 to match StrEnum usage`
  - Entry: `Fixed startup on machines running Python 3.11 or newer.`
- Every entry answers "what do I gain?" — new capability, improved behavior, or a fix I'd care about.

## Goals

1. Auto-generated user-facing changelog, produced **at release time**, included **in the release** (body + asset), never as a committed source file.
2. Complete coverage: every user-visible change since the user's last seen version appears — no gaps, no silent drops.
3. Grounded AI rewrite: structured output with per-entry commit-SHA citations, validated fail-closed against the commit range (no hallucinated SHAs, features, versions, or identifiers).
4. AI disclaimer on every release and in `changelog.json`.
5. Conventional Commits + Conventional Branches + semver tags enforced (standard + tooling), so the generator has reliable input.
6. Minimal runtime surface: `odi changelog [--since VERSION] [--all] [--json]`, fetching notes from GitHub Releases; GUI (Streamlit client) reuses the same core module later.

## Non-Goals / Anti-Goals

- **No committed `CHANGELOG.md`** — this supersedes PR #8's release-please default behavior (`skip-changelog: true`; see "Release workflow integration").
- No raw commit-log dump presented to users; no developer changelog as the user-facing artifact.
- No LLM call in the shipped CLI/GUI — generation is release-time only; runtime only fetches and renders.
- No routine human review step in the release happy path ("fully automated" honored); humans are involved only when a guardrail trips (fail-closed draft) or during recovery.
- No requirement that contributors write user-facing prose in commits (the AI owns the rewrite).
- No bundling full release history into the binary; no i18n scope; no per-commit entries for hidden commit classes.

## The Standard (input quality)

### Commits — Conventional Commits

`type(scope): subject`, optional `!` or `BREAKING CHANGE:` footer.

- Types: `feat`, `fix`, `perf`, `refactor`, `docs`, `test`, `build`, `ci`, `chore`, `revert`, `style`.
- Scopes: package names (`cli`, `client`, `connectors`, `core`, `mcp_server`, `local_server`) plus `ci`, `deps`, `release`, `workspace`.
- PR titles must follow the same form (squash merges make the PR title the commit on `main`).
- Enforcement: `core.convention` module → pre-commit `commit-msg` hook (local), CI `convention` job (PR title on `pull_request`, head-commit subject on `push`; merge commits exempt).

### Branches — Conventional Branch

Allowed prefixes (kebab-case, single level): `feature/`, `fix/`, `hotfix/`, `chore/`, `docs/`, `refactor/`, `test/`, `release/`, and `topic/` (documented legacy alias of `feature/`, from the project's existing `topic/*` habit). Exempt from checks: `main`, `dependabot/*`, `renovate/*`, `release-please*`, `worktree/*`, `superpowers/*`. Enforced in CI on every PR head ref (no local branch hook — documented convention only).

### Tags / semver

`vX.Y.Z`. Breaking → major, `feat` → minor, else patch; **`bump-minor-pre-major: true`** (pre-1.0 breaking changes bump minor, not jump to 1.0). Engine: **release-please** (kept from PR #8 — see reconcilation below).

### What "complete" honestly means

- **Coverage-required** (must be cited by ≥1 entry or validation fails): types `feat`, `fix`, `perf`, `revert`, and any commit with `!`/`BREAKING CHANGE:`.
- **Hidden from users** (never required; omitted unless clearly user-value-bearing): `chore`, `ci`, `build`, `test`, `docs`, `style`, and `deps` (a `chore(deps)` scope). Their omission is not a gap — they are not changes *to the user's product*.
- **Eligible but optional**: `refactor` (AI may surface it under Improved when the commit states a user benefit; absence never fails validation).
- **Exempt**: merge commits (excluded from the manifest entirely) and commits whose subject doesn't parse as conventional (the pre-standard legacy minority — 13 of 64 today). "Complete" = complete over changes **expressed in the standard**; legacy commits may be surfaced opportunistically but are not gateable.

## Data Pipeline

```
commits on main (Conventional Commits, squash-merged)
        │
        ▼
release-please  ──►  Release PR (semver decision) ──merge──►  tag vX.Y.Z
        │                                                      + DRAFT GitHub Release
        │ chained job (same workflow, output-gated on releases_created=true)
        ▼
① manifest:  git log prev-tag..tag  (sha, subject, body≤600c, type/scope/breaking, files≤50)
        ▼
② AI rewrite: pinned model, temperature 0, JSON-mode, prompt = docs-in-repo prompt.md
        ▼
③ guardrails: schema + cited-SHA existence + coverage + grounding checks (fail-closed, exit 2)
        ▼
④ emit:      changelog.json (schema-validated) + changelog.md (release body) + manifest.json (audit)
        ▼
⑤ publish:   gh release upload changelog.json  →  gh release edit --notes-file changelog.md --draft=false
              (any failure above ⇒ release stays a draft; nothing broken ships half-annotated)
        │
        ▼
release.yml (PR #8) builds binaries & attaches assets
        │
        ▼
runtime:  odi changelog  ──fetch──►  GitHub Releases API  ──►  changelog.json assets
          since last-seen version ► rendered plain-language "What's new" + AI disclosure
```

Delivery is **fetch-from-GitHub-Releases** (user decision): the binary stays lean; the CLI (and later the Streamlit GUI) computes the gap between the last version whose notes were shown and the installed version.

## Grounding Guardrails Spec

### 1. Source material (the only ground truth)

The manifest is built exclusively from git: for each non-merge commit in `prev_tag..tag` (or full history in initial mode): full 40-char SHA, subject, body (truncated to 600 chars), parsed `type`/`scope`/`breaking` (or `null`), and up to 50 changed file paths. No PR descriptions, no web content, no prior changelog text enters the prompt.

### 2. Generation contract

- Provider-agnostic OpenAI-compatible chat endpoint; env: `AGENTIC_ODI_CHANGELOG_MODEL` (required), `AGENTIC_ODI_CHANGELOG_BASE_URL` (default `https://api.openai.com/v1`), `AGENTIC_ODI_CHANGELOG_API_KEY` (required online).
- `temperature: 0`, `response_format: {"type": "json_object"}`, prompt pinned in `scripts/changelog/prompt.md` with a `prompt_version` constant (bump when prompt changes).
- Prompt rules: end-user voice; only manifest information; every entry cites ≥1 source SHA (full); one sentence per entry (≤ ~200 chars); section vocabulary fixed; cover every coverage-required commit; `breaking` flag set for `!` commits; output only JSON.

### 3. Validation (fail-closed — exit code 2, release stays draft)

| # | Rule | Tier |
|---|------|------|
| G1 | Response parses as JSON and matches the schema (`changelog.json` shape) | hard |
| G2 | Every cited SHA resolves to a manifest commit (≥7-char prefix of a real SHA in range) | hard |
| G3 | Every entry has ≥1 citation; every section non-empty; ≥1 entry total | hard |
| G4 | Every coverage-required manifest commit is cited by ≥1 entry | hard |
| G5 | Section names ∈ {Initial release, Added, Improved, Fixed, Security, Removed} | hard |
| G6a | "Risky" tokens in entry text must appear in manifest text: backtick spans, `snake_case`, file paths with extensions, `x.y.z` version numbers | hard |
| G6b | `SCREAMING_CASE` tokens not found in manifest | soft (warn only) |

G6b is deliberately soft: acronyms like JTBD/MCP are common prose and a false positive must not block a release. G6a is hard: backticked code, snake identifiers, paths, and version numbers are exactly where hallucination would do damage.

**Reconciliation with "fully automated":** the happy path requires zero human touch. The safety mechanism is the fail-closed draft — generation/validation failure leaves the release as an unpublished draft with a red Actions run; the runbook (CONTRIBUTING) covers recovery (fix & rerun, or regenerate locally and attach manually). No prose review gate on every release.

**Audit trail:** `manifest.json` + the raw model response are uploaded as workflow artifacts (90 days) so any entry can be traced to its sources after the fact.

### 4. Disclaimer

Constant, used in the CLI footer and appended to every release body:

> This changelog was generated with AI from our release history.

`changelog.json` also carries `"generated_by": "ai"` and `generator: {model, prompt_version}`.

## Output Schema

`changelog.json` (one asset per release; the machine-readable contract for CLI/GUI):

```json
{
  "schema_version": 1,
  "version": "0.2.0",
  "previous_version": "0.1.0",
  "date": "2026-10-18",
  "generated_by": "ai",
  "generator": { "model": "<pinned model id>", "prompt_version": "1" },
  "disclosure": "This changelog was generated with AI from our release history.",
  "sections": [
    { "name": "Added",
      "entries": [
        { "text": "Write outcome updates from the local server.",
          "sources": ["<full 40-char sha>", "..."],
          "breaking": false }
      ] }
  ]
}
```

- `previous_version`: `null` for the initial release. `date`: UTC `YYYY-MM-DD`.
- `sources` are builder details: SHAs tying every sentence to the commits it came from; hidden from default rendering, shown in `--json`.
- Release body (markdown) = per-section `### Section` + `- text` bullets (`- **Breaking change:** text` when flagged), blank line, italic disclosure. No SHAs in prose.

## Release Workflow Integration (reconciling with PR #8)

PR #8 (release-please + self-update) is the semver/tag authority and stays. It is amended, not replaced:

1. `release-please-config.json` (package `.`) gains:
   - `"skip-changelog": true` — release-please never writes a `CHANGELOG.md` (dissolves the merge-conflict concern; `.release-please-manifest.json` remains a tiny, conflict-light version marker, not a changelog).
   - `"draft": true` + `"force-tag-creation": true` — releases are born drafts (GitHub doesn't tag drafts until publish; `force-tag-creation` makes the tag immediately so ranges resolve).
   - `"bump-minor-pre-major": true`.
2. `.github/workflows/release-please.yml` gains a chained `changelog` job (`needs: release-please`, `if: releases_created == 'true'`, step `id: release-please`): checkout `fetch-depth: 0` → `generate.py --tag $TAG` → upload `manifest.json` artifact → `gh release upload` → `gh release edit --notes-file changelog.md --draft=false`. Publishing is the last step, so **failure ⇒ draft stays** (the fail-closed gate).
3. **Why chained, not event-triggered:** release-please creates tags/releases with `GITHUB_TOKEN`; per GitHub's recursion prevention (and release-please's own README), those resources do **not** trigger other workflows. A chained job in the same workflow is immune to this.
4. **Cross-plan gap flagged for PR #8:** its `release.yml` (tag push) and `e2e-install.yml` have the same suppression problem and may never fire. Remediation included in Task 4: `token: ${{ secrets.RELEASE_PLEASE_TOKEN || github.token }}` on the release-please action (PAT enables downstream triggers; also gets CI running on release PRs). Ops prerequisite documented, not code-blocking.
5. Ordering: draft release + tag → changelog generated/validated/published → asset builds attach to the now-public release. If builds land first (race), they attach to the draft — invisible until publish; harmless.

**Ops prerequisites:** repo secrets `AGENTIC_ODI_CHANGELOG_MODEL`, `AGENTIC_ODI_CHANGELOG_API_KEY`, optional `AGENTIC_ODI_CHANGELOG_BASE_URL`; optional `RELEASE_PLEASE_TOKEN` PAT; branch protection requiring `CI green` + `convention`; squash-merge-only merge setting (repo settings, manual).

## Runtime UX

### `odi changelog`

```
odi changelog                 # everything since the last version whose notes were shown
odi changelog --since 0.1.0   # explicit lower bound (exclusive)
odi changelog --all           # every published release with notes
odi changelog --json          # machine-readable array of changelog.json objects
```

- **State:** `last_changelog_version` added to PR #8's `update.json` (`paths.state_file()`, under the install root). It advances **only after notes are displayed** — that is how "no gaps" and "since the version you last ran" are reconciled: the marker remembers the version whose changes the user last *saw*, so skipped versions accumulate instead of being silently marked read. Missing marker (fresh install) ⇒ show all available releases once, then set the marker. `--since` is ad-hoc and does not move the marker.
- **Hint:** on a TTY, ordinary commands print one line when the marker exists and is behind the running version: `New in v0.2.0 — run '<prog> changelog' to see what changed.` (skipped for `changelog`/`version`/`update`, non-TTY, `--version`). After a successful `odi update`, append: `Run '<prog> changelog' to see what's new.`
- **Fetch:** `GET /repos/alehar9320/agentic-odi/releases?per_page=100` (prereleases skipped), then each release's `changelog.json` asset via its `browser_download_url`; malformed/missing assets are skipped per release. Injectable fetch callable (stdlib `urllib`, no new deps); 10s timeout; `User-Agent: agentic-odi-changelog`.
- **Copy (exact):**
  - header: `What's new since v0.1.0` / `All published releases`
  - no gap: `You're up to date — no changes since v0.1.0.`
  - nothing published: `No published releases yet.`
  - empty release: `  (No user-facing changes.)`
  - fetch failure: `Couldn't fetch release notes — check your connection and try again.` (exit 1, no traceback)
  - invalid `--since`: `Invalid version: <x>` (exit 1)
  - footer (once, at end): the disclosure constant.
- **Rendering:** plain text, no ANSI, sections in fixed order (Initial release → Added → Improved → Fixed → Security → Removed), empty sections omitted, entries as `  • text` with `Breaking change: ` prefix when flagged.

### Future GUI

`core.changelog` (models, fetch, range, render) is the shared module; the Streamlit client calls it unchanged. Out of scope here beyond keeping the module GUI-ready.

## Backfill Strategy (0.1.0 "Initial release")

- No tags exist yet; history is 64 commits, 51 conventional, 5 merge commits, 13 non-conforming.
- When release-please cuts `v0.1.0`, `generate.py` finds no previous `v*` tag ⇒ **initial mode** automatically: manifest = full history (`git log v0.1.0`), merge commits excluded, bodies truncated harder (subjects + files only beyond 200 commits — cheap token discipline).
- Prompt variant: the single section is **"Initial release"** — highlights of what the product does for the user, each entry still citing real SHAs. Coverage gate applies only to parseable `feat/fix/perf/revert` commits (the legacy non-conforming minority is exempt, per the honest definition above).
- If generation fails on first release: runbook path — regenerate locally with the same script, `gh release upload` + `gh release edit --draft=false`.

## Review Focus (likely to bite)

1. **Silent stuck draft** (secret missing / validation failure): red Actions run on the release job + runbook recovery documented; publish is always the last step. (Tasks 4, 6)
2. **GITHUB_TOKEN suppression** breaks tag/release-event triggers — chained job is safe; PR #8's `release.yml` gap flagged with PAT remediation. (Task 4)
3. **Coverage gate false-fails on messy history**: merge commits and unparseable legacy subjects are exempt; verified against the real repo history by the local harness. (Task 3)
4. **Grounding heuristic false positives** block releases: hard/soft split (G6a/G6b) + soft tokens only warn. (Task 3)
5. **State clobber**: PR #8's `record_check` rewrites `update.json` wholesale and would erase the changelog marker — must merge-write. (Task 5)
6. **Range/edge behavior**: marker ≥ current, unsorted/non-semver tags, releases without assets, prereleases, `--since` invalid/out-of-range, offline mode. (Tasks 2, 5)
7. **Offline-harness drift**: fixtures are schema-validated in CI against the same pydantic models the runtime uses. (Task 3)
8. **Token budget** of the initial-release manifest (64 commits and growing): body/file caps. (Task 3)

## Resolved Questions (user decisions, binding)

1. **Prose mechanism:** fully automated AI rewrite at release time, AI disclaimer, guardrails ensuring output is grounded in source material.
2. **Branch naming:** Conventional Branch standard.
3. **Distribution:** fetch from GitHub Releases — CLI (later GUI) computes all changes since the version the user last ran.

## Builder Calls (made in this design)

1. **Semver engine kept = release-please** (PR #8), amended with `skip-changelog` / `draft` / `force-tag-creation` / `bump-minor-pre-major`; no replacement tag tool. Changelog generation is chained into its workflow because GITHUB_TOKEN-created releases don't trigger other workflows.
2. **Human publish gate → fail-closed draft:** "fully automated" is honored (nothing to review per release); the safety mechanism is validation-failure ⇒ draft never publishes.
3. **Code layout:** models/range/fetch/render live in `core/src/core/changelog.py` (shared with future GUI, stdlib fetch, injectable); generator + guardrails live in `scripts/changelog/` (release-time only, stdlib-only, no workspace deps added).
4. **Marker semantics:** `last_changelog_version` advances only on display (reconciles "since the version you last ran" with the no-gaps requirement); hint line bridges the gap in between.
5. **"Builder details"** = commit/build metadata consumed by the pipeline: parsed type/scope/breaking + per-entry SHA citations + `version`/`previous_version`/`date`/`generator` in `changelog.json`.
6. **Coverage rule set:** required = `feat/fix/perf/revert` + breaking; hidden = `chore/ci/build/test/docs/style/deps`; `refactor` eligible-optional; merges + unparseable legacy exempt.
7. **Exempt branch prefixes** for CI: `dependabot/`, `renovate/`, `release-please*`, `worktree/`, `superpowers/` (so automation and tool branches don't trip the check); `topic/` allowed as a legacy `feature/` alias.
8. **Testing strategy:** generator tests live in `scripts/changelog/tests/`, run by a new step in the existing CI `test` job (no new job, `ci-green` untouched); convention/changelog-runtime tests live in `core/tests/` and `cli/tests/` (already covered).
9. **Tooling choice for enforcement:** in-repo `core.convention` module (regex + classification, unit-tested) driven by a pre-commit `commit-msg` hook and a CI job — no Node commitlint, no commitizen dependency.
10. **Squash-only merges** documented as the merge policy (PR title becomes the conventional commit); enforced via docs + branch protection (repo setting).
