# 0002 — Treat the package diagram as a dependency contract

- **Status:** accepted
- **Date:** 2026-10-31

## Context

The workspace's layering rule has always been written down: `packages/core` at the
bottom, three apps above it, `packages/connectors` reachable from the CLI and the
sidecar, and no app importing another app. It was stated in
`docs/architecture/README.md` and in `.agents/rules/agent_instructions.md`, and
enforced by nothing.

While building the first rendered architecture diagram we found the cost of that.
`apps/studio-api` imported `agentic_odi_connectors` at module level in five files
— `studio/router.py`, `studio/connectors.py`, `studio/marketplace.py`,
`studio/schemas.py` — without declaring it in `[project] dependencies`. Every
test passed. The import resolved only because `uv sync --all-packages` installs
all five members into one virtualenv, so the edge was invisible to the dependency
resolver, to the docs, and to the suite at the same time. In the same document,
the sentence describing `packages/connectors` said it depends on core "where it
needs shared models"; connectors imports nothing from core.

Separately, every diagram in the repository was a hand-drawn block of ASCII. A
picture that cannot be rendered on GitHub or on the site is a picture nobody
looks at, and a picture nobody looks at is not updated.

## Decision

The mermaid diagram under **Dependency Direction** in `docs/architecture/README.md`
is the normative statement of workspace dependencies, and
`tests/test_architecture.py` makes it true. It asserts three sets are equal:

1. the arrows drawn in the diagram,
2. the `agentic-odi-*` entries in each member's `[project] dependencies`,
3. the cross-package imports found in the source, using `grimp`.

It asserts it in both directions, so an import without a declaration fails and a
declaration nothing imports also fails. Two further rules the documents already
claimed are now checked the same way: core imports no workspace package, and no
app imports another app.

Diagrams are markdown fences, not separate files, and are not rendered to images.
GitHub draws a ` ```mermaid ` fence in a `.md` file; the site build passes the
source through escaped and lets a lazily-loaded vendored runtime draw it. Adding a
workspace dependency means three edits in one task: the declaration, its
`[tool.uv.sources]` entry, and the arrow.

## Consequences

**Easier**

- A new edge cannot exist in code alone; the failure names the edge and the file.
- Reviewers see the picture and the diff of the picture together, on GitHub, with
  no tooling between them.
- The two layering claims the docs made without evidence are now evidence-backed.

**Harder**

- Splitting a package or renaming a distribution now edits a diagram too. That is
  the intent, but it is one more file in the change.
- `grimp` is a dev dependency (pinned, `>=3.10` floor matching the CI matrix), and
  the test requires the workspace to be synced editable — it asserts that, rather
  than silently analysing an installed copy.
- The check covers Python edges between workspace members. Third-party
  dependencies, TypeScript imports, and the Worker are outside it, and call-level
  coupling inside `packages/core` is unmeasured.

**Now we maintain**

- `tests/test_architecture.py` and the diagram stay in step with each other.
- `docs/architecture/testing.md` lists the test so a failure is findable.

## Alternatives considered

**`import-linter`.** The standard tool, and good. Rejected because its contracts
restate the same facts in a third language that a reader of the diagram still has
to cross-check, and its `layers` model fights a `packages/core` that holds domain,
persistence, methodology stages, and the MCP contract in one namespace. It earns
its keep on a codebase with more packages than five.

**Rendering diagrams to PNG/SVG and committing images.** Rejected: a merge
conflict in a binary is not reviewable, and the toolchain (mermaid-cli pulls in a
headless browser) is the heaviest part of the idea for the least value.

**A generated diagram.** Draw the picture from the declarations at build time and
drift is impossible. Rejected for now because it removes the human: a generated
graph cannot say which edges are *intended*, and half of what a diagram is for here
is saying "this arrow is a decision". Revisit if the workspace grows past a dozen
packages.

**Keeping `.mmd` files as the source and including them in markdown.** Rejected:
neither GitHub nor a plain markdown include can render a separate `.mmd`, so the
diagram would need a second copy in the doc — the exact duplication this ADR
exists to prevent.
