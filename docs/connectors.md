# External Connectors (MCP Ingest)

Connectors are named integrations stored in `~/.config/agentic-odi/connectors.json`
(or a path you pass with `--config` / `AGENTIC_ODI_CONNECTORS_CONFIG`). The first kind is
`mcp`: Agentic ODI acts as an MCP **client** and pulls catalog, resources, and
optional tool results from an external MCP **server**.

## Presets

The fastest way to connect is a preset. `connectors catalog` lists every
built-in preset, grouped by the capability area it serves:

```bash
python -m agentic_odi_cli connectors catalog                          # all presets
python -m agentic_odi_cli connectors catalog --area strategy-alignment
python -m agentic_odi_cli connectors catalog --json
```

| Capability area (`--area`) | Presets |
|---|---|
| Voice of customer & qualitative research (`voice-of-customer`) | `notion`, `gong`, `fireflies`, `intercom`, `confluence` |
| Quantitative data & opportunity scoring (`quantitative-data`) | `posthog`, `amplitude`, `mixpanel` |
| Market & competitive intelligence (`market-intelligence`) | `exa`, `tavily` |
| Product strategy & backlog alignment (`strategy-alignment`) | `linear`, `github`, `jira`, `miro`, `figma` |
| Strategy & knowledge management output (`knowledge-output`) | `slack` |

`docs/connectors-catalog.json` is the catalog as JSON, committed so a drift shows
up in review. `packages/connectors/tests/test_catalog.py` fails when it stops
matching the code; regenerate it after adding or editing a preset:

```bash
uv run python -m agentic_odi_cli connectors catalog --json > docs/connectors-catalog.json
```

Register one with `--preset`; `--name` defaults to the preset id:

```bash
# Token-based preset: export the variable it needs first
export GITHUB_PERSONAL_ACCESS_TOKEN=ghp_...
python -m agentic_odi_cli connectors add mcp --preset github
python -m agentic_odi_cli connectors health --name github
python -m agentic_odi_cli connectors ingest --name github

# OAuth-based preset: the browser consent flow starts on first use
python -m agentic_odi_cli connectors add mcp --preset notion
```

Credentials never enter the registry. Presets that use API keys store `${VAR}`
placeholders that are resolved from the environment when a connection is
opened, and `connectors health` names any variable that is missing. `--url`
overrides the endpoint (self-hosted or proxied deployments) and `--tool` still
selects which tools to call during ingest.

Custom servers keep working the same way:

```bash
python -m agentic_odi_cli connectors add mcp --name internal --url https://mcp.internal.example/mcp --tool latest_quote
python -m agentic_odi_cli connectors list
```

Omit `--name` from `connectors health` to check every configured connector in
one pass. It prints a markdown table of connector, status, and latency, names
the error for each unreachable connector, and exits non-zero if any failed —
so it can gate a deployment.

> [!NOTE]
> Presets cover MCP servers with a hosted endpoint. Servers you run yourself
> (Snowflake, BigQuery, Google Drive, Brave Search, and similar) are added with
> an explicit `--url`. The catalog lives in
> `packages/connectors/src/agentic_odi_connectors/catalog.py`.

> [!NOTE]
> OAuth tokens are cached in memory for the life of one CLI process, so an OAuth
> preset may ask for consent again on the next `connectors health` or
> `connectors ingest`. Prefer a token-based preset where the server offers one.

## Ingest behavior

Ingested records are normalized (`catalog`, `resource`, `tool_result`) and
appended to the in-process ingest sink. They are **not** written into the ODI
jobs/outcomes store — mapping ingested evidence onto ODI artifacts is still on
the [roadmap](roadmap.md).

Pass `--dry-run` to fetch and normalize without writing anything: it prints the
record count, the first normalized record, and — when `--job-id`, `--step-id`,
or `--outcome-id` is given — how many evidence drafts the ingest would create.

Additional kinds (REST, webhooks, and so on) can register against the same
`Connector` protocol later.
