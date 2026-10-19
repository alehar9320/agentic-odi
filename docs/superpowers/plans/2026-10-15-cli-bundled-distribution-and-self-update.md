# Bundled CLI Distribution & Self-Update Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship `odi` as a self-contained per-platform binary installed via `curl … | sh`, with background auto-update and an explicit `odi update`, driven by an automated tag/release pipeline.

**Architecture:** PyInstaller `--onedir` bundles the CLI plus its interpreter and dependency tree into a versioned directory; a small updater module downloads and atomically swaps a `current` symlink to a new version. release-please tags releases and a GitHub Actions matrix builds/attaches the archives.

**Tech Stack:** Python 3.10+, Typer, pydantic v2, fastmcp, PyInstaller, uv, GitHub Actions, release-please.

**Spec:** `docs/superpowers/specs/2026-10-15-cli-bundled-distribution-design.md`

## Global Constraints

- Python `>= 3.10` (workspace `requires-python`); CLI package `agentic-odi-cli`, entry `cli.cli:app`.
- Binary/primary command name `odi`; aliases `odipm`, `odi-cli`, and legacy `agentic-odi`.
- Versioning: **semver primary, release datetime secondary**. Tag `v<semver>`; embed `VERSION` and `RELEASE_DATE_UTC`.
- First released version is **`0.1.0`**.
- Install layout under `~/.local/share/agentic-odi/` (`versions/<v>`, `current` symlink); config/state under `~/.config/agentic-odi/`; bin dir `~/.local/bin`. All overridable via XDG env vars; install root also via `AGENTIC_ODI_INSTALL_DIR`.
- **User-local install only** — the installer never escalates; no `/usr/local`, no sudo.
- Auto-update is **on by default**, applies on next run, at most one check per 24h.
- Update opt-outs: `--no-update` flag and env `AGENTIC_ODI_NO_UPDATE=1`. Auto-update is disabled for non-frozen (source) runs and non-writable install dirs.
- Linux artifacts target **glibc 2.17-class** (build in a manylinux2014 / Ubuntu 20.04 container).
- **No UPX. No code signing** (v1). Bundle full functionality so `--backend mcp` works.
- Artifact names: `odi_<version>_<os>_<arch>.tar.gz` (unix) / `odi_<version>_<os>_<arch>.zip` (windows). `os`/`arch` ∈ {`linux`,`macos`,`windows`} × {`x86_64`,`arm64`}. A `checksums.txt` (SHA-256) ships alongside.
- `local` backend is the CLI default; `mcp` preserves prior behavior (env `AGENTIC_ODI_MCP_URL`, default `http://localhost:8000/mcp`).
- Repo `alehar9320/agentic-odi`; releases from GitHub Releases.

## Review Focus

Uncovered inputs/conditions most likely to bite a user — each has a test in the task that owns the code:

1. **Offline / network failure during update** — the command still runs; update silently no-ops. (Task 5)
2. **Checksum mismatch / truncated download** — install is never corrupted; update aborts. (Task 4)
3. **Interrupted swap** — `current` always points at a complete version dir; no partial state. (Task 4)
4. **Non-writable install dir** — auto-update disables gracefully instead of erroring. (Task 5)
5. **`odi update` on a source (non-frozen) install** — clear message, no crash, non-zero-free. (Task 6)
6. **Concurrent invocations** — only one update proceeds; the other skips. (Task 4)
7. **Local backend DB path** — directory is created on first write. (Task 3)

---

### Task 1: Build metadata + version display

**Files:**
- Create: `cli/src/cli/_build_info.py`
- Modify: `cli/src/cli/version.py`
- Modify: `cli/src/cli/cli.py` (`_version_callback`)
- Test: `cli/tests/test_build_info.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `_build_info.VERSION: str`, `_build_info.RELEASE_DATE_UTC: str` (ISO-8601 `…Z` or `""`), `_build_info.COMMIT: str`, `_build_info.TARGET: str`. `version.__version__: str`, `version.release_date: str | None`, `version.build_summary() -> str`, `version.verbose_summary() -> str`.

- [ ] **Step 1: Write the failing test**

```python
# cli/tests/test_build_info.py
from cli import version


def test_version_matches_build_info():
    from cli import _build_info

    assert version.__version__ == _build_info.VERSION
    assert version.__version__ == "0.1.0"


def test_build_summary_omits_date_when_empty(monkeypatch):
    monkeypatch.setattr(version, "RELEASE_DATE_UTC", "")
    assert version.build_summary() == "0.1.0"


