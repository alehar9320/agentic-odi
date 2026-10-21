import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import App from "./App";

vi.mock("./api/studioApi", () => ({
  fetchConfig: vi.fn(async () => ({
    base_url: "http://localhost:8001/v1",
    api_key: "local",
    model_name: "local-tools-model",
    mcp_url: "http://localhost:8000/mcp",
  })),
  fetchCanvas: vi.fn(async () => ({
    jobs: [{ id: "JOB-402", name: "Propagate secrets" }],
    steps: [],
    outcomes: [
      {
        id: "O-1",
        job_id: "JOB-402",
        statement: "Minimize the time it takes to propagate secrets",
        importance: 9.2,
        satisfaction: 3.1,
        opportunity_score: 15.3,
      },
    ],
    source: "local" as const,
  })),
  healthMcp: vi.fn(async () => ({ reachable: true })),
  healthLlm: vi.fn(async () => ({ healthy: true, message: "LLM backend is reachable." })),
  addStep: vi.fn(async () => ({ ok: true, result: "created" })),
  addOutcome: vi.fn(async () => ({ ok: true, result: "created" })),
  streamChat: vi.fn(
    async (
      _request: unknown,
      onEvent: (event: { event: string; data: Record<string, unknown> }) => void,
    ) => {
      onEvent({ event: "status", data: { phase: "model" } });
      onEvent({ event: "delta", data: { text: "Start with the **job**." } });
      onEvent({ event: "message", data: { content: "Start with the **job**." } });
    },
  ),
}));

describe("studio shell", () => {
  it("opens as a conversation with a greeting and suggestion pills", async () => {
    render(<App />);

    expect(
      await screen.findByRole("heading", { name: /^Good (morning|afternoon|evening)/ }),
    ).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: /message the studio/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /define a job/i })).toBeInTheDocument();
    // The classic UI is secondary: no workspace panel until you ask for one.
    expect(screen.queryByRole("heading", { name: /opportunity landscape/i })).toBeNull();
  });

  it("opens a workspace panel from the drawer and closes it again", async () => {
    render(<App />);

    fireEvent.click(await screen.findByRole("button", { name: /^landscape/i }));

    expect(
      await screen.findByRole("heading", { name: /opportunity landscape/i }),
    ).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /close panel/i }));

    await waitFor(() => {
      expect(screen.queryByRole("heading", { name: /opportunity landscape/i })).toBeNull();
    });
  });

  it("streams an answer into the transcript after sending a message", async () => {
    render(<App />);

    const composer = await screen.findByRole("textbox", { name: /message the studio/i });
    fireEvent.change(composer, { target: { value: "Where do I start?" } });
    fireEvent.click(screen.getByRole("button", { name: /send message/i }));

    expect(await screen.findByText("Where do I start?")).toBeInTheDocument();
    expect(await screen.findByText("job")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /copy reply/i })).toBeInTheDocument();
  });

  it("puts the composer back in the hero after starting a new conversation", async () => {
    render(<App />);

    const composer = await screen.findByRole("textbox", { name: /message the studio/i });
    fireEvent.change(composer, { target: { value: "Where do I start?" } });
    fireEvent.click(screen.getByRole("button", { name: /send message/i }));
    await screen.findByText("Where do I start?");

    fireEvent.click(screen.getByRole("button", { name: /new conversation/i }));

    await waitFor(() => {
      expect(screen.queryByText("Where do I start?")).toBeNull();
    });
    expect(
      screen.getByRole("heading", { name: /^Good (morning|afternoon|evening)/ }),
    ).toBeInTheDocument();
  });
});
