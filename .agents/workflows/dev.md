---
description: Start the local dev stack and run end-to-end browser tests against the Streamlit UI
---

# Local Dev & Test Workflow

Use this workflow whenever the user asks to:
- Run the app locally
- Test the agent/server/client stack end-to-end
- Open the browser and interact with the Streamlit UI

## Steps

1. **Start the server** — Launch the FastMCP server as a background process.

```
python my_server.py
```

Run with `WaitMsBeforeAsync: 2000` so the server has time to bind port 8000 before continuing.
Save the CommandId as `SERVER_CMD`.

2. **Verify the server is healthy** — Check `SERVER_CMD` status. If it has exited with an error, stop and report the error to the user. Do not proceed.

3. **Start the Streamlit client** — Launch the UI as a background process.

```
streamlit run my_client.py --server.headless true
```

Run with `WaitMsBeforeAsync: 3000`. Save the CommandId as `CLIENT_CMD`.

4. **Verify the client is running** — Check `CLIENT_CMD` status. If it has exited, stop and report.

5. **Open the browser** — Use the `browser_subagent` tool to navigate to `http://localhost:8501` and visually confirm the Streamlit app loads correctly (title "Agentic ODI 🚀" is visible).

6. **Run end-to-end interaction** — Use `browser_subagent` to send a test message in the chat (e.g., "What can you do?") and confirm the assistant responds. Report what you see.

7. **Report results** — Use `notify_user` to summarize:
   - Whether the server and client started cleanly
   - What the browser showed
   - Any errors encountered

8. **Teardown (when done)** — Terminate `SERVER_CMD` and `CLIENT_CMD` using `send_command_input` with `Terminate: true`.

## Notes

- The MCP server runs on `http://localhost:8000/mcp`
- The Streamlit UI runs on `http://localhost:8501`
- All commands should be run from the project root: `c:\GIT repositories\agentic-odi`
- The default LLM in the sidebar points to Ollama (`http://localhost:11434/v1`). If Ollama is not running, the chat won't complete but the UI will still load.
