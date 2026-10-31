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
python -m agentic_odi_cli --version            # print the Agentic ODI version
python -m agentic_odi_cli --version --verbose  # print version with build metadata
python -m agentic_odi_cli --help               # show available options and commands
python -m agentic_odi_cli                      # start interactive chat in a terminal (help when piped)
```

A console script is also installed, so `agentic-odi --version` and
`agentic-odi version --verbose` work the same way.

## Global options

| Option | Environment variable | Default | Meaning |
|---|---|---|---|
| `--backend auto\|local\|mcp` | `AGENTIC_ODI_BACKEND` | `local` | Run in-process against SQLite, call a remote MCP server, or (`auto`) try local first and fall back to MCP. |
| `--db PATH` | `AGENTIC_ODI_DB` | `~/.agentic-odi/odi.db` | Store path for the `local` backend. |
| `--mcp-url URL` | `AGENTIC_ODI_MCP_URL` | `http://localhost:8000/mcp` | Server URL for the `mcp` backend. |

Data commands print readable tables and blocks by default; add `--json` for
machine-readable output. Diagnostics go to stderr and failures exit non-zero
(`0` success, `1` error, `2` usage error).

## MCP connection limits

| Variable | Default | Meaning |
|---|---|---|
| `AGENTIC_ODI_MCP_TIMEOUT` | `30.0` | Seconds allowed for one MCP call and for the connection handshake. Invalid or non-positive values fall back to the default. |
| `AGENTIC_ODI_MCP_KEEPALIVE` | `15.0` | Keepalive interval in seconds for MCP sessions; `0` disables keepalive. |

Both values are parsed by `agentic_odi_core.MCPConnectionConfig.from_env()`.
The CLI hands the timeout to the FastMCP client for every call, so a frozen
server fails with a clear error instead of hanging. FastMCP has no
keepalive-interval setting yet, so the interval is carried for transports that
support session keepalive.

## Interactive chat

`agentic-odi chat` (or simply `agentic-odi` in a terminal) starts an
offline-first interactive REPL. The session always boots, even when no model or
MCP server is reachable — a yellow warning is shown for any unavailable service,
and free-text messages return a friendly nudge until you connect.

```bash
agentic-odi chat
agentic-odi chat --model local-tools-model --mcp-url http://localhost:8000/mcp
```

Thinking does not need the Studio or its sidecar. While the first token is on
its way, a dim `thinking…` sits on the prompt line and is erased when the reply
starts, so a cold model reads as work rather than a hung session. When the
model exposes its reasoning (`reasoning_content` or `reasoning`, as vLLM,
Ollama, and DeepSeek do), it is printed dimmed on stderr as `thinking › …`:
the answer on stdout stays clean, and the thinking is never replayed as
conversation history.

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
agentic-odi steps add --job-id <job-id> --name "Execute" --order 5 --stage execute
agentic-odi steps list --job-id <job-id>
agentic-odi steps get <step-id>
agentic-odi steps update <step-id> --order 2
agentic-odi steps delete <step-id> --yes

Capture a desired or customer outcome before adding a step. Use `--allow-empty-job-map`
only when you intentionally need to stage a map before capturing outcomes.

# Desired Outcomes
agentic-odi desired-outcomes add --job-id <job-id> --statement "Minimize the time it takes to get a working environment" --importance 8 --satisfaction 4
agentic-odi desired-outcomes list --job-id <job-id>
agentic-odi desired-outcomes get <outcome-id>
agentic-odi desired-outcomes update <outcome-id> --satisfaction 6
agentic-odi desired-outcomes delete <outcome-id> --yes
agentic-odi desired-outcomes export --job-id <job-id> --format csv > outcomes.csv
agentic-odi desired-outcomes export --job-id <job-id> --format json | jq '.[].opportunity_score'
agentic-odi desired-outcomes evaluate "Minimize the time to ship when onboarding"
agentic-odi desired-outcomes value <outcome-id> --estimate 250000 --unit currency --basis market --source "Gartner 2025 plugin market report"
agentic-odi desired-outcomes value <outcome-id>            # omit --estimate to clear the value

