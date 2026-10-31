# Roadmap & Next Steps

As we validate the feasibility of this architecture, our next milestones include:

- [x] **External MCP client connector**: Pluggable connectors package with an
  HTTP MCP ingest client, CLI adapter, and in-memory tests.
- [x] **Conversational rich surfaces**: the studio agent composes validated
  cards inline from a closed, client-owned catalog instead of describing them
  in prose.
- [x] **Map ingested evidence onto ODI artifacts**: Turn connector records into
  jobs, outcomes, or evidence without mixing connector plumbing into the ODI
  store.
- [x] **Conversation runtime**: Streaming, reasoning, tool calls, write
  approvals, sources, attachments, branches, and suggestions now run on
  assistant-ui, with the Studio's own store and the sidecar's SSE contract
  unchanged. Voice is deferred behind a documented seam.
- [x] **First minute**: The studio opens on a guided conversation, not a modal —
  one invitation, three starters, and a single dismissible hint that teaches the
  next thing in place.
- [x] **Product tour**: An optional, skippable, resumable four-step tour with
  inline connection repair, ending in the chosen surface or a handoff to the
  context conversation — isolated in `apps/studio/src/onboarding/` behind the
  `firstRunWizard` flag, and only opened on request.
- [x] **Additional connector kinds**: REST/webhooks and similar integrations
  implementing the same `Connector` protocol.
- [x] **ODI Schema Definition**: Define standardized Pydantic models for *Jobs*,
  *Steps*, and *Outcomes*.
- [x] **CLI Dataset Commands**: Extend `apps/cli` so the ODI dataset can be
  created, queried, and scored from the terminal, in addition to the current
  MCP path.
- [x] **Context Tooling**: Replace the dummy `greet` tool with capabilities like
  `get_job_map(job_id)`, `get_outcomes(job_id)`, `get_step(step_id)`,
  `get_outcome(outcome_id)`, or `evaluate_outcome(statement)`.
- [x] **Data Persistence Layer**: Connect the FastMCP server to a lightweight
  SQLite repository containing actual user research data.
- [x] **Agentic Integration**: Hook the CLI chat up to an LLM (via the
  `openai` package) so the LLM can *discover* the ODI tools and intelligently
  request customer insights when ideating features.
- [x] **Store version and migration guard**: The SQLite event log carries a
  `schema_meta` version, migrates in one transaction, and refuses a database
  newer than the build with both versions named — `agentic-odi store` reports it.
- [x] **The ODI spine, end to end**: quote → candidate → outcome → score → brief
  → decision → bet → measure now runs on the real store, with a person's
  acceptance the only path from a proposal to an outcome and an unmeasured bet
  reporting `None` rather than a fabricated zero.
- [x] **A labelled demo workspace**: `agentic-odi demo load` fills a store with
  a typed, `origin="demo"` corpus so a newcomer sees a filled canvas without
  doing the research first; a second load is a no-op.
- [x] **Pin the contract, fail on drift**: the MCP tool contract is snapshotted
  against the live registry, so a rename, a requiredness change, or a missing
  tool fails CI instead of drifting silently.
