# User-Facing Auto-Generated Changelog Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> Tasks 4–7 are **BLOCKED — requires PR #8 (`feature/cli-bundled-distribution`) merged** (they create/modify files that PR #8 introduces: `release-please-config.json`, `.release-please-manifest.json`, `.github/workflows/release-please.yml`, `cli/src/cli/paths.py`, `cli/src/cli/update.py`, `cli/src/cli/cli.py` root callback). Tasks 1–3 are unblocked and executable on `main` today.

**Goal:** Release-time, fully automated AI changelog written for end users — grounded in the release commits (cited SHAs, validated fail-closed), delivered as the GitHub Release body + a `changelog.json` asset (never a committed `CHANGELOG.md`), fetched by `odi changelog` to show every change since the version whose notes the user last saw — plus the Conventional Commits/Branches/semver standard and enforcement that keeps the generator's input honest.

**Architecture:** `core/src/core/convention.py` (commit/branch standard, unit-tested, driven by a pre-commit `commit-msg` hook and a CI `convention` job); `core/src/core/changelog.py` (pydantic models, GitHub Releases fetch, semver range, plain/markdown renderers — shared with the future GUI); `scripts/changelog/` (release-time tooling: `manifest.py` git-range manifest builder, `prompt.md` pinned prompt, `validate.py` guardrails, `generate.py` orchestrator with offline fixture mode); release-please amended (`skip-changelog`, `draft`, `force-tag-creation`) with a chained `changelog` job in its workflow; `cli/src/cli/changelog.py` (`odi changelog`, `last_changelog_version` state in PR #8's `update.json`, upgrade hint).

**Tech Stack:** Python 3.10–3.12, pydantic v2 (core), Typer (cli), stdlib only for generator/fetch (urllib, subprocess, argparse), pytest, ruff/mypy/bandit, GitHub Actions, release-please.

**Spec:** `docs/superpowers/specs/2026-10-18-user-facing-changelog-design.md`

## Global Constraints

- **No new workspace dependencies.** Generator and fetch are stdlib-only (`urllib.request`, `subprocess`, `argparse`). `pydantic` (core) and `typer` (cli) already exist.
- **How tooling runs** (uv `--directory` chdirs first): generator `uv run --directory core python ../scripts/changelog/generate.py …`; generator tests `uv run --directory core pytest ../scripts/changelog/tests -v`; convention module `uv run --directory core python -m core.convention …`.
- **Tests never touch the network, an LLM, or GitHub.** Generator tests use `--offline-manifest`/`--offline-response` fixtures; runtime tests inject a fake fetch callable; no real model/API key anywhere in CI.
- **Secrets only via env:** `AGENTIC_ODI_CHANGELOG_MODEL`, `AGENTIC_ODI_CHANGELOG_BASE_URL` (default OpenAI), `AGENTIC_ODI_CHANGELOG_API_KEY`. Never in the repo; fixtures use fake 40-hex SHAs (`"a"*40` …).
- **Never commit a `CHANGELOG.md`.** This plan supersedes PR #8's release-please changelog behavior via `skip-changelog: true`. `.release-please-manifest.json` (version marker) stays committed — it is not a changelog.
- **Fail-closed everywhere:** guardrail violations ⇒ exit code 2, no output files written, no `gh release edit` ⇒ release stays a draft.
- **User-facing copy is exact** per the spec (header, up-to-date, empty, failure, hint, disclosure strings). Program name via `Path(sys.argv[0]).name or "agentic-odi"` helper — never hard-code `odi` in new copy.
- **Disclosure constant** (single source, `core.changelog.DISCLOSURE`): `This changelog was generated with AI from our release history.`
- **Ruff:** line-length 100; new root `[tool.ruff]` mirrors package config so `scripts/` is covered by `uv run ruff check .` / `ruff format --check .`. Broad `except Exception` gets `# noqa: BLE001` (house style, as in `update.py`).
- **Tooling coverage (accepted, deliberate):** bandit scans package `src/` only; mypy runs per-package on `src`+tests — `scripts/` is neither bandit- nor mypy-scanned; its guardrails are the unit tests. When writing the fetch code, keep `urlopen` args as runtime variables (bandit B310 inspects literals only).
- **Python 3.10 compatibility** (CI matrix 3.10/3.11/3.12): no `tomllib`, no 3.11+ typing syntax.
- **Every task commits with a Conventional Commit message** (the standard this plan introduces).
- **Contention:** `cli/src/cli/cli.py`'s root callback is also modified by the pending first-run-onboarding plan (`--no-onboard`, `ctx` param) — keep edits minimal; whichever plan lands second rebases.
- Repo facts that shape tests: no tags exist yet (first release `0.1.0`); `cli.version.__version__` is `0.1.0` in tests (from `_build_info` on the PR #8 branch); history is 64 commits / 51 conventional / 5 merges / 13 non-conforming.

## Review Focus

Uncovered inputs/conditions most likely to bite a user — each has a test in the task that owns the code:

1. **Release stuck as draft** (missing secret or guardrail failure) — publish is always the last workflow step; runbook recovery documented. (Tasks 4, 6)
2. **GITHUB_TOKEN-created tags/releases don't trigger other workflows** — changelog job is chained in the same workflow (immune); PR #8's tag-push `release.yml` gap gets the PAT remediation. (Task 4)
3. **Coverage gate false-fails on messy history** — merge commits and unparseable legacy subjects are exempt; verified against a real tmp git repo including a merge commit. (Tasks 3, 6)
4. **Grounding heuristic false positives block releases** — hard (G6a) vs soft-warn (G6b) split, tested both ways. (Task 3)
5. **State clobber** — PR #8's `record_check` rewrites `update.json` wholesale and would erase `last_changelog_version`; merge-write with regression test. (Task 5)
6. **Range/edge behavior** — marker ≥ current, marker missing (show-all once), invalid `--since`, fetch failure (soft line, exit 1, marker not advanced), prereleases skipped, releases without assets skipped, malformed asset skipped. (Tasks 2, 5)
7. **Offline-harness drift** — fixtures validated in CI by the same pydantic models the runtime parses with. (Task 3)
8. **Token budget of the initial-release manifest** — body/file truncation in `manifest.py`; `initial` mode drops bodies beyond 200 commits. (Tasks 3, 6)

---

### Task 1: Commit/branch standard + enforcement

**Files:**
- Create: `CONTRIBUTING.md`
- Create: `core/src/core/convention.py`
- Test: `core/tests/test_convention.py`
- Modify: `.pre-commit-config.yaml` (add `commit-msg` local hook)
- Modify: `.github/workflows/ci.yml` (add `convention` job; add it to `ci-green` `needs`)

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `convention.COMMIT_TYPES: tuple[str, ...]` = `("build", "chore", "ci", "docs", "feat", "fix", "perf", "refactor", "revert", "style", "test")`
  - `convention.COVERAGE_REQUIRED_TYPES: frozenset[str]` = `{"feat", "fix", "perf", "revert"}`
  - `convention.ParsedCommit` (frozen dataclass): `type: str`, `scope: str | None`, `breaking: bool`, `subject: str`
  - `convention.parse_commit_subject(subject: str, body: str = "") -> ParsedCommit | None` — matches `^(type)(\(scope\))?(!)?: subject` with `type in COMMIT_TYPES`, scope `[A-Za-z0-9_-]+`; `breaking` is `True` when `!` present **or** `body` contains a line starting `BREAKING CHANGE:`; returns `None` for non-conforming subjects (incl. `Merge …`, legacy free-text).
  - `convention.is_conventional_title(title: str) -> bool` — `parse_commit_subject(title) is not None`.
  - `convention.is_valid_branch(name: str) -> bool` — exact `main`; exempt prefixes `("dependabot/", "renovate/", "release-please", "worktree/", "superpowers/")`; else must start with one of `("feature/", "fix/", "hotfix/", "chore/", "docs/", "refactor/", "test/", "release/", "topic/")` and the remainder must `re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*")`. (`topic/` is a documented legacy alias of `feature/`.)
  - `convention.is_coverage_required(pc: ParsedCommit) -> bool` — `pc.type in COVERAGE_REQUIRED_TYPES or pc.breaking`.
  - `convention.main(argv: list[str] | None = None) -> int` — subcommands, prints failures to stderr, returns 0/1:
    - `pr-title <title>`
    - `branch <name>`
    - `commit-subject <words…>` (join remaining args)
    - `commit-msg-file <path>` (strip lines starting `#`, first non-empty line = subject, remainder = body, then `parse_commit_subject`)

- [ ] **Step 1: Write the failing tests**

```python
# core/tests/test_convention.py
from core import convention as c


def test_parse_valid_feat_with_scope():
    pc = c.parse_commit_subject("feat(cli): add changelog command")
    assert pc is not None
    assert (pc.type, pc.scope, pc.breaking, pc.subject) == (
        "feat",
        "cli",
        False,
        "add changelog command",
    )


def test_parse_breaking_marker_and_footer():
    assert c.parse_commit_subject("feat!: drop py39").breaking is True
    pc = c.parse_commit_subject("refactor(core): reshape store", "BREAKING CHANGE: new layout")
    assert pc is not None and pc.breaking is True


def test_parse_rejects_unknown_type_merge_and_legacy():
    assert c.parse_commit_subject("wip: half done") is None
    assert c.parse_commit_subject("Merge pull request #7 from x/y") is None
    assert c.parse_commit_subject("Add CustomerOutcome entities") is None
    assert (
        c.parse_commit_subject("chore(deps): bump actions") is not None
    )  # valid, just hidden later


def test_coverage_required_rules():
    assert c.is_coverage_required(c.parse_commit_subject("fix(core): stop crash"))
    assert c.is_coverage_required(c.parse_commit_subject("feat!: new format"))
    assert not c.is_coverage_required(c.parse_commit_subject("chore(deps): bump x"))
    assert not c.is_coverage_required(c.parse_commit_subject("docs: clarify readme"))


def test_is_conventional_title():
    assert c.is_conventional_title("fix(cli): repair update check")
    assert not c.is_conventional_title("Repair update check")
    assert not c.is_conventional_title("fix: repair update check with empty subject follows? no")


def test_branch_validation():
    assert c.is_valid_branch("feature/changelog-runtime")
    assert c.is_valid_branch("fix/typo-in-help")
    assert c.is_valid_branch("topic/experiment")  # legacy alias
    assert c.is_valid_branch("main")
    assert c.is_valid_branch("dependabot/github_actions/x-1.0.0")
    assert c.is_valid_branch("release-please--branches--main")
    assert not c.is_valid_branch("Changelog/Runtime")  # bad prefix + case
    assert c.is_valid_branch("feature/BadCase") is False  # non-kebab-case remainder
    assert not c.is_valid_branch("random/branch")
    assert not c.is_valid_branch("feature/extra/slash")


def test_main_pr_title_and_branch_exit_codes(capsys):
    assert c.main(["pr-title", "feat(core): add thing"]) == 0
    assert c.main(["pr-title", "add thing"]) == 1
    assert c.main(["branch", "feature/thing"]) == 0
    assert c.main(["branch", "thing"]) == 1
    assert "conventional" in capsys.readouterr().err.lower() or capsys.readouterr() is not None


def test_main_commit_msg_file(tmp_path):
    msg = tmp_path / "COMMIT_EDITMSG"
    msg.write_text("# comment\nfeat(cli): real subject\n\nBREAKING CHANGE: gone\n")
    assert c.main(["commit-msg-file", str(msg)]) == 0
    msg.write_text("just a message\n")
    assert c.main(["commit-msg-file", str(msg)]) == 1


def test_main_commit_subject_joins_words():
    assert c.main(["commit-subject", "feat(cli):", "two", "words"]) == 0
    assert c.main(["commit-subject", "two words"]) == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run --directory core pytest tests/test_convention.py -v`
Expected: FAIL (no module `core.convention`).

- [ ] **Step 3: Implement `core/src/core/convention.py`**

Module docstring, `from __future__ import annotations`, `import re`, dataclass `ParsedCommit`. Constants and functions exactly per Interfaces. `parse_commit_subject`: compile `COMMIT_RE = re.compile(r"^(?P<type>[a-z]+)(?:\((?P<scope>[A-Za-z0-9_-]+)\))?(?P<bang>!)?: (?P<subject>\S.*)$")`; return `None` when no match or type not in `COMMIT_TYPES` or subject empty; `breaking = bool(bang) or bool(re.search(r"^BREAKING CHANGE:", body, re.MULTILINE))`. `main`: dispatch on `argv[0]`, print `f"…: expected conventional <thing>, got: {value}"` to stderr, return 1 on failure, 0 otherwise; `commit-msg-file` reads with `Path(path).read_text(errors="replace")`, drops `#` lines, splits first non-empty line from the rest.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run --directory core pytest tests/test_convention.py -v`
Expected: PASS. Then `uv run --directory core mypy .` → clean (type annotations on all public functions).

- [ ] **Step 5: Write `CONTRIBUTING.md`**

Contents (prose, concise): how to run the project (uv workspace); **Commits** — Conventional Commits form, allowed types/scopes table, `!`/`BREAKING CHANGE:` breaking marker, PR title = commit subject (squash-only merge policy: enable "Squash and merge", disable merge/rebase commits in branch protection — repo setting, manual); **Branches** — allowed prefixes incl. `topic/` legacy alias, exempt automation prefixes, kebab-case rule; **Enforcement** — pre-commit hook install command `pre-commit install --hook-type pre-commit --hook-type commit-msg`, CI `convention` job behavior (PR: title + head branch; push: head commit subject, merge commits exempt); **Releases** — pointer: releases are cut by release-please; the user changelog is generated at release time (link the design doc); note that no `CHANGELOG.md` is committed, on purpose.

- [ ] **Step 6: Wire the pre-commit hook**

Append to `.pre-commit-config.yaml`:

```yaml
  - repo: local
    hooks:
      - id: conventional-commit-message
        name: conventional commit message
        entry: uv run --directory core python -m core.convention commit-msg-file
        language: system
        stages: [commit-msg]
```

- [ ] **Step 7: Add the CI `convention` job**

Add to `.github/workflows/ci.yml` (job must never be skipped — `ci-green` fails on any non-`success` need):

```yaml
  convention:
    runs-on: ubuntu-latest
    timeout-minutes: 5
    steps:
      - uses: actions/checkout@v7
      - uses: ./.github/actions/setup
      - name: Check conventional PR title / branch / commit
        env:
          EVENT_NAME: ${{ github.event_name }}
          PR_TITLE: ${{ github.event.pull_request.title }}
          HEAD_REF: ${{ github.head_ref }}
          REF_NAME: ${{ github.ref_name }}
        run: |
          if [ "$EVENT_NAME" = "pull_request" ]; then
            uv run --directory core python -m core.convention pr-title "$PR_TITLE"
            uv run --directory core python -m core.convention branch "$HEAD_REF"
          else
            parents=$(git log -1 --format=%p | wc -w)
            if [ "$parents" -le 1 ]; then
              uv run --directory core python -m core.convention commit-subject "$(git log -1 --format=%s)"
            fi
            uv run --directory core python -m core.convention branch "$REF_NAME"
          fi
```

Then change `ci-green`'s `needs:` to `[lint, typecheck, security, test, smoke, convention]`.

- [ ] **Step 8: Run the whole core suite + lint**

Run: `uv run --directory core pytest -v && uv run ruff check . && uv run ruff format --check .`
Expected: ALL PASS / clean.

- [ ] **Step 9: Commit**

```bash
git add CONTRIBUTING.md core/src/core/convention.py core/tests/test_convention.py .pre-commit-config.yaml .github/workflows/ci.yml
git commit -m "feat(core): commit/branch convention module with CI and hook enforcement"
```

---

### Task 2: Changelog models, release fetch, range, renderers (core)

**Files:**
- Create: `core/src/core/changelog.py`
- Test: `core/tests/test_changelog.py`

**Interfaces:**
- Consumes: nothing (stdlib `urllib`, pydantic).
- Produces:
  - `changelog.DISCLOSURE = "This changelog was generated with AI from our release history."`
  - `changelog.SECTION_ORDER = ("Initial release", "Added", "Improved", "Fixed", "Security", "Removed")`
  - `changelog.RELEASES_LIST_API = "https://api.github.com/repos/alehar9320/agentic-odi/releases?per_page=100"`
  - Models (pydantic v2): `Entry(text: str = Field(min_length=1), sources: list[str] = Field(min_length=1), breaking: bool = False)`; `Section(name: Literal[SECTION_ORDER…], entries: list[Entry])`; `GeneratorInfo(model: str, prompt_version: str)`; `ReleaseNotes(schema_version: Literal[1] = 1, version: str, previous_version: str | None = None, date: str, generated_by: Literal["ai"] = "ai", generator: GeneratorInfo, disclosure: str, sections: list[Section])`
  - `changelog.ChangelogFetchError(Exception)`
  - `changelog.parse_version(s: str) -> tuple[int, int, int]` (lstrip `v`, pad to 3, non-numeric raises `ValueError`)
  - `changelog.version_sort_key(s)`, `changelog.in_range(version: str, since: str | None, current: str) -> bool` — `since is None` ⇒ True; else `parse_version(since) < parse_version(version) <= parse_version(current)`
  - `changelog.fetch_release_notes(*, fetch: Callable[[str], str] | None = None) -> list[ReleaseNotes]` — default fetch = urllib GET (10s timeout, `User-Agent: agentic-odi-changelog`, returns text). GET the list; on network error / non-JSON list raise `ChangelogFetchError`. For each release with `prerelease == false`, find asset named `changelog.json`, GET its `browser_download_url`, parse with `ReleaseNotes.model_validate_json` — invalid/missing assets are **skipped** (never raise per-release). Result sorted ascending by `parse_version`.
  - `changelog.render_plain(notes: list[ReleaseNotes], since: str | None) -> str` — exact shape:

    ```
    What's new since v0.1.0          ← since given; or "All published releases" when since is None
    <blank>
    v0.1.0 — 2026-10-10
      Initial release
        • Entry text
      Added
        • Entry text
        • Breaking change: Entry text     ← only when breaking
    <blank>
    v0.0.5 — 2026-10-01
      (No user-facing changes.)           ← only when sections empty
    <blank>
    This changelog was generated with AI from our release history.
    ```

    Per release: header `f"{tag} — {date}"` where tag = `v` + `version`; sections iterated in `SECTION_ORDER` order; empty sections omitted; entry bullet `f"        • {text}"` with `"Breaking change: "` prefix when flagged; releases joined by one blank line; footer `DISCLOSURE` after a blank line.
  - `changelog.render_markdown(release: ReleaseNotes) -> str` — for each non-empty section in `SECTION_ORDER`: `### {name}` then `- {text}` (`- **Breaking change:** {text}` when flagged); ends with blank line + `_{DISCLOSURE}_`.

- [ ] **Step 1: Write the failing tests**

```python
# core/tests/test_changelog.py
import json

import pytest
from pydantic import ValidationError

from core import changelog as cl


def _release(version, prev, sections, date="2026-10-18"):
    return cl.ReleaseNotes(
        version=version,
        previous_version=prev,
        date=date,
        generator=cl.GeneratorInfo(model="test-model", prompt_version="1"),
        disclosure=cl.DISCLOSURE,
        sections=sections,
    )


def _section(name, texts, breaking=None):
    breaking = breaking or [False] * len(texts)
    return cl.Section(
        name=name,
        entries=[cl.Entry(text=t, sources=["a" * 40], breaking=b) for t, b in zip(texts, breaking)],
    )


def test_schema_rejects_empty_sources_and_bad_section():
    with pytest.raises(ValidationError):
        cl.Entry(text="hi", sources=[])
    with pytest.raises(ValidationError):
        cl.Section(name="Changed!", entries=[])


def test_parse_version_and_range():
    assert cl.parse_version("v1.2.3") == (1, 2, 3)
    assert cl.parse_version("1.2") == (1, 2, 0)
    assert cl.in_range("0.1.0", "0.0.5", "0.1.0") is True  # current inclusive
    assert cl.in_range("0.0.5", "0.0.5", "0.1.0") is False  # since exclusive
    assert cl.in_range("0.2.0", "0.0.5", "0.1.0") is False  # beyond installed
    assert cl.in_range("0.2.0", None, "0.1.0") is True  # no lower bound
    with pytest.raises(ValueError):
        cl.parse_version("not.a.version")


def test_render_plain_structure_and_disclosure_once():
    notes = [
        _release(
            "0.0.5",
            None,
            [_section("Initial release", ["First ship."])],
            date="2026-10-01",
        ),
        _release(
            "0.1.0",
            "0.0.5",
            [
                _section("Added", ["A new view."]),
                _section("Fixed", ["A crash."], breaking=[True]),
            ],
        ),
    ]
    out = cl.render_plain(notes, "0.0.5")
    assert out.startswith("What's new since v0.0.5")
    assert "v0.1.0 — 2026-10-18" in out
    assert out.index("Added") < out.index("Fixed")  # SECTION_ORDER
    assert "• A new view." in out
    assert "Breaking change: A crash." in out
    assert "Initial release" not in out  # 0.0.5 excluded by range
    assert out.count(cl.DISCLOSURE) == 1


def test_render_plain_all_and_empty_release():
    notes = [_release("0.1.0", "0.0.5", [])]
    out = cl.render_plain(notes, None)
    assert out.startswith("All published releases")
    assert "(No user-facing changes.)" in out


def test_render_markdown():
    md = cl.render_markdown(
        _release(
            "0.1.0",
            "0.0.5",
            [
                _section("Added", ["A view."]),
                _section("Fixed", ["Crash."], breaking=[True]),
            ],
        )
    )
    assert "### Added\n- A view." in md
    assert "- **Breaking change:** Crash." in md
    assert md.rstrip().endswith(f"_{cl.DISCLOSURE}_")


def _list_payload(*releases):
    return json.dumps(list(releases))


def test_fetch_release_notes_happy_prerelease_and_bad_asset():
    rel_ok = {
        "tag_name": "v0.1.0",
        "prerelease": False,
        "assets": [
            {
                "name": "checksums.txt",
                "browser_download_url": "https://x/checksums.txt",
            },
            {
                "name": "changelog.json",
                "browser_download_url": "https://x/changelog.json",
            },
        ],
    }
    rel_pre = {"tag_name": "v0.2.0-rc.1", "prerelease": True, "assets": []}
    rel_bad = {
        "tag_name": "v0.0.5",
        "prerelease": False,
        "assets": [
            {
                "name": "changelog.json",
                "browser_download_url": "https://bad/changelog.json",
            },
        ],
    }
    valid_body = _release("0.1.0", "0.0.5", [_section("Added", ["A view."])]).model_dump_json()

    def fake_fetch(url):
        if "per_page" in url:
            return _list_payload(rel_ok, rel_pre, rel_bad)
        if url == "https://x/changelog.json":
            return valid_body
        if url == "https://bad/changelog.json":
            return '{"schema_version": 1}'  # invalid → skipped
        raise AssertionError(f"unexpected url {url}")

    notes = cl.fetch_release_notes(fetch=fake_fetch)
    assert [n.version for n in notes] == ["0.1.0"]  # prerelease + malformed skipped


def test_fetch_release_notes_bad_list_raises():
    with pytest.raises(cl.ChangelogFetchError):
        cl.fetch_release_notes(fetch=lambda url: "not json")


def test_fetch_release_notes_network_error_raises():
    def boom(url):
        raise OSError("down")

    with pytest.raises(cl.ChangelogFetchError):
        cl.fetch_release_notes(fetch=boom)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run --directory core pytest tests/test_changelog.py -v`
Expected: FAIL (no module `core.changelog`).

- [ ] **Step 3: Implement `core/src/core/changelog.py`**

Per Interfaces. `fetch_release_notes` default fetcher wraps `urllib.request.urlopen(url, timeout=10)` with `Request(url, headers={"User-Agent": "agentic-odi-changelog", "Accept": "application/vnd.github+json"})` — args must stay runtime variables (see Global Constraints). Wrap **list-level** failures (`OSError`, `ValueError`, `json.JSONDecodeError`, `KeyError`/`TypeError` from payload shape) in `ChangelogFetchError from exc`; per-asset failures are caught narrowly (`OSError`, `ValueError`, `ValidationError`) and skipped. `since` in `render_plain` is displayed after `lstrip("v")`-normalization: header `f"What's new since v{since.lstrip('v')}"`.

- [ ] **Step 4: Run tests to verify they pass, then typecheck/lint**

Run: `uv run --directory core pytest -v && uv run --directory core mypy . && uv run ruff check core && uv run ruff format --check core`
Expected: ALL PASS / clean.

- [ ] **Step 5: Commit**

```bash
git add core/src/core/changelog.py core/tests/test_changelog.py
git commit -m "feat(core): changelog models, GitHub release fetch, and renderers"
```

---

### Task 3: Generator + grounding guardrails + offline fixture harness

**Files:**
- Create: `scripts/changelog/manifest.py`
- Create: `scripts/changelog/prompt.md`
- Create: `scripts/changelog/validate.py`
- Create: `scripts/changelog/generate.py`
- Create: `scripts/changelog/tests/conftest.py`, `scripts/changelog/tests/test_validate.py`, `scripts/changelog/tests/test_generate.py`
- Create: `scripts/changelog/fixtures/{valid,unknown_sha,missing_coverage,unknown_identifier}/manifest.json` and `response.json`
- Modify: `pyproject.toml` (root: add `[tool.ruff]` + `[tool.ruff.lint]`)
- Modify: `.github/workflows/ci.yml` (one new step in the `test` job)

**Interfaces:**
- Consumes: `core.convention` (parse/coverage rules), `core.changelog` (models, renderers) — importable because everything runs under `uv run --directory core`.
- Produces:
  - `manifest.build_manifest(*, repo: Path, version: str, previous_version: str | None) -> dict` — runs `git -C repo log --no-merges --format=%H%x1f%s%x1f%b <revspec>` with `revspec = f"v{previous_version}..v{version}"` when previous is set else `v{version}`; per commit: `sha`, `subject`, `body` (capped 600 chars; omitted entirely when `initial` i.e. previous is None **and** commit count > 200), `type`/`scope`/`breaking` from `core.convention.parse_commit_subject` (else `None`/`None`/`False`), `files` from `git diff-tree --no-commit-id --name-only -r <sha>` capped at 50. Returns `{"schema_version": 1, "version", "previous_version", "initial": bool, "range": revspec, "commits": [...]}`. Raises `FileNotFoundError`/`RuntimeError` on git failures.
  - `generate.resolve_range(repo: Path, tag: str) -> tuple[str | None, bool]` — lists `git tag --list "v*" --sort=version:refname`; if `tag` not present raise `ValueError(f"tag not found: {tag}")`; `prev` = previous element or `None`; returns `(prev, initial)`.
  - `generate.parse_response(raw: str, meta: dict) -> tuple[ReleaseNotes | None, list[str]]` — strips optional ` ```json ` fences, `json.loads`, requires a `sections` key, rebuilds `{**meta, "sections": obj["sections"]}` and runs `ReleaseNotes.model_validate`; returns `(None, [err])` on failure.
  - `generate.call_model(prompt: str, manifest_json: str) -> str` — POST `{base}/chat/completions` (urllib) with `Authorization: Bearer {key}`, body `{"model": env, "temperature": 0, "response_format": {"type": "json_object"}, "messages": [{"role": "system", "content": prompt}, {"role": "user", "content": manifest_json}]}`; returns `choices[0].message.content`. Missing env or HTTP/network error ⇒ raise `RuntimeError` (main exits 1).
  - `validate.validate_notes(notes: ReleaseNotes, manifest: dict) -> tuple[list[str], list[str]]` — returns `(violations, warnings)`:
    - **G2** every cited source resolves: `len(cited) >= 7` and some manifest `sha.startswith(cited)` ⇒ else `f"G2: cited sha not in release range: {cited}"`.
    - **G3/G7** enforced by the pydantic models (min lengths, non-empty sections) + one check: total entries ≥ 1 ⇒ else `"G3: changelog has no entries"`.
    - **G4** every commit with `core.convention.is_coverage_required` cited ⇒ else `f"G4: uncovered {type} commit {sha[:7]} {subject}"`.
    - **G6a** hard risky tokens in entry text not present in manifest text (concat of subject+body+files): backtick spans `` `…` ``, `snake_case` tokens (`\b[a-z0-9]+_[a-z0-9_]+\b`), file paths with extension (`\b[\w.-]+/[\w./-]+\.\w+\b`), `x.y.z` versions (`\b\d+\.\d+\.\d+\b`) ⇒ `f"G6a: ungrounded token in entry: {tok}"`.
    - **G6b** soft: `SCREAMING_CASE` tokens (`\b[A-Z][A-Z0-9_]{2,}\b`) missing from manifest ⇒ warning `"G6b: unverified acronym (allowed): {tok}"` — warnings never fail the run.
  - `generate.main(argv: list[str] | None = None) -> int` — args: `--tag` (required in online mode), `--repo` (default `.`), `--out` (default `changelog.json`), `--notes` (default `changelog.md`), `--audit` (default `manifest.json`), `--offline-manifest PATH`, `--offline-response PATH`. Flow: offline ⇒ load manifest from file (version/previous from it; no git); online ⇒ `resolve_range` + `build_manifest` ⇒ **always write `--audit` first** (audit trail even on failure) ⇒ obtain response (file or `call_model`) ⇒ `parse_response` with authoritative meta (`schema_version/version/previous_version/date` = today UTC `YYYY-MM-DD`/`generated_by="ai"`/`generator={"model": env-or-"offline", "prompt_version": PROMPT_VERSION}`/`disclosure=DISCLOSURE`) ⇒ `validate_notes` ⇒ print warnings, print violations ⇒ if any violation: **exit 2, write nothing else** ⇒ write `--out` (`model_dump_json(indent=2)`) and `--notes` (`render_markdown`) ⇒ exit 0. Returns 1 for usage/git/env/model errors (message to stderr, no traceback).
  - `prompt.md` — pinned prompt, rendered as the system message; `PROMPT_VERSION = "1"` in `generate.py`.
- Root `pyproject.toml` gains:

  ```toml
  [tool.ruff]
  line-length = 100
  target-version = "py310"

  [tool.ruff.lint]
  select = ["E4", "E7", "E9", "F", "I", "UP", "B", "BLE"]
  ```

  (Nearest-config discovery: packages keep their own identical config; this only covers `scripts/` and the root.)

- [ ] **Step 1: Write the failing tests**

```python
# scripts/changelog/tests/conftest.py
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
```

```python
# scripts/changelog/tests/test_validate.py
import json
from pathlib import Path

import validate as vmod

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def _manifest():
    return json.loads((FIXTURES / "valid" / "manifest.json").read_text())


def _resp(name):
    return (FIXTURES / name / "response.json").read_text()


def _meta():
    return {
        "schema_version": 1,
        "version": "0.2.0",
        "previous_version": "0.1.0",
        "date": "2026-10-18",
        "generated_by": "ai",
        "generator": {"model": "offline", "prompt_version": "1"},
        "disclosure": "This changelog was generated with AI from our release history.",
    }


def test_valid_fixture_has_no_violations():
    notes, errs = vmod.parse_response(_resp("valid"), _meta())
    assert errs == [] and notes is not None
    violations, warnings = vmod.validate_notes(notes, _manifest())
    assert violations == [] and warnings == []


def test_parse_response_strips_code_fence():
    fenced = "```json\n" + _resp("valid") + "\n```"
    notes, errs = vmod.parse_response(fenced, _meta())
    assert errs == [] and notes is not None


def test_g2_unknown_cited_sha_fails():
    notes, errs = vmod.parse_response(_resp("unknown_sha"), _meta())
    assert errs == [] and notes is not None
    violations, _ = vmod.validate_notes(notes, _manifest())
    assert any(v.startswith("G2:") for v in violations)


def test_g4_missing_coverage_fails_and_names_commit():
    notes, errs = vmod.parse_response(_resp("missing_coverage"), _meta())
    assert errs == [] and notes is not None
    violations, _ = vmod.validate_notes(notes, _manifest())
    assert any(v.startswith("G4:") and "bbbbbbb" in v for v in violations)


def test_g6a_ungrounded_snake_case_fails():
    notes, errs = vmod.parse_response(_resp("unknown_identifier"), _meta())
    assert errs == [] and notes is not None
    violations, _ = vmod.validate_notes(notes, _manifest())
    assert any(v.startswith("G6a:") for v in violations)


def test_g6b_screaming_case_only_warns():
    payload = json.loads(_resp("valid"))
    payload["sections"][0]["entries"][0]["text"] += " Powered by NEWFRAMEWORK."
    notes, errs = vmod.parse_response(json.dumps(payload), _meta())
    assert errs == [] and notes is not None
    violations, warnings = vmod.validate_notes(notes, _manifest())
    assert violations == []
    assert any("NEWFRAMEWORK" in w for w in warnings)


def test_schema_rejects_empty_sources():
    payload = json.loads(_resp("valid"))
    payload["sections"][0]["entries"][0]["sources"] = []
    notes, errs = vmod.parse_response(json.dumps(payload), _meta())
    assert notes is None and errs
```

```python
# scripts/changelog/tests/test_generate.py
import json
from pathlib import Path

from core.changelog import ReleaseNotes

import generate as gmod

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def test_offline_run_writes_out_notes_and_audit(tmp_path):
    out = tmp_path / "changelog.json"
    notes = tmp_path / "changelog.md"
    audit = tmp_path / "manifest.json"
    rc = gmod.main(
        [
            "--offline-manifest",
            str(FIXTURES / "valid" / "manifest.json"),
            "--offline-response",
            str(FIXTURES / "valid" / "response.json"),
            "--out",
            str(out),
            "--notes",
            str(notes),
            "--audit",
            str(audit),
        ]
    )
    assert rc == 0
    parsed = ReleaseNotes.model_validate_json(out.read_text())
    assert parsed.version == "0.2.0"
    assert parsed.generated_by == "ai"
    assert "This changelog was generated with AI" in notes.read_text()
    assert json.loads(audit.read_text())["commits"]  # audit always written


def test_offline_run_fails_closed_on_violation(tmp_path):
    out = tmp_path / "changelog.json"
    notes = tmp_path / "changelog.md"
    audit = tmp_path / "manifest.json"
    rc = gmod.main(
        [
            "--offline-manifest",
            str(FIXTURES / "valid" / "manifest.json"),
            "--offline-response",
            str(FIXTURES / "unknown_sha" / "response.json"),
            "--out",
            str(out),
            "--notes",
            str(notes),
            "--audit",
            str(audit),
        ]
    )
    assert rc == 2
    assert not out.exists() and not notes.exists()
    assert audit.exists()  # audit survives failure


def test_online_mode_without_tag_exits_1(tmp_path, capsys):
    rc = gmod.main(["--repo", str(tmp_path)])
    assert rc == 1
    assert "tag" in capsys.readouterr().err.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run --directory core pytest ../scripts/changelog/tests -v`
Expected: FAIL (modules `validate`/`generate` missing).

- [ ] **Step 3: Write the fixtures**

`scripts/changelog/fixtures/valid/manifest.json`:

```json
{
  "schema_version": 1,
  "version": "0.2.0",
  "previous_version": "0.1.0",
  "initial": false,
  "range": "v0.1.0..v0.2.0",
  "commits": [
    {"sha": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", "subject": "feat(cli): add one-command changelog view", "body": "Users can run the CLI to see all changes since last time.", "type": "feat", "scope": "cli", "breaking": false, "files": ["cli/src/cli/changelog.py"]},
    {"sha": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb", "subject": "fix(core): stop state file clobbering markers", "body": "The marker file no longer loses data on update checks.", "type": "fix", "scope": "core", "breaking": false, "files": ["cli/src/cli/update.py"]},
    {"sha": "cccccccccccccccccccccccccccccccccccccccc", "subject": "chore(deps): bump actions/checkout", "body": "", "type": "chore", "scope": "deps", "breaking": false, "files": [".github/workflows/ci.yml"]}
  ]
}
```

`valid/response.json` (SHA citations of `a…`/`b…` are 8 chars — valid prefixes of the manifest SHAs):

```json
{
  "schema_version": 1,
  "version": "0.2.0",
  "previous_version": "0.1.0",
  "date": "2026-10-18",
  "generated_by": "ai",
  "generator": {"model": "offline", "prompt_version": "1"},
  "disclosure": "This changelog was generated with AI from our release history.",
  "sections": [
    {"name": "Added", "entries": [{"text": "See every change since your last version in one command.", "sources": ["aaaaaaaa"], "breaking": false}]},
    {"name": "Fixed", "entries": [{"text": "Your update history is no longer lost during update checks.", "sources": ["bbbbbbbb"], "breaking": false}]}
  ]
}
```

Mutations (copy `valid/` then change exactly one thing):
- `unknown_sha/`: first entry `"sources": ["dddddddd"]`.
- `missing_coverage/`: delete the `Fixed` section entirely (leaves the `fix` commit `bbbb…` uncovered).
- `unknown_identifier/`: first entry text becomes ``"Adds a `zebra_queue_cache` layer for faster syncs."`` (token absent from manifest).

- [ ] **Step 4: Implement `manifest.py`, `prompt.md`, `validate.py`, `generate.py`**

Per Interfaces. Implementation notes:
- `manifest.py` imports `from core.convention import parse_commit_subject`; git calls via `subprocess.run([...], check=True, capture_output=True, text=True, cwd=repo)` with `\x1f`/`\x1e`-free simple format (`%H%x1f%s%x1f%b`, split records on commit boundaries by using `--format=%H%x1f%s%x1f%b%x1e` and splitting on `\x1e`).
- `prompt.md` (exact content — system message):

```markdown
You write release notes for Agentic ODI, aimed at the person who installs and uses the product — never at developers.

# Input
You receive one JSON manifest: every commit in this release (full SHA, subject, body, parsed type/scope/breaking, changed files). It is the only information you may use.

# Rules
1. Use ONLY facts present in the manifest. Never invent features, product names, versions, file paths, numbers, or benefits that the commits do not support.
2. Write plain-language, value-focused sentences: one sentence per entry, ideally under 200 characters. Never quote commit subjects verbatim; no scopes, branch names, PR numbers, jargon, exclamation marks, or emoji.
3. Group entries under exactly these section names and omit empty ones: "Initial release" (only when manifest.initial is true), "Added", "Improved", "Fixed", "Security", "Removed". Keep this order.
4. Every entry cites the full 40-character SHA of at least one manifest commit in "sources".
5. Every manifest commit with type feat, fix, perf, or revert, or marked breaking, MUST be covered by at least one entry. Do not invent entries that cite nothing.
6. Do not create entries for chore, ci, build, test, docs, style, or dependency-bump commits unless the commit clearly describes a user benefit. Put refactor commits under "Improved" only when the commit states a user-visible benefit.
7. Set "breaking": true for entries summarizing a breaking commit and start that entry's text with "Breaking change: ".
8. Output ONLY one JSON object, no prose and no code fences, with exactly this shape:
{"schema_version": 1, "version": "...", "previous_version": "... or null", "date": "YYYY-MM-DD", "generated_by": "ai", "generator": {"model": "...", "prompt_version": "1"}, "disclosure": "This changelog was generated with AI from our release history.", "sections": [{"name": "Added", "entries": [{"text": "...", "sources": ["<40-char sha>"], "breaking": false}]}]}
```

- `validate.py` imports `from core.changelog import ReleaseNotes` and `from core.convention import is_coverage_required, parse_commit_subject`; regexes per Interfaces; manifest text for grounding = `" ".join(subject + body + files for all commits)`. Return `(violations, warnings)` sorted for deterministic output.
- `generate.py`: `argparse`; `PROMPT_VERSION = "1"`; env names per Global Constraints; `meta` built from manifest + `datetime.now(timezone.utc).strftime("%Y-%m-%d")`; model-supplied top-level fields are discarded (meta wins) except `sections`; broad network catch `# noqa: BLE001`; on violations print `f"{v}"` per line to stderr; write files atomically-enough (direct write is fine — CI workspace).

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run --directory core pytest ../scripts/changelog/tests -v`
Expected: PASS.

- [ ] **Step 6: Lint/format the new `scripts/` code + wire CI step**

Run: `uv run ruff format scripts && uv run ruff check . && uv run ruff format --check .`
Expected: clean.

Add after the `Pytest (core)` step in `.github/workflows/ci.yml`:

```yaml
      - name: Pytest (changelog generator)
        run: uv run --directory core pytest ../scripts/changelog/tests -v
```

(Existing `test` job ⇒ `ci-green` `needs` unchanged. The step intentionally runs without coverage flags so the combine step is unaffected.)

- [ ] **Step 7: Commit**

```bash
git add scripts/changelog pyproject.toml .github/workflows/ci.yml
git commit -m "feat: changelog generator with grounding guardrails and offline harness"
```

---

### Task 4: Release pipeline wiring — release-please amended, chained changelog job

**BLOCKED — requires PR #8 merge** (creates/modifies `release-please-config.json`, `.release-please-manifest.json`, `.github/workflows/release-please.yml`).

**Files:**
- Modify: `release-please-config.json`
- Modify: `.github/workflows/release-please.yml`
- Test: `scripts/changelog/tests/test_release_wiring.py`

**Interfaces:**
- Consumes: Task 3 generator; PR #8 release-please setup.
- Produces:
  - `release-please-config.json` package `.` becomes:

    ```json
    {
      "release-type": "simple",
      "packages": {
        ".": {
          "release-type": "simple",
          "skip-changelog": true,
          "draft": true,
          "force-tag-creation": true,
          "bump-minor-pre-major": true
        }
      }
    }
    ```

  - `.github/workflows/release-please.yml` becomes (full file):

    ```yaml
    name: release-please

    on:
      push:
        branches:
          - main

    permissions:
      contents: write
      pull-requests: write

    jobs:
      release-please:
        runs-on: ubuntu-latest
        outputs:
          releases_created: ${{ steps.release.outputs.releases_created }}
          tag_name: ${{ steps.release.outputs.tag_name }}
        steps:
          - name: Release Please
            id: release
            uses: googleapis/release-please-action@v4
            with:
              config-file: release-please-config.json
              manifest-file: .release-please-manifest.json
              # Cross-plan remediation: with a PAT (repo secret), tags/releases
              # created by release-please DO trigger release.yml / e2e-install.yml.
              # GITHUB_TOKEN-created resources never trigger other workflows.
              token: ${{ secrets.RELEASE_PLEASE_TOKEN || github.token }}

      changelog:
        needs: release-please
        if: needs.release-please.outputs.releases_created == 'true'
        runs-on: ubuntu-latest
        steps:
          - uses: actions/checkout@v7
            with:
              fetch-depth: 0
          - uses: ./.github/actions/setup
          - name: Generate and validate changelog (fail-closed)
            env:
              AGENTIC_ODI_CHANGELOG_MODEL: ${{ secrets.AGENTIC_ODI_CHANGELOG_MODEL }}
              AGENTIC_ODI_CHANGELOG_API_KEY: ${{ secrets.AGENTIC_ODI_CHANGELOG_API_KEY }}
              AGENTIC_ODI_CHANGELOG_BASE_URL: ${{ secrets.AGENTIC_ODI_CHANGELOG_BASE_URL }}
            run: |
              uv run --directory core python ../scripts/changelog/generate.py \
                --tag "${{ needs.release-please.outputs.tag_name }}" \
                --out changelog.json --notes changelog.md --audit changelog-manifest.json
          - name: Upload generation audit
            uses: actions/upload-artifact@v7
            with:
              name: changelog-audit-${{ needs.release-please.outputs.tag_name }}
              path: |
                changelog-manifest.json
                changelog.json
              retention-days: 90
          - name: Attach and publish release (last step — failure keeps draft)
            env:
              GH_TOKEN: ${{ github.token }}
            run: |
              TAG="${{ needs.release-please.outputs.tag_name }}"
              gh release upload "$TAG" changelog.json --clobber
              gh release edit "$TAG" --notes-file changelog.md --draft=false
    ```

- [ ] **Step 1: Write the failing tests**

```python
# scripts/changelog/tests/test_release_wiring.py
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_release_please_config_flags():
    cfg = json.loads((ROOT / "release-please-config.json").read_text())
    pkg = cfg["packages"]["."]
    assert pkg["skip-changelog"] is True, "must never commit a CHANGELOG.md"
    assert pkg["draft"] is True
    assert pkg["force-tag-creation"] is True
    assert pkg["bump-minor-pre-major"] is True


def test_release_please_workflow_chains_generation_and_publish():
    wf = (ROOT / ".github/workflows/release-please.yml").read_text()
    assert "releases_created" in wf  # chained, not event-triggered
    assert "generate.py" in wf
    assert "gh release upload" in wf
    assert "--draft=false" in wf  # publish is the LAST operation
    assert "fetch-depth: 0" in wf  # full history for the manifest
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run --directory core pytest ../scripts/changelog/tests/test_release_wiring.py -v`
Expected: FAIL (flags absent, no changelog job).

- [ ] **Step 3: Apply config + workflow changes**

Replace both files with the Interfaces content. **Verify** (local, not CI): `uv run --with pyyaml python -c "import yaml; yaml.safe_load(open('.github/workflows/release-please.yml'))"` and `uv run python -c "import json; json.load(open('release-please-config.json'))"`.

Ops note to append to the Task 1 `CONTRIBUTING.md` release section (or PR description if CONTRIBUTING is frozen): repo secrets required for releases — `AGENTIC_ODI_CHANGELOG_MODEL`, `AGENTIC_ODI_CHANGELOG_API_KEY`, optional `AGENTIC_ODI_CHANGELOG_BASE_URL`, optional `RELEASE_PLEASE_TOKEN` (PAT: contents + pull-requests write; enables tag-push workflows and CI on release PRs).

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run --directory core pytest ../scripts/changelog/tests -v`
Expected: ALL PASS (Task 3 + Task 4 tests).

- [ ] **Step 5: Commit**

```bash
git add release-please-config.json .github/workflows/release-please.yml scripts/changelog/tests/test_release_wiring.py
git commit -m "ci(release): generate AI changelog at release time, no committed CHANGELOG.md"
```

---

### Task 5: `odi changelog` command + last-seen state + hints

**BLOCKED — requires PR #8 merge** (`paths.state_file()`, `update.py`, `cli.py` root callback come from that branch).

**Files:**
- Modify: `cli/src/cli/update.py` (merge-write state + marker helpers)
- Create: `cli/src/cli/changelog.py`
- Modify: `cli/src/cli/cli.py` (root callback hint, `changelog` command, `update` success hint)
- Test: `cli/tests/test_changelog_cmd.py`

**Interfaces:**
- Consumes: `core.changelog` (`fetch_release_notes`, `render_plain`, `ChangelogFetchError`, `in_range`, `parse_version`, `version_sort_key`), `cli.paths.state_file()`, `cli.version.__version__`.
- Produces (`update.py` additions):
  - `update.read_state(state_file: Path) -> dict` — `{}` on missing/corrupt/unreadable.
  - `update.record_check(state_file: Path, now: float) -> None` — **reimplemented as merge-write**: `data = read_state(); data["last_check"] = now; write json` (preserves `last_changelog_version`; PR #8's existing tests keep passing because a fresh file still serializes to `{"last_check": …}`).
  - `update.last_changelog_version(state_file: Path) -> str | None`
  - `update.record_changelog_version(state_file: Path, version: str) -> None` (mkdir parents, direct write like `record_check`).
- Produces (`cli/src/cli/changelog.py`):
  - `changelog.cli_name() -> str` — `Path(sys.argv[0]).name or "agentic-odi"`.
  - `changelog.show_hint(invoked_subcommand: str | None, *, stdout_isatty: bool | None = None) -> str | None` — `None` when subcommand ∈ `{"changelog", "version", "update"}`, when not TTY (`stdout_isatty` defaults to `sys.stdout.isatty()`), when marker missing, or when `parse_version(__version__) <= parse_version(marker)`; else `f"New in v{__version__} — run '{cli_name()} changelog' to see what changed."`. State read failures (unwritable install root on source installs) return `None`.
  - `changelog.changelog_cmd(since: str | None, show_all: bool, json_out: bool) -> None` — Typer options `--since`, `--all`, `--json`. Flow:
    1. `current = __version__`; `state = paths.state_file()`; `marker = update.last_changelog_version(state)`.
    2. Lower bound: `show_all` ⇒ `None`; `since` given ⇒ validate with `parse_version` (failure ⇒ echo `f"Invalid version: {since}"`, `raise typer.Exit(1)`, normalized `since.lstrip("v")`); else ⇒ `marker`.
    3. `notes = fetch_release_notes()` — import names into module namespace so tests can monkeypatch `cli.changelog.fetch_release_notes`. On `ChangelogFetchError`: echo `Couldn't fetch release notes — check your connection and try again.` (stderr), exit 1, **do not advance marker**.
    4. `selected = sorted([n for n in notes if in_range(n.version, lower, current)], key=version_sort_key)`.
    5. If `json_out`: print `json.dumps([n.model_dump() for n in selected], indent=2)` only (no other stdout).
       Elif `selected`: print `render_plain(selected, lower)`.
       Elif `lower`: print `f"You're up to date — no changes since v{lower.lstrip('v')}."`
       Else: print `No published releases yet.` (and skip step 6 — nothing was shown).
    6. Advance marker: if `since is None` and anything was shown or the up-to-date line printed ⇒ `update.record_changelog_version(state, current)`.
- Produces (`cli.py` edits, minimal):
  - Root callback signature gains `ctx: typer.Context` **if not already present** (onboarding plan may have added it — rebase rather than duplicate); first body statement: `hint = changelog.show_hint(ctx.invoked_subcommand)` + `if hint: typer.echo(hint)`.
  - `app.command("changelog")(changelog.changelog_cmd)` alongside the other command registrations.
  - In `update_cmd`, immediately after `typer.echo(f"Updated to v{target}")`, add `typer.echo(f"Run '{changelog.cli_name()} changelog' to see what's new.")`.

- [ ] **Step 1: Write the failing tests**

```python
# cli/tests/test_changelog_cmd.py
import json

from typer.testing import CliRunner

from cli import changelog as cl, paths, update
from cli.cli import app
from cli.version import __version__
from core.changelog import (
    ChangelogFetchError,
    Entry,
    GeneratorInfo,
    ReleaseNotes,
    Section,
)


def _install(monkeypatch, tmp_path):
    monkeypatch.setenv("AGENTIC_ODI_INSTALL_DIR", str(tmp_path / "install"))


def _release(version, prev, texts, date="2026-10-18", name="Added"):
    return ReleaseNotes(
        version=version,
        previous_version=prev,
        date=date,
        generator=GeneratorInfo(model="test", prompt_version="1"),
        disclosure=cl_core_disclosure(),
        sections=[Section(name=name, entries=[Entry(text=t, sources=["a" * 40]) for t in texts])]
        if texts
        else [],
    )


def cl_core_disclosure():
    from core.changelog import DISCLOSURE

    return DISCLOSURE


NOTES = [
    _release(
        "0.0.5",
        None,
        ["The very first release."],
        date="2026-10-01",
        name="Initial release",
    ),
    _release("0.1.0", "0.0.5", ["Everything, in one view."]),
]


def _patch_fetch(monkeypatch, notes=NOTES, boom=False):
    if boom:

        def _boom(**kwargs):
            raise ChangelogFetchError("down")

        monkeypatch.setattr(cl, "fetch_release_notes", _boom)
    else:
        monkeypatch.setattr(cl, "fetch_release_notes", lambda **kwargs: list(notes))


def test_changelog_since_marker_shows_only_gap(monkeypatch, tmp_path, capsys):
    _install(monkeypatch, tmp_path)
    update.record_changelog_version(paths.state_file(), "0.0.5")
    _patch_fetch(monkeypatch)
    runner = CliRunner()
    result = runner.invoke(app, ["changelog"])
    assert result.exit_code == 0
    out = result.output
    assert "What's new since v0.0.5" in out
    assert "Everything, in one view." in out
    assert "The very first release." not in out
    assert out.count(cl_core_disclosure()) == 1
    assert update.last_changelog_version(paths.state_file()) == __version__  # advanced


def test_changelog_without_marker_shows_everything(monkeypatch, tmp_path):
    _install(monkeypatch, tmp_path)
    _patch_fetch(monkeypatch)
    result = CliRunner().invoke(app, ["changelog"])
    assert result.exit_code == 0
    assert "All published releases" in result.output
    assert "The very first release." in result.output
    assert update.last_changelog_version(paths.state_file()) == __version__


def test_changelog_up_to_date_line(monkeypatch, tmp_path):
    _install(monkeypatch, tmp_path)
    update.record_changelog_version(paths.state_file(), __version__)
    _patch_fetch(monkeypatch)
    result = CliRunner().invoke(app, ["changelog"])
    assert result.exit_code == 0
    assert f"You're up to date — no changes since v{__version__}" in result.output


def test_changelog_since_flag_does_not_move_marker(monkeypatch, tmp_path):
    _install(monkeypatch, tmp_path)
    update.record_changelog_version(paths.state_file(), "0.0.5")
    _patch_fetch(monkeypatch)
    result = CliRunner().invoke(app, ["changelog", "--since", "v0.0.5"])
    assert result.exit_code == 0
    assert "What's new since v0.0.5" in result.output
    assert update.last_changelog_version(paths.state_file()) == "0.0.5"


def test_changelog_invalid_since(monkeypatch, tmp_path):
    _install(monkeypatch, tmp_path)
    _patch_fetch(monkeypatch)
    result = CliRunner().invoke(app, ["changelog", "--since", "not.a.version"])
    assert result.exit_code == 1
    assert "Invalid version: not.a.version" in result.output


def test_changelog_fetch_failure_is_soft_and_keeps_marker(monkeypatch, tmp_path):
    _install(monkeypatch, tmp_path)
    update.record_changelog_version(paths.state_file(), "0.0.5")
    _patch_fetch(monkeypatch, boom=True)
    result = CliRunner().invoke(app, ["changelog"])
    assert result.exit_code == 1
    assert "Couldn't fetch release notes" in result.output
    assert "Traceback" not in result.output
    assert update.last_changelog_version(paths.state_file()) == "0.0.5"


def test_changelog_json(monkeypatch, tmp_path):
    _install(monkeypatch, tmp_path)
    _patch_fetch(monkeypatch)
    result = CliRunner().invoke(app, ["changelog", "--all", "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert [p["version"] for p in payload] == ["0.0.5", "0.1.0"]


def test_changelog_no_releases_published(monkeypatch, tmp_path):
    _install(monkeypatch, tmp_path)
    _patch_fetch(monkeypatch, notes=[])
    result = CliRunner().invoke(app, ["changelog", "--all"])
    assert result.exit_code == 0
    assert "No published releases yet." in result.output
    assert update.last_changelog_version(paths.state_file()) is None  # nothing shown


def test_show_hint_rules(monkeypatch, tmp_path):
    _install(monkeypatch, tmp_path)
    update.record_changelog_version(paths.state_file(), "0.0.5")
    hint = cl.show_hint("outcomes", stdout_isatty=True)
    assert hint is not None and f"New in v{__version__}" in hint
    assert cl.show_hint("changelog", stdout_isatty=True) is None
    assert cl.show_hint("version", stdout_isatty=True) is None
    assert cl.show_hint("outcomes", stdout_isatty=False) is None


def test_show_hint_absent_or_current_marker(monkeypatch, tmp_path):
    _install(monkeypatch, tmp_path)
    assert cl.show_hint("outcomes", stdout_isatty=True) is None  # no marker yet
    update.record_changelog_version(paths.state_file(), __version__)
    assert cl.show_hint("outcomes", stdout_isatty=True) is None  # marker == current


def test_record_check_preserves_changelog_marker(tmp_path):
    state = tmp_path / "update.json"
    state.write_text(json.dumps({"last_changelog_version": "0.0.5"}))
    update.record_check(state, 123.0)
    data = json.loads(state.read_text())
    assert data["last_check"] == 123.0
    assert data["last_changelog_version"] == "0.0.5"


def test_last_changelog_version_missing_or_corrupt(tmp_path):
    assert update.last_changelog_version(tmp_path / "nope.json") is None
    bad = tmp_path / "update.json"
    bad.write_text("not json")
    assert update.last_changelog_version(bad) is None


def test_update_cmd_prints_changelog_hint(monkeypatch, tmp_path):
    _install(monkeypatch, tmp_path)
    from cli import paths as cli_paths, update as cli_update

    monkeypatch.setattr(cli_paths, "is_frozen", lambda: True)
    monkeypatch.setattr(cli_update, "latest_release", lambda current: "0.1.0")

    def fake_download(version, dest_dir, fetch_bytes=None):
        dest = dest_dir / "archive.bin"
        dest.write_bytes(b"fake")
        return dest

    monkeypatch.setattr(cli_update, "download", fake_download)
    monkeypatch.setattr(cli_update, "perform_update", lambda *a, **k: tmp_path)
    result = CliRunner().invoke(app, ["update"])
    assert result.exit_code == 0
    assert "changelog" in result.output
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run --directory cli pytest tests/test_changelog_cmd.py -v`
Expected: FAIL (no `cli.changelog`, no `update.last_changelog_version`, no `changelog` command).

- [ ] **Step 3: Implement**

1. `update.py`: add `read_state`, reimplement `record_check` as merge-write, add `last_changelog_version` / `record_changelog_version` (docstrings in house style; keep `should_check`/`latest_release` untouched — PR #8's tests must stay green).
2. `cli/src/cli/changelog.py` per Interfaces (`from core.changelog import ChangelogFetchError, fetch_release_notes, in_range, parse_version, render_plain, version_sort_key` at module top so tests patch `cl.fetch_release_notes`; `import json`, `sys`, `typer`, `from cli import paths, update`; `from cli.version import __version__`).
3. `cli.py`: root-callback hint + `app.command("changelog")` + `update_cmd` hint line (rebase around the onboarding plan's `ctx`/`--no-onboard` edits if they landed first).

- [ ] **Step 4: Run tests to verify they pass, then the whole suite**

Run: `uv run --directory cli pytest -v`
Expected: ALL PASS (incl. PR #8's `test_update*.py`, `test_cli.py`, and onboarding tests if merged).

- [ ] **Step 5: Lint + typecheck**

Run: `uv run --directory cli ruff check src tests && uv run --directory cli mypy . && uv run ruff format --check cli`
Expected: clean.

- [ ] **Step 6: Commit**

```bash
git add cli/src/cli/update.py cli/src/cli/changelog.py cli/src/cli/cli.py cli/tests/test_changelog_cmd.py
git commit -m "feat(cli): changelog command with last-seen version tracking and upgrade hint"
```

---

### Task 6: Backfill verification (initial mode), audit assertions, release runbook

**BLOCKED — requires PR #8 merge** (shares the release wiring/files from Task 4; runbook documents those commands).

**Files:**
- Create: `scripts/changelog/fixtures/initial/manifest.json` + `response.json`
- Create: `scripts/changelog/tests/test_git_range.py`
- Modify: `CONTRIBUTING.md` (append "Cutting a release" runbook)

**Interfaces:**
- Consumes: `generate.resolve_range`, `generate.main`, `manifest.build_manifest`.
- Produces:
  - Git-integration tests using a **real temp git repo** (hermetic, no network): `git init`, `git -c user.email=t@t -c user.name=t commit …`, tags via `git tag`.
  - Initial-mode fixture: manifest with `"previous_version": null, "initial": true, "version": "0.1.0"`, 2 commits (one `feat`, one legacy non-conforming subject `type: null`); response with the single section `"Initial release"` citing the feat SHA. Offline run must yield a valid `ReleaseNotes` whose first section name is `Initial release`.
  - Runbook (CONTRIBUTING.md): normal release flow (merge release PR → Actions `release-please` job → chained `changelog` job publishes draft → `release.yml` attaches binaries); **stuck-draft recovery**: read the failed `changelog` job log; common causes = missing `AGENTIC_ODI_CHANGELOG_*` secrets or guardrail violation (violations are printed as `G2/G4/G6a: …`); fix & re-run the job, or regenerate locally:

    ```bash
    AGENTIC_ODI_CHANGELOG_MODEL=… AGENTIC_ODI_CHANGELOG_API_KEY=… \
      uv run --directory core python ../scripts/changelog/generate.py --tag vX.Y.Z \
      --out changelog.json --notes changelog.md --audit manifest.json
    gh release upload vX.Y.Z changelog.json --clobber
    gh release edit vX.Y.Z --notes-file changelog.md --draft=false
    ```

- [ ] **Step 1: Write the failing tests**

```python
# scripts/changelog/tests/test_git_range.py
import subprocess
from pathlib import Path

import generate as gmod
import manifest as mmod


def _git(repo, *args):
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )


def _repo(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    (repo / "a.txt").write_text("a")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "feat(core): first feature")
    _git(repo, "tag", "v0.1.0")
    (repo / "a.txt").write_text("b")
    _git(repo, "commit", "-q", "-am", "fix(core): repair crash")
    # side branch + merge (merge commits must be excluded from the manifest)
    _git(repo, "checkout", "-q", "-b", "feature/side")
    (repo / "b.txt").write_text("x")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "feat(cli): side work")
    _git(repo, "checkout", "-q", "main")
    (repo / "c.txt").write_text("y")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "chore: housekeeping")
    _git(
        repo,
        "merge",
        "--no-ff",
        "-q",
        "-m",
        "Merge branch 'feature/side'",
        "feature/side",
    )
    _git(repo, "tag", "v0.2.0")
    return repo


def test_resolve_range_finds_previous_tag(tmp_path):
    repo = _repo(tmp_path)
    prev, initial = gmod.resolve_range(repo, "v0.2.0")
    assert prev == "v0.1.0" and initial is False


def test_resolve_range_initial_when_no_tags(tmp_path):
    repo = tmp_path / "bare"
    repo.mkdir()
    _git(repo, "init", "-q")
    (repo / "a.txt").write_text("a")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "Add legacy free-text subject")
    _git(repo, "tag", "v0.1.0")
    prev, initial = gmod.resolve_range(repo, "v0.1.0")
    assert prev is None and initial is True


def test_resolve_range_unknown_tag_raises(tmp_path):
    repo = _repo(tmp_path)
    try:
        gmod.resolve_range(repo, "v9.9.9")
    except ValueError as exc:
        assert "v9.9.9" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_build_manifest_excludes_merges_and_parses_types(tmp_path):
    repo = _repo(tmp_path)
    data = mmod.build_manifest(repo=repo, version="0.2.0", previous_version="0.1.0")
    subjects = [c["subject"] for c in data["commits"]]
    assert not any(s.startswith("Merge ") for s in subjects)
    by_subject = {c["subject"]: c for c in data["commits"]}
    assert by_subject["fix(core): repair crash"]["type"] == "fix"
    assert by_subject["chore: housekeeping"]["type"] == "chore"
    assert data["range"] == "v0.1.0..v0.2.0"
    assert data["initial"] is False


def test_build_manifest_initial_uses_full_history(tmp_path):
    repo = tmp_path / "bare"
    repo.mkdir()
    _git(repo, "init", "-q")
    (repo / "a.txt").write_text("a")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "feat: ship it")
    _git(repo, "tag", "v0.1.0")
    data = mmod.build_manifest(repo=repo, version="0.1.0", previous_version=None)
    assert data["initial"] is True
    assert data["range"] == "v0.1.0"
    assert len(data["commits"]) == 1


def test_offline_initial_fixture_renders_initial_release(tmp_path):
    from core.changelog import ReleaseNotes

    fixtures = Path(__file__).resolve().parents[1] / "fixtures" / "initial"
    out = tmp_path / "changelog.json"
    notes_md = tmp_path / "changelog.md"
    audit = tmp_path / "manifest.json"
    rc = gmod.main(
        [
            "--offline-manifest",
            str(fixtures / "manifest.json"),
            "--offline-response",
            str(fixtures / "response.json"),
            "--out",
            str(out),
            "--notes",
            str(notes_md),
            "--audit",
            str(audit),
        ]
    )
    assert rc == 0
    parsed = ReleaseNotes.model_validate_json(out.read_text())
    assert parsed.sections[0].name == "Initial release"
    assert parsed.previous_version is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run --directory core pytest ../scripts/changelog/tests/test_git_range.py -v`
Expected: FAIL (`resolve_range` not implemented / `initial` fixture missing).

- [ ] **Step 3: Implement**

- `resolve_range` in `generate.py` per Task 3 Interfaces (already specified there; add it now if Task 3 deferred it — Task 3's `main` calls it).
- Write the `fixtures/initial/` pair (manifest: `version "0.1.0"`, `previous_version null`, `initial true`, commits: one `feat: …` with SHA `"e"*40`, one legacy `"Add CustomerOutcome entities"` with `"type": null`; response: one section `Initial release`, entry citing `"eeeeeeee"`, top-level meta with `"previous_version": null`).
- Append the runbook to `CONTRIBUTING.md`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run --directory core pytest ../scripts/changelog/tests -v`
Expected: ALL PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/changelog CONTRIBUTING.md
git commit -m "feat: backfill initial-release mode, audit assertions, and release runbook"
```

---

### Task 7: Docs, spec reconciliation, full verification

**BLOCKED — requires PR #8 merge and Tasks 4–6.**

**Files:**
- Modify: `README.md` (short "What's new" note under Getting Started: run `<prog> changelog`; releases page carries the full notes)
- Modify: `docs/superpowers/specs/2026-10-15-cli-bundled-distribution-design.md` and `docs/superpowers/plans/2026-10-15-cli-bundled-distribution-and-self-update.md` (reconciliation notes: release-please now `skip-changelog` + `draft` + `force-tag-creation`; no committed `CHANGELOG.md` — superseded by the user-facing changelog design; `release.yml` should run via the release-please PAT token or chained job)
- Verify only (no code): full local check suite + PR with green checks.

- [ ] **Step 1: Doc edits**

README: 3–5 lines max. Spec/plan reconciliation: add a short "Updated by 2026-10-18 changelog design" note pointing at `docs/superpowers/specs/2026-10-18-user-facing-changelog-design.md` — do not rewrite their content.

- [ ] **Step 2: Run the full verification suite (CI parity)**

```bash
uv run ruff check .
uv run ruff format --check .
uv run --directory core mypy .
uv run --directory mcp_server mypy .
uv run --directory local_server mypy .
uv run --directory cli mypy .
uv run --directory client mypy .
uv run --directory connectors mypy .
uv run bandit -c pyproject.toml -r core/src mcp_server/src local_server/src cli/src client/src connectors/src
uv run --directory core pytest -v
uv run --directory core pytest ../scripts/changelog/tests -v
uv run --directory mcp_server pytest -v
uv run --directory local_server pytest -v
uv run --directory cli pytest -v
uv run --directory client pytest -v
uv run --directory connectors pytest -v
```

Expected: all clean. Locally smoke the offline harness once end-to-end:

```bash
uv run --directory core python ../scripts/changelog/generate.py \
  --offline-manifest scripts/changelog/fixtures/valid/manifest.json \
  --offline-response scripts/changelog/fixtures/valid/response.json \
  --out /tmp/changelog.json --notes /tmp/changelog.md --audit /tmp/manifest.json
```

- [ ] **Step 3: Open the PR and confirm GitHub Actions green**

**Definition of done:** PR opened against `main` with **all** GitHub Actions checks green — `lint`, `typecheck`, `security`, `test` (Python 3.10/3.11/3.12 matrix, incl. the new `Pytest (changelog generator)` step), `smoke`, `convention` (new), and the **`CI green`** aggregate job. Additionally: no `CHANGELOG.md` exists anywhere in the diff; `odi changelog` prints the spec'd copy against fixture state; the release-please config test guards the four flags.

- [ ] **Step 4: Commit**

```bash
git add README.md docs/superpowers
git commit -m "docs: changelog user docs and release-plan reconciliation"
```
