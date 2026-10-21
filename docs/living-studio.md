# Running The Living Studio

**The Living Studio** is the conversational GUI for Outcome-Driven Innovation:
an interactive Opportunity Landscape, Universal Job Map, WYSIWYG Impact
Simulation, and Causal Lineage inspection, paired with an autonomous agent
connected to the MCP server.

The Studio runs three ways locally, plus a hosted deployment. All of them serve
the same SPA, which talks only to the sidecar on `http://127.0.0.1:8100` — the
SPA never contacts MCP or the LLM directly.

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

## Interface

The Studio opens as a conversation, not a dashboard.

| Surface | What it does |
|---|---|
| **First run** | A short conversation in the chat, not a form: what you are building, who feels the problem, the job they are trying to get done, then where it hurts. One question at a time, with a reflection before the next ask, quick replies, and **Explore on my own** always visible. Skipping is allowed; answers and progress are kept as a draft. Re-open it any time with `/start`, the sidebar's **Your context**, or Settings. |
| **Hero** | One rotating headline above the composer: a greeting (time of day, plus your name if you set one in Settings), the product/job you set up, what is already on the canvas, or what the studio can do. It cycles every few seconds and stays still under `prefers-reduced-motion`. |
| **Suggestion pills** | Below the headline. Some open a surface (landscape, simulate, capture), others start a conversation. They change as the canvas fills up. |
| **Composer** | Docked at the bottom of the transcript. `Enter` sends, `Shift`+`Enter` adds a line, `Cmd/Ctrl`+`K` focuses it, and `/` opens the command palette. The send button becomes a stop button while a reply streams. |
| **Drawer** (left) | The wordmark is a home button. Below it: new conversation, your context, the five workspace surfaces with counts, live model/MCP status, and Settings. Collapses to an icon rail with `Cmd/Ctrl`+`B`; becomes an overlay sheet on narrow screens. |
| **Workspace surfaces** | The classic UI — opportunity landscape, job map, impact simulation, evidence, direct capture, settings — takes the whole stage while open. **Back to conversation** or `Esc` returns; the chat is never squeezed into a side column. |

Replies render Markdown (headings, lists, emphasis, inline and fenced code).
Tool calls appear inline as small trace chips while the agent works.

### Slash commands

Type `/` to open the palette. `Up`/`Down` move, `Enter` or `Tab` runs the
selected command, `Esc` closes it. Commands are handled in the SPA and never call
the model, so they work when it is offline.

| Command | Effect |
|---|---|
| `/help` | Every command, as a notice in the transcript |
| `/start` | Resume the context conversation |
| `/new` | New conversation |
| `/home` | Return to the empty stage |
| `/jobs` | Job summary, then the job map |
| `/landscape`, `/jobmap`, `/impact`, `/evidence`, `/capture`, `/settings` | Open that surface full screen |
| `/status` | Model, MCP, context, and canvas status |

Unknown commands produce a transcript notice pointing at `/help`.

### Guidance, not gates

The setup conversation is a nudge, never a prerequisite. If you skip it, the
home stage keeps a dashed **Tell me what you're building** pill and the sidebar
marks **Your context** with a dot; both reopen the conversation exactly where
you left off. `/start` does the same. The conversation also understands a
natural reply: say "skip", "not now", or "show me the landscape" and it reacts
instead of recording it as an answer. When a brief exists, it opens on a review
and asks what changed rather than asking everything again.

### Without a model

When the LLM is unreachable the Studio keeps working:

- A **Working by hand** strip explains the state and offers capture, job map,
  and context.
- Messages still return deterministic ODI guidance from the sidecar, labelled
  **Local guidance**.
- Jobs can be created, renamed, and deleted; steps added, edited, and removed;
  outcomes recorded, re-scored, and removed. All of it goes through the same
  local repository the model uses.
- Settings → Base URL and Model reconnect the assistant whenever you are ready.

The user's context is sent with every chat request, so the assistant starts from
the product, audience, job, and problem rather than asking for them again.

## Rich responses

The copilot does not only talk. When a surface carries the evidence better than a
paragraph, the agent renders one **inline in the conversation**: a scored
outcome, a ranked opportunity board, a before/after simulation of a bet, a
customer quote with its lineage, the eight-stage job map, or a decision record.
Three properties keep this safe and cheap to extend:

- **The catalog is closed and owned by the SPA.**
  `apps/studio/src/ui/catalog.ts` declares nine primitives and six cards, their
  JSON Schema props, and the description the model reads. There is no HTML, no
  eval, and no third-party component in the path. Prose is rendered by the same
  `Markdown` component the transcript already used.
- **The sidecar is catalog-agnostic.** The SPA sends the catalog with each turn;
  the sidecar derives the `render_ui` tool schema from it, validates what comes
  back, and streams a `ui` SSE event. Invalid props return to the model as a tool
  result naming the exact violation, and the loop offers the tool again, so a
  fumbled prop is corrected in the same reply. A client that sends no catalog
  never sees the tool.
- **Cards are views, never actors.** Every button is an `intent` string that the
  agent receives as the user's next message — one authority, one audit trail.

A surface is one node tree, streamed as one event:

```json
{
  "type": "outcome-card",
  "props": {
    "id": "O-1",
    "statement": "Minimize the time it takes to propagate secrets across environments",
    "importance": 9,
    "satisfaction": 3
  }
}
```

The conversation keeps the order the agent produced: a `delta` appends to the
open prose part, a `ui` event opens a card, and the next `delta` opens a new
paragraph after it. The opportunity score is computed from importance and
satisfaction when the agent omits it, so the ODI formula has exactly one home
(`src/lib/odi.ts`). Unknown component types degrade to a quiet fallback; a tree
that fails validation is dropped whole, and the surrounding prose still reads.

### Adding a surface

1. Add an entry to `CATALOG` in `apps/studio/src/ui/catalog.ts` — props as a
   JSON Schema subset, plus the description the model will read.
2. Register the component in `apps/studio/src/ui/registry.ts`.
3. Implement it in `apps/studio/src/ui/cards.tsx` (domain shape) or
   `apps/studio/src/ui/primitives.tsx` (composition).
4. Run `npm --prefix apps/studio test`. The `registry parity` test fails if the
   catalog and the registry drift apart.

No server change is needed, and no new dependency.

## Hosted (experimental)

The built SPA is also served from Cloudflare Workers at
**[https://agentic-odi.alehar.workers.dev/](https://agentic-odi.alehar.workers.dev/)**.
The UI loads without a backend; canvas data, chat, and mutations need the local
sidecar and MCP server. Pull requests get preview URLs from Cloudflare Workers
Builds. See [Deployment](deployment.md) for the Worker setup.

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
