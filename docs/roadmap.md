# Roadmap & Next Steps

As we validate the feasibility of this architecture, our next milestones include:

- [x] **External MCP client connector**: Pluggable connectors package with an
  HTTP MCP ingest client, CLI adapter, and in-memory tests.
- [x] **Map ingested evidence onto ODI artifacts**: Turn connector records into
  jobs, outcomes, or evidence without mixing connector plumbing into the ODI
  store.
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
