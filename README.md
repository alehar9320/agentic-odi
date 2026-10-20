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

## Code Overview

A [uv workspace](https://docs.astral.sh/uv/concepts/projects/workspaces/) of six
installable Python projects plus the React `studio/` front end, each with its own
build, tests, and layout:

| Package | Description |
|---|---|
| **`core/`** (`agentic-odi-core`) | Domain models, the `ODIService` business-logic layer, and repository implementations (in-memory and SQLite), including ODI opportunity-score computation. |
| **`mcp_server/`** (`agentic-odi-mcp-server`) | A foundational MCP Server exposing an HTTP transport layer. It hosts tools for Jobs, Steps, Desired Outcomes, and Customer Outcomes (linking customer value to business value). |
| **`local_server/`** (`agentic-odi-local-server`) | The FastAPI **Living Studio sidecar**. It talks to the MCP server on the client's behalf and serves the Studio API — configuration, health probes, canvas data, MCP mutations, and streaming (SSE) chat with the LLM tool-loop — plus the built SPA when `studio/dist` exists. |
| **`client/`** (`agentic-odi-client`) | The local dev **launcher** (`run.py` / `python -m client.run`) that starts the MCP server and the Studio sidecar together. |
| **`studio/`** (React + TypeScript + Vite) | **The Living Studio** front end — a spatial, conversational GUI for Outcome-Driven Innovation with an interactive Opportunity Landscape, Universal Job Map, WYSIWYG Impact Simulation, and Causal Lineage inspection, paired with an autonomous copilot. Ships as a browser SPA and as a **Tauri 2 desktop app** (`studio/src-tauri/`). |
| **`cli/`** (`agentic-odi-cli`) | A [`Typer`](https://github.com/fastapi/typer)-based command-line interface with an interactive chat mode plus `version`, `update`, `schema`, `jobs`, `steps`, `desired-outcomes`, `customer-outcomes` (alias `outcomes`), `evidence`, and `connectors` commands. Every ODI entity has full create/read/update/delete parity with the MCP tools. Data commands are local-first (`--backend local`, default) or remote (`--backend mcp`), with readable tables, `--json`, and a top-level `score`. |
| **`connectors/`** (`agentic-odi-connectors`) | Pluggable external integrations. The first kind is an **MCP client connector** that connects to a remote MCP server over HTTP, checks health, and ingests tools/resources into a local ingest sink. Additional kinds (REST, webhooks, and so on) can register against the same protocol later. |

## Quick Start

**Prerequisites:** Python 3.10+ and the [uv](https://docs.astral.sh/uv/) package
manager.

```bash
# Install the entire workspace (all six projects plus dev tooling)
uv sync --all-packages

# Build the Studio SPA, then launch the MCP server and Living Studio together
npm --prefix studio run build
python -m client.run
```

| Service | URL |
|---|---|
| MCP Server | http://localhost:8000/mcp |
| The Living Studio | http://127.0.0.1:8100 |

For hot reload, `npm --prefix studio run dev:full` starts the MCP server, the
sidecar, and Vite together on http://localhost:5173. For the desktop app, use
`npm --prefix studio run tauri dev`. See
[Running The Living Studio](docs/living-studio.md).

The Studio needs an OpenAI-compatible LLM with tool-calling support to drive its
agent — see the [Local LLM Backend](docs/local-llm.md).

### CLI at a glance

The CLI is local-first, so data commands work without a running server:

```bash
python -m cli --version          # print the Agentic ODI version
python -m cli --help             # show available options and commands
python -m cli                    # start interactive chat in a terminal
agentic-odi jobs list            # Jobs-to-be-Done
agentic-odi steps list --job-id <id>
agentic-odi desired-outcomes list --job-id <id>
agentic-odi customer-outcomes list
agentic-odi evidence list --job-id <id>
agentic-odi schema               # canonical JSON schema for every entity
agentic-odi score 8 2            # ODI opportunity score → 14.00
```

Add `--backend mcp` to route data commands through a running MCP server
(`python -m mcp_server`). See the [CLI Reference](docs/cli.md).

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
| [Running The Living Studio](docs/living-studio.md) | Run modes, desktop signing and updates, agent-driven testing (`/dev`, `/test`) |
| [Local LLM Backend](docs/local-llm.md) | Running a local OpenAI-compatible model with tool calling |
| [Development](docs/development.md) | Lint, format, type checks, frontend checks, tests and the coverage map |
| [Installation](docs/installation.md) | Binary install, updater behavior, and release automation |
| [Deployment](docs/deployment.md) | Hosted chat UI, the MCP server endpoint, and the free-plan Cloudflare Worker |
| [Roadmap](docs/roadmap.md) | Completed and upcoming milestones |
| [Superpowers](docs/superpowers.md) | Pi, OpenCode, and Freebuff integration |

## Contributing

Contributions are welcome! This project uses [Ruff](https://docs.astral.sh/ruff/)
for linting and formatting and [pytest](https://pytest.org/) for tests. Make sure
your change passes the [lint, format, and test checks](docs/development.md) before
opening a pull request.

## License

No license has been specified for this repository yet. Until one is added, all
rights reserved by the maintainers. Please reach out before reuse or
redistribution.

---

<div align="center">

*Let's build AI that builds what people actually need.*

</div>