# One-screen report: job header, phase coverage, biggest opportunities
agentic-odi summary <job-id>
agentic-odi summary <job-id> --top 3 --json
```

`--importance` and `--satisfaction` (1–10) are now required on `add`. `evaluate`
checks a statement against the ODI format rules before saving.

Job names are validated by the core model: 3–64 characters drawn from letters,
digits, spaces, underscores, and hyphens. Descriptions may be up to 500
characters. The CLI prints the first validation message instead of a traceback,
and the Studio API returns a 422 with the same message.

`summary` shows how many of the eight job-map phases the Job covers, which are
still missing, and the underserved outcomes (score above 10) in descending
order. `--top` caps that list; `--json` returns the same data for a script.

Add `--json` to any command for machine-readable output. `export` writes to
stdout only — CSV has one row per outcome with the same fields the table shows
plus `job_id` and `step_id`, so it pipes straight into a spreadsheet or `jq`.

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

## The signal inbox

Writes emit signals — a job added, an outcome re-scored, evidence promoted, a
job map covering all eight stages. Reads never emit, and an empty inbox means the
workspace was genuinely quiet. Deletions are recorded data, not news, so they
emit nothing.

```bash
agentic-odi signals list                 # newest first
agentic-odi signals list --unread --limit 5
agentic-odi signals unread --json
agentic-odi signals read <signal-id>
agentic-odi signals dismiss <signal-id>
```

At most 20 signals per day are surfaced (`AGENTIC_ODI_SIGNAL_BUDGET`); `urgent`
ones — an opportunity score crossing 10 upward — bypass that cap. Suppressed
signals stay in the store and stay reachable by id.
See [The Signal Inbox](architecture/notifications.md).

## Schema, scoring, and guidance

```bash
agentic-odi schema            # canonical JSON schema for every ODI entity
agentic-odi health            # check that the ODI store is reachable
agentic-odi health --json     # {"status": "ok", "store": "accessible"}
agentic-odi score 8 2         # ODI opportunity score → 14.00
agentic-odi evaluate "Minimize the time to ship when onboarding"  # outcome-format check
agentic-odi evaluate --json "Minimize the time to ship when onboarding"
agentic-odi guidelines        # the ODI stage-by-stage guide
agentic-odi capabilities      # what the assistant can do
agentic-odi capabilities --json   # machine-readable manifest
agentic-odi capabilities tools  # tool names only
```

`evaluate` returns the same verdict the `evaluate_outcome` MCP tool does, so the
check works with or without a running server.

`health` runs the `get_health` check against the configured backend and exits
non-zero when the store is degraded, so it can gate a deployment.

`capabilities` groups every tool by effect (read/write/destructive) and by ODI
stage. `capabilities --json` emits the full machine-readable manifest.
`capabilities tools` lists tool names only.

## The factual case for a job

```bash
agentic-odi brief export --job-id JOB-1                # markdown to stdout
agentic-odi brief export --job-id JOB-1 --format html  # standalone HTML document
agentic-odi brief export --job-id JOB-1 --out case.md  # write a file, print its path
```

`brief export` renders the same deterministic case the Studio shows: the job,
the decision under consideration, the underserved outcomes with their score,
band, and sources, and the risks. Every numeral comes from a recorded
measurement; a field nobody supplied renders `not measured`, never `0`. The
`--format html` document inlines its own print styles, so it opens and prints
with no app CSS and no network access. `--generated-at` stamps a fixed
timestamp when you need byte-identical output.

## Record a decision

```bash
agentic-odi decide record --job-id JOB-1 \
  --choose OUT-1 --choose OUT-2 \
  --reject OUT-3="Already served by the support team." \
  --rationale "The publishing path blocks every release." \
  --decided-by dana
