<div align="center">

# Agentic ODI

[![CI](https://github.com/alehar9320/agentic-odi/actions/workflows/ci.yml/badge.svg)](https://github.com/alehar9320/agentic-odi/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![uv](https://img.shields.io/badge/uv-managed-green)](https://docs.astral.sh/uv/)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![FastMCP](https://img.shields.io/badge/FastMCP-powered-orange)](https://github.com/jlowin/fastmcp)
[![pytest](https://img.shields.io/badge/tests-pytest-blue)](https://pytest.org)
[![MCP](https://img.shields.io/badge/Model%20Context%20Protocol-enabled-8A2BE2)](https://modelcontextprotocol.io)

> **Experimental test to learn and evaluate the feasibility of utilizing Model Context Protocol (MCP) for Outcome-Driven Innovation (ODI) specifications.**

</div>

---

## 📋 Table of Contents

- [The Vision: Context-Aware Innovation](#-the-vision-context-aware-innovation)
- [Current State (Experimental Testbed)](#-current-state-experimental-testbed)
- [Code Overview](#-code-overview)
- [Getting Started](#-getting-started)
  - [Command-Line Interface (CLI)](#-command-line-interface-cli)
  - [Interactive Chat](#-interactive-chat)
  - [Manage Customer Outcomes](#-manage-customer-outcomes)
  - [External Connectors (MCP Ingest)](#-external-connectors-mcp-ingest)
  - [Living Studio Run Modes](#-living-studio-run-modes)
  - [Local Tools-Capable LLM Backend](#-local-tools-capable-llm-backend-for-mcp-testing)
  - [Agent-Driven Testing](#-agent-driven-testing)
- [Linting, Formatting & Type Checks](#-linting-formatting--type-checks-ci-parity)
- [Testing](#-testing)
  - [Test Coverage Map](#-test-coverage-map)
  - [Agent Session Tracking](#-agent-session-tracking)
- [Superpowers with Pi](#-superpowers-with-pi)
  - [Developer Workflow for Formatting](#-developer-workflow-for-formatting)
- [Deployment](#-deployment)
- [Roadmap & Next Steps](#-roadmap--next-steps)
- [Contributing](#-contributing)
- [License](#-license)

---

## 🌟 The Vision: Context-Aware Innovation

**Outcome-Driven Innovation (ODI)**, built on the "Jobs-to-be-Done" theory, relies on deeply understanding customer needs, desired outcomes, and execution contexts. Historically, applying ODI requires meticulous research, structured data modeling, and rigorous analysis.

**Model Context Protocol (MCP)** represents a paradigm shift in how AI systems consume and reason over external context. By adopting MCP, we can bridge the gap between static user research and dynamic, agentic AI.

The vision for **Agentic ODI** is to build a unified, open protocol where LLMs and autonomous agents can natively query, understand, and reason over ODI data (Job Maps, Desired Outcomes, and Opportunity Scores) dynamically in real-time. Instead of feeding LLMs disconnected prompts, an MCP-powered ODI server will act as the "brain" of customer needs, allowing agents to invent, evaluate, and ideate solutions strictly anchored in verified user outcomes.

---

## 🏗️ Current State (Experimental Testbed)

This repository serves as an initial sandbox for understanding server-client MCP communication streams. We are utilizing [`FastMCP`](https://github.com/jlowin/fastmcp) to prototype HTTP-based context delivery.

---

## 🧩 Code Overview

This repository is a [uv workspace](https://docs.astral.sh/uv/concepts/projects/workspaces/) made up of **six** installable Python projects plus the React `studio/` front end, each with its own build, tests, and layout:

| Package | Description |
|---|---|
| **`core/`** (`agentic-odi-core`) | Domain models, the `ODIService` business-logic layer, and repository implementations (in-memory and SQLite), including ODI opportunity-score computation. |
| **`mcp_server/`** (`agentic-odi-mcp-server`) | A foundational MCP Server exposing an HTTP transport layer. It hosts tools for Jobs, Steps, Desired Outcomes, and Customer Outcomes (linking customer value to business value). |
| **`local_server/`** (`agentic-odi-local-server`) | The FastAPI **Living Studio sidecar**. It talks to the MCP server on the client's behalf and serves the Studio API — configuration, health probes, canvas data, MCP mutations, and streaming (SSE) chat with the LLM tool-loop — plus the built SPA when `studio/dist` exists. |
| **`client/`** (`agentic-odi-client`) | The local dev **launcher** (`run.py` / `python -m client.run`) that starts the MCP server and the Studio sidecar together. (Its former Streamlit UI has been replaced by the `studio/` SPA.) |
| **`studio/`** (React + TypeScript + Vite) | **The Living Studio** front end — a spatial, conversational GUI for Outcome-Driven Innovation with an interactive Opportunity Landscape, Universal Job Map, WYSIWYG Impact Simulation, and Causal Lineage inspection, paired with an autonomous copilot. Ships as a browser SPA and as a **Tauri 2 desktop app** (`studio/src-tauri/`). |
| **`cli/`** (`agentic-odi-cli`) | A [`Typer`](https://github.com/fastapi/typer)-based command-line interface with an interactive chat mode plus `version`, `update`, `outcomes`, and `connectors` commands. |
| **`connectors/`** (`agentic-odi-connectors`) | Pluggable external integrations. The first kind is an **MCP client connector** that connects to a remote MCP server over HTTP, checks health, and ingests tools/resources into a local ingest sink. Additional kinds (REST, webhooks, and so on) can register against the same protocol later. |

---

## 🚀 Getting Started

### Prerequisites

- **Python** 3.10+
- [**uv**](https://docs.astral.sh/uv/) package manager

Install the entire workspace (all six projects plus dev tooling):

```bash
uv sync --all-packages
```

This creates a `.venv` and installs `agentic-odi-core`, `agentic-odi-mcp-server`, `agentic-odi-local-server`, `agentic-odi-client`, `agentic-odi-cli`, and `agentic-odi-connectors` in editable mode.

### 💻 Command-Line Interface (CLI)

The [`Typer`](https://github.com/fastapi/typer)-based CLI lets you interact with Agentic ODI directly from your terminal. It provides an interactive chat mode plus version, update, and data commands.

Launch it with:

```bash
python -m cli --version   # print the Agentic ODI version
python -m cli --help      # show available options and commands
python -m cli             # start interactive chat in a terminal (help when piped)
```

A console script is also installed, so `agentic-odi --version` works the same way.

### 💬 Interactive Chat

`agentic-odi chat` (or simply `agentic-odi` in a terminal) starts a conversational session against the MCP server and an OpenAI-compatible LLM. Responses stream to the terminal, and the assistant can call the ODI MCP tools as it talks.

```bash
agentic-odi chat
agentic-odi chat --model local-tools-model --mcp-url http://localhost:8000/mcp
```

Before starting, run the MCP server (`python -m mcp_server`) and point the chat at an OpenAI-compatible model endpoint. The chat reads the same environment variables as the Living Studio:

| Variable | Default | CLI flag |
|---|---|---|
| `AGENTIC_ODI_BASE_URL` | `http://localhost:8001/v1` | `--base-url` |
| `AGENTIC_ODI_MODEL` | `local-tools-model` | `--model` |
| `AGENTIC_ODI_API_KEY` | `local` | `--api-key` |
| `AGENTIC_ODI_MCP_URL` | `http://localhost:8000/mcp` | `--mcp-url` |

Inside the session, `/help` lists the commands, `/tools` lists the MCP tools the assistant can call, `/clear` resets the conversation, and `/exit` (or `/quit`) ends the session.

> [!NOTE]
> Chat is the only CLI mode that needs an LLM endpoint. The `outcomes` and `connectors` commands keep working without one.

### 🎯 Manage Customer Outcomes

Manage Customer Outcomes (linking customer value to business value) via the CLI. The CLI acts as an MCP client, so the server must be running (`python -m mcp_server`):

```bash
# Add a Customer Outcome
agentic-odi outcomes add --job-id <job-id>   --direction minimize --unit "time" --object "to resolve setup errors"   --statement "Minimize the time to resolve environment setup errors when onboarding"   --importance 8.8 --satisfaction 3.2   --category cost_reduction   --business-statement "Saves engineering hours and reduces early churn"

# List outcomes (optionally filtered)
agentic-odi outcomes list
agentic-odi outcomes list --job-id <job-id>

# Get, update, delete
agentic-odi outcomes get <outcome-id>
agentic-odi outcomes update <outcome-id> --importance 9.0
agentic-odi outcomes delete <outcome-id> --yes

# Compute ODI Opportunity Score
agentic-odi outcomes score 8 2
```

Set `AGENTIC_ODI_MCP_URL` to point to a non-default server if needed.

### 🔌 External Connectors (MCP Ingest)

Connectors are named integrations stored in `.agentic-odi/connectors.json` (or a path you pass with `--config` / `AGENTIC_ODI_CONNECTORS_FILE`). The first kind is `mcp`: Agentic ODI acts as an MCP **client** and pulls catalog, resources, and optional tool results from an external MCP **server**.

```bash
python -m cli connectors add mcp --name gong --url http://localhost:9000/mcp --tool latest_quote
python -m cli connectors list
python -m cli connectors health --name gong
python -m cli connectors ingest --name gong
```

Ingested records are normalized (`catalog`, `resource`, `tool_result`) and appended to the in-process ingest sink. They are not written into the ODI jobs/outcomes store.

### ⚡ Living Studio Run Modes

The Living Studio runs three ways. All of them serve the same SPA, which talks only to the sidecar on `http://127.0.0.1:8100` — the SPA never contacts MCP or the LLM directly.

**Architecture**

```text
┌────────────────────────────┐  /api (JSON)  ┌───────────────────────────────┐
│  Living Studio SPA         │ ────────────▶ │  local_server (sidecar)       │
│  React + TS + Vite         │  /api/chat    │  FastAPI on 127.0.0.1:8100    │
│  (browser or Tauri webview)│ ◀──────────── │  - config / health / canvas   │
└────────────────────────────┘  SSE stream   │  - steps / outcomes (via MCP) │
                                             │  - /api/chat (LLM tool-loop)  │
                                             └───────────────┬───────────────┘
                                                             │ MCP (HTTP)
                                                             ▼
                                             ┌───────────────────────────────┐
                                             │  mcp_server  :8000/mcp        │
                                             └───────────────────────────────┘
                                                             ▲
                                                             │ OpenAI-compatible
                                             ┌───────────────┴───────────────┐
                                             │  Your local LLM backend       │
                                             └───────────────────────────────┘
```

**1. Web — production build (recommended for a quick look)**

```bash
npm --prefix studio run build   # build the SPA into studio/dist
python -m client.run            # starts MCP :8000 + sidecar :8100
```

| Service | URL |
|---|---|
| MCP Server | http://localhost:8000/mcp |
| Living Studio | http://127.0.0.1:8100 |

**2. Web — dev with hot reload** (Vite proxies `/api` to the sidecar):

```bash
npm --prefix studio run dev:full   # MCP + sidecar + Vite together
# open http://localhost:5173
```

**3. Desktop — Tauri 2** (the app spawns the MCP server and sidecar itself):

```bash
npm --prefix studio run tauri dev     # dev window
npm --prefix studio run tauri build   # bundles: .deb / .AppImage (Linux), .app / .dmg (macOS), .msi / .exe (Windows)
```

> [!NOTE]
> **Tauri prerequisites.** The desktop build needs the WebKitGTK toolchain and Rust 1.90+. On Debian/Ubuntu:
>
> ```bash
> sudo apt-get install -y libwebkit2gtk-4.1-dev build-essential pkg-config curl wget file \
>   libxdo-dev libssl-dev libayatana-appindicator3-dev librsvg2-dev patchelf xdg-utils libfuse2t64
> ```
>
> The Tauri CLI ships as the `@tauri-apps/cli` npm dev dependency (`npm --prefix studio run tauri`). The sidecar is launched with `uv run python -m …` from the repository root; if the app cannot locate the repo root, set `AGENTIC_ODI_REPO_ROOT`.

#### 🔐 Desktop signing & updater secrets

Self-updating and code signing are **env-driven**: if a secret is absent, an unsigned artifact is produced instead of failing. CI reads these from GitHub Actions secrets.

| Secret | Purpose |
|---|---|
| `TAURI_SIGNING_PRIVATE_KEY` | Signs updater artifacts (`.sig`) and the `latest.json` manifest. A tagged release fails loudly without it. Generate with `npm --prefix studio run tauri signer generate`. |
| `TAURI_SIGNING_PRIVATE_KEY_PASSWORD` | Password for the private key (optional when the key has none). |
| `APPLE_CERTIFICATE` / `APPLE_CERTIFICATE_PASSWORD` | macOS Developer ID certificate (base64 `.p12`) and its password. |
| `APPLE_SIGNING_IDENTITY` | macOS signing identity. |
| `APPLE_ID` / `APPLE_PASSWORD` / `APPLE_TEAM_ID` | macOS notarization credentials. |
| `WINDOWS_CERTIFICATE` / `WINDOWS_CERTIFICATE_PASSWORD` | Windows Authenticode PFX (base64) and its password; imported by CI and injected into the bundle config. |

Releases are published by `.github/workflows/tauri-release.yml` when a `v*` tag is pushed. The desktop app checks for updates on startup and via **Settings → Check for updates**.

#### 🔑 Managing the updater signing key

The updater key pair authenticates release artifacts so an installed app can verify that an auto-update genuinely came from you. The **public** key is embedded in `studio/src-tauri/tauri.conf.json` (`plugins.updater.pubkey`) and is safe to commit. The **private** key must never be committed, logged, printed in CI, or attached to a build artifact.

1. **Generate a key pair** (only if you need a new one). Leave `-p ""` for a passwordless key, or pass a password and remember it:

   ```bash
   npm --prefix studio run tauri signer generate -- -w ./living-studio.key -p "" -f
   ```

   This writes `living-studio.key` (private, `0600`) and `living-studio.key.pub` (public).

2. **Paste the public key** into `studio/src-tauri/tauri.conf.json`:

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

3. **Store the private key outside the repository** (the repo root is git-tracked; a sibling directory is not), with restricted permissions:

   ```bash
   mkdir -p ~/repos/agentic-odi-keys && chmod 700 ~/repos/agentic-odi-keys
   mv living-studio.key ~/repos/agentic-odi-keys/
   chmod 600 ~/repos/agentic-odi-keys/living-studio.key
   ```

   Move it to a long-term secret store (password manager, 1Password/Bitwarden/Vault, or a private encrypted backup) when you decide where that lives. Losing it means future releases can no longer be signed for existing installs.

4. **Add the private key as a GitHub Actions secret** (Settings → Secrets and variables → Actions → New repository secret), or via the CLI:

   ```bash
   gh secret set TAURI_SIGNING_PRIVATE_KEY < ~/repos/agentic-odi-keys/living-studio.key
   gh secret set TAURI_SIGNING_PRIVATE_KEY_PASSWORD --body ""   # only if you set a password
   ```

5. **Verify** the secrets exist (values are never displayed):

   ```bash
   gh secret list
   ```

6. **Rotate** by repeating steps 1–4, then publishing a release signed with the new key. Existing installs still verify against the public key compiled into their binary, so keep the old private key usable and publish the new public key ahead of the cut-over.

> [!CAUTION]
> If the private key leaks, treat auto-updates as compromised: generate a new pair, rotate the Actions secret, and publish a freshly signed release.

> [!IMPORTANT]
> **Migration note.** The Streamlit UI (`client/src/client/app.py`) has been removed. The Living Studio now lives in `studio/` (browser SPA + Tauri desktop app) and is served by the `local_server` sidecar on port **8100** (previously Streamlit's `8501`). Start everything with `python -m client.run`. All `AGENTIC_ODI_*` environment variable names, the demo dataset, and the ODI formulas are unchanged.

### 🧠 Local Tools-Capable LLM Backend (for MCP testing)

To exercise real tool-calling end-to-end against the MCP server, you need a local LLM backend that:

- Exposes an **OpenAI-compatible Chat Completions API** (for example, `/v1/chat/completions`), and
- Supports OpenAI-style **`tools` / `tool_calls`**.

A simple fully local option is [`llama-cpp-python`](https://github.com/abetlen/llama-cpp-python), which can run a quantized model on your machine and expose an OpenAI-compatible server.

1. **Install a local LLM server**

   Install `llama-cpp-python` in your environment (see its README for platform-specific build notes):

   ```bash
   pip install llama-cpp-python
   ```

2. **Download a small tools-capable model**

   Download a small GGUF model that supports function/tool calling (for example, a 7B function-calling variant from Hugging Face) and note its path, e.g. `C:\models\local-tools-model.gguf`.

3. **Start the OpenAI-compatible server**

   Start the server and give the model a friendly alias that matches the default used by the Living Studio sidecar:

   ```bash
   python -m llama_cpp.server \
     --model "C:\models\local-tools-model.gguf" \
     --model_alias local-tools-model \
     --host 127.0.0.1 --port 8001 \
     --chat_format openai
   ```

   This exposes an OpenAI-style API at `http://127.0.0.1:8001/v1`.

4. **Point the Living Studio at the local server**

   The sidecar reads defaults from environment variables (with sensible fallbacks):

   | Variable | Default |
   |---|---|
   | `AGENTIC_ODI_BASE_URL` | `http://localhost:8001/v1` |
   | `AGENTIC_ODI_MODEL` | `local-tools-model` |
   | `AGENTIC_ODI_MCP_URL` | `http://localhost:8000/mcp` |
   | `AGENTIC_ODI_API_KEY` | `local` |

   You can either set these in your shell or adjust them in the Living Studio's **Settings** panel.

5. **Verify tool-calling against the MCP server**

   - (Optional) Before starting the UI, confirm the LLM backend is reachable:

     ```bash
     curl http://127.0.0.1:8001/v1/models
     ```

     If this request fails, fix your local LLM server configuration before debugging the MCP client/server.

   - Start the MCP server and the Living Studio (via `python -m client.run` or `npm --prefix studio run dev:full`).
   - In the browser UI, ask the assistant something that should use ODI tools, for example: “Help me define a new Job-to-be-Done and add it to your ODI repository.”
   - You should see the assistant briefly display that it is calling tools (for example, `add_job`, `get_jobs`, etc.) and then respond with grounded ODI guidance, confirming that the local LLM, MCP server, and client wiring all work together.
   - If the LLM backend is unreachable or misconfigured, the UI will show a clear error banner indicating that the backend at your configured **Base URL** could not be reached, along with details from the underlying error. Use that message together with the steps above to fix your local LLM setup.

### 🤖 Agent-Driven Testing

Type `/dev` in the AI assistant to trigger the full automated workflow: it will start both processes, open the browser, send a test message, and report the results.

---

## 🧹 Linting, Formatting & Type Checks (CI parity)

The CI pipeline runs several quality checks. You can mirror them locally with:

```bash
# Ruff lint and formatting checks (per-file config comes from each project's pyproject.toml)
uv run ruff check .
uv run ruff format --check .

# Type checking (run per project so each project's config applies)
uv run --directory core mypy .
uv run --directory mcp_server mypy .
uv run --directory local_server mypy .
uv run --directory client mypy .
uv run --directory cli mypy .
uv run --directory connectors mypy .

# Security scanning
uv run bandit -c pyproject.toml -r core/src mcp_server/src local_server/src cli/src client/src connectors/src

# Tests (same as CI)
uv run --directory core pytest
uv run --directory mcp_server pytest
uv run --directory local_server pytest
uv run --directory client pytest
uv run --directory cli pytest
uv run --directory connectors pytest
```

### 🖥️ Frontend & Desktop Checks (studio)

The SPA and Tauri shell mirror their CI jobs locally:

```bash
npm --prefix studio run lint       # ESLint
npm --prefix studio run typecheck  # tsc --noEmit
npm --prefix studio test -- --run  # Vitest (run once)
npm --prefix studio run build      # production build → studio/dist
cd studio/src-tauri && cargo fmt --check && cargo clippy -- -D warnings && cargo check
```

To run these automatically before each commit, enable the bundled pre-commit hooks:

```bash
uv tool install pre-commit
pre-commit install
```

After this, `ruff` and `ruff-format` will run on staged files whenever you commit. You can also trigger them manually with:

```bash
pre-commit run --all-files
```

---

## ✅ Testing

Tests use **pytest** with **pytest-asyncio** (strict mode) and run entirely in-memory — no running server required. Each project owns its tests. CI runs the suite on Python **3.10, 3.11, and 3.12** and stores a coverage report as a build artifact:

```bash
uv run --directory core pytest
uv run --directory mcp_server pytest
uv run --directory local_server pytest
uv run --directory client pytest
uv run --directory cli pytest
uv run --directory connectors pytest
```

### 📊 Test Coverage Map

| File | What it covers |
|---|---|
| `core/tests/test_models.py` | Domain models and ODI opportunity-score computation |
| `core/tests/test_service.py` | `ODIService` jobs/steps/outcomes and Customer Outcome CRUD |
| `mcp_server/tests/test_odi.py` | Full ODI workflow (add job → steps → outcomes → retrieval) + capabilities tool |
| `mcp_server/tests/test_customer_outcomes.py` | Customer Outcomes CRUD, filtering, computed opportunity scores, and tool validation |
| `mcp_server/tests/test_server_tools.py` | Error handling and retrieval for the MCP tools |
| `mcp_server/tests/test_tools.py` | Tool response-shape contract for `add_job` |
| `local_server/tests/test_api.py` | Local FastAPI health endpoint |
| `local_server/tests/test_studio_api.py` | Living Studio sidecar API (config, health, canvas, SSE chat, steps/outcomes) |
| `client/tests/test_run.py` | Dev launcher helpers (port checks, mcp + sidecar commands) |
| `studio/src/**/*.test.ts` | SPA units: ODI math, transport bridge, SSE parser, sidecar client |
| `cli/tests/test_cli.py` | CLI `--version` and `--help` behavior |
| `cli/tests/test_outcomes_cli.py` | Customer Outcomes CLI subcommands with MCP stub |
| `cli/tests/test_connectors_cli.py` | CLI `connectors` add/list/health/ingest adapter |
| `connectors/tests/test_registry.py` | JSON connector registry persist/load and kind checks |
| `connectors/tests/test_mcp_connector.py` | In-memory FastMCP health and ingest records |

**Conventions:**

- Test files live under each project's `tests/` directory and are named `test_*.py`.
- Every async test is decorated with `@pytest.mark.asyncio`.
- Use `Client(mcp)` directly (no HTTP server needed) for fast, isolated tests.
- The server's `reset_db` autouse fixture clears in-memory state before each test.

> [!TIP]
> Type `/test` in the AI assistant to have the agent run all tests and report the results automatically.

### 🧪 Agent Session Tracking

Agent sessions are captured with the [Entire](https://docs.entire.io/overview) CLI. The repository integration lives in `.entire/settings.json`, `.cursor/hooks.json`, and `.opencode/plugins/entire.ts`. Run `entire status` to confirm it is enabled and `entire checkpoint list` to inspect captured checkpoints.

---

## 🤝 Superpowers with Pi

This project includes [Superpowers](https://github.com/obra/superpowers) as a [Pi package](https://pi.dev/docs/packages). When using [Pi](https://pi.dev) with this project, Superpowers skills and extensions are automatically loaded.

To enable:

1. Install Pi: `curl -fsSL https://pi.dev/install.sh | sh`
2. Trust the project (first time only): `pi config --local --approve`
3. Start Pi: `pi`

The `.pi/settings.json` declares the Superpowers package. Pi will clone it and load:

- **Extension**: `superpowers.ts` — injects the `using-superpowers` bootstrap at session startup and after compaction
- **Skills**: 12 Superpowers skills (TDD, subagent-driven-development, systematic-debugging, etc.)

> [!NOTE]
> Superpowers is also available for OpenCode via the plugin in `opencode.json`. The Pi package provides native Pi integration without needing the OpenCode compatibility layer.

### 🧼 Developer Workflow for Formatting

- **When editing Python files**, either:
  - Rely on the **pre-commit hooks** above (recommended), or
  - Run Ruff formatting directly before pushing:

    ```bash
    uv run ruff format .
    ```

- **CI behavior**:
  - CI runs `uv run ruff check .` to lint without modifying files.
  - CI runs `uv run ruff format --check .` to *verify* formatting only.
  - If CI fails on formatting, run `uv run ruff format .` locally, commit the changes, and push again.

---

## Quick Install (Binary)

Prebuilt binaries are available for Linux, macOS, and Windows. Install the latest release with one command:

```bash
curl -fsSL https://github.com/alehar9320/agentic-odi/releases/latest/download/install.sh | sh
```

The installer places the binary under `~/.local/share/agentic-odi/versions/<version>/`, creates a `current` symlink, and symlinks `odi`, `odipm`, `odi-cli`, and `agentic-odi` into `~/.local/bin/`.

If `~/.local/bin` is not on your PATH, add it (e.g., `export PATH="$HOME/.local/bin:$PATH"`). On Windows, the PowerShell installer uses `~\AppData\Local\agentic-odi\` and copies `.exe` files to `~\AppData\Local\agentic-odi\bin\`.

### Update

By default, `odi` auto-checks for updates once every 24 hours and applies the update on the next run (auto-update is enabled by default). Control behavior with:

- `odi update` — explicit check and update
- `--no-update` flag — skip auto-update for this run
- `AGENTIC_ODI_NO_UPDATE=1` — disable auto-update globally

When running from a non-frozen source install, auto-update is suppressed automatically.

### Install layout

```
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

Environment variables: `AGENTIC_ODI_INSTALL_DIR` (override install root), `XDG_DATA_HOME`, `XDG_BIN_HOME`. The default backend is `local` (`--backend local`); no MCP server is required.

### Unsigned binaries

macOS may quarantine downloaded binaries: `xattr -d com.apple.quarantine ~/.local/bin/odi` (if needed). Windows SmartScreen may show a warning for unsigned binaries; choose "More info → Run anyway" if you trust the release.

## ☁️ Deployment

The server is deployed via **[Horizon Prefect](https://www.prefect.io/horizon)**, Prefect's managed infrastructure for hosting MCP-compatible agents.

### 🧪 Test Chat (UI)

Interact with the deployed agent directly in your browser:

> **[https://horizon.prefect.io/alhase/servers/agentic-odi/chat](https://horizon.prefect.io/alhase/servers/agentic-odi/chat)**

### 🔌 MCP Server Endpoint

Integrate via the MCP protocol at:

> **[https://agentic-odi.fastmcp.app/mcp](https://agentic-odi.fastmcp.app/mcp)**

> [!IMPORTANT]
> **Authentication is required** to access the MCP server endpoint. Please reach out to the maintainers to obtain the necessary credentials before connecting a client.

---

## 🗺️ Roadmap & Next Steps

As we validate the feasibility of this architecture, our next milestones include:

- [x] **External MCP client connector**: Pluggable connectors package with an HTTP MCP ingest client, CLI adapter, and in-memory tests.
- [ ] **Map ingested evidence onto ODI artifacts**: Turn connector records into jobs, outcomes, or evidence without mixing connector plumbing into the ODI store.
- [ ] **Additional connector kinds**: REST/webhooks and similar integrations implementing the same `Connector` protocol.
- [ ] **ODI Schema Definition**: Define standardized Pydantic models for *Jobs*, *Steps*, and *Outcomes*.
- [x] **CLI Dataset Commands**: Extend `cli/` so the ODI dataset can be created, queried, and scored from the terminal, in addition to the current MCP path.
- [ ] **Context Tooling**: Replace the dummy `greet` tool with capabilities like `get_job_map(job_id)` or `evaluate_outcome(statement)`.
- [ ] **Data Persistence Layer**: Connect the fastmcp server to a lightweight vector or relational database containing actual user research data.
- [ ] **Agentic Integration**: Hook the client up to an LLM (e.g., via LangChain or standard OpenAI clients) so the LLM can *discover* the ODI tools and intelligently request customer insights when ideating features.

---

## 🤝 Contributing

Contributions are welcome! This project uses [Ruff](https://docs.astral.sh/ruff/) for linting and formatting and [pytest](https://pytest.org/) for tests. Please ensure any change passes the [lint, format, and test checks](#-linting-formatting--type-checks-ci-parity) before opening a pull request.

---

## 📄 License

No license has been specified for this repository yet. Until one is added, all rights reserved by the maintainers. Please reach out before reuse or redistribution.

---

<div align="center">

*Let's build AI that builds what people actually need.*

</div>
