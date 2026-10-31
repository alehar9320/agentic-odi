# Roadmap

A roadmap that says everything is done is not a roadmap. This page tracks three
things: what has shipped (and where to verify it), what is open in review, and
what is queued next. An entry is only "Shipped" when the pull request that built
it is merged; the link is the proof.

## Shipped

- [x] **One tool contract, exposed** — `ToolName` / `TOOL_SPECS` in `packages/core` are the single source of truth, and `get_capabilities` describes the surface from it ([PR #263](https://github.com/alehar9320/agentic-odi/pull/263)).
- [x] **Generated capability manifest** — the CLI, MCP server, and Studio read the same capability manifest, and the CLI's local handlers are checked for parity ([PR #272](https://github.com/alehar9320/agentic-odi/pull/272)).
- [x] **ODI write contract on every path** — every write path validates Job, Step, and Outcome rules instead of trusting the caller ([PR #270](https://github.com/alehar9320/agentic-odi/pull/270)).
- [x] **A signal inbox that means something** — writes emit deduped, budgeted signals stored in the event log; the CLI, MCP clients, and the Studio bell read the same records ([PR #277](https://github.com/alehar9320/agentic-odi/pull/277)).
- [x] **assistant-ui conversation runtime** — streaming, reasoning, tool calls, write approvals, sources, attachments, branches, and suggestions over the sidecar's existing SSE contract ([PR #266](https://github.com/alehar9320/agentic-odi/pull/266)).
- [x] **Open on a guided conversation** — the first minute is one invitation, three starters, and one dismissible hint instead of a modal ([PR #268](https://github.com/alehar9320/agentic-odi/pull/268)).
- [x] **Customize: one place for connectors** — installed connectors, curated picks, and the vendor marketplace, with tokens named but never stored ([PR #262](https://github.com/alehar9320/agentic-odi/pull/262)).
- [x] **One banner system for every notice** — every failure, warning, and success uses the same notice shapes ([PR #264](https://github.com/alehar9320/agentic-odi/pull/264)).
- [x] **Scheduled work, honestly recorded** — schedule, list, trigger, and cancel background work, with a stored record instead of a pretend scheduler ([PR #265](https://github.com/alehar9320/agentic-odi/pull/265)).
- [x] **Evidence keeps a link back** — evidence records name their source, and a captured record can be promoted into a Job or an Outcome ([PR #261](https://github.com/alehar9320/agentic-odi/pull/261)).
- [x] **A verifiable release** — version parity, a signed updater manifest, and the updater exercised in CI ([PR #275](https://github.com/alehar9320/agentic-odi/pull/275)).
- [x] **Demo, seed, and simulated surfaces are labelled** — no surface presents fixture data as a customer's own ([PR #274](https://github.com/alehar9320/agentic-odi/pull/274)).
- [x] **Pull request guardrails** — diff-shape, body-truth, and fabrication gates on the cumulative diff ([PR #273](https://github.com/alehar9320/agentic-odi/pull/273)).
- [x] **Browser-level Studio suite** — the conversation, an outcome capture, the landscape, the workspace views, and the passthrough backend, driven against the real stack ([PR #267](https://github.com/alehar9320/agentic-odi/pull/267)).
- [x] **Offline-first CLI and hosted Studio** — the terminal REPL with `/connect`, and the Living Studio served from a Cloudflare Worker ([v0.7.0](https://github.com/alehar9320/agentic-odi/releases/tag/v0.7.0)).
- [x] **EvidenceDraft validation at ingest** — connector records conform before they enter the store ([PR #287](https://github.com/alehar9320/agentic-odi/pull/287)).
- [x] **Tool spec validation on MCP startup** — the server refuses to serve a malformed registry ([PR #288](https://github.com/alehar9320/agentic-odi/pull/288)).
- [x] **Keyboard navigation for the feed and job map** — phase cards, step rows, and both dialogs are operable without a mouse ([PR #297](https://github.com/alehar9320/agentic-odi/pull/297)).
- [x] **`odi data export`** — back the ODI state up as JSON ([PR #293](https://github.com/alehar9320/agentic-odi/pull/293)).
- [x] **Conversational first-run introduction** — the agent speaks first in five short turns and returns an editable brief, replacing the setup form ([PR #362](https://github.com/alehar9320/agentic-odi/pull/362)).
- [x] **`odi connectors list-presets`** — discover and copy a preset from the terminal ([PR #290](https://github.com/alehar9320/agentic-odi/pull/290)).

## In flight

Open pull requests that change a capability this milestone cares about. Each
links to the pull request; a red or draft entry is stated as such rather than
counted as done.

- [ ] **A cold open under a second** — a deterministic 1,500-outcome study corpus, per-segment measurement, an incremental event replay instead of a full rescan, and a deferred landscape render; before/after recorded in `docs/development.md` (this change).
- [ ] **Rate-limit the ingest sink** — a token bucket sheds a high-volume batch instead of exhausting memory ([PR #298](https://github.com/alehar9320/agentic-odi/pull/298)).
- [ ] **Job validation at the model level** — name and description constraints live in `packages/core` ([PR #296](https://github.com/alehar9320/agentic-odi/pull/296)).
- [ ] **MCP connection limits** — timeout and pool settings so a hanging connection is bounded ([PR #294](https://github.com/alehar9320/agentic-odi/pull/294)).
- [ ] **Shared HTTP client for connectors** — configurable connection pools for ingest ([PR #292](https://github.com/alehar9320/agentic-odi/pull/292)).
- [ ] **Merge candidate evidence into one outcome** — the review step for duplicate candidates ([PR #291](https://github.com/alehar9320/agentic-odi/pull/291)).
- [ ] **`odi connectors health`** — every registered connector's health in one table ([PR #289](https://github.com/alehar9320/agentic-odi/pull/289)).
- [ ] **MCP `/health` store probe** — the server reports whether its SQLite store is reachable ([PR #286](https://github.com/alehar9320/agentic-odi/pull/286)).
- [ ] **Durable sessions and a real memory** — the conversation survives a reload ([PR #285](https://github.com/alehar9320/agentic-odi/pull/285)).
- [ ] **Accept or reject a candidate without losing evidence** — the review half of candidate extraction ([PR #284](https://github.com/alehar9320/agentic-odi/pull/284)).
- [ ] **Outcome-based segments and the strategy they imply** — the scored outcomes group into segments, and the recorded path names the ones it beat ([PR #367](https://github.com/alehar9320/agentic-odi/pull/367)).
- [ ] **A vendor tree that cannot rot into app code** — copied markup lives in `src/vendor`, with lint and a resolving test on its imports ([PR #417](https://github.com/alehar9320/agentic-odi/pull/417)).
- [ ] **Tailwind scoped to the copied components** — v4 styles `src/vendor` alone, the product keeps its own stylesheet ([PR #422](https://github.com/alehar9320/agentic-odi/pull/422)).

## Next

The open issues this milestone still has to answer, grouped by what they change.

### Evidence becomes outcomes

- [ ] **Evidence must become outcomes** — the mapping that turns a quote into a scored opportunity ([#80](https://github.com/alehar9320/agentic-odi/issues/80)).
- [ ] **Outcome-based segments and the strategy they imply** — the missing half of ODI ([#85](https://github.com/alehar9320/agentic-odi/issues/85)).

### Agents that actually run

- [ ] **Background agents must actually run** — real triggers, real failures, and a morning briefing ([#95](https://github.com/alehar9320/agentic-odi/issues/95)).
- [ ] **The local model must be real** — an honest routing tier with a true availability probe ([#94](https://github.com/alehar9320/agentic-odi/issues/94)).

### Consent, access, and release integrity

- [ ] **The agent must ask before it acts** — consent, escalation, and an audit trail ([#82](https://github.com/alehar9320/agentic-odi/issues/82)).
- [ ] **The Studio has no front door** — auth, CSP, and secret handling ([#90](https://github.com/alehar9320/agentic-odi/issues/90)).
- [ ] **A release must be verifiable** — version sync, a signed updater manifest, and the updater in CI ([#89](https://github.com/alehar9320/agentic-odi/issues/89)).
- [ ] **Hold the line** — a coverage floor that fails the build ([#88](https://github.com/alehar9320/agentic-odi/issues/88)).

### Reach and accessibility

- [ ] **The Studio must fit in a pocket** — a real mobile shell with offline capture ([#93](https://github.com/alehar9320/agentic-odi/issues/93)).
- [ ] **Usable without a mouse** — accessibility on the surfaces that actually ship ([#92](https://github.com/alehar9320/agentic-odi/issues/92)).

### The docs stay true

- [ ] **The docs must be the truth** — README, architecture, and a roadmap that tracks reality (this change).
