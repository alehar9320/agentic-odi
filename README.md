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

You will need Python 3.10+ and the `fastmcp` package (along with an ASGI server like `uvicorn` and an HTTP client like `httpx`).

```bash
pip install fastmcp uvicorn httpx
```

### Running the Environment

You'll need two terminal windows to witness the MCP architecture in action.

1. **Start the MCP Server:**
   This starts the context provider on `http://localhost:8000`.
   ```bash
   python my_server.py
   ```

2. **Run the MCP Client:**
   In a separate terminal, execute the client to request execution and context from the server.
   ```bash
   python my_client.py
   ```

## 🗺️ Roadmap & Next Steps

As we validate the feasibility of this architecture, our next milestones include:

- [ ] **ODI Schema Definition**: Define standardized Pydantic models for *Jobs*, *Steps*, and *Outcomes*.
- [ ] **Context Tooling**: Replace the dummy `greet` tool with capabilities like `get_job_map(job_id)` or `evaluate_outcome(statement)`.
- [ ] **Data Persistence Layer**: Connect the fastmcp server to a lightweight vector or relational database containing actual user research data.
- [ ] **Agentic Integration**: Hook the client up to an LLM (e.g., via LangChain or standard OpenAI clients) so the LLM can *discover* the ODI tools and intelligently request customer insights when ideating features.

---

*Let's build AI that builds what people actually need.*
