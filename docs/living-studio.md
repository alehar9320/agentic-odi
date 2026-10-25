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
                                             │  - conversations + PM memory  │
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
| **First-run tour** | A four-step, skippable welcome on the very first visit: what the studio is, which ambition brought you here, the live state of your sidecar/MCP/model (with inline repair when the model is down), and the first move. The four doors are **I have one in mind**, **My boss handed me a priority**, **Help me find the next one**, and **Pressure-test a bet**; each starts the matching conversation. Replay it from **Settings → Replay the welcome tour**. |
| **First run** | A short conversation in the chat, not a form: what you are building, who feels the problem, the job they are trying to get done, then where it hurts. One question at a time, with a reflection before the next ask, quick replies, and **Explore on my own** always visible. Skipping is allowed; answers and progress are kept as a draft. Re-open it any time with `/start`, the home stage's context pill, or Settings. |
| **Hero** | One rotating headline above the composer: a greeting (time of day, plus your name if you set one in Settings), the product/job you set up, what is already on the canvas, or an intent-first prompt such as *What are you trying to win this quarter?* It cycles every few seconds and stays still under `prefers-reduced-motion`. |
| **Suggestion pills** | Below the headline. **Sharpen an opportunity** always starts a conversation; the next pill becomes **Pressure-test a bet** once outcomes exist, or **Find the next opportunity** before that. **Capture what you heard** replaces the landscape pill once a job exists. They change as the canvas fills up. |
| **Composer** | Docked at the bottom of the transcript. `Enter` sends, `Shift`+`Enter` adds a line, `Cmd/Ctrl`+`K` focuses it, `/` opens the command palette, and `Esc` stops a reply that is still streaming. The send button becomes a stop button while a reply streams. On touch screens the field stays at 16px so mobile browsers do not zoom into it. |
| **Model picker** | The model name under the composer is a selector when the endpoint publishes a catalog (`POST /api/models`, asked at boot and again whenever the base URL or key changes); the configured name is always an option, and picking one changes the model used by the next message. A provider that will not list its models leaves the name as plain text, with the reason in its tooltip, and Settings keeps the free-text field plus the known models as suggestions. |
| **Transcript** | A focusable, labelled log: the arrow keys, `Page Up`/`Page Down`, and `Home`/`End` scroll history without a mouse. If you scroll back while the studio replies, **Jump to latest** returns you to the newest turn and puts focus in the transcript. |
| **Bar** | The only persistent chrome: home, new conversation, catch-up, live model status, and settings. There is no navigation drawer to compete with the thread. |
| **Rail** | Above the conversation, and only once the thread has produced something: `Landscape · N`, `Job map · N`, `Evidence · N`, `What I know · N`. Every item is derived from the canvas and the memory, so the strip is a record of the work rather than a fixed menu. |
| **Lens** | A view docks to the right of the thread on wide screens and becomes a full-height sheet on narrow ones. The transcript and the composer stay on screen and stay usable; `Esc`, **Close**, or the rail chip closes it. Every lens ends in one sentence that re-enters the conversation — *Ask which to chase*, *Walk me through the job*, *Weigh the evidence* — so leaving a view is never a return to a menu. Settings and catch-up use the same lens. |

Replies render Markdown (headings, lists, emphasis, inline and fenced code).

### Run activity

Every tool call is one row in the turn's timeline, not one row per event. While
a turn streams, the studio names the work in flight — *Reading your jobs*,
*Adding an outcome*, or the sidecar's own stage (*Waking the model*, *Opening
your studio tools*, *Thinking*) — so a slow turn never looks like a stalled one.
Each row carries its own outcome and duration, and a failed call keeps the
tool's own words, so the transcript says which call broke instead of only that
something did.

When the turn settles the timeline collapses to a single line — `2 tools ·
1.9s`, plus `1 failed` when it applies — which opens to the full list. The
steps live on the turn itself (`ChatMessage.tools`), so the record survives the
next question instead of being reset per run. The reducer that folds `tool`
SSE events into steps is `apps/studio/src/lib/run.ts`, kept pure and testable.

Stopping a run is a fact the transcript keeps. `Esc` (or the stop button) halts
the stream, any tool still in flight is marked stopped, whatever prose arrived
stays in place, and the turn says *Stopped by you* with **Ask again** — not a
failure, because nothing broke, and not a silent disappearance, because the
question is still on screen.

Screen readers are not handed a streaming firehose. The transcript is not a
live region; each settled reply is announced once, as prose with the Markdown
markers removed, through a polite status region. The run's current step
announces as it changes, each step's outcome is read as part of its row, a
stopped turn is spoken as stopped rather than as a reply, failures arrive as an
alert with their retry, and every turn is
labelled with who said it — "You said", "Studio said", "Studio notice" — so
navigating turn by turn keeps its author.

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
| `/landscape`, `/jobmap`, `/evidence`, `/settings` | Open that lens beside the conversation |
| `/impact`, `/capture` | Start the conversation that produces the card. `/capture` falls back to the offline form when no model answers. |
| `/status` | Model, MCP, context, and canvas status |

Unknown commands produce a transcript notice pointing at `/help`.

### The welcome tour

The tour is the front door, the context conversation is the first room. It is
skippable at every step (`Skip the tour` or `Escape`), resumable (progress is
stored after every transition in `localStorage["studio.onboarding"]`), and
replayable from Settings.

