<div align="center">

<img src="brand/assets/odi-mascot-256.png" alt="Odi the Otter" width="150" />

# Agentic ODI

[![CI](https://github.com/alehar9320/agentic-odi/actions/workflows/ci.yml/badge.svg)](https://github.com/alehar9320/agentic-odi/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/alehar9320/agentic-odi/branch/main/graph/badge.svg)](https://codecov.io/gh/alehar9320/agentic-odi)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![uv](https://img.shields.io/badge/uv-managed-green)](https://docs.astral.sh/uv/)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![FastMCP](https://img.shields.io/badge/FastMCP-powered-orange)](https://github.com/jlowin/fastmcp)
[![pytest](https://img.shields.io/badge/tests-pytest-blue)](https://pytest.org)
[![MCP](https://img.shields.io/badge/Model%20Context%20Protocol-enabled-8A2BE2)](https://modelcontextprotocol.io)
[![Buy me a coffee](https://img.shields.io/badge/Buy%20me%20a%20coffee-FFDD00?style=for-the-badge&logo=buymeacoffee&logoColor=000000)](https://buymeacoffee.com/signup)

**Your roadmap is a guess. This makes it evidence.**

An **MCP server** that hands your agents verified customer outcomes — the jobs,
desired outcomes, and opportunity scores that rank them.

[![Open the Living Studio](https://img.shields.io/badge/Open%20the%20Living%20Studio-F38020?style=for-the-badge&logo=cloudflare&logoColor=white)](https://agentic-odi.alehar.workers.dev/)
[![Run it locally](https://img.shields.io/badge/Run%20it%20locally-1e293b?style=for-the-badge&logo=gnubash&logoColor=white)](#install)

[![Download Linux](https://img.shields.io/badge/Download-Linux-blue?style=for-the-badge&logo=linux&logoColor=white)](https://github.com/alehar9320/agentic-odi/releases/latest/download/odi_0.14.0_linux_x86_64.tar.gz)
[![Download macOS Apple Silicon](https://img.shields.io/badge/Download-macOS%20Apple%20Silicon-blue?style=for-the-badge&logo=apple&logoColor=white)](https://github.com/alehar9320/agentic-odi/releases/latest/download/odi_0.14.0_macos_arm64.tar.gz)
[![Download macOS Intel](https://img.shields.io/badge/Download-macOS%20Intel-blue?style=for-the-badge&logo=apple&logoColor=white)](https://github.com/alehar9320/agentic-odi/releases/latest/download/odi_0.14.0_macos_x86_64.tar.gz)
[![Download Windows](https://img.shields.io/badge/Download-Windows-blue?style=for-the-badge&logo=windows&logoColor=white)](https://github.com/alehar9320/agentic-odi/releases/latest/download/odi_0.14.0_windows_x86_64.zip)

</div>

![Agentic ODI — The Living Studio](docs/assets/studio-hero.png)

## Features

| Feature | Learn more |
| --- | --- |
| **A brain for customer needs** — Jobs, desired outcomes, evidence, and opportunity scores in one store, queryable by any MCP client. | [Docs →](docs/studio.md) |
| **The other half of ODI** — Stage 5 clusters scored outcomes into segments; Stage 6 recommends the one innovation path those segments support, with every path rejected and why. | [Docs →](docs/roadmap.md) |
| **A conversation, not a form** — The Living Studio opens on one question and answers back as a brief you can edit line by line. | [Docs →](docs/studio.md) |
| **Evidence over opinions** — Every claim in the Studio traces to evidence; when nothing can answer, it says so plainly. | [Docs →](docs/studio.md) |
| **Local-first and MCP-native** — Works in your browser, runs locally with the sidecar, and exposes jobs/outcomes to any MCP client. | [Docs →](docs/connectors.md) |

## Also in the box

- **CLI** — Interactive chat, full entity CRUD, schema and connectors over local or remote data.
- **Living Studio SPA + Tauri desktop** — Built on assistant-ui, keyboard- and screen-reader-operable, with auto-updates.
- **FastMCP server** — Jobs, Steps, Desired Outcomes, Customer Outcomes, Evidence, Segments, Strategy and traceability tools.
- **Connectors** — Pluggable MCP and REST connectors with presets for ingest.
- **Hosted sample** — [Open the sample workspace](https://alehar9320.github.io/agentic-odi/sample/) to see the outputs first.

## Supported platforms

![Linux](https://img.shields.io/badge/Linux-supported-blue?logo=linux&logoColor=white)
![macOS](https://img.shields.io/badge/macOS-supported-black?logo=apple&logoColor=white)
![Windows](https://img.shields.io/badge/Windows-supported-0078D6?logo=windows&logoColor=white)

## Install

### One-line install (Linux, macOS)

```bash
curl -fsSL https://github.com/alehar9320/agentic-odi/releases/latest/download/install.sh | sh
```

### Windows (PowerShell)

```powershell
iex (Invoke-WebRequest -Uri https://github.com/alehar9320/agentic-odi/releases/latest/download/install.ps1 -UseBasicParsing)
```

### Direct download

[![Download Linux](https://img.shields.io/badge/Download-Linux-blue?style=for-the-badge&logo=linux&logoColor=white)](https://github.com/alehar9320/agentic-odi/releases/latest/download/odi_0.14.0_linux_x86_64.tar.gz)
[![Download macOS Apple Silicon](https://img.shields.io/badge/Download-macOS%20Apple%20Silicon-blue?style=for-the-badge&logo=apple&logoColor=white)](https://github.com/alehar9320/agentic-odi/releases/latest/download/odi_0.14.0_macos_arm64.tar.gz)
[![Download macOS Intel](https://img.shields.io/badge/Download-macOS%20Intel-blue?style=for-the-badge&logo=apple&logoColor=white)](https://github.com/alehar9320/agentic-odi/releases/latest/download/odi_0.14.0_macos_x86_64.tar.gz)
[![Download Windows](https://img.shields.io/badge/Download-Windows-blue?style=for-the-badge&logo=windows&logoColor=white)](https://github.com/alehar9320/agentic-odi/releases/latest/download/odi_0.14.0_windows_x86_64.zip)

Both installers verify the download against `checksums.txt`; every
[release](https://github.com/alehar9320/agentic-odi/releases/latest) also carries
per-platform archives with SHA-256 checksums for a manual download. See
[Installation](docs/installation.md) for the install layout and updater.

**Try it now — nothing to install.** The Studio opens in your browser and works
from the first minute: the canvas, the thread, and the assistant all run on your
device. Add the local sidecar below for live MCP data and your own model. Want to
see what it produces first? [Open the sample
workspace](https://alehar9320.github.io/agentic-odi/sample/) — a read-only job,
its scored outcomes, and the evidence behind them, generated from a committed
fixture and labelled a sample on every row.

## Community

- [Documentation](docs/)
- [Open an issue](https://github.com/alehar9320/agentic-odi/issues)
- [Buy me a coffee](https://buymeacoffee.com/signup)

## Developing

Open a pull request against the **default** tier in
[`.agents/workflows/test.md`](.agents/workflows/test.md) — that is the bar.

```bash
uv run ruff check . && uv run ruff format --check .
uv run mypy apps packages && uv run pytest
uv run python scripts/doc_check.py   # documented commands, paths, routes, env vars, and the assistant-ui ledger hold up
```

See [Development](docs/development.md) for the frontend checks, the coverage
map, and how every pull request is automatically risk-classified.
The browser-level Studio suite runs in its own non-blocking CI job; set the
repository variable `AGENTIC_ODI_E2E` to `false` to skip it.


## Code Overview

A [uv workspace](https://docs.astral.sh/uv/concepts/projects/workspaces/) with
shared tooling at the root. Packages live in `packages/`, runnable services in
`apps/`, and deployment assets in `infra/`. The
[architecture index](docs/architecture/README.md) explains how the pieces fit
together and where each contract is enforced; its Dependency Direction diagram
is a contract of its own — `tests/test_architecture.py` checks the drawn arrows
against the declared dependencies and the real imports, so the picture cannot
drift from the workspace. The distributions are:

| Path | Distribution | Description |
|---|---|---|
| **`packages/core/`** | `agentic-odi-core` | Domain models, the `ODIService` layer, in-memory and SQLite repositories, a bounded SQLite integrity gate at open with a WAL checkpoint policy, the shared MCP tool contract, opportunity-score computation, evidence-to-outcome proposals, outcome-based segmentation (Stage 5), the innovation strategy (Stage 6), and traceability (which objectives outcomes advance, which are unfunded, which links drifted). |
| **`packages/connectors/`** | `agentic-odi-connectors` | Pluggable MCP and REST connectors with presets and an ingest sink. |
| **`apps/mcp-server/`** | `agentic-odi-mcp-server` | FastMCP server exposing Jobs, Steps, Desired Outcomes, Customer Outcomes, Evidence, outcome proposals, Segments, Strategy, traceability, and context tools over HTTP. SQLite by default. |
| **`apps/studio-api/`** | `agentic-odi-studio-api` | FastAPI **Living Studio sidecar**: config, health, metadata-only diagnostics, canvas, local mutations, MCP passthrough, SSE chat, conversations, PM memory, and scoped read-only share tokens for one artifact. It gates both SQLite files on boot, serves a structured failure page for a damaged store, and checkpoints and closes them on a clean stop. |
| **`apps/cli/`** | `agentic-odi-cli` | Typer CLI with interactive chat, full entity CRUD, `schema`, `connectors`, and local or remote data access. |
| **`apps/studio/`** | React + TypeScript + Vite | **The Living Studio** SPA and Tauri 2 desktop shell, built on [assistant-ui](https://www.assistant-ui.com). Keyboard- and screen-reader-operable, gated by an [axe-core](https://github.com/dequelabs/axe-core) WCAG 2.1 AA sweep in the frontend suite and a rendered-contrast gate over the core screens in both themes. Its browser-level suite lives in `apps/studio/e2e/`. Copied UI components land under `src/vendor/`, which is the only place Tailwind styles. Installed desktop builds **update themselves** in the background and apply on restart. A service worker (`src/sw.ts`, built to `dist/sw.js`) precaches the built shell so the app opens with no network, answers an uncached navigation with the cached shell or `public/offline.html`, and never caches `/api/**`. |
| **`infra/cloudflare/`** | Worker | Free-plan Workers Static Assets deployment and sidecar tunnel. |
| **`website/`** | — | The static project site: a generator over the repository's own sources, plus the committed read-only sample workspace at `website/sample/`. |
| **`scripts/`** | — | Dev launcher, binary build, installer tests, the deterministic study-corpus generator (`gen_corpus.py`), the shared structural audit every artifact HTML passes through (`artifact_a11y.py`, with its renderer inventory in `artifact_renderers.py`), and the hosted probe that asks the production URL whether it keeps the promises this README makes (`verify-hosted-first-run.sh`). |
| **`tests/contract/`** | — | Cross-package MCP contract tests. |

Inside `packages/core` there are four groups, and the rules between them are
written down rather than implied — with `errors.py`, the exception hierarchy, open
to every group. **Domain** (`models.py`, `evaluation.py`, `mapping.py`,
`corpus.py`) is the vocabulary and imports no other group. **Persistence**
(`repository.py`, `sqlite_repository.py`, `intent_store.py`, `events.py`,
`factory.py`) stores what the other groups decide and may not import methodology —
`tests/test_architecture.py` enforces that one rule, and also refuses a new core
module that belongs to no group. **Methodology** (`services.py`, `segmentation.py`,
`strategy.py`, `router.py`, `messages.py`, `steve_jobs.py`) owns the service door,
which is `services.py`. **Contract** (`contract.py`, `errors.py`, `remote.py`,
`schema.py`, `connection.py`, `consent.py`) is the MCP wire protocol; anything may
import it and it imports no persistence or methodology. The full table, and the
reason `contract.py` is not its own package yet, is in
[ADR 0005](docs/architecture/adr/0005-core-layers-and-the-contract-split.md).

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
