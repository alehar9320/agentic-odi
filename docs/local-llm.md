# Local Tools-Capable LLM Backend

To exercise real tool-calling end-to-end against the MCP server, you need a
local LLM backend that:

- Exposes an **OpenAI-compatible Chat Completions API** (for example,
  `/v1/chat/completions`), and
- Supports OpenAI-style **`tools` / `tool_calls`**.

A simple fully local option is
[`llama-cpp-python`](https://github.com/abetlen/llama-cpp-python), which can run
a quantized model on your machine and expose an OpenAI-compatible server.

## 1. Install a local LLM server

Install `llama-cpp-python` in your environment (see its README for
platform-specific build notes):

```bash
pip install llama-cpp-python
```

## 2. Download a small tools-capable model

Download a small GGUF model that supports function/tool calling (for example, a
7B function-calling variant from Hugging Face) and note its path, e.g.
`C:\models\local-tools-model.gguf`.

## 3. Start the OpenAI-compatible server

Start the server and give the model a friendly alias that matches the default
used by the Living Studio sidecar and the CLI chat:

```bash
python -m llama_cpp.server \
  --model "C:\models\local-tools-model.gguf" \
  --model_alias local-tools-model \
  --host 127.0.0.1 --port 8001 \
  --chat_format openai
```

This exposes an OpenAI-style API at `http://127.0.0.1:8001/v1`.

## 4. Configure the Studio

The Living Studio sidecar and the CLI chat read the following environment
variables (with sensible defaults):

| Variable | Default |
|---|---|
| `AGENTIC_ODI_BASE_URL` | `http://localhost:8001/v1` |
| `AGENTIC_ODI_MODEL` | `local-tools-model` |
| `AGENTIC_ODI_MCP_URL` | `http://localhost:8000/mcp` |
| `AGENTIC_ODI_API_KEY` | `local` |

You can either set these in your shell or adjust them in the Living Studio's
**Settings** panel.

## 5. Verify tool-calling against the MCP server

- (Optional) Before starting the UI, confirm the LLM backend is reachable:

  ```bash
  curl http://127.0.0.1:8001/v1/models
  ```

  If this request fails, fix your local LLM server configuration before
  debugging the MCP client/server.

- Start the MCP server and Studio (via `python -m client.run` or one of the
  [run modes](living-studio.md)).
- In the browser UI, ask the assistant something that should use ODI tools, for
  example: *"Help me define a new Job-to-be-Done and add it to your ODI
  repository."*
- You should see the assistant briefly display that it is calling tools (for
  example, `add_job`, `get_jobs`, etc.) and then respond with grounded ODI
  guidance, confirming the local LLM, MCP server, and client wiring all work
  together.
- If the LLM backend is unreachable or misconfigured, the UI shows a clear error
  banner indicating the configured **Base URL** could not be reached, along with
  details from the underlying error. Use that message together with the steps
  above to fix your local LLM setup.
