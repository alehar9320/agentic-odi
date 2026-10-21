<div align="center">

# Agentic ODI

[![CI](https://github.com/alehar9320/agentic-odi/actions/workflows/ci.yml/badge.svg)](https://github.com/alehar9320/agentic-odi/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/alehar9320/agentic-odi/branch/main/graph/badge.svg)](https://codecov.io/gh/alehar9320/agentic-odi)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![uv](https://img.shields.io/badge/uv-managed-green)](https://docs.astral.sh/uv/)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![FastMCP](https://img.shields.io/badge/FastMCP-powered-orange)](https://github.com/jlowin/fastmcp)
[![pytest](https://img.shields.io/badge/tests-pytest-blue)](https://pytest.org)
[![MCP](https://img.shields.io/badge/Model%20Context%20Protocol-enabled-8A2BE2)](https://modelcontextprotocol.io)

> **[![Experimental](https://img.shields.io/badge/Experimental-1e293b?style=for-the-badge)](https://github.com/alehar9320/agentic-odi)**

> **Experimental test to learn and evaluate the feasibility of utilizing Model Context Protocol (MCP) for Outcome-Driven Innovation (ODI) specifications.**

</div>

---

**Agentic ODI** explores how the [Model Context Protocol](https://modelcontextprotocol.io)
can turn [Outcome-Driven Innovation](https://strategyn.com/outcome-driven-innovation/)
into a live, agent-queryable source of context. Instead of feeding LLMs
disconnected prompts, an MCP-powered ODI server acts as the "brain" of customer
needs — letting agents invent, evaluate, and ideate solutions anchored in
verified, measurable customer outcomes (Job Maps, Desired Outcomes, and
Opportunity Scores).

This repository is an experimental testbed for understanding server–client MCP
communication streams, built on [`FastMCP`](https://github.com/jlowin/fastmcp).

We don't publish dates. This page changes when the code does.

**Hosted Studio:** the experimental Living Studio UI runs at
**[agentic-odi.alehar.workers.dev](https://agentic-odi.alehar.workers.dev/)**.
It loads without a backend; live data needs the sidecar tunnel described in
[Deployment](docs/deployment.md). Pull requests get preview URLs from Cloudflare
Workers Builds.

## Code Overview

A [uv workspace](https://docs.astral.sh/uv/concepts/projects/workspaces/) with
shared tooling at the root. Packages live in `packages/`, runnable services in
`apps/`, and deployment assets in `infra/`:

| Path | Distribution | Description |
|---|---|---|
| **`packages/core/`** | `agentic-odi-core` | Domain models, the `ODIService` business-logic layer, repository implementations (in-memory and SQLite), the shared MCP tool contract, and ODI opportunity-score computation. |
| **`packages/connectors/`** | `agentic-odi-connectors` | Pluggable MCP and REST connectors with presets and an ingest sink. |
| **`apps/mcp-server/`** | `agentic-odi-mcp-server` | FastMCP server exposing Jobs, Steps, Desired Outcomes, Customer Outcomes, Evidence, and context tools over HTTP. Persists to SQLite by default. |
| **`apps/studio-api/`** | `agentic-odi-studio-api` | FastAPI **Living Studio sidecar**. Serves config, health, canvas data, local mutations, MCP passthrough, SSE chat, and the built SPA. |
| **`apps/cli/`** | `agentic-odi-cli` | Typer CLI with interactive chat plus full entity CRUD, `schema`, `connectors`, and local-first (`--backend local`) or remote (`--backend mcp`) data access. |
| **`apps/studio/`** | React + TypeScript + Vite | **The Living Studio** SPA and Tauri 2 desktop shell. The copilot renders **agent-composed surfaces inline** — scored outcomes, opportunity boards, bet simulations — from a closed catalog the SPA owns. |
| **`infra/cloudflare/`** | Worker | Free-plan Workers Static Assets deployment and sidecar tunnel. |
| **`scripts/`** | — | Dev launcher, binary build, installer tests. |
| **`tests/contract/`** | — | Cross-package MCP contract tests. |

See [Architecture](docs/architecture/README.md) for the dependency graph, data
flow, and testing strategy.

## Quick Start

**Prerequisites:** Python 3.10+ and the [uv](https://docs.astral.sh/uv/) package
manager.

```bash
# Install the entire workspace (all five Python projects plus dev tooling)
uv sync --all-packages

# Build the Studio SPA, then launch the MCP server and Living Studio together
npm --prefix apps/studio run build
python scripts/dev.py
```

| Service | URL |
|---|---|
| MCP Server | http://localhost:8000/mcp |
| The Living Studio | http://127.0.0.1:8100 |

For hot reload, `npm --prefix apps/studio run dev:full` starts the MCP server, the
sidecar, and Vite together on http://localhost:5173. For the desktop app, use
`npm --prefix apps/studio run tauri dev`. See
[Running The Living Studio](docs/living-studio.md).

The first time you open the Studio it asks — conversationally, in the chat, and
skippable at any point — for your product, audience, and the job your customers
are trying to get done. Answer what you like; every reply starts from what you
shared. After that it opens as a conversation: describe a job or a customer
frustration, type `/` for commands that mirror the CLI, use the top bar bell icon
or drawer to **catch up on background outcome shifts, simulations, and telemetry signals while you were away**, or open the opportunity landscape, job map, impact simulation, evidence, and capture surfaces full screen.

The Studio is better with an OpenAI-compatible LLM with tool-calling support
(see the [Local LLM Backend](docs/local-llm.md)), but it does not depend on one:
with no model reachable it says so and every job, step, and outcome remains
editable by hand.

### Connectors (MCP ↔ Living Studio)

Register MCP or REST connectors that the copilot can discover and invoke.

- **Where they live**: a shared `connectors.json` registry. Override its location
  with `AGENTIC_ODI_CONNECTORS_CONFIG`; by default it is
  `~/.config/agentic-odi/connectors.json`. See
  [External Connectors](docs/connectors.md).
- **In the Living Studio**: open the **Settings** drawer → **Connectors** to list,
  remove, or add one of the recommended presets (Notion, PostHog, Exa, Linear,
  GitHub).
- **Conversationally**: tell the copilot "use Notion" / "add the GitHub connector".
  It emits an `add_connector` local tool (handled in-process) that writes the
  preset to the registry, plus a `connector` SSE event the Studio surfaces as a
  suggestion chip. Dismissing or accepting the chip also refreshes the list.
- **API**: `GET/POST/DELETE /api/connectors`, `GET /api/connectors/catalog`, and
  `GET /api/connectors/{name}/health` (the catalog honors
  `?area=<capability>` and `?recommended=true`).
- **CLI**: `agentic-odi connectors catalog | add <preset> | list | health <name> | ingest <name>`.

### CLI at a glance

The CLI is local-first, so data commands work without a running server:

```bash
python -m agentic_odi_cli --version          # print the Agentic ODI version
python -m agentic_odi_cli --help             # show available options and commands
python -m agentic_odi_cli       # start interactive chat in a terminal
agentic-odi jobs list            # Jobs-to-be-Done
agentic-odi steps list --job-id <id>
agentic-odi desired-outcomes list --job-id <id>
agentic-odi customer-outcomes list
agentic-odi evidence list --job-id <id>
agentic-odi schema               # canonical JSON schema for every entity
agentic-odi score 8 2            # ODI opportunity score → 14.00
```

Add `--backend mcp` to route data commands through a running MCP server
(`python -m agentic_odi_mcp_server`). See the [CLI Reference](docs/cli.md).

### Install the binary

Prebuilt binaries are available for Linux, macOS, and Windows:

```bash
curl -fsSL https://github.com/alehar9320/agentic-odi/releases/latest/download/install.sh | sh
```

The installer symlinks `odi`, `odipm`, `odi-cli`, and `agentic-odi` into
`~/.local/bin/`. See [Installation](docs/installation.md) for the install
layout, updates, and release automation.

## Documentation

| Guide | Contents |
|---|---|
| [CLI Reference](docs/cli.md) | Backends, interactive chat, Jobs/Steps/desired Outcomes/Customer Outcomes/evidence, `connectors`, scoring, environment variables |
| [External Connectors](docs/connectors.md) | The MCP ingest connector, presets, and the `Connector` protocol |
| [Running The Living Studio](docs/living-studio.md) | Interface, rich inline responses and the UI catalog, run modes, desktop signing and updates, agent-driven testing (`/dev`, `/test`) |
| [Local LLM Backend](docs/local-llm.md) | Running a local OpenAI-compatible model with tool calling |
| [Development](docs/development.md) | Lint, format, type checks, frontend checks, tests and the coverage map |
| [Architecture](docs/architecture/README.md) | Workspace layout, dependency direction, data flow, and testing |
| [Installation](docs/installation.md) | Binary install, updater behavior, and release automation |
| [Deployment](docs/deployment.md) | Hosted Studio and PR preview URLs, the MCP server endpoint, and the free-plan Cloudflare Worker |
| [Roadmap](docs/roadmap.md) | Completed and upcoming milestones |
| [Superpowers](docs/superpowers.md) | Pi, OpenCode, and Freebuff integration |

## Contributing

Contributions are welcome! This project uses [Ruff](https://docs.astral.sh/ruff/)
for linting and formatting and [pytest](https://pytest.org/) for tests. Make sure
your change passes the [lint, format, and test checks](docs/development.md) before
opening a pull request.

## License

This project is licensed under the terms of the MIT License — see
[LICENSE](LICENSE) for details.

---

<div align="center">

*Let's build AI that builds what people actually need.*

</div>
