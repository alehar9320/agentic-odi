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
- [x] **`odi connectors list-presets`** — discover and copy a preset from the terminal ([PR #290](https://github.com/alehar9320/agentic-odi/pull/290)).

## In flight

Open pull requests that change a capability this milestone cares about. Each
links to the pull request; a red or draft entry is stated as such rather than
counted as done.

- [ ] **Resume the last job, step, or outcome after a reload** — the Studio keeps its place in browser storage ([PR #299](https://github.com/alehar9320/agentic-odi/pull/299)).
- [ ] **Rate-limit the ingest sink** — a token bucket sheds a high-volume batch instead of exhausting memory ([PR #298](https://github.com/alehar9320/agentic-odi/pull/298)).
- [ ] **Job validation at the model level** — name and description constraints live in `packages/core` ([PR #296](https://github.com/alehar9320/agentic-odi/pull/296)).
- [ ] **MCP connection limits** — timeout and pool settings so a hanging connection is bounded ([PR #294](https://github.com/alehar9320/agentic-odi/pull/294)).
- [ ] **Shared HTTP client for connectors** — configurable connection pools for ingest ([PR #292](https://github.com/alehar9320/agentic-odi/pull/292)).
- [ ] **Merge candidate evidence into one outcome** — the review step for duplicate candidates ([PR #291](https://github.com/alehar9320/agentic-odi/pull/291)).
- [ ] **`odi connectors health`** — every registered connector's health in one table ([PR #289](https://github.com/alehar9320/agentic-odi/pull/289)).
- [ ] **MCP `/health` store probe** — the server reports whether its SQLite store is reachable ([PR #286](https://github.com/alehar9320/agentic-odi/pull/286)).
- [ ] **Durable sessions and a real memory** — the conversation survives a reload ([PR #285](https://github.com/alehar9320/agentic-odi/pull/285)).
- [ ] **Accept or reject a candidate without losing evidence** — the review half of candidate extraction ([PR #284](https://github.com/alehar9320/agentic-odi/pull/284)).

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
- [x] **Outcome sample and method** — every desired-outcome score carries `importance_n`, `satisfaction_n` and `score_method` (`estimate`, `survey`, `import`) through the model, service, SQLite replay, MCP tools, CLI and Studio API; an unknown count renders as `est.`, and an `estimate` that claims a sample above one is refused before the write ([PR #281](https://github.com/alehar9320/agentic-odi/pull/281)).

- [x] **Score history** — every accepted score change is written as an append-only `ScoreSnapshot` alongside the score's sample and method, with an optional `note`. `desired-outcomes history`, `get_outcome_history` and `GET /api/outcomes/{id}/history` replay the trail; a rejected mutation writes no snapshot, so history never shows a change that did not happen. `desired-outcomes get` shows the latest accepted reason as a `note` line, so the detail view carries the same "why" as the history without inventing one ([PR #281](https://github.com/alehar9320/agentic-odi/pull/281)).

- [x] **Survey import**: `odi survey import <csv>` parses a response file,
  aggregates one mean per outcome and lands the mean, its sample (`n`) and a
  bootstrap band computed from the real paired responses. The import is
  all-or-nothing: an unresolved reference or a malformed row fails before any
  outcome is written.
- [x] **No row disappears without a report line**: `survey import` builds a
  side-effect-free plan before it writes. `--dry-run` prints the match table and
  writes nothing; every row is named by its 1-based CSV line (the record's
  starting line when a quoted field spans several), so unmatched, ambiguous,
  invalid and missing-field rows are listed rather than dropped. `--match`
  proposes one normalized-exact candidate per unmatched reference and asks a
  person to confirm each; a suggestion is never applied silently, a stale or
  ambiguous confirmation cannot assign a row, and a run with any unresolved row
  is refused whole, so a partial score write is impossible.
- [x] **Reproducible bands**: A survey outcome stores `opportunity_low`/
  `opportunity_high` with their provenance (`interval_n`, seed, confidence level,
  computed-at). A score or method edit without a fresh band clears the stale one
  in the same write, so a new number never carries an old range; an estimate
  keeps the no-band placeholder rather than a fabricated width. The stored band
  is readable through `get_outcome_interval`, `desired-outcomes get` and
  `GET /api/outcomes/{id}/interval`; a no-band score reads as `no band` rather
  than a zero-width range, and a band whose score a later snapshot moved is
  marked `stale`.
- [x] **Honest ranking**: `classify_confidence` labels each outcome
  `measured`/`thin`/`none` from its weakest dimension, and
  `rank_outcomes_for_job` ranks within a section by the band's low end, so an
  estimate can no longer outrank a measured score. `odi top` lists the measured
  section (naming the thin and unscored it excluded) and `odi coverage` reports
  the split; the landscape renders the same band and groups by confidence class.
- [x] **Signed deltas**: `outcome_delta` reads the recorded snapshots and reports
  the per-dimension and opportunity differences with an explicit `direction`,
  never inferring an "improvement" from a bare number. `desired-outcomes history
  --why` and `GET /api/outcomes/{id}/delta` expose it; a missing dimension stays
  `null`, not `0`.
- [x] **Thin-sample advisory (M2-14)**: one `MIN_MEANINGFUL_N = 20` constant and
  one `n_advisory(outcome) -> Advisory | None` in `evaluation.py` warn when a
  recorded sample is below the threshold. The advisory takes the smaller of the
  two counts and names the dimension that triggered it, returns a single sentence
  plus `{n, threshold, method, dimension}`, and is worded as "below the advisory
  threshold" — a product warning, not a claim of statistical validity on either
  side. It is a statement about the data, never a filter: the score still renders
  and still ranks. `odi top` prints it as a footer line, `desired-outcomes get`
  prints it as an `advisory` line, and the landscape shows an `n<20` chip with the
  sentence on hover; an estimate or an unknown count produces no advisory rather
  than a fabricated `n=0`.
- [x] **Trust seams for the gated increments**: The remaining Pillar-2
  increments wait on decisions that are not yet approved, so `agentic_odi_core.trust`
  exposes their shapes and refuses to answer: `retain_survey_inputs` (retention
  policy) and `persisted_interval` when no band is stored (interval provenance).
  Each raises `TrustContractPendingError` naming the blocking decision instead of
  returning a fabricated band, class or direction. The retention read side,
  `retained_survey_inputs`, refuses when nothing was retained for an outcome
  rather than returning an empty list that would read as "zero responses".
- [x] **Pillar integration contract**: one fixture is imported with per-outcome
  counts, persisted and replayed through SQLite, ranked without mixing absent
  scores into zeroes, explained with recorded arithmetic/method, and shown with
  its band and confidence class — while an invalid import leaves the prior state
  unchanged and a score edit clears the stale band. Pinned end to end by
  `test_trust_pillar.py`.
