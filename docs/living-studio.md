# Running The Living Studio

**The Living Studio** is the conversational GUI for Outcome-Driven Innovation:
an interactive Opportunity Landscape, Universal Job Map, WYSIWYG Impact
Simulation, and Causal Lineage inspection, paired with an autonomous agent
connected to the MCP server.

The Studio runs three ways. All of them serve the same SPA, which talks only to
the sidecar on `http://127.0.0.1:8100` — the SPA never contacts MCP or the LLM
directly.

## Architecture

```text
┌────────────────────────────┐  /api (JSON)  ┌───────────────────────────────┐
│  Living Studio SPA         │ ────────────▶ │  apps/studio-api (sidecar)    │
│  React + TS + Vite         │  /api/chat    │  FastAPI on 127.0.0.1:8100    │
│  (browser or Tauri webview)│ ◀──────────── │  - config / health / canvas   │
└────────────────────────────┘  SSE stream   │  - steps / outcomes (via MCP) │
                                             │  - /api/chat (LLM tool-loop)  │
                                             └───────────────┬───────────────┘
                                                             │ MCP (HTTP)
                                                             ▼
                                             ┌───────────────────────────────┐
                                             │  apps/mcp-server :8000/mcp    │
                                             └───────────────────────────────┘
                                                             ▲
                                                             │ OpenAI-compatible
                                             ┌───────────────┴───────────────┐
                                             │  Your local LLM backend       │
                                             └───────────────────────────────┘
```

## 1. Web — production build (recommended for a quick look)

```bash
npm --prefix apps/studio run build   # build the SPA into apps/studio/dist
python scripts/dev.py            # starts MCP :8000 + sidecar :8100
```

| Service | URL |
|---|---|
| MCP Server | http://localhost:8000/mcp |
| Living Studio | http://127.0.0.1:8100 |

`python scripts/dev.py` starts both processes concurrently; press **Ctrl+C** to
stop both.

## 2. Web — dev with hot reload

Vite proxies `/api` to the sidecar:

```bash
npm --prefix apps/studio run dev:full   # MCP + sidecar + Vite together
# open http://localhost:5173
```

## 3. Desktop — Tauri 2

The app spawns the MCP server and sidecar itself:

```bash
npm --prefix apps/studio run tauri dev     # dev window
npm --prefix apps/studio run tauri build   # bundles: .deb / .AppImage (Linux), .app / .dmg (macOS), .msi / .exe (Windows)
```

> [!NOTE]
> **Tauri prerequisites.** The desktop build needs the WebKitGTK toolchain and
> Rust 1.90+. On Debian/Ubuntu:
>
> ```bash
> sudo apt-get install -y libwebkit2gtk-4.1-dev build-essential pkg-config curl wget file \
>   libxdo-dev libssl-dev libayatana-appindicator3-dev librsvg2-dev patchelf xdg-utils libfuse2t64
> ```
>
> The Tauri CLI ships as the `@tauri-apps/cli` npm dev dependency
> (`npm --prefix apps/studio run tauri`). The sidecar is launched with
> `uv run python -m …` from the repository root; if the app cannot locate the
> repo root, set `AGENTIC_ODI_REPO_ROOT`.

## Desktop signing & updater secrets

Self-updating and code signing are **env-driven**: if a secret is absent, an
unsigned artifact is produced instead of failing. CI reads these from GitHub
Actions secrets.

| Secret | Purpose |
|---|---|
| `TAURI_SIGNING_PRIVATE_KEY` | Signs updater artifacts (`.sig`) and the `latest.json` manifest. A tagged release fails loudly without it. Generate with `npm --prefix apps/studio run tauri signer generate`. |
| `TAURI_SIGNING_PRIVATE_KEY_PASSWORD` | Password for the private key (optional when the key has none). |
| `APPLE_CERTIFICATE` / `APPLE_CERTIFICATE_PASSWORD` | macOS Developer ID certificate (base64 `.p12`) and its password. |
| `APPLE_SIGNING_IDENTITY` | macOS signing identity. |
| `APPLE_ID` / `APPLE_PASSWORD` / `APPLE_TEAM_ID` | macOS notarization credentials. |
| `WINDOWS_CERTIFICATE` / `WINDOWS_CERTIFICATE_PASSWORD` | Windows Authenticode PFX (base64) and its password; imported by CI and injected into the bundle config. |

