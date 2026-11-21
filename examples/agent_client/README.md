# An example MCP client for the Agentic ODI store

This directory holds a minimal, runnable client for the ODI MCP server — the
code that backs the walkthrough in [`docs/integration.md`](../../docs/integration.md).
It is executed by the test suite against an in-memory server, so it cannot
describe a call the product does not answer.

The client is deliberately small. It shows the four things a third-party agent
needs and nothing else:

1. **Connect** to the MCP server and read its tool surface.
2. **Read** the landscape, one page at a time, and stop on a short page.
3. **Evaluate** a statement and read a score — including the honest empty states.
4. **Write** one row, through consent, and show that a refused write changes
   nothing.

Run it directly for a demonstration against an isolated in-memory store (no
credentials, no network, no access to your own store):

```bash
uv run python -m examples.agent_client.client
```

The same code path is asserted by
[`tests/test_integration_example.py`](../../tests/test_integration_example.py).
