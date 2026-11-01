# Agentic ODI - AI Developer Guardrails

This file provides system instructions and guardrails for any AI agents (or LLMs) assisting with the development of the **Agentic ODI** project. Please adhere to these guidelines to maintain consistency and align with the project's vision.

> **Source of Truth for ODI Methodology**: `docs/reference/Strategyn_what_is_Outcome_Driven_Innovation.pdf` by Anthony W. Ulwick (Strategyn). All ODI concepts in this project are grounded in that document. When in doubt, refer agents back to its definitions.

---

## 🎯 ODI Methodology Guardrails

This section defines how agents MUST understand and apply Outcome-Driven Innovation within this project. These are not implementation guidelines — they are domain constraints that ensure the system reflects the ODI methodology correctly.

### What is Outcome-Driven Innovation (ODI)?

ODI is a strategy and innovation process rooted in the **Jobs-to-be-Done (JTBD)** theory. Its core premise is: **people buy products and services to get a "job" done**. A "job" is the functional process a person is trying to execute — it remains stable over time, while products and technologies are point-in-time solutions that eventually become obsolete.

ODI achieves an **86% innovation success rate** by replacing guesswork with a rigorous, data-driven framework grounded in measurable customer needs.

---

### Stage 1: Define the Market and the Job-to-be-Done

- A **market** is defined as: **a group of people + the functional job they are trying to get done** (e.g., "parents trying to pass on life lessons to children").
- A **Job-to-be-Done** is the core functional unit of analysis. It is NOT a product, solution, or feature — it is a stable human goal.
- **Agent rule**: Before anything else, the agent MUST help the user define the Job-to-be-Done. If no Job exists, use `add_job` to capture it. If one exists already, use `get_jobs()` to check first.
- ❌ **Never skip this stage**. No outcomes, steps, or scoring can be meaningful without a well-defined Job.

---

### Stage 2: Uncover Desired Outcomes

- **Desired outcomes** are the metrics customers use to measure success when getting a job done. They are the "needs" in ODI.
- Qualitative interviews typically uncover **50–150 desired outcome statements**.
- **Correct outcome statement format** (must be enforced when capturing user input):

  > `[Direction] + [Unit of Measure] + [Object of Control] + [Contextual Clarifier]`

  - ✅ **Good**: *"Minimize the time it takes to determine if the corn seeds are germinating."*
  - ✅ **Good**: *"Minimize the likelihood of damaging the surface when cutting."*
  - ❌ **Bad**: *"Make it faster"* — too vague, no direction, no measurable unit.
  - ❌ **Bad**: *"I want a notification"* — this is a solution/feature, not an outcome.

- **Agent rule**: Guide the user to express outcomes using this exact format. Reject or reframe vague statements before calling `add_outcome`. Always capture `importance` and `satisfaction` scores (1–10 scale) to enable opportunity scoring.

---

### Stage 3: Inventory the Job (Universal Job Map)

- All functional jobs decompose into **8 universal process steps** (the Universal Job Map):
  1. **Define** — Plan what needs to be done; select goals or resources
  2. **Locate** — Gather the inputs, information, or resources needed
  3. **Prepare** — Set up and organize everything required
  4. **Confirm** — Validate readiness; decide whether to proceed
  5. **Execute** — Perform the core task
  6. **Monitor** — Verify and track performance while executing
  7. **Modify** — Adjust or update based on feedback
  8. **Conclude** — Store, finish, or dispose of outputs

- **Agent rule**: When a user is decomposing a job into steps, reference these 8 universal stages as a guide. Steps captured via `add_step` should map to or be inspired by these universal phases. Use `get_job_map` to visualize the ordered structure.
- ❌ **Do not build the Job Map before capturing outcome statements** — outcomes define *what success looks like*; the job map defines *where in the process* that success matters.

---

### Stage 4: Discover Where the Market is Underserved (Opportunity Scoring)

- Each desired outcome is rated by customers on two dimensions:
  - **Importance** (1–10): How important is this outcome to the customer?
  - **Satisfaction** (1–10): How satisfied are customers with current solutions?

- **Opportunity Algorithm** (must be implemented correctly):

  ```
  Opportunity Score = Importance + Max(Importance - Satisfaction, 0)
  ```