```

`decide record` persists what was chosen, what was rejected, and why. Each
rejection is a repeated `--reject OUTCOME_ID=REASON` flag, so an id or reason
that contains punctuation cannot be mistaken for the other. `--decided-at`
defaults to now in UTC; `--confidence` is `low`, `medium`, or `high`. Pass
`--supersedes DEC-ID` to replace an earlier decision: the predecessor stays
readable and records the successor that superseded it. The same validation
runs behind `POST /api/decisions`, so the CLI and the Studio cannot disagree
about what a valid decision is.

## Render the outcome roadmap

```bash
agentic-odi roadmap show --job-id JOB-1                # markdown to stdout
agentic-odi roadmap show --job-id JOB-1 --horizon 4    # four quarters back
agentic-odi roadmap show --job-id JOB-1 --today 2026-11-15
agentic-odi roadmap show --job-id JOB-1 --json
```

`roadmap show` derives the roadmap from the job's recorded decisions: one entry
per chosen outcome, grouped by the quarter of its decision date in UTC. It is a
view, not a store — nothing is written. An outcome with no decision is excluded
and counted, and the footer says how many were left out and why; a superseded
decision contributes no rows. `--today` pins the window so the output is
reproducible; `--horizon` sets how many quarters it spans. A baseline or target
nobody measured prints `not measured`, never `0`.

## Review a past decision

```bash
agentic-odi review show --decision-id DEC-1
agentic-odi review show --decision-id DEC-1 --today 2027-01-30
agentic-odi review show --decision-id DEC-1 --json
```

`review show` compares each outcome a decision chose against the latest score
snapshot and prints one line per outcome: `improved`, `degraded`, `no change`,
`no evidence`, or `orphaned`. It writes nothing. A missing measurement stays
`no evidence`, never `no change`; an outcome that no longer exists is `orphaned`,
never a crash. `--today` pins the comparison date so the day count and the
verdicts are reproducible. The same projection backs `POST /api/decisions/review`
and the Studio's decision-review card.

## Track a bet

```bash
agentic-odi bets add --decision-id DEC-1 --outcome-id OUT-1 \
  --hypothesis "Auto-matching halves the weekly reconciliation time" \
  --target 17 --measure-by 2026-04-01
agentic-odi bets list --job-id JOB-1
agentic-odi bets show --bet-id BET-1
agentic-odi bets advance --bet-id BET-1 --status running
agentic-odi bets advance --bet-id BET-1 --status measured --at 2026-04-02T00:00:00Z
```

`bets add` records an expectation and captures its baseline at creation — the
outcome's current opportunity score, or the explicit `--baseline` — and stores
it. The baseline is never recomputed from the live score, so the starting point
cannot drift. The outcome must be one the decision chose. `bets advance` moves a
bet through `planned → running → measured` (or `abandoned`); an illegal
transition is refused by name. `--at` pins the transition timestamp.

## Segments and strategy

```bash
agentic-odi segments add --job-id JOB-1 --name "Release engineers" \
  --criterion "They own the publish step." \
  --outcome-id OUT-1 --outcome-id OUT-2
agentic-odi segments list --job-id JOB-1
agentic-odi segments show --segment-id SEG-1
agentic-odi segments delete --segment-id SEG-1

agentic-odi segments suggest --job-id JOB-1
agentic-odi segments accept --job-id JOB-1 --fingerprint <fingerprint>

agentic-odi segments profile --segment-id SEG-1

agentic-odi segments strategy --segment-id SEG-1 --kind differentiated \
  --rationale "The publish path blocks every release." \
  --expected-effect "Shorter publish time."
