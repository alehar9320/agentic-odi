<div align="center">

# Agentic ODI

<img src="brand/assets/odi-mascot-256.png" alt="" width="180" />

[![Open the Living Studio](https://img.shields.io/badge/Open%20the%20Living%20Studio-F38020?style=for-the-badge&logo=cloudflare&logoColor=white)](https://agentic-odi.alehar.workers.dev/)

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

> **See it live:** **[agentic-odi.alehar.workers.dev](https://agentic-odi.alehar.workers.dev/)**.
> No install required; the interface loads immediately, while live data, chat, and
> mutations need the local sidecar ([Deployment](docs/deployment.md)). To run the
> full stack yourself, jump to [Quick Start](#quick-start).

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

**Project site:** the site lives at
**[alehar9320.github.io/agentic-odi](https://alehar9320.github.io/agentic-odi/)**,
with a documentation hub at
**[alehar9320.github.io/agentic-odi/docs/](https://alehar9320.github.io/agentic-odi/docs/)**.
It is republished by the `Pages` workflow on every push to `main`. The site is
generated from this repository — the MCP tool reference, the connector catalog,
and the ODI schema are read from the code that ships, so they cannot drift from
it. The CLI reference is hand-written; a test fails when it misses a command.

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
| **`apps/studio-api/`** | `agentic-odi-studio-api` | FastAPI **Living Studio sidecar**. Serves config, health, canvas data, local mutations, MCP passthrough, SSE chat, conversation history, and the PM memory store, plus the built SPA. |
| **`apps/cli/`** | `agentic-odi-cli` | Typer CLI with interactive chat plus full entity CRUD, `schema`, `connectors`, and local-first (`--backend local`) or remote (`--backend mcp`) data access. |
| **`apps/studio/`** | React + TypeScript + Vite | **The Living Studio** SPA and Tauri 2 desktop shell. The copilot renders **agent-composed surfaces inline** — scored outcomes, opportunity theses, bet simulations — from a closed catalog the SPA owns. A feature-flagged **four-step first-run tour** starts from the PM's ambition, and a local memory records what matters across sessions. |
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

The first time you open the Studio, the tour asks what you want to win: an
opportunity you already have in mind, a priority your boss handed you, finding
the next opportunity, or pressure-testing a bet. Pick one and the conversation
starts there — no form, no framework speech. It still asks for your product and
audience when it needs them, and everything you say is optional and skippable.

After that it opens as one room: the transcript and the composer never leave the
screen. Describe a job or a customer frustration, or type `/` for commands that
mirror the CLI. Whatever the thread produces — scored outcomes, an opportunity
thesis, a job map, customer evidence — arrives as an inline surface, and a quiet
rail above the conversation opens it in a lens that docks beside the thread
instead of replacing it. Capture and simulation are conversations too: tell the
studio what a customer said, or what bet you are weighing, and it renders the
card. Use the bell to **catch up on outcome shifts, simulations, and telemetry
signals while you were away**.

The studio also remembers the person, not just the canvas. As you talk it notes
what matters — your role, the opportunity, business constraints, stakeholders,
evidence, how you like to work — and shows each note under **What I know** so you
can confirm, correct, add, or forget it. The thread and those notes resume on the
next launch. Memory lives in `~/.agentic-odi/studio.db` (override with
`AGENTIC_ODI_STUDIO_DB`, or use `:memory:` for tests) and never blocks a reply if
it fails. **Forget everything** clears the notes and the thread.

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

### When something fails

Failures are shown where they happen, not dressed up as empty results. Every
HTTP error from the Living Studio sidecar carries one body —
`{"error": {"code", "message", "detail", "suggestion", "retryable", "request_id"}}` —
and the Studio renders it in place with a **Retry** button that keeps your
question. A chat turn always ends with exactly one reply or one error, the
canvas shows an invitation when there is nothing yet and a failure panel when
the fetch failed, and a broken lens is contained to that lens. Quote the
`request_id` when you report a failure: it is echoed on the response header and
on every streamed frame, and it is the id in the sidecar's per-turn log line.

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
| [Running The Living Studio](docs/living-studio.md) | First-run tour and its flag, local memory and conversation resume, interface, rich inline responses and the UI catalog, run modes, desktop signing and updates, agent-driven testing (`/dev`, `/test`) |
| [Local LLM Backend](docs/local-llm.md) | Running a local OpenAI-compatible model with tool calling |
| [Development](docs/development.md) | Lint, format, type checks, frontend checks, tests and the coverage map |
| [Architecture](docs/architecture/README.md) | Workspace layout, dependency direction, data flow, and testing |
| [Installation](docs/installation.md) | Binary install, updater behavior, and release automation |
| [Deployment](docs/deployment.md) | Project site on GitHub Pages, Hosted Studio and PR preview URLs, the MCP server endpoint, and the free-plan Cloudflare Worker |
| [Roadmap](docs/roadmap.md) | Completed and upcoming milestones |
| [Superpowers](docs/superpowers.md) | Pi, OpenCode, and Freebuff integration |

Every guide above is also published on the
[project site](https://alehar9320.github.io/agentic-odi/docs/), rendered from
these files. The site adds a quick start, a generated MCP tool reference, and
the connector catalog.

## Contributing

Contributions are welcome! This project uses [Ruff](https://docs.astral.sh/ruff/)
for linting and formatting and [pytest](https://pytest.org/) for tests. Make sure
your change passes the [lint, format, and test checks](docs/development.md) before
opening a pull request.

## 🦦 Brand

Odi the Otter is the mascot of Agentic ODI — a golden-ratio-derived pixel otter
who appears in the CLI, the Living Studio, the desktop app icon, the favicon,
and this page. The artwork is original, generated by a committed script, and
documented in [brand/README.md](brand/README.md).

```bash
uv run python brand/tools/render.py   # regenerate every Odi asset
```

## License

This project is licensed under the terms of the MIT License — see
[LICENSE](LICENSE) for details.

---

<div align="center">

*Let's build AI that builds what people actually need.*

</div>
