import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { StudioRuntimeProvider } from "../../assistant/StudioRuntime";
import type { ChatMessage } from "../../types";
import { catalogManifest } from "../../ui/catalog";
import { parseUiSpec, type UiNode } from "../../ui/protocol";
import { Conversation } from "./Conversation";

const harness = vi.hoisted(() => ({
  state: {
    messages: [] as unknown[],
    streaming: false,
    thinkingPhase: null as string | null,
    toolActivity: [] as unknown[],
    offlineReply: false,
    canvas: null,
    regenerateFrom: vi.fn(),
    editFrom: vi.fn(),
    switchBranch: vi.fn(),
    respondToApproval: vi.fn(),
    stopStreaming: vi.fn(),
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
  return render(
    <StudioRuntimeProvider>
      <Conversation />
    </StudioRuntimeProvider>,
  );
}

describe("Conversation", () => {
  it("renders prose and surfaces in the agent's order", () => {
    const { container } = renderTurn([
      {
        id: "m-1",
        parentId: null,
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
      { id: "m-1", parentId: null, role: "assistant", content: "**Scored** three outcomes." },
    ]);

    expect(container.textContent).toContain("Scored");
    expect(container.querySelector("strong")).not.toBeNull();
  });

  it("renders a surface-only turn", () => {
    const { container } = renderTurn([
      {
        id: "m-1",
        parentId: null,
        role: "assistant",
        content: "",
        parts: [{ kind: "ui", id: "ui-1", node: outcomeCard() }],
      },
    ]);

    expect(container.textContent).toContain("Minimize the time it takes to propagate secrets");
  });

  it("keeps reasoning behind a disclosure that opens on request", () => {
    const { container } = renderTurn([
      {
        id: "m-1",
        parentId: null,
        role: "assistant",
        content: "Two outcomes matter.",
        parts: [
          { kind: "reasoning", text: "Weighing the scored outcomes against the job map." },
          { kind: "text", text: "Two outcomes matter." },
        ],
      },
    ]);

    const toggle = screen.getByRole("button", { name: /Thought process/ });
    const panel = container.querySelector(".reasoning__body") as HTMLElement;
    expect(toggle).toHaveAttribute("aria-expanded", "false");
    expect(panel.hidden).toBe(true);

    fireEvent.click(toggle);

    expect(toggle).toHaveAttribute("aria-expanded", "true");
    expect(panel.hidden).toBe(false);
    expect(panel.textContent).toContain("Weighing the scored outcomes");
  });

  it("opens reasoning while it is written, then reports how long it took", async () => {
    harness.state.streaming = true;
    const turn: ChatMessage[] = [
      {
        id: "a-1",
        parentId: null,
        role: "assistant",
        content: "",
        parts: [{ kind: "reasoning", text: "Weighing the scored outcomes." }],
      },
    ];
    harness.state.messages = turn;
    const { rerender } = render(
      <StudioRuntimeProvider>
        <Conversation />
      </StudioRuntimeProvider>,
    );

    const thinking = screen.getByRole("button", { name: /Thinking/ });
    expect(thinking).toHaveAttribute("aria-expanded", "true");

    harness.state.streaming = false;
    rerender(
      <StudioRuntimeProvider>
        <Conversation />
      </StudioRuntimeProvider>,
    );

    await screen.findByRole("button", { name: /Thought for \d+s/ });
  });

  it("names the phase while a reply has no text yet", () => {
    harness.state.streaming = true;
    harness.state.thinkingPhase = "mcp_tools";
    const { container } = renderTurn([
      { id: "u-1", parentId: null, role: "user", content: "Check this bet" },
      { id: "a-1", parentId: "u-1", role: "assistant", content: "", parts: [] },
    ]);

    expect(screen.getByRole("status")).toHaveTextContent("Opening your studio tools");
    expect(container.querySelector(".message--assistant")).toHaveAttribute(
      "aria-busy",
      "true",
    );

    harness.state.streaming = false;
    harness.state.thinkingPhase = null;
  });

  it("marks a settled reply as no longer busy", () => {
    const { container } = renderTurn([
      { id: "u-1", parentId: null, role: "user", content: "Check this bet" },
      { id: "a-1", parentId: "u-1", role: "assistant", content: "A useful reply." },
    ]);

    expect(container.querySelector(".message--assistant")).toHaveAttribute(
      "aria-busy",
      "false",
    );
  });

  it("renders a source chip for what the turn read", () => {
    const { container } = renderTurn([
      {
        id: "m-1",
        parentId: null,
        role: "assistant",
        content: "One job.",
        parts: [
          { kind: "text", text: "One job." },
          {
            kind: "source",
            id: "src-1",
            title: "get_jobs — JOB-1 Retention",
            filename: "get_jobs",
            mediaType: "application/json",
          },
        ],
      },
    ]);

    const chip = container.querySelector(".source-chip");
    expect(chip?.textContent).toContain("get_jobs — JOB-1 Retention");
  });

  it("labels assistant actions and explains reply alternatives", () => {
    const { container } = renderTurn([
      { id: "u-1", parentId: null, role: "user", content: "Check this bet" },
      { id: "a-1", parentId: "u-1", role: "assistant", content: "A useful reply." },
    ]);

    expect(screen.getByRole("button", { name: "Copy reply" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Regenerate reply" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Edit message" })).toBeInTheDocument();
    expect(container.querySelector(".branch-picker")).toBeNull();
  });

  it("switches between contextual alternative replies through the thread runtime", () => {
    const firstPath: ChatMessage[] = [
      { id: "u-1", parentId: null, role: "user", content: "Check this bet" },
      { id: "a-1", parentId: "u-1", role: "assistant", content: "First reply." },
    ];
    harness.state.messages = firstPath;
    const { container, rerender } = render(
      <StudioRuntimeProvider>
        <Conversation />
      </StudioRuntimeProvider>,
    );

    expect(container.querySelector(".branch-picker")).toBeNull();

    harness.state.messages = [
      firstPath[0],
      { id: "a-2", parentId: "u-1", role: "assistant", content: "Alternative reply." },
    ];
    rerender(
      <StudioRuntimeProvider>
        <Conversation />
      </StudioRuntimeProvider>,
    );

    // The group is named, and the position stays readable text rather than
    // being replaced by an aria-label of its own.
    expect(screen.getByRole("group", { name: "Reply alternatives" })).toHaveTextContent(
      "Alternative 2 of 2",
    );
    const previous = screen.getByRole("button", { name: "Previous alternative" });
    expect(screen.getByRole("button", { name: "Next alternative" })).toBeInTheDocument();
    expect(previous).not.toBeDisabled();
    fireEvent.click(previous);
    expect(harness.state.switchBranch).toHaveBeenCalledWith(firstPath);
  });

  it("turns a card action into the user's next message", () => {
    harness.state.sendMessage = vi.fn<(text: string) => Promise<void>>();
    renderTurn([
      {
        id: "m-1",
        parentId: null,
        role: "assistant",
        content: "",
        parts: [{ kind: "ui", id: "ui-1", node: outcomeCard(true) }],
      },
    ]);

    fireEvent.click(document.querySelector("button.ui-action") as HTMLButtonElement);

    expect(harness.state.sendMessage).toHaveBeenCalledWith("Simulate O-1");
  });
});

describe("Conversation failures", () => {
  it("shows the failure, the suggestion, and a retry that re-sends the question", () => {
    harness.state.sendMessage = vi.fn<(text: string) => Promise<void>>();
    const { container } = renderTurn([
      { id: "m-1", parentId: null, role: "user", content: "list the jobs" },
      {
        id: "m-2",
        parentId: "m-1",
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
