# Roadmap & Next Steps

As we validate the feasibility of this architecture, our next milestones include:

- [x] **External MCP client connector**: Pluggable connectors package with an
  HTTP MCP ingest client, CLI adapter, and in-memory tests.
- [ ] **Map ingested evidence onto ODI artifacts**: Turn connector records into
  jobs, outcomes, or evidence without mixing connector plumbing into the ODI
  store.
- [ ] **Additional connector kinds**: REST/webhooks and similar integrations
  implementing the same `Connector` protocol.
- [ ] **ODI Schema Definition**: Define standardized Pydantic models for *Jobs*,
  *Steps*, and *Outcomes*.
- [x] **CLI Dataset Commands**: Extend `cli/` so the ODI dataset can be created,
  queried, and scored from the terminal, in addition to the current MCP path.
- [ ] **Context Tooling**: Replace the dummy `greet` tool with capabilities like
  `get_job_map(job_id)` or `evaluate_outcome(statement)`.
- [ ] **Data Persistence Layer**: Connect the fastmcp server to a lightweight
  vector or relational database containing actual user research data.
- [ ] **Agentic Integration**: Hook the client up to an LLM (e.g., via LangChain
  or standard OpenAI clients) so the LLM can *discover* the ODI tools and
  intelligently request customer insights when ideating features.
