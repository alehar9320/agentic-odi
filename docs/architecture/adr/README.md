# Architecture Decision Records

Short, dated records of the decisions that shape Agentic ODI: what we chose,
what we gave up, and what would make us revisit it.

An ADR is written once and is not edited afterwards. If a decision changes,
write a new ADR that supersedes the old one and link them. The point is to
record the reasoning at the time, not to keep a single current story.

## Format

Every ADR uses the same sections:

- **Status** — `proposed`, `accepted`, `superseded by ADR-NNNN`, or `deprecated`.
- **Date** — when the decision was made.
- **Context** — the forces in play: constraints, prior art, what hurt.
- **Decision** — what we do, in the present tense.
- **Consequences** — what becomes easier, what becomes harder, and what we now
  have to maintain.
- **Alternatives considered** — the options that lost and why.

Keep an ADR to one page. If it needs more, the decision is probably two
decisions.

## Index

| ADR | Title | Status |
|---|---|---|
| [0001](0001-mcp-http-transport.md) | Drive MCP over HTTP instead of stdio | accepted |
| [0002](0002-package-diagram-as-contract.md) | Treat the package diagram as a dependency contract | accepted |
| [0003](0003-consent-on-the-domain-path.md) | Put consent on the domain path, not the Studio's chat loop | proposed |
| [0004](0004-two-stores-one-reference.md) | Two stores stay two stores; the reference between them becomes honest | proposed |