agentic-odi segments strategies --segment-id SEG-1
```

A segment is a named group defined by the outcomes it cares about — never by
demographics. Every member must belong to the job; a cross-job or missing member
is refused before any write, and duplicate ids collapse to one. Deleting a
segment never touches its outcomes.

`segments suggest` derives candidates deterministically from the scores: groups
that share an opportunity band and an importance decile, at least three members
each. It **writes nothing**. `segments accept` is the only write, and it targets
exactly the candidate you saw by its fingerprint; a fingerprint whose membership
has changed is refused as stale rather than accepting a different group, and
repeating an acceptance returns the same segment instead of a second one.

`segments profile` reads a segment's servability with the underserved and
overserved halves kept separate. An empty segment reports zeroed counts; a
segment with no scored outcome reports the ratio as `not measured`, never `0`,
and says why.

`segments strategy` records one of `differentiated`, `disruptive`, or
`new_market` with its rationale and expected effect. Each kind is refused unless
the segment's data supports it — a differentiated strategy needs an underserved
outcome, a disruptive one needs an overserved outcome — and the message names
the missing condition. `new_market` is refused while alternatives evidence
(`M2-07`) is absent, because an unchecked absence is not proof that no solution
exists. A recorded strategy renders into the brief's decision section.

## Back up and export

```bash
agentic-odi data-export                        # ./odi-export-<timestamp>.json
agentic-odi data-export --output backup.json   # explicit path
agentic-odi data-export --job-id JOB-1         # one job and its children
```

`data-export` writes jobs, steps, desired outcomes, customer outcomes, and
evidence to one JSON file (`format: agentic-odi-export`, `version: 1`). Every
record is the same `model_dump()` shape the MCP tools return, so each entry can
be re-validated with the corresponding core Pydantic model. The default
filename carries a UTC ISO 8601 timestamp (`YYYYMMDDTHHMMSSZ`).

## Inspect settings and feature flags

```bash
agentic-odi settings flags list
agentic-odi settings flags get experimental_connectors
agentic-odi settings flags set experimental_connectors true
agentic-odi settings flags reset
```

`experimental_connectors` gates the `connectors` group (`add`, `health`,
`ingest`). `auto_update` gates startup auto-update checks. `advanced_metrics`
gates detailed metrics output in `desired-outcomes evaluate`. `developer_mode`
gates raw MCP trace debugging.

## Manage your profile and run setup

```bash
agentic-odi profile show
agentic-odi profile show --json
agentic-odi profile set --product-name "My Product" --domain "acme.test"
agentic-odi profile path
agentic-odi setup       # interactive baseline wizard
```

`profile show` prints the baseline fields; add `--json` to emit the raw JSON.
`profile set` updates any subset of baseline fields with explicit options.
`profile path` prints the baseline file path. `setup` runs the interactive
baseline wizard.

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

## Schedule Work

Schedule, inspect, cancel, and trigger background cloud agent work tasks:

```bash
# Schedule a task
agentic-odi schedule create --name "Nightly ODI Audit" --expression "0 0 * * *" --trigger-type cron

# List, inspect, trigger, and cancel
agentic-odi schedule list
agentic-odi schedule list --json
agentic-odi schedule show <work-id>
agentic-odi schedule trigger <work-id>
agentic-odi schedule cancel <work-id>
```

## Connectors

The `connectors` group manages external MCP integrations. See
[External Connectors](connectors.md) for presets, the connector registry, and
ingest behavior.

```bash
python -m agentic_odi_cli connectors catalog
python -m agentic_odi_cli connectors add mcp --preset github
python -m agentic_odi_cli connectors list
python -m agentic_odi_cli connectors list --json   # name, kind, url, enabled per connector
python -m agentic_odi_cli connectors health --name github
python -m agentic_odi_cli connectors ingest --name github
python -m agentic_odi_cli connectors ingest --name github --dry-run   # preview only
```

## Updates

`odi update` checks for and installs a new binary release. Auto-update is on by
default; disable it with `--no-update` for one run or
`AGENTIC_ODI_NO_UPDATE=1` globally. See [Installation](installation.md).