Everything lives in `apps/studio/src/onboarding/`:

| File | Role |
|---|---|
| `content.ts` | Steps and goal copy as typed data — the only place the words live |
| `machine.ts` | Pure state transitions, no React or storage |
| `storage.ts` | Versioned, defensive `localStorage` persistence |
| `OnboardingProvider.tsx` | Auto-open, persistence, replay |
| `FirstRunWizard.tsx`, `steps.tsx`, `onboarding.css` | The dialog |
| `../features/flags.ts` | The `firstRunWizard` toggle |

`App.tsx` only wires the provider and the wizard around the existing shell;
the chat, canvas, and sidecar code are untouched.

#### Toggling the tour

`firstRunWizard` defaults to on. Resolution order, highest first:

| Source | Example | Use |
|---|---|---|
| Query parameter | `?flags=firstRunWizard:off` | QA a build without rebuilding |
| Local override | `localStorage["studio.flags.firstRunWizard"] = "off"` | Per-browser opt-out |
| Build environment | `VITE_STUDIO_FIRST_RUN_WIZARD=off npm --prefix apps/studio run build` | Ship it dark |
| Default | on | |

Accepted values are `1`/`0`, `true`/`false`, `on`/`off`, `yes`/`no`, and
`enabled`/`disabled`. With the flag off, no dialog renders, no onboarding state
is written, and Settings hides the replay action.

### Guidance, not gates

The setup conversation is a nudge, never a prerequisite. If you skip it, the
home stage keeps a dashed **Tell me what you're building** pill; it reopens the
conversation exactly where you left off. `/start` and Settings do the same. The conversation also understands a
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

### The thread is the room

Capture, scoring, simulation, and decisions are conversations. The storefront
never asks the PM to leave the thread to do work: the agent asks for the
customer's words or the bet in plain language, then renders the surface that
carries it. A lens exists for reading and for people who prefer a click, not for
doing the work.

That is also enforced in the agent's system prompt: it is told to keep every
artifact in the conversation, never to send the PM to a panel, and to end each
reply with the next move as an action on the surface.

### What it remembers

The studio keeps a small, local, editable model of the person it is helping. It
is not a profile and not a transcript index; it is the handful of things that
change the next answer.

| Kind | What it captures |
|---|---|
| `career` | The PM's role, remit, and what success looks like for them |
| `opportunity` | The opportunity or bet currently in play |
| `business` | Goals, metrics, and commercial constraints |
| `stakeholder` | Who else matters and what they care about |
| `constraint` | Time, budget, policy, or technical limits |
| `evidence` | What has actually been heard or measured |
| `preference` | How the PM likes to work and be spoken to |

Each note is `suggested` or `confirmed`. Suggested notes appear first under
**What I know** with **Yes, that's right**, **That's not it**, and **Edit**;
confirmed notes can be edited or forgotten. The PM can also add a note by hand.
Nothing is silently promoted: the agent may propose, but the person decides.

The agent writes notes through a `remember` tool during a normal reply. The
sidecar applies it, emits a `memory` SSE event, and the panel updates without a
refresh. Memory writes are best-effort — a database failure never turns a good
answer into an error.

Storage is a separate SQLite file from the ODI repository:
`~/.agentic-odi/studio.db`, overridable with `AGENTIC_ODI_STUDIO_DB`
(`:memory:` is supported and is what the tests use). The API is small:

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/memory/observations` | Everything the agent believes |
| `POST` | `/api/memory/observations` | Add a note by hand |
| `PATCH` | `/api/memory/observations/{id}` | Edit text, confidence, or status |
| `DELETE` | `/api/memory/observations/{id}` | Forget one note |
| `DELETE` | `/api/memory` | Forget all notes and conversations |

**Forget everything** is a two-step confirmation and also clears the visible
thread, because the server deletes the conversations behind it.

### The thread comes back

Conversations are stored beside the memory. On launch the SPA asks
`GET /api/conversations/latest`, restores that thread's user and assistant
turns, and continues with the same `conversation_id` on the next message. **New
conversation** starts a fresh one without touching the memory; **Forget
everything** removes both. The composer stays usable while the restore is in
flight, and a restore failure simply leaves the room empty.

## Rich responses

The copilot does not only talk. When a surface carries the evidence better than a
paragraph, the agent renders one **inline in the conversation**: a scored
outcome, a ranked opportunity board, a before/after simulation of a bet, a
customer quote with its lineage, the eight-stage job map, an opportunity thesis, or a decision record.
Three properties keep this safe and cheap to extend:

- **The catalog is closed and owned by the SPA.**
  `apps/studio/src/ui/catalog.ts` declares nine primitives and seven cards, their
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

The opportunity thesis is the intent-first card: one opportunity with its
importance, satisfaction, the gap in plain words, the thesis itself, and the
smallest next move. It is the shape the agent reaches for when the PM is deciding
what to chase, rather than when they are inspecting a single score.

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

## Connecting an LLM

The Studio needs an OpenAI-compatible LLM backend with tool-calling support to
drive the agent. For a fully local setup, see
[Local LLM Backend](local-llm.md).

## Agent-Driven Testing

Type `/dev` in the AI assistant to trigger the full automated workflow: it starts
both processes, opens the browser, sends a test message, and reports the results.

Type `/test` to have the agent run all tests and report the results
automatically.
