# Release Download & Run Instructions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every GitHub release page for Agentic ODI contains end-user instructions for downloading and running that release, listing all related artifacts (per-platform archives, checksums, installers), without altering the release-please changelog.

**Architecture:** A Python script (`scripts/release_instructions.py`) builds an end-user "## 📦 Download & Run" markdown section from the release's uploaded assets and applies it to the release body idempotently (HTML-comment markers). A new `release-instructions` job in `.github/workflows/release.yml` runs after the binary builds upload assets, invokes the script with `GH_TOKEN`, and publishes the updated body via `gh release edit`. Pure functions are unit-tested with pytest; the `gh` orchestration is tested with monkeypatched subprocess.

**Tech Stack:** Python 3.10+, GitHub Actions, `gh` CLI, pytest, ruff.

**Spec:** The user's request — "Whenever a release is made, we want the github releases page for that release to contain instructions for how to download and run that release, including related artifacts, from the end-users perspective." There is no separate design doc; this plan is the spec.

## Global Constraints

- Python 3.10+ (pyproject.toml `requires-python`)
- ruff: line-length 100; lint selects E4, E7, E9, F, I, UP, B, BLE
- pytest: `testpaths = ["apps", "packages", "tests", "website"]`, tests named `test_*.py`, asyncio strict mode
- Keep `README.md`/`docs/` current when capabilities change (AGENTS.md README guardrail)
- Do not alter the release-please changelog or any release body text outside the instructions section
- Idempotent: re-running the release workflow must not duplicate the instructions section

## Review Focus

1. Release published by release-please before assets exist → instructions step runs only after `build`/`checksums`/`upload-installers` finish, so download targets are present.
2. Re-running the release workflow (rebuild/re-upload) → must not duplicate the instructions section (idempotent marker replacement).
3. release-please changelog already in the body → must be preserved untouched; instructions added in their own section.
4. `checksums.txt` missing or no sha256 tool → must degrade gracefully to links-only instructions, not fail the release.
5. Windows (`.zip`) vs Linux/macOS (`.tar.gz`) archives → correct per-platform artifact names and `install.sh`/`install.ps1` links.

## File Structure

- Create: `scripts/release_instructions.py` — pure `build_instructions_section(tag, repo, artifacts, checksums_text) -> str` and `apply_instructions(body, section) -> str`, plus a `main()` that uses `gh` to fetch the release/assets/checksums and `gh release edit` to publish.
- Create: `tests/scripts/test_release_instructions.py` — pytest unit tests for the generator, body application, and `main()` with monkeypatched `subprocess` (no network, no `gh` required).
- Modify: `.github/workflows/release.yml` — add a `release-instructions` job (needs `checksums`, `upload-installers`) that runs the script with `GH_TOKEN`.
- Modify: `docs/installation.md` — document that each release page now carries download & run instructions (Release automation section).

## Tasks

### Task 1: Pure release-instructions generator and body application

**Files:**
- Create: `scripts/release_instructions.py`
- Create: `tests/scripts/test_release_instructions.py`

**Interfaces:**
- Consumes: none (pure functions)
- Produces: `build_instructions_section(tag: str, repo: str, artifacts: list[dict], checksums_text: str) -> str`; `apply_instructions(body: str | None, section: str) -> str`

- [ ] **Step 1: Write the failing test**

```python
def test_build_instructions_section_contains_artifacts_and_installers():
    artifacts = [
        {"name": "odi_0.7.0_linux_x86_64.tar.gz", "browser_download_url": "https://github.com/alehar9320/agentic-odi/releases/download/v0.7.0/odi_0.7.0_linux_x86_64.tar.gz", "size": 12345},
        {"name": "odi_0.7.0_windows_x86_64.zip", "browser_download_url": "https://github.com/alehar9320/agentic-odi/releases/download/v0.7.0/odi_0.7.0_windows_x86_64.zip", "size": 67890},
        {"name": "checksums.txt", "browser_download_url": ".../checksums.txt", "size": 100},
        {"name": "install.sh", "browser_download_url": ".../install.sh", "size": 200},
        {"name": "install.ps1", "browser_download_url": ".../install.ps1", "size": 210},
    ]
    section = build_instructions_section("v0.7.0", "alehar9320/agentic-odi", artifacts, "abc123  odi_0.7.0_linux_x86_64.tar.gz\n")
    assert "## 📦 Download & Run" in section
    assert "<!-- AGENTIC_ODI_DOWNLOAD_START -->" in section
    assert "<!-- AGENTIC_ODI_DOWNLOAD_END -->" in section
    assert artifacts[0]["browser_download_url"] in section
    assert artifacts[1]["browser_download_url"] in section
    assert "checksums.txt" in section
    assert "install.sh | sh" in section
    assert "install.ps1 | iex" in section
    assert "odi --version" in section
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/scripts/test_release_instructions.py -v`
Expected: FAIL with "name 'build_instructions_section' is not defined"

