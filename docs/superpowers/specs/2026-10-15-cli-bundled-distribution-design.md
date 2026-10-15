# Bundled CLI Distribution & Self-Update — Design

Date: 2026-10-15
Status: Approved (design); implementation plan pending

## Intent and why

Today the `agentic-odi` CLI is consumed by installing the whole `uv`
workspace in editable mode. We want a world-class, "state-of-the-art"
binary distribution: a self-contained executable that a user installs with
a single `curl … | sh` and that keeps itself current without the user
managing a Python toolchain.

This mirrors the experience of `gh`, `deno`, `bun`, and `ollama`: install
with a one-liner, get a native-feeling command, and receive updates without
thinking about it.

## Goals

- A self-contained artifact per platform with **near-instant startup**.
- One-line install: `curl -fsSL <url>/install.sh | sh` (and a PowerShell
  equivalent for Windows).
- **Automatic background updates, on by default**, plus an explicit
  user-invoked update command.
- Automated versioning and release/tag creation driven by CI.
- Support Linux (x86_64, arm64), macOS (x86_64, arm64), Windows (x86_64).

## Non-goals

- Code signing / notarization (deferred; document the workarounds).
- Packaging the MCP server / local server / chat client as binaries (this is
  about the CLI only).
- Publishing to PyPI as the primary distribution channel.
- A vanity download domain (use GitHub Releases for now).

## Anti-goals (what would make this a failure even if it "works")

- Shipping a build that crashes on `--backend mcp` because a dependency was
  stripped for size.
- An auto-updater that blocks or slows a command when offline.
- An updater that can corrupt an install if interrupted (non-atomic swap).
- Replacing a running executable in place (fails on Windows; races on unix).

## Constraints

- The CLI is a Python package (`agentic-odi-cli`) in a `uv` workspace with
  six members. Once bundled, the CLI no longer depends on the workspace at
  runtime; the source tree keeps its current editable-install workflow.
- **Correction found during design review:** although a `LocalBackend` exists
  (`cli/src/cli/backend.py`), every `outcomes` command currently hardcodes the
  MCP backend (`get_backend("mcp", …)`, and `score` calls `_call_mcp`
  directly). `LocalBackend` is unreachable and there is no `--backend` flag.
  So the CLI as shipped effectively requires a running MCP server. Wiring the
  local backend up and exposing `--backend {local,mcp}` is **in scope** (see
  Decision 7) so the binary is genuinely useful standalone.
- The CLI imports `fastmcp` at module top (`cli/src/cli/outcomes.py`), which
  pulls a large tree (mcp, httpx, starlette, uvicorn). `pydantic` v2 pulls
  compiled `pydantic-core`. These are the bundling risk points.
- No git tags exist today; `cli/src/cli/version.py` hardcodes `0.1.0`.
- Reproduction of the current runner matrix: GitHub-hosted Ubuntu, macOS,
  and Windows runners.

## Decisions (made by the human partner unless noted)

1. **Bundler: PyInstaller `--onedir`, shipped as a compressed archive.**
   `--onefile` re-extracts to a temp dir on every invocation and adds
   ~0.5–1.5s startup latency; `--onedir` starts near-instantly. We accept
   "one downloadable archive, installed into a versioned directory" instead
   of "one literal file." Nuitka is the fallback if PyInstaller proves
   unusable.
2. **No code signing for now.** Document Gatekeeper (macOS) and SmartScreen
   (Windows) workarounds in the README.
3. **Background auto-update is ON by default**, applied on the next run,
   with opt-out (flag/env). Also expose explicit `odi update`.