def test_build_summary_includes_date_when_set(monkeypatch):
    monkeypatch.setattr(version, "RELEASE_DATE_UTC", "2026-10-15T21:13:00Z")
    assert version.build_summary() == "0.1.0 (2026-10-15)"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --directory cli pytest tests/test_build_info.py -v`
Expected: FAIL (no module `cli._build_info` / no `build_summary`).

- [ ] **Step 3: Create `_build_info.py` and rewrite `version.py`**

`_build_info.py` (committed dev defaults; CI overwrites these values at build time):

```python
VERSION = "0.1.0"
RELEASE_DATE_UTC = ""
COMMIT = "dev"
TARGET = "dev"
```

`version.py`:

```python
from cli._build_info import (
    COMMIT,
    RELEASE_DATE_UTC as _RELEASE_DATE_UTC,
    TARGET,
    VERSION,
)

__version__ = VERSION
RELEASE_DATE_UTC = _RELEASE_DATE_UTC
COMMIT = COMMIT
TARGET = TARGET
release_date = RELEASE_DATE_UTC or None


def build_summary() -> str:
    if RELEASE_DATE_UTC:
        return f"{VERSION} ({RELEASE_DATE_UTC[:10]})"
    return VERSION


def verbose_summary() -> str:
    return f"{build_summary()}\ncommit: {COMMIT}\ntarget: {TARGET}"
```

- [ ] **Step 4: Point `--version` at the summary**

In `cli/src/cli/cli.py`, change `_version_callback` to `typer.echo(version.build_summary())` (import `from cli import version`). Leave `__version__` imported for the existing test.

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run --directory cli pytest tests/test_build_info.py tests/test_cli.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add cli/src/cli/_build_info.py cli/src/cli/version.py cli/src/cli/cli.py cli/tests/test_build_info.py
git commit -m "feat(cli): build metadata and version display"
```

---

### Task 2: Path resolution module

**Files:**
- Create: `cli/src/cli/paths.py`
- Test: `cli/tests/test_paths.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `paths.install_root() -> Path`, `paths.bin_dir() -> Path`, `paths.config_dir() -> Path`, `paths.versions_dir() -> Path`, `paths.current_link() -> Path`, `paths.state_file() -> Path`, `paths.is_frozen() -> bool`, `paths.is_writable_dir(p: Path) -> bool`.

- [ ] **Step 1: Write the failing test**

```python
# cli/tests/test_paths.py
import sys
from pathlib import Path

import pytest

from cli import paths


def test_install_root_env_override(monkeypatch, tmp_path):
    monkeypatch.setenv("AGENTIC_ODI_INSTALL_DIR", str(tmp_path / "root"))
    assert paths.install_root() == tmp_path / "root"


def test_install_root_uses_xdg_data_home(monkeypatch, tmp_path):
    monkeypatch.delenv("AGENTIC_ODI_INSTALL_DIR", raising=False)
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    assert paths.install_root() == tmp_path / "data" / "agentic-odi"


def test_install_root_defaults_to_local_share(monkeypatch, tmp_path):
    monkeypatch.delenv("AGENTIC_ODI_INSTALL_DIR", raising=False)
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    assert paths.install_root() == tmp_path / ".local" / "share" / "agentic-odi"


def test_config_dir_uses_xdg_config_home(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))
    assert paths.config_dir() == tmp_path / "cfg" / "agentic-odi"


def test_derived_paths(monkeypatch, tmp_path):
    monkeypatch.setenv("AGENTIC_ODI_INSTALL_DIR", str(tmp_path / "root"))
    assert paths.versions_dir() == tmp_path / "root" / "versions"
    assert paths.current_link() == tmp_path / "root" / "current"
    assert paths.state_file().name == "update.json"


def test_is_frozen_false_by_default():
    assert paths.is_frozen() is False


@pytest.mark.skipif(sys.platform == "win32", reason="posix permission semantics")
def test_is_writable_dir(tmp_path):
    assert paths.is_writable_dir(tmp_path) is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --directory cli pytest tests/test_paths.py -v`
Expected: FAIL (no module `cli.paths`).

- [ ] **Step 3: Implement `paths.py`**

Implement XDG resolution: `install_root` = `AGENTIC_ODI_INSTALL_DIR` → `XDG_DATA_HOME/agentic-odi` → `~/.local/share/agentic-odi` (Windows: `%LOCALAPPDATA%\agentic-odi`). `config_dir` = `XDG_CONFIG_HOME/agentic-odi` → `~/.config/agentic-odi` (Windows: `%APPDATA%\agentic-odi`). `bin_dir` = `XDG_BIN_HOME` → `~/.local/bin` (Windows: `%LOCALAPPDATA%\agentic-odi\bin`). `is_frozen()` returns `bool(getattr(sys, "frozen", False))`. `is_writable_dir` uses `os.access(p, os.W_OK)`.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --directory cli pytest tests/test_paths.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add cli/src/cli/paths.py cli/tests/test_paths.py
git commit -m "feat(cli): XDG-aware path resolution"
```

---

### Task 3: Standalone local backend + `--backend` flag

**Files:**
- Create: `cli/src/cli/context.py`
- Modify: `cli/src/cli/cli.py` (root callback: add `--backend`)
- Modify: `cli/src/cli/outcomes.py` (use selected backend instead of hardcoded `"mcp"`)
- Modify: `cli/tests/test_outcomes_cli.py` (existing MCP tests must opt in)
- Test: `cli/tests/test_backend_selection.py`

