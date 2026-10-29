<div align="center">

<img src="brand/assets/odi-mascot-256.png" alt="Odi the Otter" width="150" />

# Agentic ODI

### Your roadmap is a guess. This makes it evidence.

An **MCP server** that hands your agents verified customer outcomes — the jobs,
desired outcomes, and opportunity scores that rank them.

[![Open the Living Studio](https://img.shields.io/badge/Open%20the%20Living%20Studio-F38020?style=for-the-badge&logo=cloudflare&logoColor=white)](https://agentic-odi.alehar.workers.dev/)
[![Run it locally](https://img.shields.io/badge/Run%20it%20locally-1e293b?style=for-the-badge&logo=gnubash&logoColor=white)](#quick-start)

**Try it now — nothing to install.** The Studio opens in your browser; live data
and chat need the local sidecar below.

**Or install the CLI in one line** (Linux, macOS):

```bash
curl -fsSL https://github.com/alehar9320/agentic-odi/releases/latest/download/install.sh | sh
```

On Windows (PowerShell):

```powershell
iex (Invoke-WebRequest -Uri https://github.com/alehar9320/agentic-odi/releases/latest/download/install.ps1 -UseBasicParsing)
```

Both installers verify the download against `checksums.txt`; every
[release](https://github.com/alehar9320/agentic-odi/releases/latest) also carries
per-platform archives with SHA-256 checksums for a manual download. See
[Installation](docs/installation.md) for the install layout and updater.

[![CI](https://github.com/alehar9320/agentic-odi/actions/workflows/ci.yml/badge.svg)](https://github.com/alehar9320/agentic-odi/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/alehar9320/agentic-odi/branch/main/graph/badge.svg)](https://codecov.io/gh/alehar9320/agentic-odi)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![uv](https://img.shields.io/badge/uv-managed-green)](https://docs.astral.sh/uv/)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![FastMCP](https://img.shields.io/badge/FastMCP-powered-orange)](https://github.com/jlowin/fastmcp)
[![pytest](https://img.shields.io/badge/tests-pytest-blue)](https://pytest.org)
[![MCP](https://img.shields.io/badge/Model%20Context%20Protocol-enabled-8A2BE2)](https://modelcontextprotocol.io)
[![Buy me a coffee](https://img.shields.io/badge/Buy%20me%20a%20coffee-FFDD00?style=for-the-badge&logo=buymeacoffee&logoColor=000000)](https://buymeacoffee.com/signup)

> **[![Experimental](https://img.shields.io/badge/Experimental-1e293b?style=for-the-badge)](https://github.com/alehar9320/agentic-odi)**

> **Experimental test to learn and evaluate the feasibility of utilizing Model Context Protocol (MCP) for Outcome-Driven Innovation (ODI) specifications.**
[![GitHub Pages](https://img.shields.io/badge/GitHub%20Pages-site-blue?logo=github)](https://alehar9320.github.io/agentic-odi/)

</div>

---

## Why this exists

- **Roadmaps are set by whoever talks loudest.** Decisions default to seniority,
  not evidence.
- **Teams build features for customers who never asked.** The idea gets
  validated; the outcome never does.
- **Agents are fluent in everything and grounded in nothing.** A model will
  confidently invent your customer.

## What you get

- **A brain for customer needs.** Jobs, desired outcomes, evidence, and
  opportunity scores in one store — queryable by any MCP client.
- **A conversation, not a form.** The Living Studio turns "a customer still
  reconciles invoices by hand" into a scored outcome, a job map, and a ranked
  opportunity board — inline in the thread.
- **Local-first by default.** The CLI and server work with no network and no
  account. Point them at a remote MCP server with one flag.

## How it works

Outcome-Driven Innovation asks customers two numbers per outcome — how much it
**matters** and how **satisfied** they are today. The gap is where products win
or die:

```text
Opportunity Score = Importance + max(Importance − Satisfaction, 0)
```

Score **> 10** → underserved, innovate. **= 10** → served, maintain.
**< 10** → overserved, disrupt. ODI reports an **86% innovation success rate**
(as reported in the [Strategyn](https://strategyn.com/outcome-driven-innovation/) literature).

## Quick Start

**Run the full stack locally.** Prerequisites: Python 3.10+,
[uv](https://docs.astral.sh/uv/), and Node.js for the Studio build.

```bash
git clone https://github.com/alehar9320/agentic-odi.git
cd agentic-odi
uv sync --all-packages              # install the whole workspace
npm --prefix apps/studio run build  # build the Living Studio once
uv run python scripts/dev.py        # start the MCP server + Studio together
```

| Service | URL |
|---|---|
| MCP Server | http://localhost:8000/mcp |
| The Living Studio | http://127.0.0.1:8100 |

- **Hot reload:** `npm --prefix apps/studio run dev:full` (Vite on
  http://localhost:5173).
- **Desktop app:** `npm --prefix apps/studio run tauri dev`.
- **No model? No problem.** Without an OpenAI-compatible LLM every job, step,
  and outcome stays editable by hand. See [Local LLM Backend](docs/local-llm.md).
- **Just the CLI:** it is local-first, so data commands need no server at all.

```bash
odi jobs list
odi desired-outcomes list --job-id <id>
odi score 8 2                        # → 14.00
odi                                  # interactive chat in a terminal
```

## Connect your agent

The server speaks the Model Context Protocol. Any MCP client can reach it:

```json
{
  "mcpServers": {
    "agentic-odi": { "url": "http://localhost:8000/mcp" }
  }
}
```

Register MCP or REST connectors (Notion, PostHog, Exa, Linear, GitHub) in the
Studio's **Settings → Connectors**, conversationally, or via
`agentic-odi connectors add <preset>`. See
[External Connectors](docs/connectors.md).

## Documentation

| Guide | Contents |
|---|---|
| [The Living Studio](docs/living-studio.md) | The chat-first interface, first run, approvals, memory, and the desktop app |
| [CLI Reference](docs/cli.md) | Backends, chat, entities, scoring, and environment variables |
| [External Connectors](docs/connectors.md) | Presets, the registry, and the `Connector` protocol |
| [Local LLM Backend](docs/local-llm.md) | Running a local OpenAI-compatible model with tool calling |
| [Architecture](docs/architecture/README.md) | Workspace layout, dependency direction, data flow, and testing |
| [Development](docs/development.md) | Lint, types, frontend checks, tests, and PR risk labels |
| [Installation](docs/installation.md) | Binary install, updater behavior, and release automation |
| [Deployment](docs/deployment.md) | Project site, Hosted Studio, MCP endpoint, and the Cloudflare Worker |
| [Roadmap](docs/roadmap.md) | Completed and upcoming milestones |
| [Superpowers](docs/superpowers.md) | Pi, OpenCode, and Freebuff integration |

Every guide is also published on the
[project site](https://alehar9320.github.io/agentic-odi/docs/), rendered from
these files. The site adds a quick start, a generated MCP tool reference, the
connector catalog, and client-side search over every page (`Ctrl`/`Cmd`+`K`).

## Code Overview

A [uv workspace](https://docs.astral.sh/uv/concepts/projects/workspaces/) with
shared tooling at the root. Packages live in `packages/`, runnable services in
`apps/`, and deployment assets in `infra/`:

| Path | Distribution | Description |
|---|---|---|
| **`packages/core/`** | `agentic-odi-core` | Domain models, the `ODIService` layer, in-memory and SQLite repositories, the shared MCP tool contract, and opportunity-score computation. |
| **`packages/connectors/`** | `agentic-odi-connectors` | Pluggable MCP and REST connectors with presets and an ingest sink. |
| **`apps/mcp-server/`** | `agentic-odi-mcp-server` | FastMCP server exposing Jobs, Steps, Desired Outcomes, Customer Outcomes, Evidence, and context tools over HTTP. SQLite by default. |
| **`apps/studio-api/`** | `agentic-odi-studio-api` | FastAPI **Living Studio sidecar**: config, health, canvas, local mutations, MCP passthrough, SSE chat, conversations, and PM memory. |
| **`apps/cli/`** | `agentic-odi-cli` | Typer CLI with interactive chat, full entity CRUD, `schema`, `connectors`, and local or remote data access. |
| **`apps/studio/`** | React + TypeScript + Vite | **The Living Studio** SPA and Tauri 2 desktop shell, built on [assistant-ui](https://www.assistant-ui.com). Installed desktop builds **update themselves** in the background and apply on restart. |
| **`infra/cloudflare/`** | Worker | Free-plan Workers Static Assets deployment and sidecar tunnel. |
| **`scripts/`** | — | Dev launcher, binary build, installer tests. |
| **`tests/contract/`** | — | Cross-package MCP contract tests. |

## Contributing

Contributions are welcome. Run the checks that CI runs before opening a pull
request:

```bash
uv run ruff check . && uv run ruff format --check .
uv run mypy apps packages && uv run pytest
```

See [Development](docs/development.md) for the frontend checks, the coverage
map, and how every pull request is automatically risk-classified.

## Brand

**Odi the Otter** is the mascot — a golden-ratio-derived pixel otter appearing in
the CLI, the Studio, the desktop icon, and this page. The artwork is original,
generated by a committed script, and documented in
[brand/README.md](brand/README.md).

```bash
uv run python brand/tools/render.py   # regenerate every Odi asset
```

## License

MIT — see [LICENSE](LICENSE).

---

<div align="center">

*Let's build AI that builds what people actually need.*

</div>