- [ ] **Step 3: Implement `build_instructions_section` and `apply_instructions` in `scripts/release_instructions.py`**

Build the section: heading, one-line summary, archive table (Platform | Archive | Download | SHA-256, hash taken from `checksums_text` when present), `checksums.txt` link + verify command, Linux/macOS one-line install via `install.sh`, Windows one-line install via `install.ps1`, manual extract + PATH steps, quick-run commands (`odi --version`, `odi --help`, `odi jobs list`), related-artifacts list, macOS quarantine / Windows SmartScreen note, wrapped in the start/end markers.
`apply_instructions` replaces text between the markers if present, otherwise appends the section separated by a blank line; leaves everything else in the body untouched.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/scripts/test_release_instructions.py -v`
Expected: PASS; also `uv run ruff check scripts/release_instructions.py tests/scripts/test_release_instructions.py`

- [ ] **Step 5: Commit**

```bash
git add scripts/release_instructions.py tests/scripts/test_release_instructions.py
git commit -m "feat(release): add end-user download & run instructions generator"
```

### Task 2: `main()` CLI that fetches release data via `gh` and publishes the updated body

**Files:**
- Modify: `scripts/release_instructions.py:1-1` (append `main()` and `if __name__ == "__main__"`)
- Modify: `tests/scripts/test_release_instructions.py` (add `main()` tests)

**Interfaces:**
- Consumes: `build_instructions_section`, `apply_instructions` from Task 1
- Produces: `main(argv: list[str] | None = None) -> int` — reads `--tag`, `--repo` (default `$GITHUB_REPOSITORY`), `--dry-run`; uses `gh release view` (current body), `gh api .../releases/tags/<tag>` (assets), `curl` (checksums.txt), then `gh release edit <tag> --notes-file <tmp>` unless `--dry-run` (prints new body)

- [ ] **Step 1: Write the failing test**

```python
def test_main_publishes_instructions(monkeypatch, tmp_path):
    calls = []
    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        if cmd[1] == "release" and cmd[2] == "view":
            class R: stdout = '{"body": "# Changelog\\n"}'
            return R()
        if cmd[1] == "api":
            class R: stdout = '{"assets": [{"name": "odi_0.7.0_linux_x86_64.tar.gz", "browser_download_url": "https://x/dl/odi_0.7.0_linux_x86_64.tar.gz", "size": 1}]}'
            return R()
        class R: stdout = ""
        return R()
    monkeypatch.setattr("subprocess.run", fake_run)
    rc = main(["--tag", "v0.7.0", "--repo", "alehar9320/agentic-odi", "--dry-run"])
    assert rc == 0
    edit_call = next(c for c in calls if c[1:4] == ["release", "edit", "v0.7.0"])
    notes_file = next(a for a in edit_call if a == "--notes-file")  # placeholder; real assertion reads the file
```

*(The concrete assertion reads the `--notes-file` path from `edit_call` and confirms it contains the download URL and "install.sh".)*

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/scripts/test_release_instructions.py::test_main_publishes_instructions -v`
Expected: FAIL with "name 'main' is not defined"

- [ ] **Step 3: Implement `main()` in `scripts/release_instructions.py`**

