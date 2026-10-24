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
python -m agentic_odi_cli --version   # print the Agentic ODI version
python -m agentic_odi_cli --help      # show available options and commands
python -m agentic_odi_cli             # start interactive chat in a terminal (help when piped)
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

`agentic-odi chat` (or simply `agentic-odi` in a terminal) starts an
offline-first interactive REPL. The session always boots, even when no model or
MCP server is reachable — a yellow warning is shown for any unavailable service,
and free-text messages return a friendly nudge until you connect.

```bash
agentic-odi chat
agentic-odi chat --model local-tools-model --mcp-url http://localhost:8000/mcp
```

### Connection settings

The chat resolves settings in priority order:
**CLI flag → environment variable → persisted profile → built-in default.**

| Variable | Default | CLI flag |
|---|---|---|
| `AGENTIC_ODI_BASE_URL` | `http://localhost:8001/v1` | `--base-url` |
| `AGENTIC_ODI_MODEL` | `local-tools-model` | `--model` |
| `AGENTIC_ODI_API_KEY` | `local` | `--api-key` |
| `AGENTIC_ODI_MCP_URL` | `http://localhost:8000/mcp` | `--mcp-url` |

The **persisted profile** is stored at
`~/.config/agentic-odi/llm_profile.json`. You can create or update it from
within the session using `/connect`.

### Slash commands

| Command | Description |
|---|---|
| `/help` | Show all available commands |
| `/status` | Show current model, base URL, and MCP server with connection status |
| `/connect` | Launch the wizard: provider → URL → API key → model → MCP URL → save |
| `/model <name>` | Hot-swap to a different model mid-session |
| `/mcp <url>` | Reconnect to a different MCP server mid-session |
| `/tools` | List the MCP tools the assistant can call |
| `/clear` | Reset conversation history (keeps connection) |
| `/exit` | Quit the session (also `/quit`) |

### /connect wizard

`/connect` walks you through configuring your LLM provider interactively:

1. **Provider** — choose `openai`, `anthropic`, `local`, or `other`
2. **Base URL** — preset filled for known providers; override freely
3. **API key** — input is hidden via `getpass`
4. **Model** — sensible default per provider
5. **MCP URL** — defaults to the current value
6. **Save to profile?** — writes `~/.config/agentic-odi/llm_profile.json` so settings persist across sessions

The wizard can be cancelled at any step with Ctrl-C.

> [!NOTE]
> Chat is the only CLI mode that needs an LLM endpoint. The `customer-outcomes`
> and `connectors` commands keep working without one.

## Manage Jobs, Steps, and desired Outcomes

Every ODI entity has the same create/read/update/delete surface in the CLI and
the MCP server. Jobs hold Steps (the Job Map) and desired Outcomes; deleting a
Job cascades to both.

```bash
# Jobs
agentic-odi jobs add --name "Onboard a customer" --description "First 30 days"
agentic-odi jobs list
agentic-odi jobs get <job-id>
agentic-odi jobs update <job-id> --name "Onboard a new customer"
agentic-odi jobs delete <job-id> --yes

# Steps (Job Map)
agentic-odi steps add --job-id <job-id> --name "Prepare environment" --order 1
agentic-odi steps list --job-id <job-id>
agentic-odi steps get <step-id>
agentic-odi steps update <step-id> --order 2
agentic-odi steps delete <step-id> --yes

# Desired Outcomes
agentic-odi desired-outcomes add --job-id <job-id>   --statement "Minimize the time it takes to get a working environment"   --importance 8 --satisfaction 4
agentic-odi desired-outcomes list --job-id <job-id>
agentic-odi desired-outcomes get <outcome-id>
agentic-odi desired-outcomes update <outcome-id> --satisfaction 6
agentic-odi desired-outcomes delete <outcome-id> --yes
```

Add `--json` to any command for machine-readable output.

## Evidence

Evidence is research captured from connectors (or entered by hand) and linked to
a Job, Step, or desired Outcome. Records can later be promoted into ODI
artifacts — the bridge from research to the model, without hand-copying.

```bash
# Capture a record by hand
agentic-odi evidence add \
  --source-name "interview" --source-kind manual \
  --name "Support lead" \
  --content "Setup takes two days for every new engineer" \
  --job-id <job-id>

# Read and delete
agentic-odi evidence list --job-id <job-id>
agentic-odi evidence list --job-id <job-id> --json
agentic-odi evidence get <evidence-id>
agentic-odi evidence delete <evidence-id> --yes

# Promote into the ODI model
agentic-odi evidence promote <evidence-id> --to job
agentic-odi evidence promote <evidence-id> --to outcome --job-id <job-id>
```

`connectors ingest --job-id <job-id>` maps every evidence-bearing record in the
ingested batch into evidence in one step.

## Schema and scoring

```bash
agentic-odi schema                   # canonical JSON schema for every ODI entity
agentic-odi framework-guidelines     # ODI stage-by-stage tool guide
agentic-odi capabilities             # what the assistant can help with
agentic-odi score 8 2                # ODI opportunity score → 14.00
```

## Manage Customer Outcomes

Customer Outcomes link customer value to business value. The `local` backend
writes to the shared SQLite store with no server required; add `--backend mcp`
to route through a running MCP server (`python -m agentic_odi_mcp_server`). The group is also
available under its historical name `outcomes`.

```bash
# Add a Customer Outcome
agentic-odi customer-outcomes add --job-id <job-id> \
  --direction minimize --unit "time" --object "to resolve setup errors" \
  --statement "Minimize the time to resolve environment setup errors when onboarding" \
  --importance 8.8 --satisfaction 3.2 \
  --category cost_reduction \
  --business-statement "Saves engineering hours and reduces early churn"

# Attach value metrics: repeatable JSON objects
agentic-odi customer-outcomes add --job-id <job-id> \
  --direction minimize --unit "time" --object "to resolve setup errors" \
  --statement "Minimize the time to resolve environment setup errors when onboarding" \
  --importance 8.8 --satisfaction 3.2 --category cost_reduction \
  --business-statement "Saves engineering hours" \
  --value-metric '{"name":"first response","direction":"minimize","unit_of_measure":"minutes","importance":7,"satisfaction":3}'

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
python -m agentic_odi_cli connectors catalog
python -m agentic_odi_cli connectors add mcp --preset github
python -m agentic_odi_cli connectors list
python -m agentic_odi_cli connectors health --name github
python -m agentic_odi_cli connectors ingest --name github
```

## Updates

`odi update` checks for and installs a new binary release. Auto-update is on by
default; disable it with `--no-update` for one run or
`AGENTIC_ODI_NO_UPDATE=1` globally. See [Installation](installation.md).
