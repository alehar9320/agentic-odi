---
description: Start the local dev stack and run end-to-end tests against the Living Studio SPA
---

# Local Dev & Test Workflow

Use this workflow whenever the user asks to:
- Run the app locally
- Test the agent/server/client stack end-to-end
- Open the browser and interact with the Living Studio SPA

## Steps

1. **Start the server** — Launch the FastMCP server and the Living Studio sidecar as a
   single background process using the dev launcher.

   ```
   uv run python scripts/dev.py
   ```

   Run with `WaitMsBeforeAsync: 2000` so the server has time to bind its port before
   continuing. Save the CommandId as `SERVER_CMD`.

2. **Verify the server is healthy** — Check `SERVER_CMD` status. If it has exited with an
   error, stop and report the error to the user. Do not proceed.

3. **Verify the studio is running** — Confirm the studio sidecar has started by checking
   for the "Living Studio" URL printout (`http://localhost:8100`).

4. **Open the browser** — Use the `browser_subagent` tool to navigate to
   `http://localhost:8100` and visually confirm the Living Studio SPA loads correctly.

5. **Run end-to-end interaction** — Use `browser_subagent` to exercise a feature
   (e.g., explore the Opportunity Landscape or query job maps) and confirm the UI
   responds correctly. Report what you see.

6. **Report results** — Use `notify_user` to summarize:
   - Whether the MCP server and studio sidecar started cleanly
   - What the browser showed
   - Any errors encountered

7. **Teardown (when done)** — Terminate `SERVER_CMD` using `send_command_input` with
   `Terminate: true`.

## Notes

- The MCP server runs on `http://localhost:8000/mcp`
- The Living Studio runs on `http://localhost:8100`
- All commands should be run from the project root (the `agentic-odi` workspace root).
- The MCP server does not require an LLM. The studio SPA is a static build; if the
  frontend is not built, the dev launcher prints a hint with the build command.