Releases are published by `.github/workflows/tauri-release.yml` when a `v*` tag
is pushed. The desktop app checks for updates on startup and via
**Settings → Check for updates**.

### Managing the updater signing key

The updater key pair authenticates release artifacts so an installed app can
verify that an auto-update genuinely came from you. The **public** key is
embedded in `apps/studio/src-tauri/tauri.conf.json` (`plugins.updater.pubkey`) and is
safe to commit. The **private** key must never be committed, logged, printed in
CI, or attached to a build artifact.

1. **Generate a key pair** (only if you need a new one). Leave `-p ""` for a
   passwordless key, or pass a password and remember it:

   ```bash
   npm --prefix apps/studio run tauri signer generate -- -w ./living-studio.key -p "" -f
   ```

   This writes `living-studio.key` (private, `0600`) and `living-studio.key.pub`
   (public).

2. **Paste the public key** into `apps/studio/src-tauri/tauri.conf.json`:

   ```jsonc
   {
     "plugins": {
       "updater": {
         "endpoints": ["https://github.com/alehar9320/agentic-odi/releases/latest/download/latest.json"],
         "pubkey": "<contents of living-studio.key.pub>"
       }
     }
   }
   ```

3. **Store the private key outside the repository** (the repo root is
   git-tracked; a sibling directory is not), with restricted permissions:

   ```bash
   mkdir -p ~/repos/agentic-odi-keys && chmod 700 ~/repos/agentic-odi-keys
   mv living-studio.key ~/repos/agentic-odi-keys/
   chmod 600 ~/repos/agentic-odi-keys/living-studio.key
   ```

   Move it to a long-term secret store (password manager, 1Password/Bitwarden/
   Vault, or a private encrypted backup) when you decide where that lives.
   Losing it means future releases can no longer be signed for existing
   installs.

4. **Add the private key as a GitHub Actions secret** (Settings → Secrets and
   variables → Actions → New repository secret), or via the CLI:

   ```bash
   gh secret set TAURI_SIGNING_PRIVATE_KEY < ~/repos/agentic-odi-keys/living-studio.key
   gh secret set TAURI_SIGNING_PRIVATE_KEY_PASSWORD --body ""   # only if you set a password
   ```

5. **Verify** the secrets exist (values are never displayed):

   ```bash
   gh secret list
   ```

6. **Rotate** by repeating steps 1–4, then publishing a release signed with the
   new key. Existing installs still verify against the public key compiled into
   their binary, so keep the old private key usable and publish the new public
   key ahead of the cut-over.

> [!CAUTION]
> If the private key leaks, treat auto-updates as compromised: generate a new
> pair, rotate the Actions secret, and publish a freshly signed release.

> [!IMPORTANT]
> **Migration note.** The Streamlit UI has been removed. The Living Studio now
> lives in `apps/studio/` (browser SPA + Tauri desktop app) and is served by the
> `apps/studio-api` sidecar on port **8100** (previously Streamlit's `8501`).
> Start everything with `python scripts/dev.py`. All `AGENTIC_ODI_*` environment
> variable names, the demo dataset, and the ODI formulas are unchanged.

## Connecting an LLM

The Studio needs an OpenAI-compatible LLM backend with tool-calling support to
drive the agent. For a fully local setup, see
[Local LLM Backend](local-llm.md).

## Agent-Driven Testing

Type `/dev` in the AI assistant to trigger the full automated workflow: it starts
both processes, opens the browser, sends a test message, and reports the results.

Type `/test` to have the agent run all tests and report the results
automatically.
