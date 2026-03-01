# Agentic ODI - AI Developer Guardrails

This file provides system instructions and guardrails for any AI agents (or LLMs) assisting with the development of the **Agentic ODI** project. Please adhere to these guidelines to maintain consistency and align with the project's vision.

## 🛠 Technology Stack & Tools
- **Language**: Python 3.10+
- **MCP Framework**: `fastmcp` (Server and Client)
- **ASGI Server**: `uvicorn`
- **HTTP Client**: `httpx`
- **Concurrency**: `asyncio`
- **Data Modeling / Validation**: `pydantic`

## 🚧 Core Guardrails & Practices

### 1. Model Context Protocol (MCP) Implementation
- **Library Choice**: ALWAYS use [`fastmcp`](https://github.com/jlowin/fastmcp) for building the MCP architecture. Avoid using the lower-level Anthropic `mcp` SDK directly unless there is a hyper-specific edge case that `fastmcp` does not support.
- **Transport Protocol**: The project is currently prototyping with **HTTP transport** (not stdio). 
  - The server should be initialized using `mcp.run(transport="http", ...)`.
  - The client must connect to the HTTP endpoint (e.g., `http://localhost:8000/mcp`).
- **Tool Creation**: 
  - Register tools on the server using the `@mcp.tool` decorator.
  - **CRITICAL**: Provide comprehensive docstrings and strict Python type hints for every tool parameter. Explain exactly what the tool does and what data it expects, as this metadata is fed directly to the LLM for tool discovery.

### 2. Async / Client Practices
- Use `asyncio` for client execution and IO-bound tool operations.
- Always use the `fastmcp.Client` securely within an asynchronous context manager (`async with client:`) to ensure connections are efficiently managed and closed.

### 3. Data Schema & Persistence (ODI Domain)
- Define all Outcome-Driven Innovation (ODI) entities (e.g., *Jobs*, *Steps*, *Desired Outcomes*, *Opportunity Scores*) using `pydantic` models.
- When expanding the server to accept complex payloads or to query data, utilize these Pydantic models for built-in type validation and schema enforcement before the server processes the request.

### 4. General Philosophy
- **Separation of Concerns**: Isolate the ODI data logic/retrieval from the MCP server tooling logic.
- **Agentic Purpose**: Remember that the tools being built are meant to be consumed by autonomous agents. Design tool interfaces that are intuitive for an LLM to call and interpret.