4. **Binary size: full functionality, optimized.** *It just works* beats
   *small* (builder's call). Bundle everything so `--backend mcp` works out
   of the box. Optimize with strip/exclusions. **No UPX** (AV false
   positives). Because onedir has no per-run extraction cost, size is only a
   download-time concern. **Concrete threshold (builder's call):** if the
   compressed per-platform archive exceeds **~80 MB**, add the lazy-`fastmcp`
   work in Phase 2 *only if* the MCP backend still works in the frozen binary;
   otherwise keep it bundled and accept the size.
5. **Versioning: semver primary + release datetime secondary.**
   Git tag is `v<semver>`; the build also embeds the release datetime (UTC)
   so users can see *when* a version was released.
6. **Command names:** primary `odi`; additionally `odipm` and `odi-cli`;
   keep `agentic-odi` for backward compatibility.
7. **Wire up the local backend + a `--backend {local,mcp}` flag** so the
   binary works standalone out of the box (human partner's call; see the
   correction under Constraints). This is a functional change to
   `cli/src/cli/outcomes.py` and `cli/src/cli/backend.py`, included in the
   plan. `local` is the default; `mcp` preserves today's behavior.
8. **Linux compatibility floor: glibc 2.17-class.** Linux artifacts are built
   inside an old-glibc container (manylinux2014 / Ubuntu 20.04) so they run on
   virtually all current distros, not just the runner's glibc (human
   partner's call). Adds a container step to the Linux build jobs.

## The how (decided)

### Artifact

- PyInstaller **onedir** build producing an executable named `odi`
  (`odi.exe` on Windows) plus its `_internal/` support directory.
- Packaged per platform:
  - unix: `odi_<version>_<os>_<arch>.tar.gz`
  - windows: `odi_<version>_<os>_<arch>.zip`
- `os`/`arch` tokens: `linux/x86_64`, `linux/arm64`, `macos/x86_64`,
  `macos/arm64`, `windows/x86_64`.
- A `checksums.txt` (SHA-256) is published alongside the archives.

### Install layout

```
~/.local/share/agentic-odi/
  versions/0.1.0/            # extracted onedir bundle (odi + _internal/)
  versions/0.2.0/
  current -> versions/0.2.0  # atomic symlink; flipping it IS the update
~/.local/bin/
  odi         -> ../share/agentic-odi/current/odi
  odipm       -> ../share/agentic-odi/current/odi
  odi-cli     -> ../share/agentic-odi/current/odi
  agentic-odi -> ../share/agentic-odi/current/odi
~/.config/agentic-odi/update.json   # last-check time + state
```

- Install root overridable via `AGENTIC_ODI_INSTALL_DIR`.
- Both `share` and `bin` roots derive from XDG (`XDG_DATA_HOME`,
  `XDG_BIN_HOME`) with sensible fallbacks. Use `platformdirs` or hand-rolled
  XDG resolution (builder's call).
- **v1 is user-local only — no sudo / system-wide mode.** The installer never
  escalates and never writes to `/usr/local`. System-wide installs are out of
  scope for v1 (builder's call); if added later, they become install-script
  managed with auto-update disabled.
- **Windows:** no symlinks. Install to `%LOCALAPPDATA%\agentic-odi\`; ship
  `odi.exe` plus `odipm.exe`, `odi-cli.exe`, `agentic-odi.exe` copies.
  Updates use a deferred helper process so the running `.exe` can be swapped.
  **Fallback (builder's call):** if the Phase 1 spike shows the deferred swap
  cannot be made safe, Windows auto-apply falls back to check-only with an
  "update available" notice, and `odi update` becomes the apply path on
  Windows. The anti-goal (never corrupt an install) wins over auto-on-by-default.

### Update mechanism

- `cli/update.py` module providing:
  - `check_for_update()` → query GitHub Releases "latest"; semver-compare
    against the embedded version.
  - `resolve_asset()` → map runtime OS/arch to the correct asset name.
  - `verify_checksum()` → SHA-256 verify against `checksums.txt`.
  - `perform_update()` → download → verify → extract to
    `versions/<new>` → **atomically** re-point `current`.
  - A **lockfile** guards concurrent updates.
- **Auto path:** on launch, at most one network check per 24h (cached in
  `update.json`). If newer, download + verify + extract + flip in a
  background thread, then print
  `Updated to vX.Y.Z — takes effect next run`. Never blocks the command;
  network failures are swallowed.
- **Suppressed when:** not a frozen build (running from source), env
  `AGENTIC_ODI_NO_UPDATE=1`, global flag `--no-update`, non-interactive
  context, lock held, or install location not writable.
- **Explicit path:** `odi update [--check] [--force] [--version X.Y.Z]
  [--now]`. `--now` re-execs into the newly installed version.
- Updates are never applied to a running process; they apply on next launch.

### Versioning & naming

- Single source of truth = the git tag `vX.Y.Z`.
- Build step injects a generated `_build_info.py` with:
  `VERSION = "0.1.0"`, `RELEASE_DATE_UTC = "2026-10-15T21:13:00Z"`,
  `COMMIT = "<sha>"`, `TARGET = "<os>-<arch>"`.
- `cli/version.py` reads from `_build_info` (falling back for editable/dev
  installs).
- `odi --version` → `0.1.0 (2026-10-15)`.
- `odi --version --verbose` → adds commit SHA, build date, target triple.

### CI / tagging

- **release-please** (Conventional Commits) maintains a release PR that
  bumps the version and updates the changelog. Merging it creates the tag
  `vX.Y.Z` and a GitHub Release.
- A single **root component** version for the whole repo (one product
  version), not per-package versions.
- **First release is `0.1.0`** (builder's call): with no prior tags and a
  commit history that would otherwise make release-please derive a higher
  number, pin the baseline explicitly (release-please `initial-version` /
  bootstrap tag) so the first `curl | sh` user gets `0.1.0` matching
  `version.py`.
- `release.yml` triggers on tag push → matrix build → uploads archives +
  `checksums.txt` + `install.sh` + `install.ps1` to the Release → publishes.

| Runner | Target | Notes |
|---|---|---|
| `ubuntu-latest` | linux-x86_64 | build inside old-glibc container |
| `ubuntu-24.04-arm` | linux-arm64 | build inside old-glibc container |
| `macos-14` | macos-arm64 | |
| `macos-13` (or Rosetta on 14) | macos-x86_64 | see flagged wrinkles |
| `windows-latest` | windows-x86_64 | |

Linux jobs run PyInstaller inside a manylinux2014 / Ubuntu 20.04 container
(glibc 2.17-class) to maximize distro compatibility (Decision 8).

## Phasing

1. **Spike (highest risk):** PyInstaller `--onedir` bundle the CLI on Linux;
   run `--version`, `--help`, `outcomes add` against both backends. Confirms
   `pydantic-core` + `fastmcp` bundle cleanly and startup is fast.
2. `_build_info` injection + `cli/update.py` + `odi update` command +
   startup hook, with unit tests (semver compare, OS/arch→asset resolution,
   checksum verify, cache/lock, atomic flip).
3. `install.sh` / `install.ps1` (aliases, PATH, completions).
4. release-please config + `release.yml` matrix + checksums.
5. README install/update docs + end-to-end test installing from a real
   tagged Release.

## Flagged wrinkles

- **macOS Intel builds:** `macos-13` is the last x86_64 runner and is being
  retired; fallback is an x86_64 build under Rosetta on `macos-14`. May
  force a "drop Intel Mac" decision later.
- **Auto-update assumes a writable home.** v1 installs are user-local, so
  this holds. If a user relocates via `AGENTIC_ODI_INSTALL_DIR` to a
  non-writable location, auto-update detects it and no-ops.
- **Offline behavior:** auto-update must always no-op gracefully and never
  block or slow a command.
- **`fastmcp` weight:** bundled for correctness; size revisited only if
  measured and if the MCP backend can stay functional.

## Left to the builder

- Exact PyInstaller spec / hidden-import hooks and exclusion list.
- Exact `platformdirs` vs hand-rolled XDG resolution.
- Exact lockfile mechanism (file lock vs atomic O_EXCL).
- Windows deferred-swap implementation details.
- release-please configuration specifics.

## Builder calls made during design review

- **Size threshold:** ~80 MB compressed triggers consideration of lazy
  `fastmcp`, conditional on the MCP backend surviving in the frozen binary.
- **First version:** `0.1.0`, pinned explicitly in release-please config.
- **Installer privilege:** user-local only in v1; no sudo/system-wide path.
- **Windows updater fallback:** deferred swap, else check-only + explicit
  `odi update`.

## Assumptions confirmed by the human partner

1. Keep `agentic-odi` as an alias alongside `odi` / `odipm` / `odi-cli`.
2. Release assets live on GitHub Releases (`alehar9320/agentic-odi`) for now.
3. release-please with a single root component (one product version).
