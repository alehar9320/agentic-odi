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

### Local tools-capable LLM backend (for MCP testing)

To exercise real tool-calling end-to-end against the MCP server, you need a local LLM backend that:

- Exposes an **OpenAI-compatible Chat Completions API** (for example, `/v1/chat/completions`), and
- Supports OpenAI-style **`tools` / `tool_calls`**.

A simple fully local option is [`llama-cpp-python`](https://github.com/abetlen/llama-cpp-python), which can run a quantized model on your machine and expose an OpenAI-compatible server.

1. **Install a local LLM server**

   Install `llama-cpp-python` in your environment (see its README for platform-specific build notes):

   ```bash
   pip install llama-cpp-python
   ```

2. **Download a small tools-capable model**

   Download a small GGUF model that supports function/tool calling (for example, a 7B function-calling variant from Hugging Face) and note its path, e.g. `C:\models\local-tools-model.gguf`.

3. **Start the OpenAI-compatible server**

   Start the server and give the model a friendly alias that matches the default used by `my_client.py`:

   ```bash
   python -m llama_cpp.server \
     --model "C:\models\local-tools-model.gguf" \
     --model_alias local-tools-model \
     --host 127.0.0.1 --port 8001 \
     --chat_format openai
   ```

   This exposes an OpenAI-style API at `http://127.0.0.1:8001/v1`.

4. **Point the Streamlit client at the local server**

   `my_client.py` reads defaults from environment variables (with sensible fallbacks):

   - `AGENTIC_ODI_BASE_URL` (default: `http://localhost:8001/v1`)
   - `AGENTIC_ODI_API_KEY` (default: `local`)
   - `AGENTIC_ODI_MODEL` (default: `local-tools-model`)
   - `AGENTIC_ODI_MCP_URL` (default: `http://localhost:8000/mcp`)

   You can either set these in your shell or adjust them in the Streamlit sidebar under **“LLM Configuration”**.

5. **Verify tool-calling against the MCP server**

   - (Optional) Before starting the UI, you can quickly verify that the LLM backend is reachable:

     ```bash
     curl http://127.0.0.1:8001/v1/models
     ```

     If this request fails, fix your local LLM server configuration before debugging the MCP client/server.

   - Start the MCP server and Streamlit UI (either via `python run.py` or the split-terminal commands above).
   - In the browser UI, ask the assistant something that should use ODI tools, for example: “Help me define a new Job-to-be-Done and add it to your ODI repository.”
   - You should see the assistant briefly display that it is calling tools (for example, `add_job`, `get_jobs`, etc.) and then respond with grounded ODI guidance, confirming that the local LLM, MCP server, and client wiring all work together.
   - If the LLM backend is unreachable or misconfigured, the UI will show a clear error banner indicating that the backend at your configured **Base URL** could not be reached, along with details from the underlying error. Use that message together with the steps above to fix your local LLM setup.

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

# Tests (same as CI)
uv run python -m pytest tests/ -v
```

To run these automatically before each commit, you can enable the bundled pre-commit hooks:

```bash
uv pip install pre-commit
pre-commit install
```

After this, `ruff` and `ruff-format` will run on staged files whenever you commit. You can also trigger them manually with:

```bash
pre-commit run --all-files
```

### 🧼 Developer workflow for formatting

- **When editing Python files**, either:
  - Rely on the **pre-commit hooks** above (recommended), or
  - Run Ruff formatting directly before pushing:

    ```bash
    uv run ruff format .
    ```

- **CI behavior**:
  - CI runs `uv run ruff check .` to lint without modifying files.
  - CI runs `uv run ruff format --check .` to *verify* formatting only.
  - If CI fails on formatting, run `uv run ruff format .` locally, commit the changes, and push again.

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
