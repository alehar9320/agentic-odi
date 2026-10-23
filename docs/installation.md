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
3. The merge cuts tag `vX.Y.Z` and the GitHub Release; the tag starts the
   `release` and `Tauri Release` workflows, which attach the CLI archives,
   `checksums.txt`, the install scripts, and the desktop bundles to it.
4. `e2e-install` runs after `release` succeeds and installs the published binary
   on Linux, macOS, and Windows.

**One-time setup (GitHub App).** GitHub holds workflow runs that start from
`GITHUB_TOKEN`-authored pushes ("This workflow requires approval from a
maintainer") and ignores the tag such a push creates, which is why releases used
to need a maintainer. A release-only GitHub App avoids both:

1. Settings → Developer settings → GitHub Apps → New GitHub App, with
   permissions: Contents `Read and write`, Issues `Read and write`, Pull
   requests `Read and write` (no webhook).
2. Install the App on this repository.
3. Add repository secrets `RELEASE_PLEASE_APP_CLIENT_ID` (the App's client ID)
   and `RELEASE_PLEASE_APP_PRIVATE_KEY` (a generated private key).

Until those secrets exist, the `release-please` workflow logs a warning and falls
back to `GITHUB_TOKEN`: releases still happen, but the release PR needs a
maintainer approval and merge, and the tag will not start the asset builds. After
adding the secrets, re-run the workflow (`gh workflow run release-please.yml`) or
push to `main` so the open release PR is re-driven by the App.

To check the installer without cutting a release, run
`bash scripts/tests/install_e2e.sh` — it serves a simulated release over HTTP and
exercises `scripts/install.sh` end to end (CI runs it too).