Parse args; `gh release view <tag> --repo <repo> --json body`; `gh api repos/<repo>/releases/tags/<tag> --json assets`; `curl -fsSL https://github.com/<repo>/releases/download/<tag>/checksums.txt` (ignore failure); build section; apply to body; `--dry-run` prints, otherwise write body to temp file and `gh release edit <tag> --repo <repo> --notes-file <temp>`. Missing `checksums.txt`/assets degrades gracefully.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/scripts/test_release_instructions.py -v`
Expected: PASS; also `uv run ruff check scripts/release_instructions.py tests/scripts/test_release_instructions.py`

- [ ] **Step 5: Commit**

```bash
git add scripts/release_instructions.py tests/scripts/test_release_instructions.py
git commit -m "feat(release): wire gh orchestration into release-instructions script"
```

### Task 3: Run the instructions step in the release workflow and document it

**Files:**
- Modify: `.github/workflows/release.yml` (add `release-instructions` job)
- Modify: `docs/installation.md` (Release automation section)

**Interfaces:**
- Consumes: `scripts/release_instructions.py` (Task 2) invoked with `GH_TOKEN` and tag `${{ github.ref_name }}`
- Produces: none (workflow behavior change; release body gains the instructions section)

- [ ] **Step 1: Add the `release-instructions` job to `.github/workflows/release.yml`**

Add a job `release-instructions` with `needs: [checksums, upload-installers]`, `runs-on: ubuntu-latest`, steps: checkout, setup uv, run `python scripts/release_instructions.py --tag "${{ github.ref_name }}" --repo "${{ github.repository }}"` with `env: GH_TOKEN: ${{ github.token }}`. This runs after archives, `checksums.txt`, and install scripts are uploaded, so every download target exists.

- [ ] **Step 2: Verify the workflow change**

Run: `uv run ruff check scripts/release_instructions.py` (lints the script the workflow calls)
Run: review the diff to confirm `needs: [checksums, upload-installers]` and that the job runs on the `push tags v*` trigger already on `release.yml`
Expected: ruff exits 0; diff shows exactly one new job and no other changes to `release.yml`

- [ ] **Step 3: Document release-page instructions in `docs/installation.md`**

Add to the Release automation section: each release page now carries an end-user "## 📦 Download & Run" section listing per-platform archives, `checksums.txt`, and the installers, plus one-line install and quick-run commands.

- [ ] **Step 4: Run the full check suite**

Run: `uv run pytest tests/scripts/test_release_instructions.py -v` and `uv run ruff check scripts/release_instructions.py tests/scripts/test_release_instructions.py`
Expected: all tests PASS; ruff exits 0

- [ ] **Step 5: Commit**

```bash
git add .github/workflows/release.yml docs/installation.md
git commit -m "feat(release): publish download & run instructions on every release"
```

---

## Self-Review (done before linking)

1. **Spec coverage:** Every phrase of the user's request maps to a task — release page instructions (Task 2 `main` + Task 3 job), end-user perspective (Task 1 section content), including related artifacts (archive table + checksums + installers). No gaps.
2. **Step scan:** Each step lets the implementer write exactly one reasonable thing; no TBD lines; function bodies appear only where the signature/tests don't determine them (the markdown layout, decided here).
3. **Type consistency:** `build_instructions_section`/`apply_instructions` signatures used identically in Task 1 tests, Task 2 implementation, and Task 3 (via `main`).
4. **Review Focus:** Each of the five failure modes has a task whose tests or behavior pin it (1→Task 3 `needs`; 2→Task 1 `apply_instructions` markers; 3→Task 1 append/replace preserving body; 4→Task 2 graceful degradation; 5→Task 1 archive table + both installer one-liners).
5. **Proportion:** Plan is roughly 1:1 with the change; code blocks are signatures/tests/short algorithms only.

**Plan complete and saved to `docs/superpowers/plans/2026-10-20-release-download-run-instructions.md`. Please review the plan. Does it capture what you want?**

I've made the how-it-gets-made calls myself (Python + `gh` + `release.yml` job + pytest unit tests + markers for idempotency), so nothing here is waiting on you. Once you confirm, I can implement it directly (Native execution) since the tasks are tightly coupled through `scripts/release_instructions.py` — there are only three tasks and the interfaces are fixed by this plan.