**Interfaces:**
- Consumes: `backend.get_backend(backend=None, db_path=None, mcp_url=None) -> Backend` (reads env `AGENTIC_ODI_BACKEND`, default `"local"` when `backend` is `None`).
- Produces: `context.set_backend(name: str | None) -> None`, `context.selected_backend() -> str`. Root option `--backend` (default `None`) calls `set_backend`; `selected_backend()` falls back to `AGENTIC_ODI_BACKEND` then `"local"`. **Do not mutate `os.environ`** — that leaks across in-process test invocations.

- [ ] **Step 1: Write the failing test**

```python
# cli/tests/test_backend_selection.py
from unittest.mock import patch

from typer.testing import CliRunner

from cli.cli import app

ADD_ARGS = [
    "outcomes",
    "add",
    "--job-id",
    "job-1",
    "--direction",
    "minimize",
    "--unit",
    "time",
    "--object",
    "to setup",
    "--statement",
    "Minimize time",
    "--importance",
    "8.5",
    "--satisfaction",
    "4.0",
    "--category",
    "cost_reduction",
    "--business-statement",
    "Saves hours",
]


def test_outcomes_add_defaults_to_local(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTIC_ODI_DB", str(tmp_path / "odi.db"))
    runner = CliRunner()
    with patch("cli.outcomes._call_mcp") as mock_call:
        result = runner.invoke(app, ADD_ARGS)
    assert result.exit_code == 0
    mock_call.assert_not_called()


def test_outcomes_add_backend_mcp_calls_mcp(monkeypatch):
    monkeypatch.setenv("AGENTIC_ODI_DB", ":memory:")
    runner = CliRunner()
    with patch("cli.outcomes._call_mcp") as mock_call:
        mock_call.return_value = "ok"
        result = runner.invoke(app, ["--backend", "mcp", *ADD_ARGS])
    assert result.exit_code == 0
    mock_call.assert_called_once()


def test_score_uses_local_backend_by_default(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTIC_ODI_DB", str(tmp_path / "odi.db"))
    runner = CliRunner()
    result = runner.invoke(app, ["outcomes", "score", "8", "2"])
    assert result.exit_code == 0
    assert "Opportunity score" in result.output


def test_unknown_backend_exits_nonzero(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTIC_ODI_DB", str(tmp_path / "odi.db"))
    runner = CliRunner()
    result = runner.invoke(app, ["--backend", "nope", *ADD_ARGS])
    assert result.exit_code != 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --directory cli pytest tests/test_backend_selection.py -v`
Expected: FAIL (`test_outcomes_add_defaults_to_local` sees MCP call; `score` needs a server).

- [ ] **Step 3: Add the context module, global flag, and command wiring**

`cli/src/cli/context.py`:
```python
_selected: str | None = None


def set_backend(name: str | None) -> None:
    global _selected
    _selected = name


def selected_backend() -> str:
    if _selected is not None:
        return _selected
    return os.environ.get("AGENTIC_ODI_BACKEND", "local")
```

In `cli/src/cli/cli.py` root callback add `backend: str | None = typer.Option(None, "--backend", help="Backend: local | mcp")` and call `context.set_backend(backend)` in `main`.

In `cli/src/cli/outcomes.py`, replace every `get_backend("mcp", mcp_url=mcp_url)` with `get_backend(context.selected_backend(), mcp_url=mcp_url)`, and change `score` to:
```python
typer.echo(
    get_backend(context.selected_backend(), mcp_url=mcp_url).call(
        "compute_opportunity", {"importance": importance, "satisfaction": satisfaction}
    )
)
```
(`LocalBackend.call("compute_opportunity", …)` already exists and returns `f"Opportunity score: {score:.2f}"`.)

- [ ] **Step 4: Update existing MCP tests to opt in**

In `cli/tests/test_outcomes_cli.py`, prefix the arg lists of `test_outcomes_add_calls_mcp`, `test_score_calls_mcp`, and `test_outcomes_list_calls_mcp_with_args` with `["--backend", "mcp"]`.

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run --directory cli pytest tests/test_backend_selection.py tests/test_outcomes_cli.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add cli/src/cli/cli.py cli/src/cli/outcomes.py cli/tests/test_backend_selection.py cli/tests/test_outcomes_cli.py
git commit -m "feat(cli): standalone local backend with --backend flag"
```

---

### Task 4: Update engine primitives

**Files:**
- Create: `cli/src/cli/update.py`
- Test: `cli/tests/test_update.py`

**Interfaces:**
- Consumes: `paths.*` (Task 2).
- Produces:
  - `update.RELEASES_API: str` = `"https://api.github.com/repos/alehar9320/agentic-odi/releases/latest"`
  - `update.parse_version(s: str) -> tuple[int, int, int]`
  - `update.is_newer(latest: str, current: str) -> bool`
  - `update.asset_name(version: str, os_name: str, arch: str) -> str`
  - `update.current_platform() -> tuple[str, str]`
  - `update.verify_checksum(path: Path, expected_hex: str) -> bool`
  - `update.extract_archive(archive: Path, dest: Path) -> None`
  - `update.perform_update(version: str, archive_path: Path, expected_sha: str, install_root: Path) -> Path` (download happens in Task 5; this verifies, extracts to `versions/<version>`, and atomically flips `current`; returns the version dir)
  - `update.UpdateError(Exception)`

- [ ] **Step 1: Write the failing test**

```python
# cli/tests/test_update.py
import hashlib
import tarfile
from pathlib import Path

