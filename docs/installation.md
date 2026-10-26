# Installation

Prebuilt binaries are available for Linux, macOS, and Windows. Install the latest
release with one command:

```bash
curl -fsSL https://github.com/alehar9320/agentic-odi/releases/latest/download/install.sh | sh
```

The installer places the binary under `~/.local/share/agentic-odi/versions/<version>/`,
creates a `current` symlink, and symlinks `odi`, `odipm`, `odi-cli`, and
`agentic-odi` into `~/.local/bin/`.

If `~/.local/bin` is not on your PATH, add it (e.g.,
`export PATH="$HOME/.local/bin:$PATH"`). On Windows, the PowerShell installer
uses `~\AppData\Local\agentic-odi\` and copies `.exe` files to
`~\AppData\Local\agentic-odi\bin\`.

## Update

By default, `odi` auto-checks for updates once every 24 hours and applies the
update on the next run (auto-update is enabled by default). Control behavior
with:

- `odi update` — explicit check and update
- `--no-update` flag — skip auto-update for this run
- `AGENTIC_ODI_NO_UPDATE=1` — disable auto-update globally

When running from a non-frozen source install, auto-update is suppressed
automatically.

## Install layout

```text
~/.local/share/agentic-odi/
  ├── versions/<version>/
  │   └── odi (and bundled files)
  └── current -> versions/<version>

~/.local/bin/
  ├── odi -> ../share/agentic-odi/current/odi
  ├── odipm
  ├── odi-cli
  └── agentic-odi

~/.config/agentic-odi/  # state/preferences
```

Environment variables: `AGENTIC_ODI_INSTALL_DIR` (override install root),
`XDG_DATA_HOME`, `XDG_BIN_HOME`. The default backend is `local`
(`--backend local`); no MCP server is required.

## Unsigned binaries

macOS may quarantine downloaded binaries:
`xattr -d com.apple.quarantine ~/.local/bin/odi` (if needed). Windows SmartScreen
may show a warning for unsigned binaries; choose "More info → Run anyway" if you
trust the release.

## Release automation

Releases are cut and published by CI with no approval step:

1. Conventional commits land on `main`; `release-please` opens or updates the
   release PR.
2. The `release-please` workflow arms auto-merge on that PR. `main` requires the
   `CI green` check (ruleset `main-requires-ci-green`), so the PR merges itself
   as soon as CI passes — nobody clicks merge.
3. The merge cuts tag `vX.Y.Z` and the GitHub Release. The `release` and
   `Tauri Release` workflows attach the CLI archives, `checksums.txt`, the
   install scripts, and the desktop bundles to it. The `release-instructions`
   job then sets a human-friendly release title (`vX.Y.Z — YYYY-MM-DD`) and
   appends an end-user "## 📦 Download & Run" section to the release page:
   numbered download / verify / install / quick-start steps, a per-platform
   SHA-256 table, and a "Living Studio (desktop)" subsection with install
   commands for each Tauri bundle. All edits are idempotent on re-runs.
4. `e2e-install` runs after `release` succeeds and installs the published binary
   on Linux, macOS, and Windows.

**Why assets are triggered by `workflow_run`, not the tag.** `release-please`
creates the tag with the repository `GITHUB_TOKEN`, and GitHub does not start
workflow runs for events that token produces. A `push: tags` trigger alone
therefore never fired, and releases shipped with no assets at all —
`install.sh` and `checksums.txt` under `/releases/latest/download/` returned
404. Both asset workflows now also run on
`workflow_run: {workflows: [release-please], types: [completed]}`, which fires
from the `release-please` run itself and is not subject to that block.

**The gate keeps it cheap and self-healing.** `release-please` runs on every
push to `main`, so the `resolve` job runs `scripts/release_assets.py` first: it
reports the tag to build and whether that release is actually missing assets.
A run that finds the release complete does nothing instead of rebuilding every
platform. Because the check is "what is missing", re-running also repairs a
release that lost assets — the next push to `main`, or a manual run, fills the
gap.

**Manual self-heal.** To repair a specific release:

```bash
# Fill in whatever the release is missing (no-op if it is already complete)
gh workflow run release.yml -f tag=v0.12.0
gh workflow run tauri-release.yml -f tag=v0.12.0

# Rebuild every platform even if the release looks complete
gh workflow run release.yml -f tag=v0.12.0 -f force=true
```

Omit `-f tag=` to target the latest release.

**Version sync (no manual work).** release-please is the single writer of every
version literal in the repo — the six `pyproject.toml` files, the CLI
`_build_info.py`, and the Studio `Cargo.toml` / `tauri.conf.json` — via the
`extra-files` entries in `release-please-config.json`. The
`tests/scripts/test_version_sync.py` gate asserts they all match
`.release-please-manifest.json`, so a release PR stays green and auto-merges;
there is no longer a `chore: sync the declared version` step to do by hand.

**Optional one-time setup (GitHub App).** A release-only GitHub App is no longer
required for assets to be attached, but it still makes the release PR merge
without a maintainer approval. GitHub holds workflow runs that start from
`GITHUB_TOKEN`-authored pull requests ("This workflow requires approval from a
maintainer"):

1. Settings → Developer settings → GitHub Apps → New GitHub App, with
   permissions: Contents `Read and write`, Issues `Read and write`, Pull
   requests `Read and write` (no webhook).
2. Install the App on this repository.
3. Add repository secrets `RELEASE_PLEASE_APP_CLIENT_ID` (the App's client ID)
   and `RELEASE_PLEASE_APP_PRIVATE_KEY` (a generated private key).

Until those secrets exist, the `release-please` workflow logs a warning and falls
back to `GITHUB_TOKEN`: releases still happen and assets are still attached (the
`workflow_run` trigger does not depend on the App), but the release PR needs a
maintainer approval. After adding the secrets, re-run the workflow
(`gh workflow run release-please.yml`) or push to `main` so the open release PR
is re-driven by the App.

To check the installer without cutting a release, run
`bash scripts/tests/install_e2e.sh` — it serves a simulated release over HTTP and
exercises `scripts/install.sh` end to end (CI runs it too).