- **Interpretation**:
  - **Score > 10**: Underserved need — significant innovation opportunity.
  - **Score 10**: Appropriately served — maintain, don't over-invest.
  - **Score < 10**: Overserved — potential for disruption via lower-cost alternatives.

- **Agent rule**: Always compute and surface the opportunity score when both `importance` and `satisfaction` are provided. Highlight outcomes scoring **> 10** as the highest priority innovation targets. Use `get_outcomes(job_id)` to review the full opportunity landscape.

---

### Stage 5: Outcome-Based Market Segmentation

- ODI does **not** use demographic segmentation (age, gender, region). Instead it segments the market by **which outcomes are underserved** for each group.
- Segments can be:
  - **Underserved** — high opportunity scores, want more from existing products
  - **Overserved** — over-investing in outcomes that aren't critical; target for disruption
  - **Appropriately served** — satisfied; maintain current value

- **Agent rule**: When the user has collected outcomes with scores, help them identify outcome clusters that represent distinct market segments. This drives targeted innovation strategy.

---

### Stage 6: Formulate an Innovation Strategy

Based on the opportunity analysis, there are three strategic paths:

| Strategy | When to use |
|---|---|
| **Differentiated** | Improve existing products to address high-opportunity underserved outcomes |
| **Disruptive** | Create low-cost solutions for overserved segments that don't need all existing features |
| **New-Market** | Design products for a new job that is entirely unaddressed |

- **Agent rule**: When the opportunity landscape is clear (outcomes scored, segments identified), guide the user to select a strategy path and align their innovation roadmap accordingly.

---

### ⚠️ ODI Behavioral Guardrails for the Agent

These are absolute constraints the agent must respect:

| DO | DON'T |
|---|---|
| Always start by defining or confirming the Job-to-be-Done | Jump to solutions, features, or product ideas before the job is defined |
| Guide outcome statements with the correct format | Accept vague or solution-framed statements as valid outcomes |
| Compute opportunity scores when importance + satisfaction are available | Skip scoring or calculate it incorrectly |
| Reference the Universal Job Map when decomposing jobs | Invent arbitrary step structures disconnected from the 8 universal stages |
| Use outcome-based logic to identify market segments | Use demographics or assumptions to segment the market |
| Treat outcomes as stable, measurable success metrics | Confuse outcomes with features, preferences, or solutions |
| Call `get_odi_framework_guidelines` when stage guidance is needed | Guess at which stage comes next |

---

## 🛠 Technology Stack & Tools
- **Language**: Python 3.10+
- **MCP Framework**: `fastmcp` (Server and Client)
- **ASGI Server**: `uvicorn`
- **HTTP Client**: `httpx`
- **UI / Chat Client**: React + Vite (`apps/studio`), FastAPI sidecar (`apps/studio-api`)
- **LLM Client**: `openai` (OpenAI-compatible, used with Ollama locally)
- **Concurrency**: `asyncio`
- **Data Modeling / Validation**: `pydantic`

---

## 📄 README Maintenance Guardrail

`README.md` is the **primary human-facing entry point** for this project: a short,
high-level front door aimed at both users and developers. Detailed material lives
in `docs/` and is linked from the README. The agent MUST keep both current at all
times.

### When to update

Update the relevant file whenever any of the following change:

| Change type | Where to update |
|---|---|
| New or removed Python file / package | `README.md` **Code Overview** |
| New dependency added (`pip install ...`) | `README.md` **Quick Start → Prerequisites** |
| New way to run the project | `README.md` **Quick Start** and `docs/living-studio.md` |
| New MCP tool or capability | `README.md` **Code Overview** / relevant doc |
| New CLI command or flag | `docs/cli.md` |
| New connector kind | `docs/connectors.md` |
| New workflow or agent instruction | `docs/living-studio.md` |
| New message part or conversation capability | `docs/living-studio.md` (conversation runtime) |
| Deployment URL or cloud setup changes | `docs/deployment.md` |
| Roadmap item completed or added | `docs/roadmap.md` |
| Test layout or coverage changes | `docs/development.md` |

### Rules