import pytest

from cli import update


def test_parse_and_compare():
    assert update.parse_version("v1.2.3") == (1, 2, 3)
    assert update.is_newer("0.2.0", "0.1.0") is True
    assert update.is_newer("0.1.0", "0.1.0") is False
    assert update.is_newer("0.1.0", "0.2.0") is False


def test_asset_name():
    assert update.asset_name("0.1.0", "linux", "x86_64") == "odi_0.1.0_linux_x86_64.tar.gz"
    assert update.asset_name("0.1.0", "windows", "x86_64") == "odi_0.1.0_windows_x86_64.zip"


def test_current_platform_mapping(monkeypatch):
    monkeypatch.setattr(update.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(update.platform, "machine", lambda: "arm64")
    assert update.current_platform() == ("macos", "arm64")


def _make_archive(tmp_path: Path, version: str) -> tuple[Path, str]:
    payload = tmp_path / "stage" / version / "odi"
    payload.parent.mkdir(parents=True)
    payload.write_text("#!/bin/sh\necho odi")
    archive = tmp_path / f"odi_{version}_linux_x86_64.tar.gz"
    with tarfile.open(archive, "w:gz") as tf:
        tf.add(payload.parent, arcname=".")
    sha = hashlib.sha256(archive.read_bytes()).hexdigest()
    return archive, sha


def test_perform_update_flips_current(tmp_path):
    archive, sha = _make_archive(tmp_path, "0.2.0")
    root = tmp_path / "install"
    version_dir = update.perform_update("0.2.0", archive, sha, root)
    assert version_dir == root / "versions" / "0.2.0"
    assert (root / "current").resolve() == version_dir.resolve()
    assert (version_dir / "odi").exists()


def test_perform_update_rejects_bad_checksum(tmp_path):
    archive, _ = _make_archive(tmp_path, "0.2.0")
    with pytest.raises(update.UpdateError):
        update.perform_update("0.2.0", archive, "deadbeef", tmp_path / "install")
    assert not (tmp_path / "install" / "current").exists()


def test_verify_checksum(tmp_path):
    p = tmp_path / "f"
    p.write_bytes(b"hello")
    good = hashlib.sha256(b"hello").hexdigest()
    assert update.verify_checksum(p, good) is True
    assert update.verify_checksum(p, "0" * 64) is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --directory cli pytest tests/test_update.py -v`
Expected: FAIL (no module `cli.update`).

- [ ] **Step 3: Implement `update.py`**

- `parse_version` strips a leading `v`, splits on `.`, takes first three ints.
- `is_newer` compares tuples.
- `asset_name` uses `.zip` for `os_name == "windows"`, else `.tar.gz`.
- `current_platform`: map `platform.system()` (`Linux`→`linux`, `Darwin`→`macos`, `Windows`→`windows`) and `platform.machine()` (`x86_64`/`AMD64`→`x86_64`, `arm64`/`aarch64`→`arm64`).
- `verify_checksum` streams the file through `hashlib.sha256` and compares case-insensitively.
- `extract_archive`: `tarfile` for `.tar.gz`, `zipfile` for `.zip`; extract into a temp dir **inside** `install_root/versions/` then `os.replace` to the final `versions/<version>` (so a crashed extract never leaves a partial `versions/<version>`).
- `perform_update`: verify checksum (raise `UpdateError` on mismatch), extract, then atomically flip: create `current.tmp` symlink → `os.replace("current.tmp", "current")`. On Windows, copy the version dir instead of symlinking and record the path in a `current` marker file.
- Serialize mutating work behind a lock file `install_root/.update.lock` created with `O_CREAT | O_EXCL`; if held, raise `UpdateError("update already in progress")`.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --directory cli pytest tests/test_update.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add cli/src/cli/update.py cli/tests/test_update.py
git commit -m "feat(cli): update engine primitives (verify, extract, atomic swap)"
```

---

### Task 5: Update check, cache, and download

**Files:**
- Modify: `cli/src/cli/update.py`
- Test: `cli/tests/test_update_check.py`

**Interfaces:**
- Consumes: Task 4 primitives; `paths.*`.
- Produces:
  - `update.CHECK_INTERVAL_SECONDS: int` = `86400`
  - `update.should_check(state_file: Path, now: float) -> bool`
  - `update.record_check(state_file: Path, now: float) -> None`
  - `update.latest_release(current: str, *, fetch: Callable[[str], str] | None = None) -> str | None` (returns newer version or `None`)
  - `update.download(version: str, dest_dir: Path, *, fetch_bytes: Callable[[str], bytes] | None = None) -> Path`
  - `update.auto_update_enabled(no_update: bool) -> bool`
  - `update.maybe_auto_update(*, no_update: bool, now: float) -> str | None`

- [ ] **Step 1: Write the failing test**

```python
# cli/tests/test_update_check.py
import json

from cli import update


def test_should_check_within_and_after_interval(tmp_path):
    state = tmp_path / "update.json"
    assert update.should_check(state, now=1000.0) is True
    update.record_check(state, now=1000.0)
    assert update.should_check(state, now=1000.0 + 100) is False
    assert update.should_check(state, now=1000.0 + update.CHECK_INTERVAL_SECONDS + 1) is True
    assert json.loads(state.read_text())["last_check"] == 1000.0


def test_latest_release_offline_returns_none():
    def boom(_url):
        raise OSError("network down")

    assert update.latest_release("0.1.0", fetch=boom) is None


def test_latest_release_returns_none_when_current():
    payload = json.dumps({"tag_name": "v0.1.0"})
    assert update.latest_release("0.1.0", fetch=lambda _u: payload) is None


def test_latest_release_returns_newer():
    payload = json.dumps({"tag_name": "v0.2.0"})
    assert update.latest_release("0.1.0", fetch=lambda _u: payload) == "0.2.0"


def test_auto_update_enabled_matrix(monkeypatch):
    assert update.auto_update_enabled(no_update=False) is True
    assert update.auto_update_enabled(no_update=True) is False
    monkeypatch.setenv("AGENTIC_ODI_NO_UPDATE", "1")
    assert update.auto_update_enabled(no_update=False) is False


def test_maybe_auto_update_disabled_is_noop(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTIC_ODI_INSTALL_DIR", str(tmp_path / "install"))
    assert update.maybe_auto_update(no_update=True, now=1000.0) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --directory cli pytest tests/test_update_check.py -v`
Expected: FAIL (names not defined).

- [ ] **Step 3: Implement**

- `should_check` / `record_check`: read/write `{"last_check": <float>}` JSON; missing/corrupt file ⇒ `True`.
- `latest_release`: GET `RELEASES_API` via injected `fetch` (default: `urllib.request`), parse `tag_name`, return stripped version when `is_newer`, else `None`; any exception ⇒ `None`.
- `download`: GET `https://github.com/alehar9320/agentic-odi/releases/download/v<version>/<asset_name>` into `dest_dir`, verify against `<asset>.sha256`; digits-only paths via injected `fetch_bytes` for tests.
- `auto_update_enabled`: `not no_update and not os.environ.get("AGENTIC_ODI_NO_UPDATE") and paths.is_frozen() and paths.is_writable_dir(paths.install_root())`.
- `maybe_auto_update`: if not enabled ⇒ `None`; if `not should_check(state_file(), now)` ⇒ `None`; else `record_check`, `latest_release(...)`; if newer, download + `perform_update`; swallow all exceptions and return `None` (never raises). Return the new version string on success.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --directory cli pytest tests/test_update_check.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add cli/src/cli/update.py cli/tests/test_update_check.py
git commit -m "feat(cli): update check, 24h cache, and download"
```

---

### Task 6: `odi update` command + startup hook

**Files:**
- Modify: `cli/src/cli/cli.py`
- Test: `cli/tests/test_update_command.py`

**Interfaces:**
- Consumes: `update.latest_release`, `update.auto_update_enabled`, `update.maybe_auto_update`, `paths.*`, `version.*`.
- Produces: `odi update [--check] [--force] [--version X.Y.Z] [--now]`; global `--no-update` flag; startup auto-update hook.

- [ ] **Step 1: Write the failing test**

```python
# cli/tests/test_update_command.py
from unittest.mock import patch

from typer.testing import CliRunner

from cli.cli import app


def test_update_check_up_to_date():
    runner = CliRunner()
    with patch("cli.update.latest_release", return_value=None):
        result = runner.invoke(app, ["update", "--check"])
    assert result.exit_code == 0
    assert "up to date" in result.output.lower()


def test_update_check_available():
    runner = CliRunner()
    with patch("cli.update.latest_release", return_value="0.2.0"):
        result = runner.invoke(app, ["update", "--check"])
    assert result.exit_code == 0
    assert "0.2.0" in result.output


def test_update_source_install_message():
    runner = CliRunner()
    with patch("cli.paths.is_frozen", return_value=False):
        result = runner.invoke(app, ["update"])
    assert result.exit_code == 0
    assert "source" in result.output.lower() or "not a bundled" in result.output.lower()


def test_no_update_flag_suppresses_startup_check(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTIC_ODI_DB", str(tmp_path / "odi.db"))
    runner = CliRunner()
    with patch("cli.update.maybe_auto_update") as mock_update:
        runner.invoke(app, ["--no-update", "outcomes", "score", "8", "2"])
    mock_update.assert_not_called()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --directory cli pytest tests/test_update_command.py -v`
Expected: FAIL (no `update` command; no `--no-update`).

- [ ] **Step 3: Implement the command and hook**

- Root callback: add `no_update: bool = typer.Option(False, "--no-update", help="Disable the startup update check")`. After the backend wiring, if `not no_update` call `update.maybe_auto_update(no_update=no_update, now=time.time())` inside a `threading.Thread(daemon=True)` so it never blocks; swallow exceptions.
- `@app.command("update")` function `update_cmd(check: bool = False, force: bool = False, version: str | None = None, now: bool = False)`:
  - If `not paths.is_frozen()`: print `"This is a source install; use your package manager to update."`, exit 0.
  - `check`: call `latest_release(version_mod.__version__)`; print `"up to date"` or `f"{latest} available"`; exit 0.
  - Otherwise resolve target (given `--version` or latest), download + `perform_update`; print `f"Updated to v{target}"`. If `--now`, `os.execv` into `paths.current_link()/"odi"`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run --directory cli pytest tests/test_update_command.py -v`
Expected: PASS.

- [ ] **Step 5: Run the whole CLI suite**

Run: `uv run --directory cli pytest -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add cli/src/cli/cli.py cli/tests/test_update_command.py
git commit -m "feat(cli): odi update command and startup auto-update hook"
```

---

### Task 7: PyInstaller onedir bundle + build script (highest-risk spike)

**Files:**
- Create: `packaging/pyinstaller/odi.spec`
- Create: `scripts/build_binary.sh`
- Create/modify: `cli/src/cli/__main__.py` (ensure it calls `app()`)

**Interfaces:**
- Consumes: `cli.cli:app`; `_build_info` values from env.
- Produces: `dist/odi/odi` (Linux/macOS) or `dist/odi/odi.exe`; a build script honoring env `VERSION`, `RELEASE_DATE_UTC`, `COMMIT`, `TARGET`.

- [ ] **Step 1: Write `scripts/build_binary.sh`**

The script: run `uv sync --all-packages --locked`; write `cli/src/cli/_build_info.py` from env (`VERSION` required; `RELEASE_DATE_UTC`, `COMMIT`, `TARGET` default to dev values); run `uv run --directory cli pyinstaller --clean --noconfirm ../../packaging/pyinstaller/odi.spec`; then package `dist/odi` into `odi_${VERSION}_${TARGET}.tar.gz` (or `.zip` when `TARGET` starts with `windows`).

- [ ] **Step 2: Write `packaging/pyinstaller/odi.spec`**

Onedir spec named `odi`, entry `cli/src/cli/__main__.py`, `pathex=["cli/src"]`. Use `PyInstaller.utils.hooks.collect_all` for `fastmcp`, `mcp`, `pydantic`, `pydantic_core`, `starlette`, `uvicorn`, `anyio`; append their `datas`/`binaries`/`hiddenimports`. `console=True`, `upx=False`.

- [ ] **Step 3: Build and smoke-test (the spike)**

Run:
```bash
VERSION=0.1.0 RELEASE_DATE_UTC=2026-10-15T21:13:00Z COMMIT=dev TARGET=linux_x86_64 bash scripts/build_binary.sh
./dist/odi/odi --version
./dist/odi/odi --help
AGENTIC_ODI_DB=/tmp/odi-spike.db ./dist/odi/odi outcomes score 8 2
```
Expected: `--version` prints `0.1.0 (2026-10-15)`; `--help` lists `outcomes`, `connectors`, `update`; `outcomes score 8 2` prints an opportunity score. **If bundling `fastmcp`/`pydantic-core` fails, stop and fix the spec's hidden imports before proceeding** (this is the plan's biggest risk).

- [ ] **Step 4: Measure startup and size**

Run: `time ./dist/odi/odi --version` and `du -h dist/odi | tail -1`.
Expected: startup well under ~0.5s (onedir, no extraction); note the compressed size. If the compressed archive exceeds ~80 MB, add a lazy `fastmcp` import in `outcomes.py` **only if** the frozen `--backend mcp` path still works, then re-run Step 3.

- [ ] **Step 5: Commit**

```bash
git add packaging/pyinstaller/odi.spec scripts/build_binary.sh cli/src/cli/__main__.py
git commit -m "build(cli): PyInstaller onedir bundle and build script"
```

---

### Task 8: `install.sh`

**Files:**
- Create: `scripts/install.sh`

**Interfaces:**
- Consumes: release asset names (Task 4), install layout (Task 2).
- Produces: a POSIX-sh installer used by `curl -fsSL …/install.sh | sh`.

- [ ] **Step 1: Implement `install.sh`**

Detect OS (`uname -s`) and arch (`uname -m`; `aarch64`→`arm64`). Resolve `VERSION` from `AGENTIC_ODI_VERSION` or the GitHub `releases/latest` `tag_name` (strip `v`). Download `odi_${VERSION}_${TARGET}.tar.gz` and `checksums.txt` from the release; verify with `sha256sum -c` (fallback `shasum -a 256`). Extract into `$INSTALL_ROOT/versions/$VERSION` (temp dir + `mv`). Atomically point `current` (`ln -sfn` to a temp name then `mv -T`). Symlink `odi`, `odipm`, `odi-cli`, `agentic-odi` into `$BIN_DIR`. Print a PATH hint if `$BIN_DIR` is not on `$PATH`. Never use sudo.

- [ ] **Step 2: Dry-run against a locally built archive**

Run (using the Task 7 archive and a local file URL via a tiny `python -m http.server`):
```bash
VERSION=0.1.0 RELEASE_DATE_UTC=2026-10-15T21:13:00Z COMMIT=dev TARGET=linux_x86_64 bash scripts/build_binary.sh
mkdir -p /tmp/odi-rel && cp odi_0.1.0_linux_x86_64.tar.gz /tmp/odi-rel/ && (cd /tmp/odi-rel && sha256sum odi_0.1.0_linux_x86_64.tar.gz > checksums.txt)
AGENTIC_ODI_INSTALL_DIR=/tmp/odi-home AGENTIC_ODI_BASE_URL=http://127.0.0.1:8099 bash scripts/install.sh
```
(Support `AGENTIC_ODI_BASE_URL` as an override for the release base URL, used by tests.) Serve `/tmp/odi-rel` on 8099 in another shell.
Expected: `/tmp/odi-home/current -> versions/0.1.0`; running `PATH=/tmp/odi-home/bin:$PATH odi --version` prints the version; `odipm`, `odi-cli`, `agentic-odi` all resolve.

- [ ] **Step 3: Verify idempotent reinstall**

Re-run Step 2's install; expect exit 0, no errors, `current` still correct.

- [ ] **Step 4: Commit**

```bash
git add scripts/install.sh
git commit -m "feat: curl installer for odi"
```

---

### Task 9: `install.ps1`

**Files:**
- Create: `scripts/install.ps1`

**Interfaces:**
- Consumes: same inputs as Task 8.
- Produces: a PowerShell installer used by `irm …/install.ps1 | iex`.

- [ ] **Step 1: Implement `install.ps1`**

Mirror `install.sh` for Windows: detect arch, resolve version, download the `.zip` and `checksums.txt`, verify with `Get-FileHash SHA256`, expand to `$env:LOCALAPPDATA\agentic-odi\versions\$Version`, write a `current` marker, and place `odi.exe`, `odipm.exe`, `odi-cli.exe`, `agentic-odi.exe` (copies, not symlinks) in `$env:LOCALAPPDATA\agentic-odi\bin`.

- [ ] **Step 2: Static check**

Run: `pwsh -NoProfile -Command "Get-Content scripts/install.ps1 | Out-String | Invoke-Expression"` is destructive — instead lint parse only:
`pwsh -NoProfile -Command "[void][System.Management.Automation.Language.Parser]::ParseFile('scripts/install.ps1', [ref]\$null, [ref]\$null)"`
Expected: no parse errors. (Full run is covered by the Windows CI job in Task 11.)

- [ ] **Step 3: Commit**

```bash
git add scripts/install.ps1
git commit -m "feat: PowerShell installer for odi"
```

---

### Task 10: release-please configuration

**Files:**
- Create: `release-please-config.json`
- Create: `.release-please-manifest.json`
- Create: `.github/workflows/release-please.yml`

**Interfaces:**
- Consumes: Conventional Commits on `main`.
- Produces: tags `vX.Y.Z` + GitHub Releases; first release `0.1.0`.

- [ ] **Step 1: Add config**

`release-please-config.json`:
```json
{ "release-type": "simple", "packages": { ".": { "release-type": "simple" } } }
```
`.release-please-manifest.json`:
```json
{ ".": "0.1.0" }
```

- [ ] **Step 2: Add the workflow**

`.github/workflows/release-please.yml`: trigger `push` to `main`; `permissions: contents: write, pull-requests: write`; step `googleapis/release-please-action@v4` with `config-file` and `manifest-file`.

- [ ] **Step 3: Validate JSON**

Run: `uv run python -c "import json; json.load(open('release-please-config.json')); json.load(open('.release-please-manifest.json'))"`
Expected: no output (valid).

- [ ] **Step 4: Commit**

```bash
git add release-please-config.json .release-please-manifest.json .github/workflows/release-please.yml
git commit -m "ci: release-please config for semver releases"
```

---

### Task 11: Release build matrix

**Files:**
- Create: `.github/workflows/release.yml`

**Interfaces:**
- Consumes: `scripts/build_binary.sh` (Task 7), install scripts (Tasks 8–9).
- Produces: archives + `checksums.txt` + installers attached to each `v*` Release.

- [ ] **Step 1: Write `release.yml`**

Trigger `on: push: tags: ["v*"]`; `permissions: contents: write`. Matrix (`include`):

| os | runner | target | container |
|---|---|---|---|
| linux | `ubuntu-latest` | `linux_x86_64` | old-glibc container |
| linux | `ubuntu-24.04-arm` | `linux_arm64` | old-glibc container |
| macos | `macos-14` | `macos_arm64` | — |
| macos | `macos-13` | `macos_x86_64` | — |
| windows | `windows-latest` | `windows_x86_64` | — |

Each job: checkout; setup uv (reuse `.github/actions/setup`); derive `VERSION` from the tag (`${GITHUB_REF_NAME#v}`) and `RELEASE_DATE_UTC` from `git log -1 --format=%cI`; run `scripts/build_binary.sh` (Linux jobs inside the manylinux2014/Ubuntu 20.04 container); generate `checksums.txt`; upload assets to the Release (`softprops/action-gh-release@v2` or `gh release upload`). A final job uploads `scripts/install.sh` and `scripts/install.ps1` as release assets.

- [ ] **Step 2: Lint the workflow YAML**

Run: `uv run python -c "import yaml,sys; yaml.safe_load(open('.github/workflows/release.yml'))"`
Expected: no output (valid YAML).

- [ ] **Step 3: Verify against a throwaway tag**

After merge, push a test tag (e.g. `v0.0.1-test`) from a scratch branch and confirm all five jobs upload assets with a valid `checksums.txt`; then delete the tag/release. (Documented manual verification — no automated assertion.)

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/release.yml
git commit -m "ci: release build matrix for all platforms"
```

---

### Task 12: End-to-end install test + docs

**Files:**
- Create: `.github/workflows/e2e-install.yml` (or add an `e2e` job to `ci.yml`)
- Modify: `README.md` (install + update section)

**Interfaces:**
- Consumes: all prior tasks.
- Produces: an automated test that installs the published binary and runs it; user-facing docs.

- [ ] **Step 1: Add the e2e job**

A workflow that, on released tags (and `workflow_dispatch`), on `ubuntu-latest`, `macos-latest`, and `windows-latest`: runs the real `curl -fsSL https://github.com/alehar9320/agentic-odi/releases/download/<tag>/install.sh | sh` into a temp `AGENTIC_ODI_INSTALL_DIR`, then asserts `odi --version`, `odi --help`, and `odi outcomes score 8 2` succeed.

- [ ] **Step 2: Run the e2e job manually against the latest release**

Run: `gh workflow run e2e-install.yml -f tag=<latest>` then `gh run watch`.
Expected: all three OS jobs green.

- [ ] **Step 3: Update the README**

Add an "Install" section (`curl -fsSL …/install.sh | sh`) with the alias list, an "Update" section (auto vs `odi update`, `AGENTIC_ODI_NO_UPDATE`, `--no-update`), the install layout, and the unsigned-binary workarounds (macOS `xattr -d com.apple.quarantine`, Windows SmartScreen). Note that `--backend local` is the default and needs no server.

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/e2e-install.yml README.md
git commit -m "docs+ci: install/update docs and end-to-end install test"
```

---

## Self-Review

- **Spec coverage:** artifact/bundler → Task 7; install layout → Tasks 2/8/9; update mechanism (auto+explicit) → Tasks 4/5/6; versioning (semver+datetime) → Tasks 1/7/11; command names → Tasks 8/9/12; CI/tagging → Tasks 10/11; install scripts → Tasks 8/9; docs/e2e → Task 12; standalone local backend (Decision 7) → Task 3; glibc floor (Decision 8) → Task 11; size threshold / Windows fallback / user-local-only / first-version calls → Tasks 7, 5, 8, 10 respectively.
- **Type consistency:** `Paths` names (`versions_dir`, `current_link`, `state_file`, `is_frozen`, `is_writable_dir`) are used identically in Tasks 4–6. `update` names (`parse_version`, `is_newer`, `asset_name`, `current_platform`, `verify_checksum`, `perform_update`, `latest_release`, `maybe_auto_update`, `auto_update_enabled`, `CHECK_INTERVAL_SECONDS`) match across Tasks 4–6. `version.build_summary()`/`verbose_summary()` consistent in Tasks 1/6.
- **Review Focus tests placed:** (1) Task 5 offline test; (2) Task 4 bad checksum; (3) Task 4 atomic flip; (4) Task 5 `auto_update_enabled` writable check; (5) Task 6 source-install message; (6) Task 4 lock; (7) Task 3 local DB path.
- **Proportion:** kept to interfaces, test names, and assertions; code blocks are only for pinned values (build metadata, config JSON, the spec/script shape), not bodies.
