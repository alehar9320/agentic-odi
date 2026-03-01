# Agentic ODI - AI Developer Guardrails

This file provides system instructions and guardrails for any AI agents (or LLMs) assisting with the development of the **Agentic ODI** project. Please adhere to these guidelines to maintain consistency and align with the project's vision.

> **Source of Truth for ODI Methodology**: `knowledge/Strategyn_what_is_Outcome_Driven_Innovation.pdf` by Anthony W. Ulwick (Strategyn). All ODI concepts in this project are grounded in that document. When in doubt, refer agents back to its definitions.

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
- **UI / Chat Client**: `streamlit`
- **LLM Client**: `openai` (OpenAI-compatible, used with Ollama locally)
- **Concurrency**: `asyncio`
- **Data Modeling / Validation**: `pydantic`

---

## 📄 README Maintenance Guardrail

`README.md` is the **primary human-facing source of truth** for this project. The agent MUST keep it current at all times.

### When to update README.md

Update `README.md` whenever any of the following change:

| Change type | README section to update |
|---|---|
| New or removed Python file | **Code Overview** |
| New dependency added (`pip install ...`) | **Prerequisites** |
| New way to run the project | **Running the Environment** |
| New MCP tool or capability | **Code Overview** / relevant section |
| New workflow or agent instruction | **Getting Started → Agent-driven testing** |
| Deployment URL or cloud setup changes | **Deployment** |
| Roadmap item completed or added | **Roadmap & Next Steps** |

### Rules

- ✅ **Update README in the same task** as the change that triggered it — never defer to a follow-up.
- ✅ **Keep the "Running the Environment" section accurate**: always reflect `python run.py` as the recommended launch command.
- ✅ **Keep Prerequisites up to date**: add any new `pip install` dependency immediately.
- ✅ **Mark Roadmap items `[x]` when completed** — do not leave stale unchecked items.
- ❌ **Never leave README in a stale state** where documented commands or files no longer match the codebase.

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
  - **Capability Synchronization**: Whenever you add, modify, or remove an MCP tool in `my_server.py`, you **MUST** simultaneously update the `get_capabilities` tool's human-readable return string to ensure the capability set exactly matches the code.

### 2. Async / Client Practices
- Use `asyncio` for client execution and IO-bound tool operations.
- Always use the `fastmcp.Client` securely within an asynchronous context manager (`async with client:`) to ensure connections are efficiently managed and closed.

### 3. Data Schema & Persistence (ODI Domain)
- Define all Outcome-Driven Innovation (ODI) entities (e.g., *Jobs*, *Steps*, *Desired Outcomes*, *Opportunity Scores*) using `pydantic` models.
- When expanding the server to accept complex payloads or to query data, utilize these Pydantic models for built-in type validation and schema enforcement before the server processes the request.

### 4. General Philosophy
- **Separation of Concerns**: Isolate the ODI data logic/retrieval from the MCP server tooling logic.
- **Agentic Purpose**: Remember that the tools being built are meant to be consumed by autonomous agents. Design tool interfaces that are intuitive for an LLM to call and interpret.

### 5. Testing Strategy (FastMCP)
- **First-Class Documentation**: Treat tests as living documentation that demonstrate how features work while protecting against regressions.
- **Speed & Isolation**: Tests must be fast (< 1s) and self-contained. Use `@pytest.mark.integration` or `@pytest.mark.client_process` for slower, integration, or resource-dependent tests.
- **Structure**: Mirror the application code structure in the `tests/` directory (e.g., `src/fastmcp/server/auth.py` -> `tests/server/test_auth.py`).
- **Atomic Tests**: Each test must verify exactly one specific behavior with clear intent in test names and assertions. Avoid multi-behavior tests.
- **In-Memory Testing (Preferred)**: Favor testing functionality deterministically by passing the `FastMCP` server directly into the `Client(server)` instance. This runs in-memory without network overhead for deterministic and lightning-fast execution.
- **Transport Testing (When Needed)**: For HTTP/SSE network transport tests, prefer the isolated in-process `fastmcp.utilities.tests.run_server_async(server)` context manager over subprocess testing (which uses `run_server_in_process` and is slower to debug).
- **Data Assertions**: Utilize `inline-snapshot` (`snapshot()`) for assessing complex data structures like tool API JSON schemas or expected responses.
