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
- [x] **First-run wizard**: A skippable, resumable four-step tour with inline
  connection repair, ending in the chosen surface or a handoff to the context
  conversation — isolated in `apps/studio/src/onboarding/` behind the
  `firstRunWizard` flag.
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
- [x] **Decide, then close the loop**: Record a decision with its rejected
  options, derive and render the outcome roadmap, review a past decision against
  today's numbers, and track a bet from its captured baseline to measured — the
  same projection behind the MCP tools, `odi decide`/`odi roadmap`/`odi review`/
  `odi bets`, the Studio API, and the Studio cards. A missing measurement stays
  `not measured` / `no evidence`, never `0` and never `no change`.
