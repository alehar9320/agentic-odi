# Agentic ODI 🚀

> **Experimental test to learn and evaluate the feasibility of utilizing Model Context Protocol (MCP) for Outcome-Driven Innovation (ODI) specifications.**

## 🌟 The Vision: Context-Aware Innovation

**Outcome-Driven Innovation (ODI)**, built on the "Jobs-to-be-Done" theory, relies on deeply understanding customer needs, desired outcomes, and execution contexts. Historically, applying ODI requires meticulous research, structured data modeling, and rigorous analysis.

**Model Context Protocol (MCP)** represents a paradigm shift in how AI systems consume and reason over external context. By adopting MCP, we can bridge the gap between static user research and dynamic, agentic AI. 

The vision for **Agentic ODI** is to build a unified, open protocol where LLMs and autonomous agents can natively query, understand, and reason over ODI data (Job Maps, Desired Outcomes, and Opportunity Scores) dynamically in real-time. Instead of feeding LLMs disconnected prompts, an MCP-powered ODI server will act as the "brain" of customer needs, allowing agents to invent, evaluate, and ideate solutions strictly anchored in verified user outcomes.

## 🏗️ Current State (Experimental Testbed)

This repository serves as an initial sandbox for understanding server-client MCP communication streams. We are utilizing [`FastMCP`](https://github.com/jlowin/fastmcp) to prototype HTTP-based context delivery.

### Code Overview
- **`my_server.py`**: A foundational MCP Server exposing an initial HTTP transport layer. Currently, it hosts a simple `greet` tool to validate the end-to-end MCP wiring. In the future, this will host tools to fetch *Job Steps*, *Desired Outcomes*, and *Opportunity Configs*.
- **`my_client.py`**: A Python-based agent client that communicates with the MCP server, executing tool calls over the active connection.

## 🚀 Getting Started

### Prerequisites

Python 3.10+ and the following packages:

```bash
pip install fastmcp uvicorn httpx streamlit openai
```

### Running the Environment

#### ⚡ One-command launch (recommended)

`run.py` starts both the MCP server and the Streamlit UI concurrently. Press **Ctrl+C** to stop both.

```bash
python run.py
```

| Service | URL |
|---|---|
| MCP Server | http://localhost:8000/mcp |
| Streamlit Chat UI | http://localhost:8501 |

#### 🔧 Manual split-terminal (alternative)

Open two terminals and run each process separately:

```bash
# Terminal 1 — MCP server
python my_server.py

# Terminal 2 — Streamlit chat UI
streamlit run my_client.py
```

#### 🤖 Agent-driven testing

Type `/dev` in the AI assistant to trigger the full automated workflow: it will start both processes, open the browser, send a test message, and report the results.

## 🧪 Testing

Tests use **pytest** with **pytest-asyncio** (strict mode) and run entirely in-memory — no running server required.

```bash
python -m pytest tests/ -v
```

### 🧹 Linting, formatting & type checks (CI parity)

The CI pipeline runs several quality checks. You can mirror them locally with:

```bash
# Ruff lint and formatting checks
uv run ruff check .
uv run ruff format --check .

# Type checking
uv run mypy .

# Security scanning
uv run bandit -r .
```

| File | What it covers |
|---|---|
| `tests/test_odi.py` | Full ODI workflow (add job → steps → outcomes → retrieval) + capabilities tool |
| `tests/test_tools.py` | Tool response-shape contract for `add_job` |

**Conventions:**
- All test files are named `test_*.py` under `tests/`.
- Every async test is decorated with `@pytest.mark.asyncio`.
- A `reset_db` autouse fixture clears in-memory state before each test — always include it.
- Use `Client(mcp)` directly (no HTTP server needed) for fast, isolated tests.

> [!TIP]
> Type `/test` in the AI assistant to have the agent run all tests and report the results automatically.

## ☁️ Deployment

The server is deployed via **[Horizon Prefect](https://www.prefect.io/horizon)**, Prefect's managed infrastructure for hosting MCP-compatible agents.

### 🧪 Test Chat (UI)

Interact with the deployed agent directly in your browser:

> **[https://horizon.prefect.io/alhase/servers/agentic-odi/chat](https://horizon.prefect.io/alhase/servers/agentic-odi/chat)**

### 🔌 MCP Server Endpoint

Integrate via the MCP protocol at:

> **[https://agentic-odi.fastmcp.app/mcp](https://agentic-odi.fastmcp.app/mcp)**

> [!IMPORTANT]
> **Authentication is required** to access the MCP server endpoint. Please reach out to the maintainers to obtain the necessary credentials before connecting a client.

---

## 🗺️ Roadmap & Next Steps

As we validate the feasibility of this architecture, our next milestones include:

- [ ] **ODI Schema Definition**: Define standardized Pydantic models for *Jobs*, *Steps*, and *Outcomes*.
- [ ] **Context Tooling**: Replace the dummy `greet` tool with capabilities like `get_job_map(job_id)` or `evaluate_outcome(statement)`.
- [ ] **Data Persistence Layer**: Connect the fastmcp server to a lightweight vector or relational database containing actual user research data.
- [ ] **Agentic Integration**: Hook the client up to an LLM (e.g., via LangChain or standard OpenAI clients) so the LLM can *discover* the ODI tools and intelligently request customer insights when ideating features.

---

*Let's build AI that builds what people actually need.*