- ✅ **Update docs in the same task** as the change that triggered it — never defer to a follow-up.
- ✅ **Keep README short**: it stays a high-level orientation page. Push detail into `docs/` and link to it rather than growing the README.
- ✅ **Optimize the first five seconds**: the top of the README carries the one-line value proposition and two distinct calls to action — try the hosted Living Studio, or run the full stack locally. Keep the `curl … install.sh | sh` one-liner in the hero.
- ✅ **Use the fixed section order**: `Why this exists` → `What you get` → `How it works` → `Quick Start` → `Connect your agent` → `Documentation` → `Code Overview` → `Contributing`. Prose sections stay bulleted and skimmable.
- ✅ **Keep the Quick Start accurate**: always reflect `uv run python scripts/dev.py` as the recommended launch command.
- ✅ **Keep Prerequisites up to date**: add any new `pip install` dependency immediately.
- ✅ **Mark Roadmap items `[x]` when completed** — do not leave stale unchecked items.
- ❌ **Never leave the README or `docs/` in a stale state** where documented commands or files no longer match the codebase.

---

## 🚧 Core Development Guardrails

### 1. Model Context Protocol (MCP) Implementation
- **Library Choice**: ALWAYS use [`fastmcp`](https://github.com/jlowin/fastmcp) for building the MCP architecture. Avoid using the lower-level Anthropic `mcp` SDK directly unless there is a hyper-specific edge case that `fastmcp` does not support.
- **Transport Protocol**: The project is currently prototyping with **HTTP transport** (not stdio). 
  - The server should be initialized using `mcp.run(transport="http", ...)`.
  - The client must connect to the HTTP endpoint (e.g., `http://localhost:8000/mcp`).
- **Tool Creation**: 
  - Register tools on the server using the `@mcp.tool` decorator.
  - **CRITICAL**: Provide comprehensive docstrings and strict Python type hints for every tool parameter. Explain exactly what the tool does and what data it expects, as this metadata is fed directly to the LLM for tool discovery.
  - **Contract Synchronization**: Whenever you add, modify, or remove an MCP tool in `apps/mcp-server/src/agentic_odi_mcp_server/mcp_server.py`, you **MUST** simultaneously update `packages/core/src/agentic_odi_core/contract.py` (`ToolName`, `TOOL_SPECS`) and the `get_capabilities` return string. `tests/contract/test_mcp_contract.py` enforces the surface.

### 2. Async / Client Practices
- Use `asyncio` for client execution and IO-bound tool operations.
- Always use the `fastmcp.Client` securely within an asynchronous context manager (`async with client:`) to ensure connections are efficiently managed and closed.

### 3. Data Schema & Persistence (ODI Domain)
- Define all Outcome-Driven Innovation (ODI) entities (e.g., *Jobs*, *Steps*, *Desired Outcomes*, *Opportunity Scores*) using `pydantic` models.
- When expanding the server to accept complex payloads or to query data, utilize these Pydantic models for built-in type validation and schema enforcement before the server processes the request.

### 4. General Philosophy
- **Reuse before you write**: take the ladder in `docs/architecture/reuse.md` in cost order — something already in this repo, then a dependency the workspace already declares, then a copy with a ledger entry, then new. A near-duplicate is a refactor-to-share, not a second copy. Any plan or pull request that adds a source file states a `Reuses:` block; `.agents/skills/reuse-first/SKILL.md` is the short form.
- **Separation of Concerns**: Isolate the ODI data logic/retrieval from the MCP server tooling logic.
- **Agentic Purpose**: Remember that the tools being built are meant to be consumed by autonomous agents. Design tool interfaces that are intuitive for an LLM to call and interpret.
- **External connectors**: Integrations live in the `packages/connectors` workspace package. New kinds implement `agentic_odi_connectors.protocol.Connector` and register via `register_kind`. Do not write ingested records into `jobs_db` / outcomes unless a later mapping task says so.
- **MCP client vs ODI server**: The ODI FastMCP **server** exposes product tools. The MCP **client connector** uses `fastmcp.Client` over HTTP to ingest data from *external* MCP servers. Prefer in-memory `Client(server)` tests for that connector, same as server tests.

### 5. Conversation UI (assistant-ui)

The Studio's transcript is [assistant-ui](https://www.assistant-ui.com) bound to
our own store; it is not a hand-rolled message list. Do not replace it, wrap it in
a second one, or re-implement streaming, the composer, attachments, branches, or
approval prompts beside it.

- **Markdown is a dependency, not a file.** `@assistant-ui/react-markdown` is
  declared in `apps/studio/package.json` and imported nowhere, while
  `apps/studio/src/lib/markdown.ts` hand-parses a subset for the transcript. That
  is the shape the reuse ladder forbids: a paid-for dependency plus a second
  implementation beside it. New rendering work goes through the library;
  collapsing the existing parser is its own task, not a reason to add a third.
- **One bridge.** `apps/studio/src/assistant/convert.ts` is the only mapping
  between `ChatMessage`/`ChatPart` and assistant-ui parts. It is pure and tested
  without a runtime. A new part type is added there, rendered in `parts.tsx`, and
  registered in the `components` map in `Conversation.tsx` — three files, never a
  fourth path.
- **The store stays ours.** `state/StudioContext.tsx` owns messages, ids,
  `parentId`, streaming state, memory, and canvas invalidation. The runtime is
  presentation: `useExternalStoreRuntime` in `assistant/StudioRuntime.tsx` maps
  `onNew`, `onEdit`, `onReload`, `onCancel`, `setMessages`, and
  `onRespondToToolApproval` onto context actions. Do not let component state
  become a second source of truth.
- **The SSE contract stays additive.** The sidecar is a Python tool loop; it is
  not migrating to Vercel's AI SDK stream protocol. New capability arrives as a
  new event (`reasoning`, `source`, `approval`, `ui`, …) or a new opt-in request
  field, and a client that sends neither must see the old stream unchanged.
- **The ODI catalog stays ours.** Generated surfaces travel as assistant-ui
  `data-*` parts and render through `UiRenderer`. assistant-ui's generic
  generative-UI vocabulary is not a replacement for the server-validated catalog.
- **No fabricated provenance.** A source names what a turn actually read; a part
  the converter does not understand is dropped, never printed as JSON.
- **Approvals gate writes, not reads.** `approvals: true` pauses mutating tools
  only; the gate is in-process, single-user, timeout-bound, and resolving a gate
  twice must not run a tool twice.
- **Voice is a seam, not a feature.** It is deliberately deferred: `adapters.dictation`
  plus `ComposerPrimitive.Dictate`, no backend change. Do not ship a microphone
  that only works in the browser shell.
- **Keep it honest in the docs.** A capability that lands here is described in
  `docs/living-studio.md` → *The conversation runtime*, with its test in
  `docs/development.md`, in the same change.

### 6. Testing Strategy (FastMCP)
- **First-Class Documentation**: Treat tests as living documentation that demonstrate how features work while protecting against regressions.
- **Speed & Isolation**: Tests must be fast (< 1s) and self-contained. Use `@pytest.mark.integration` or `@pytest.mark.client_process` for slower, integration, or resource-dependent tests.
- **Structure**: This repo is a uv workspace. Mirror each project's code structure in its own `tests/` directory (e.g., `apps/mcp-server/src/agentic_odi_mcp_server/mcp_server.py` -> `apps/mcp-server/tests/test_server_tools.py`, `packages/connectors/src/agentic_odi_connectors/mcp/connector.py` -> `packages/connectors/tests/test_mcp_connector.py`).
- **Atomic Tests**: Each test must verify exactly one specific behavior with clear intent in test names and assertions. Avoid multi-behavior tests.
- **In-Memory Testing (Preferred)**: Favor testing functionality deterministically by passing the `FastMCP` server directly into the `Client(server)` instance. This runs in-memory without network overhead for deterministic and lightning-fast execution.
- **Transport Testing (When Needed)**: For HTTP/SSE network transport tests, prefer the isolated in-process `fastmcp.utilities.tests.run_server_async(server)` context manager over subprocess testing (which uses `run_server_in_process` and is slower to debug).
- **Data Assertions**: Utilize `inline-snapshot` (`snapshot()`) for assessing complex data structures like tool API JSON schemas or expected responses.
