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

    const text = (container.querySelector(".conversation") as HTMLElement).textContent ?? "";
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

describe("Conversation offline context", () => {
  it("marks a content-less offline turn as local guidance", () => {
    harness.state.offlineReply = true;
    const { container } = renderTurn([
      {
        id: "m-1",
        parentId: null,
        role: "assistant",
        content: "",
        parts: [{ kind: "ui", id: "ui-1", node: outcomeCard() }],
      },
    ]);

    expect(screen.getByText("Local guidance")).toBeInTheDocument();
    expect(container.querySelector(".message__tag")).not.toBeNull();
    harness.state.offlineReply = false;
  });
});


describe("Conversation live regions", () => {
  it("announces tool traces politely as they arrive without making the log live", () => {
    const { container } = renderTurn([
      {
        id: "m-1",
        parentId: null,
        role: "assistant",
        content: "Working",
        parts: [
          { kind: "text", text: "Working" },
          { kind: "tool", id: "call-1", name: "list_jobs", status: "ok" },
        ],
      },
    ]);

    const trace = container.querySelector(".tool-trace") as HTMLElement;
    expect(trace.textContent).toContain("list jobs");
    expect(screen.getByRole("log", { name: "Conversation" })).not.toHaveAttribute("aria-live");
  });

  it("announces only the newest reply, not the history", () => {
    renderTurn([
      { id: "u-1", parentId: null, role: "user", content: "Check this bet" },
      { id: "a-1", parentId: "u-1", role: "assistant", content: "An older reply." },
      { id: "a-2", parentId: "u-1", role: "assistant", content: "The newest reply." },
    ]);

    const status = screen.getByRole("status");
    expect(status).toHaveTextContent("The newest reply.");
    expect(status).not.toHaveTextContent("An older reply.");
    expect(status).not.toHaveTextContent("Check this bet");
  });

  it("holds the live region while a reply streams, then announces it settled", () => {
    harness.state.streaming = true;
    harness.state.thinkingPhase = "model";
    const messages: ChatMessage[] = [
      { id: "u-1", parentId: null, role: "user", content: "Check this bet" },
      { id: "a-1", parentId: "u-1", role: "assistant", content: "Half a reply" },
    ];
    harness.state.messages = messages;
    const { rerender } = render(
      <StudioRuntimeProvider>
        <Conversation />
      </StudioRuntimeProvider>,
    );

    const status = screen.getByRole("status");
    expect(status).toHaveAttribute("aria-busy", "true");
    expect(status).toHaveTextContent("Thinking");
    expect(status).not.toHaveTextContent("Half a reply");

    harness.state.streaming = false;
    harness.state.thinkingPhase = null;
    rerender(
      <StudioRuntimeProvider>
        <Conversation />
      </StudioRuntimeProvider>,
    );

    expect(screen.getByRole("status")).toHaveAttribute("aria-busy", "false");
    expect(screen.getByRole("status")).toHaveTextContent("Half a reply");
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

describe("Conversation run rows", () => {
  it("collapses a settled turn's calls into one row that expands into the cards", () => {
    harness.state.streaming = false;
    const { container } = renderTurn([
      {
        id: "m-1",
        parentId: null,
        role: "assistant",
        content: "Scored.",
        parts: [
          { kind: "text", text: "Scored." },
          { kind: "tool", id: "call-1", name: "list_jobs", status: "ok" },
          { kind: "tool", id: "call-2", name: "add_outcome", status: "ok" },
        ],
      },
    ]);

    expect(container.querySelectorAll(".run-summary")).toHaveLength(1);
    const toggle = container.querySelector(".run-summary__toggle") as HTMLElement;
    expect(toggle).toHaveAttribute("aria-expanded", "false");
    expect(toggle.textContent).toContain("2 calls · 1 write");
    expect(container.querySelectorAll(".tool-trace")).toHaveLength(2);

    fireEvent.click(toggle);
    expect(toggle).toHaveAttribute("aria-expanded", "true");
    expect(container.querySelector(".run-summary__panel")).not.toHaveAttribute("hidden");
  });

  it("renders no row for a turn that made no calls", () => {
    const { container } = renderTurn([
      {
        id: "m-1",
        parentId: null,
        role: "assistant",
        content: "No tools here.",
        parts: [{ kind: "text", text: "No tools here." }],
      },
    ]);

    expect(container.querySelector(".run-summary")).toBeNull();
    expect(container.querySelector(".conversation")).toHaveTextContent("No tools here.");
  });

  it("keeps the row open while the turn streams", () => {
    harness.state.streaming = true;
    const { container } = renderTurn([
      {
        id: "m-1",
        parentId: null,
        role: "assistant",
        content: "",
        parts: [{ kind: "tool", id: "call-1", name: "list_jobs", status: "running" }],
      },
    ]);

    expect(container.querySelector(".run-summary__toggle")).toHaveAttribute(
      "aria-expanded",
      "true",
    );

    harness.state.streaming = false;
  });

  it("will not hide a call that is still asking", () => {
    harness.state.streaming = false;
    const { container } = renderTurn([
      {
        id: "m-1",
        parentId: null,
        role: "assistant",
        content: "",
        parts: [
          {
            kind: "tool",
            id: "call-1",
            name: "add_job",
            status: "running",
            approval: { id: "ap-1", prompt: "Write this to your board?" },
          },
        ],
      },
    ]);

    expect(container.querySelector(".approval")).not.toBeNull();
    expect(container.querySelector(".run-summary__panel")).not.toHaveAttribute("hidden");
    const toggle = container.querySelector(".run-summary__toggle") as HTMLElement;
    expect(toggle).toHaveAttribute("aria-expanded", "true");
    expect(toggle).toHaveAttribute("disabled");
  });

  it("keeps prose and surfaces in order around the rows", () => {
    const { container } = renderTurn([
      {
        id: "m-1",
        parentId: null,
        role: "assistant",
        content: "Before. After.",
        parts: [
          { kind: "text", text: "Before." },
          { kind: "tool", id: "call-1", name: "list_jobs", status: "ok" },
          { kind: "text", text: "After." },
        ],
      },
    ]);

    const text = (container.querySelector(".conversation") as HTMLElement).textContent ?? "";
    expect(text.indexOf("Before.")).toBeLessThan(text.indexOf("1 call"));
    expect(text.indexOf("1 call")).toBeLessThan(text.indexOf("After."));
  });
});

describe("Conversation markup without calls", () => {
  /** Markup plus prose, with none of the generated ids that differ per render. */
  function shape(body: HTMLElement): string {
    const tags = [...body.querySelectorAll("*")]
      .map((el) => `${el.tagName.toLowerCase()} ${el.getAttribute("class") ?? ""}`)
      .join("\n");
    return `${tags}\ntext: ${body.textContent}`;
  }

  it("renders a call-free turn exactly as the transcript did before the run row", () => {
    harness.state.streaming = false;
    const { container } = renderTurn([
      {
        id: "m-1",
        parentId: null,
        role: "assistant",
        content: "Before.",
        parts: [
          { kind: "text", text: "Before." },
          { kind: "ui", id: "ui-1", node: outcomeCard(true) },
          { kind: "source", id: "s-1", title: "Call with Acme", mediaType: "text/markdown" },
        ],
      },
    ]);

    expect(shape(container.querySelector(".message__body") as HTMLElement)).toMatchInlineSnapshot(`
      "div md
      p md-paragraph
      div ui-surface
      article ui-card ui-card--outcome ui-card--urgent
      header ui-card__head
      span ui-card__id
      span ui-pill ui-pill--warning
      p ui-card__statement
      div ui-card__meters
      div ui-meter
      div ui-meter__head
      span 
      span ui-meter__value
      div ui-meter__track
      span ui-meter__fill ui-tone-bg--info
      div ui-meter
      div ui-meter__head
      span 
      span ui-meter__value
      div ui-meter__track
      span ui-meter__fill ui-tone-bg--warning
      p ui-card__formula
      b 
      div ui-actions
      button ui-action ui-action--primary
      button ui-action ui-action--ghost
      span source-chip
      span source-chip__label
      span source-chip__title
      div message__actions
      button quiet-action
      svg 
      rect 
      path 
      button quiet-action
      text: Before.O-1Underserved · 15.0Minimize the time it takes to propagate secretsImportance9/10Satisfaction today3/10Opportunity = importance + max(importance − satisfaction, 0) = 15.0Simulate this betFind evidenceSourceCall with AcmeCopyRegenerate"
    `);
  });
});
