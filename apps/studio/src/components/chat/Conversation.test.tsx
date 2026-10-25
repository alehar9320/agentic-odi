import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { ChatMessage } from "../../types";
import { catalogManifest } from "../../ui/catalog";
import { parseUiSpec, type UiNode } from "../../ui/protocol";
import { Conversation } from "./Conversation";

const harness = vi.hoisted(() => ({
  state: {
    messages: [] as unknown[],
    streaming: false,
    thinkingPhase: null as string | null,
    offlineReply: false,
    sendMessage: vi.fn<(text: string) => Promise<void>>(),
  },
}));

vi.mock("../../state/StudioContext", () => ({
  useStudio: () => harness.state,
}));

function nodeOf(spec: unknown): UiNode {
  const parsed = parseUiSpec(spec, catalogManifest());
  if (!parsed.ok) {
    throw new Error(parsed.reason);
  }
  return parsed.node;
}

function outcomeCard(actions = false): UiNode {
  return nodeOf({
    type: "outcome-card",
    props: {
      id: "O-1",
      statement: "Minimize the time it takes to propagate secrets",
      importance: 9,
      satisfaction: 3,
      ...(actions
        ? {
            actions: [
              { label: "Simulate this bet", intent: "Simulate O-1", tone: "primary" },
              { label: "Find evidence", intent: "Find evidence for O-1", tone: "ghost" },
            ],
          }
        : {}),
    },
  });
}

function renderTurn(messages: ChatMessage[]) {
  harness.state.messages = messages;
  return render(<Conversation />);
}

describe("Conversation", () => {
  it("renders prose and surfaces in the agent's order", () => {
    const { container } = renderTurn([
      {
        role: "assistant",
        content: "Here is the board. It is the top bet.",
        parts: [
          { kind: "text", text: "Here is the board." },
          { kind: "ui", id: "ui-1", node: outcomeCard() },
          { kind: "text", text: "It is the top bet." },
        ],
      },
    ]);

    const text = container.textContent ?? "";
    const intro = text.indexOf("Here is the board.");
    const card = text.indexOf("Minimize the time it takes to propagate secrets");
    const outro = text.indexOf("It is the top bet.");

    expect(intro).toBeGreaterThanOrEqual(0);
    expect(card).toBeGreaterThan(intro);
    expect(outro).toBeGreaterThan(card);
  });

  it("keeps history without parts readable", () => {
    const { container } = renderTurn([
      { role: "assistant", content: "**Scored** three outcomes." },
    ]);

    expect(container.textContent).toContain("Scored");
    expect(container.querySelector("strong")).not.toBeNull();
  });

  it("renders a surface-only turn", () => {
    const { container } = renderTurn([
      { role: "assistant", content: "", parts: [{ kind: "ui", id: "ui-1", node: outcomeCard() }] },
    ]);

    expect(container.textContent).toContain("Minimize the time it takes to propagate secrets");
  });

  it("turns a card action into the user's next message", () => {
    harness.state.sendMessage = vi.fn<(text: string) => Promise<void>>();
    renderTurn([
      {
        role: "assistant",
        content: "",
        parts: [{ kind: "ui", id: "ui-1", node: outcomeCard(true) }],
      },
    ]);

    fireEvent.click(document.querySelector("button.ui-action") as HTMLButtonElement);

    expect(harness.state.sendMessage).toHaveBeenCalledWith("Simulate O-1");
  });
});

describe("Conversation run activity", () => {
  beforeEach(() => {
    harness.state.streaming = false;
    harness.state.thinkingPhase = null;
  });

  it("names the tool in flight instead of leaving the turn blank", () => {
    harness.state.streaming = true;
    harness.state.thinkingPhase = "model";
    const { container } = renderTurn([
      {
        role: "assistant",
        content: "",
        tools: [{ id: "get_jobs-0", name: "get_jobs", status: "running", startedAt: 0 }],
      },
    ]);

    expect(container.textContent).toContain("Reading your jobs");
    expect(container.textContent).toContain("in progress");
  });

  it("collapses a finished run to one line that still opens", () => {
    const { container } = renderTurn([
      {
        role: "assistant",
        content: "Two jobs, four outcomes.",
        tools: [
          { id: "get_jobs-0", name: "get_jobs", status: "ok", startedAt: 0, endedAt: 600 },
          { id: "get_outcomes-1", name: "get_outcomes", status: "ok", startedAt: 600, endedAt: 1900 },
        ],
      },
    ]);

    const summary = container.querySelector("summary");
    expect(summary?.textContent).toContain("2 tools");
    expect(summary?.textContent).toContain("1.9s");
    expect(container.textContent).toContain("Scoring outcomes");
  });

  it("keeps a failed step visible with what the tool said", () => {
    const { container } = renderTurn([
      {
        role: "assistant",
        content: "I could not read the board.",
        tools: [
          {
            id: "get_jobs-0",
            name: "get_jobs",
            status: "error",
            preview: "MCP server unreachable",
            startedAt: 0,
            endedAt: 300,
          },
        ],
      },
    ]);

    expect(container.textContent).toContain("1 failed");
    expect(container.textContent).toContain("MCP server unreachable");
    expect(container.textContent).toContain("failed");
  });
});

describe("Conversation stopped runs", () => {
  it("says the reader stopped it, and offers to ask again", () => {
    harness.state.sendMessage = vi.fn<(text: string) => Promise<void>>();
    const { container } = renderTurn([
      { role: "user", content: "list the jobs" },
      { role: "assistant", content: "Here is what I have so", stopped: true, retryText: "list the jobs" },
    ]);

    expect(container.textContent).toContain("Stopped by you.");
    expect(container.textContent).toContain("Here is what I have so");

    fireEvent.click(screen.getByRole("button", { name: /ask again/i }));

    expect(harness.state.sendMessage).toHaveBeenCalledWith("list the jobs");
  });

  it("still shows a stop that produced nothing at all", () => {
    const { container } = renderTurn([
      { role: "user", content: "list the jobs" },
      { role: "assistant", content: "", parts: [], stopped: true, retryText: "list the jobs" },
    ]);

    expect(container.textContent).toContain("Stopped by you.");
  });
});

describe("Conversation failures", () => {
  it("shows the failure, the suggestion, and a retry that re-sends the question", () => {
    harness.state.sendMessage = vi.fn<(text: string) => Promise<void>>();
    const { container } = renderTurn([
      { role: "user", content: "list the jobs" },
      {
        role: "assistant",
        content: "",
        parts: [],
        error: {
          code: "mcp_unreachable",
          message: "The MCP server is unreachable.",
          detail: "connection refused",
          suggestion: "Check that the MCP server is running, then try again.",
          retryable: true,
          request_id: "req-1",
        },
        retryText: "list the jobs",
      },
    ]);

    expect(container.textContent).toContain("The MCP server is unreachable.");
    expect(container.textContent).toContain("Check that the MCP server is running");
    expect(container.querySelector('[role="alert"]')).not.toBeNull();
    expect(container.textContent).toContain("req-1");

    const retry = screen.getByRole("button", { name: /retry/i });
    fireEvent.click(retry);

    expect(harness.state.sendMessage).toHaveBeenCalledWith("list the jobs");
  });
});
