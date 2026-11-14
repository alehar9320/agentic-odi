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
| Product strategy & backlog alignment (`strategy-alignment`) | `linear`, `github`, `jira`, `miro`, `figma`, `composio` |
| Strategy & knowledge management output (`knowledge-output`) | `context7`, `slack` |

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
python -m agentic_odi_cli connectors list-presets   # markdown table of built-in presets

# OAuth-based preset: the browser consent flow starts on first use
python -m agentic_odi_cli connectors add mcp --preset notion
python -m agentic_odi_cli connectors add mcp --preset composio
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

> [!NOTE]
> **Composio is optional, and the CLI is fail-open.** Health and ingest are
> per-connector, so a missing, unreachable, or rate-limited Composio endpoint
> reports unhealthy for `composio` only and never blocks another connector, the
> `connectors health` table, or any default flow. Adding the `composio` preset
> changes behavior for no workspace that does not configure it. If Composio is
> down or runs out, keep using the other connectors and the AI flow; it is
> designed to keep working.

## Adding Composio as an integration

Composio is a managed MCP hub for 1000+ apps (GitHub, Slack, Linear, Notion,
Jira, ...). It is wired up like any other preset, and it is **optional**:
nothing in the CLI or the default flow requires it. Composio documents two
connection modes, and this guide covers both without adding a dependency.

### Shared endpoint (recommended for most teams)

`https://connect.composio.dev/mcp` is Composio's hosted MCP URL for an MCP
client that authorizes in the browser. The preset carries that static URL and
`auth: "oauth"`, with no credential in the registry:

```bash
# Register the preset; the browser consent flow starts on the first health/ingest call
python -m agentic_odi_cli connectors add mcp --preset composio

# Check it independently; a down or rate-limited endpoint reports unhealthy
# for composio only
python -m agentic_odi_cli connectors health --name composio

# Ingest is per-connector and opt-in; another connector's ingest is unaffected
python -m agentic_odi_cli connectors ingest --name composio --job-id job_123
```

A generic MCP client that cannot run the browser consent flow can send
Composio's consumer key header instead. The `${VAR}` placeholder is resolved
from the environment when a connection is opened, so the key never enters the
registry:

```bash
export COMPOSIO_CONSUMER_KEY=your-consumer-key
python -m agentic_odi_cli connectors add mcp --name composio \
  --url https://connect.composio.dev/mcp \
  --header "x-consumer-api-key=${COMPOSIO_CONSUMER_KEY}"
```

### Per-user toolkits (session-scoped)

When each person needs their own toolkits and connected accounts, Composio
issues a session-scoped MCP URL. There is no static per-user URL to hardcode:
create a session with the Composio API, then read `mcp.url` and `mcp.headers`
from the response.

```bash
export COMPOSIO_API_KEY=your-api-key
curl -sS -X POST https://backend.composio.dev/api/v3.1/tool_router/session \
  -H "x-api-key: $COMPOSIO_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"user_id": "user_123"}' | jq -r '.mcp.url'
```

Register that URL for the user. `--header` is repeatable and interpolates
`${VAR}` from the environment; use the header name Composio returns in
`session.mcp.headers` (`x-api-key` in the documented flow):

```bash
python -m agentic_odi_cli connectors add mcp --name composio-user_123 \
  --url "https://backend.composio.dev/..." \
  --header "x-api-key=${COMPOSIO_API_KEY}"
```

Both modes are strictly optional and fail-open. `connectors health` and
`connectors ingest` are per-connector, so a missing, unreachable, or
rate-limited Composio endpoint reports unhealthy for `composio` only and never
blocks another connector, the `connectors health` table, or any default flow.
Adding the `composio` preset changes behavior for no workspace that does not
configure it.

The preset shape lives in
`packages/connectors/src/agentic_odi_connectors/catalog.py`. To add it to
another project, copy the `composio` entry (id, label, area, summary, url,
auth, docs, `is_recommended: false`), regenerate the catalog JSON, and update
the presets table. The shared URL is static; the session URL is per user and
comes from the API response, so copy the recipe rather than the URL. Because
health and ingest are per-connector, a missing or unreachable Composio endpoint
never breaks another connector or the CLI — verify that in the host project
before shipping.

## Ingest behavior

Ingested records are normalized (`catalog`, `resource`, `tool_result`) and
appended to the in-process ingest sink. When `--job-id`, `--step-id`, or
`--outcome-id` is supplied, each normalized record is **also** mapped to an
evidence draft and written to the ODI store as an `Evidence` record, carrying
the source name, source kind, item type, content, URL when one is present, the
raw payload, and the link.

Without a target id nothing enters the ODI store: the batch lives only in the
in-process sink and is lost when the process exits.

With `--propose` (the default), each evidence draft becomes a scored,
approvable outcome proposal instead of being written directly. The proposal
routes the record to a job and step, extracts a candidate ODI-format outcome
statement, suggests importance/satisfaction with confidence, and shows its
rationale. Nothing is written to the ODI store until a human approves the
proposal. Pass `--apply` to write outcomes directly (opt-in, destructive).

Pass `--dry-run` to fetch and normalize without writing anything: it prints the
record count, the first normalized record, and — when `--job-id`, `--step-id`,
or `--outcome-id` is given — how many evidence drafts the ingest would create.

Every evidence draft is an `EvidenceDraft` model, so construction raises before
a record that crossed a process boundary can reach the ODI store with a missing
or mistyped field. `validate_evidence_draft()` applies the same check to a draft
that arrives as a plain dict; the CLI path builds the model directly. Drafts
carry a `discriminator` (the stable key of the source record) so re-ingesting
the same source record does not create a duplicate proposal.

### Ingest rate limit

The sink admits records through a token bucket so a burst cannot grow the
in-process buffer without bound. `IngestSink.append` asks for one token per
record and raises `RateLimitExceededError` when the bucket is empty; the CLI
prints that as `Error: Rate limit exceeded: …` and exits 1. An empty batch does
not consume tokens.

| Setting | Environment variable | Default |
|---|---|---|
| Records admitted per second | `AGENTIC_ODI_INGEST_RATE` | `100` |
| Burst (max tokens held) | one second's worth | `100` for the default rate |

Invalid or non-positive values fall back to 100. The limiter never blocks: a
burst is shed with a typed error instead of being queued in memory, which is the
failure mode this guard exists to prevent. Construct `IngestSink` with an
explicit `RateLimiter` to override the rate or the burst in-process.

Additional kinds (REST, webhooks, and so on) can register against the same
`Connector` protocol later.

## HTTP client configuration

Connector HTTP traffic goes through one configurable client,
`agentic_odi_connectors.get_http_client()`, so pool size, timeout, and retry
behavior are predictable. Tune it with environment variables:

| Variable | Default | Meaning |
|---|---|---|
| `AGENTIC_ODI_HTTP_POOL_SIZE` | `10` | Maximum open connections (and keep-alive connections) |
| `AGENTIC_ODI_HTTP_TIMEOUT` | `30.0` | Per-request timeout in seconds |
| `AGENTIC_ODI_HTTP_RETRIES` | `3` | Retries for connection-level failures |

Invalid or out-of-range values fall back to the default instead of failing the
process.

