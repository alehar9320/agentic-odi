<div align="center">

# Agentic ODI

### Your roadmap is a guess. This makes it evidence.

An **MCP server** that hands your agents verified customer outcomes — the jobs,
desired outcomes, and opportunity scores that rank them.

[![Open the Living Studio](https://img.shields.io/badge/Open%20the%20Living%20Studio-F38020?style=for-the-badge&logo=cloudflare&logoColor=white)](https://agentic-odi.alehar.workers.dev/)
[![Run it locally](https://img.shields.io/badge/Run%20it%20locally-1e293b?style=for-the-badge&logo=gnubash&logoColor=white)](#quick-start)

**Try it now — nothing to install.** The Studio opens in your browser; live data
and chat need the local sidecar below.

**Or install the CLI in one line** (Linux, macOS, Windows):

```bash
curl -fsSL https://github.com/alehar9320/agentic-odi/releases/latest/download/install.sh | sh
```

[![CI](https://github.com/alehar9320/agentic-odi/actions/workflows/ci.yml/badge.svg)](https://github.com/alehar9320/agentic-odi/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/alehar9320/agentic-odi/branch/main/graph/badge.svg)](https://codecov.io/gh/alehar9320/agentic-odi)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![uv](https://img.shields.io/badge/uv-managed-green)](https://docs.astral.sh/uv/)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![FastMCP](https://img.shields.io/badge/FastMCP-powered-orange)](https://github.com/jlowin/fastmcp)
[![pytest](https://img.shields.io/badge/tests-pytest-blue)](https://pytest.org)
[![MCP](https://img.shields.io/badge/Model%20Context%20Protocol-enabled-8A2BE2)](https://modelcontextprotocol.io)

> **[![Experimental](https://img.shields.io/badge/Experimental-1e293b?style=for-the-badge)](https://github.com/alehar9320/agentic-odi)**

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
- **A conversation, not a form.** The Living Studio turns customer friction into
  outcomes and opportunity insights.
- **Local-first by default.** The CLI and server work locally and can connect to
  a remote MCP server when needed.

## How it works

Outcome-Driven Innovation measures how much an outcome **matters** and how
**satisfied** customers are today:

```text
Opportunity Score = Importance + max(Importance − Satisfaction, 0)
```

Scores **> 10** indicate underserved outcomes; **= 10** are appropriately
served; **< 10** are overserved. See [Strategyn's ODI overview](https://strategyn.com/outcome-driven-innovation/).

## Quick Start

Prerequisites: Python 3.10+, [uv](https://docs.astral.sh/uv/), and Node.js.

```bash
uv sync --all-packages
npm --prefix apps/studio run build
uv run python scripts/dev.py
```

The MCP server is available at http://localhost:8000/mcp and the Studio at
http://127.0.0.1:8100. For hot reload, run
`npm --prefix apps/studio run dev:full`; for the desktop app, run
`npm --prefix apps/studio run tauri dev`.

The Studio can use an OpenAI-compatible model with tool-calling support, and
includes an offline fallback. See [Local LLM Backend](docs/local-llm.md).
The CLI is local-first:

```bash
agentic-odi jobs list
agentic-odi desired-outcomes list --job-id <id>
agentic-odi score 8 2
```

## Connect your agent

The MCP server accepts connections at `http://localhost:8000/mcp`. For example:

```json
{
  "mcpServers": {
    "agentic-odi": { "url": "http://localhost:8000/mcp" }
  }
}
```

See [External Connectors](docs/connectors.md) to connect MCP or REST data sources.

## Documentation

| Guide | Contents |
|---|---|
| [CLI Reference](docs/cli.md) | Commands, backends, and environment variables |
| [External Connectors](docs/connectors.md) | Connector presets, registry, and protocol |
| [Running The Living Studio](docs/living-studio.md) | Run modes and desktop app |
| [Local LLM Backend](docs/local-llm.md) | Configure an OpenAI-compatible local model |
| [Development](docs/development.md) | Lint, type checks, frontend checks, and tests |
| [Architecture](docs/architecture/README.md) | Workspace, dependencies, and data flow |
| [Installation](docs/installation.md) | Binary install and release automation |
| [Deployment](docs/deployment.md) | Hosted Studio, MCP endpoint, and Cloudflare Worker |
| [Roadmap](docs/roadmap.md) | Completed and upcoming milestones |
| [Superpowers](docs/superpowers.md) | Pi, OpenCode, and Freebuff integration |

## Code Overview

Python packages are under `packages/`, runnable services under `apps/`, and
deployment assets under `infra/`:

| Path | Distribution | Description |
|---|---|---|
| **`packages/core/`** | `agentic-odi-core` | ODI models, repositories, MCP contract, scoring, and model routing. |
| **`packages/connectors/`** | `agentic-odi-connectors` | Pluggable MCP and REST connectors. |
| **`apps/mcp-server/`** | `agentic-odi-mcp-server` | FastMCP server for ODI data and tools. |
| **`apps/studio-api/`** | `agentic-odi-studio-api` | FastAPI Living Studio sidecar and streaming chat. |
| **`apps/cli/`** | `agentic-odi-cli` | Local-first Typer CLI with chat and entity commands. |
| **`apps/studio/`** | React + TypeScript + Vite | Living Studio SPA and Tauri desktop shell. |
| **`infra/cloudflare/`** | Worker | Cloudflare static assets and sidecar tunnel. |

See [Architecture](docs/architecture/README.md) for workspace dependencies and
data flow.

## Contributing

Run the checks used by CI before opening a pull request:

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy apps packages
uv run pytest
```

No license has been specified for this repository; all rights are reserved by
the maintainers. Please reach out before reuse or redistribution.
