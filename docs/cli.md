# CLI Reference

The `agentic-odi` CLI is a [`Typer`](https://github.com/fastapi/typer)-based
command-line interface for working with Agentic ODI without a chat UI. It
provides an interactive chat mode plus version, update, and data commands. Data
commands are **local-first**: they read and write a SQLite store with no server
required, and switch to a remote MCP server with `--backend mcp`.

Install the workspace first if you have not already:

```bash
uv sync --all-packages
```

## Launching

```bash
python -m cli --version   # print the Agentic ODI version
python -m cli --help      # show available options and commands
python -m cli             # start interactive chat in a terminal (help when piped)
```

A console script is also installed, so `agentic-odi --version` works the same way.

## Global options

| Option | Environment variable | Default | Meaning |
|---|---|---|---|
| `--backend local\|mcp` | `AGENTIC_ODI_BACKEND` | `local` | Run in-process against SQLite, or call a remote MCP server. |
| `--db PATH` | `AGENTIC_ODI_DB` | `~/.agentic-odi/odi.db` | Store path for the `local` backend. |
| `--mcp-url URL` | `AGENTIC_ODI_MCP_URL` | `http://localhost:8000/mcp` | Server URL for the `mcp` backend. |

Data commands print readable tables and blocks by default; add `--json` for
machine-readable output. Diagnostics go to stderr and failures exit non-zero
(`0` success, `1` error, `2` usage error).

## Interactive chat

`agentic-odi chat` (or simply `agentic-odi` in a terminal) starts a
conversational session against the MCP server and an OpenAI-compatible LLM.
Responses stream to the terminal, and the assistant can call the ODI MCP tools
as it talks.

```bash
agentic-odi chat
agentic-odi chat --model local-tools-model --mcp-url http://localhost:8000/mcp
```

Before starting, run the MCP server (`python -m mcp_server`) and point the chat
at an OpenAI-compatible model endpoint. The chat reads the same environment
variables as the Living Studio:

| Variable | Default | CLI flag |
|---|---|---|
| `AGENTIC_ODI_BASE_URL` | `http://localhost:8001/v1` | `--base-url` |
| `AGENTIC_ODI_MODEL` | `local-tools-model` | `--model` |
| `AGENTIC_ODI_API_KEY` | `local` | `--api-key` |
| `AGENTIC_ODI_MCP_URL` | `http://localhost:8000/mcp` | `--mcp-url` |

Inside the session, `/help` lists the commands, `/tools` lists the MCP tools the
assistant can call, `/clear` resets the conversation, and `/exit` (or `/quit`)
ends the session.

> [!NOTE]
> Chat is the only CLI mode that needs an LLM endpoint. The `customer-outcomes`
> and `connectors` commands keep working without one.

## Manage Customer Outcomes

Customer Outcomes link customer value to business value. The `local` backend
writes to the shared SQLite store with no server required; add `--backend mcp`
to route through a running MCP server (`python -m mcp_server`). The group is also
available under its historical name `outcomes`.

```bash
# Add a Customer Outcome
agentic-odi customer-outcomes add --job-id <job-id> \
  --direction minimize --unit "time" --object "to resolve setup errors" \
  --statement "Minimize the time to resolve environment setup errors when onboarding" \
  --importance 8.8 --satisfaction 3.2 \
  --category cost_reduction \
  --business-statement "Saves engineering hours and reduces early churn"

# List outcomes (optionally filtered, or as JSON)
agentic-odi customer-outcomes list
agentic-odi customer-outcomes list --job-id <job-id>
agentic-odi customer-outcomes list --json

# Get, update, delete
agentic-odi customer-outcomes get <outcome-id>
agentic-odi customer-outcomes update <outcome-id> --importance 9.0
agentic-odi customer-outcomes delete <outcome-id> --yes

# Compute an ODI Opportunity Score (top-level, also under the group)
agentic-odi score 8 2
agentic-odi outcomes score 8 2
```

`score` applies the ODI opportunity formula,
`importance + max(importance - satisfaction, 0)`.

Set `AGENTIC_ODI_MCP_URL` (or `--mcp-url`) to point to a non-default server when
using `--backend mcp` (default: `http://localhost:8000/mcp`).

## Connectors

The `connectors` group manages external MCP integrations. See
[External Connectors](connectors.md) for presets, the connector registry, and
ingest behavior.

```bash
python -m cli connectors catalog
python -m cli connectors add mcp --preset github
python -m cli connectors list
python -m cli connectors health --name github
python -m cli connectors ingest --name github
```

## Updates

`odi update` checks for and installs a new binary release. Auto-update is on by
default; disable it with `--no-update` for one run or
`AGENTIC_ODI_NO_UPDATE=1` globally. See [Installation](installation.md).
