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

- Start the MCP server and Studio (via `python scripts/dev.py` or one of the
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

## 6. Model routing tiers and fallback

Agentic ODI includes a multi-tier **Model Router** (`agentic_odi_core.router`)
that ensures an honest, graceful experience when no model is reachable:

| Tier | Name | What it is | Availability |
|---|---|---|---|
| 0 | `deterministic` | Honest rule-based responder. Never fabricates numbers, scores, or customer names. Points at `compute_opportunity` for scoring instead of inventing a number. | Always available |
| 1 | `local` | OpenAI-compatible client for a locally-run model server you run yourself (the Studio does **not** bundle a model). | Available only when the endpoint answers — probed with a 2s timeout, TTL-cached at 30s |
| 2 | `remote` | The configured OpenAI-compatible cloud endpoint. | Probed via `check_llm_health` |

In default **`auto`** mode, the router selects the smartest available tier:
`remote` → `local` → `deterministic`. If a tier fails mid-turn, the router
demotes to the next tier and reports the demotion visibly in the transcript —
it never silently substitutes or fabricates an answer.

The routing mode is a field on the chat request (`routing_mode` in the
`/api/chat` payload) and accepts `auto`, `deterministic`, `local`, or `remote`;
the studio sends `auto` unless a caller overrides it. A forced mode that fails
reports the failure rather than silently falling back.

The Studio shows which tier answered via a status indicator, and the
**Settings** panel's **Model** section lets you configure the base URL, API key,
and model name, and test the connection with **Find models**. The CLI's
`/status` command reports the tier in use.

### The browser tier (edge models)

Conversation turns in the Studio client have a fourth option that runs no
server at all: a quantized model executed on the visitor's own GPU via WebLLM
(`apps/studio/src/edge/`). It engages only when no healthy paid endpoint is
configured. Then a strip appears above the composer — *"This browser can
answer, free."* — naming the model and its one-time download size, with
**Answer in this browser** and **Not now**. Yes records consent and starts the
fetch the next time the tab is idle; the strip becomes progress, then a
one-line celebration, and every turn after that is answered in the tab. "Not
now" is durable: the studio never asks again, and the answer can be changed in
Settings. Once it is answering, the browser earns its next rung — ten served
turns, or fifteen minutes of streamed output, buys the bigger model in the
background (1B → 3B → 8B, capped by what the device could actually host).

**Settings → Answers in this browser** is where that answer stops being
one-way. A switch turns the capability off — nothing downloaded, nothing run —
and the consent underneath it can be changed: *"Stop answering here"* withdraws
it, and one button names the weakest tier this device could host with its size
(*"Download Llama 3.2 1B — about 1.3 GB, once"*) and fetches it through the same
call the banner button makes, including the honest notice when another tab holds
the engine or the moment is not quiet. Each tier is then listed with its size and
what it is doing ("answering", "on this device", "not downloaded"), and when a
tier is missing a device requirement the reason sits on that row ("Needs about a
8 GB-class device; this one reports 4 GB."). Anything on disk can be freed for
its storage back, which rewrites the ladder's truth rather than hiding it. A
meter counts the answers served here toward the next tier, and a line reports how
much of the site's storage quota the weights are using.

Two honest caveats: nothing in CI has WebGPU, so the engine itself has only
ever been driven through a fake engine, and the real-GPU path is an unchecked
box in `docs/superpowers/plans/2026-11-01-edge-llm-ladder-remaining-work.md`.
The engine never reaches the `browser-model` capability from the
server manifests — a server cannot see a client GPU — so the Worker and
sidecar keep reporting it `available: false`; only the browser's capability
registry reports the truth. The hosted CSP admits `'wasm-unsafe-eval'` and
the model-weight origins (`huggingface.co`, `raw.githubusercontent.com`,
`cdn.jsdelivr.net`) this tier needs.
