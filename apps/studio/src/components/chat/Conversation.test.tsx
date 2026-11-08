import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { StudioRuntimeProvider } from "../../assistant/StudioRuntime";
import { formatClockTime } from "../../lib/relativeTime";
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
    offlineReplyFor: null as string | null,
    openPanel: vi.fn<(panel: string) => void>(),
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

// The clamp reads real layout, which jsdom does not compute. Each test that
// stubs it registers the way back here, so no later test inherits a fake height.
let restoreLayout: (() => void) | null = null;

afterEach(() => {
  restoreLayout?.();
  restoreLayout = null;
});

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
  it("names the provenance on the one reply that needs it and offers the fix", () => {
    harness.state.offlineReplyFor = "m-2";
    const { container } = renderTurn([
      {
        id: "m-1",
        parentId: null,
        role: "assistant",
        content: "From the model.",
        parts: [{ kind: "text", text: "From the model." }],
      },
      {
        id: "m-2",
        parentId: null,
        role: "assistant",
        content: "",
        parts: [{ kind: "ui", id: "ui-1", node: outcomeCard() }],
      },
    ]);

    const chips = container.querySelectorAll("button.message__tag");
    expect(chips).toHaveLength(1);
    expect(chips[0]).toHaveTextContent("Local draft, no model connected");

    fireEvent.click(chips[0] as HTMLButtonElement);
    expect(harness.state.openPanel).toHaveBeenCalledWith("settings");

    harness.state.offlineReplyFor = null;
    harness.state.openPanel.mockClear();
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
  it("clamps a pasted document behind a keyboard-reachable Show more (#696)", () => {
    Object.defineProperty(HTMLElement.prototype, "scrollHeight", {
      configurable: true,
      get: () => 400,
    });
    Object.defineProperty(HTMLElement.prototype, "clientHeight", {
      configurable: true,
      get: () => 128,
    });
    // Both stubs shadow jsdom's Element getters; deleting the own properties on
    // HTMLElement.prototype puts the real measurement back for later tests.
    restoreLayout = () => {
      delete (HTMLElement.prototype as unknown as Record<string, unknown>).scrollHeight;
      delete (HTMLElement.prototype as unknown as Record<string, unknown>).clientHeight;
    };

    const paste = Array.from({ length: 30 }, (_, index) => `Line ${index + 1} of a pasted doc`).join(
      "\n",
    );
    renderTurn([{ id: "m-1", parentId: null, role: "user", content: paste }]);

    const bubble = document.querySelector(".message__bubble") as HTMLElement;
    expect(bubble).toHaveClass("is-clamped");

    const more = screen.getByRole("button", { name: "Show more" });
    expect(more).toHaveAttribute("aria-expanded", "false");

    fireEvent.click(more);

    expect(screen.getByRole("button", { name: "Show less" })).toHaveAttribute(
      "aria-expanded",
      "true",
    );
    expect(bubble).not.toHaveClass("is-clamped");
    // Clamping is presentation: the whole message is still the message, so Copy
    // (which reads the turn, not the bubble) copies all of it.
    expect(bubble.textContent).toContain("Line 30 of a pasted doc");
    expect(screen.getByRole("button", { name: "Copy message" })).toBeInTheDocument();

  });

  it("leaves a short message alone, with no control to expand (#696)", () => {
    renderTurn([{ id: "m-1", parentId: null, role: "user", content: "Short question." }]);

    expect(document.querySelector(".message__bubble")).not.toHaveClass("is-clamped");
    expect(screen.queryByRole("button", { name: /show more/i })).toBeNull();
  });

});

describe("transcript day dividers (#694 D14)", () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  it("puts one separator between calendar days and none inside a day", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date(2026, 9, 22, 9, 0));
    try {
      renderTurn([
        {
          id: "u-1",
          parentId: null,
          role: "user",
          content: "Before midnight",
          createdAt: new Date(2026, 9, 21, 23, 50).toISOString(),
        },
        {
          id: "a-1",
          parentId: "u-1",
          role: "assistant",
          content: "Still the same evening",
          createdAt: new Date(2026, 9, 21, 23, 55).toISOString(),
        },
        {
          id: "u-2",
          parentId: "a-1",
          role: "user",
          content: "After midnight",
          createdAt: new Date(2026, 9, 22, 0, 10).toISOString(),
        },
      ]);

      const separators = screen.getAllByRole("separator");
      expect(separators).toHaveLength(1);
      expect(separators[0]).toHaveAttribute("aria-label", "Today");
    } finally {
      vi.useRealTimers();
    }
  });

  it("separates nothing when a thread stays inside one day", () => {
    renderTurn([
      {
        id: "u-1",
        parentId: null,
        role: "user",
        content: "Morning",
        createdAt: new Date(2026, 8, 3, 9, 0).toISOString(),
      },
      {
        id: "a-1",
        parentId: "u-1",
        role: "assistant",
        content: "Afternoon",
        createdAt: new Date(2026, 8, 3, 15, 0).toISOString(),
      },
    ]);

    expect(screen.queryAllByRole("separator")).toHaveLength(0);
  });
});

describe("message timestamps (#694 D15)", () => {
  it("keeps the exact time off the page until the message is asked for", () => {
    const at = new Date(2026, 9, 22, 9, 30).toISOString();
    const clock = formatClockTime(at);

    renderTurn([
      { id: "u-1", parentId: null, role: "user", content: "A question", createdAt: at },
      { id: "a-1", parentId: "u-1", role: "assistant", content: "An answer", createdAt: at },
    ]);

    const times = Array.from(document.querySelectorAll("time.message__time")) as HTMLTimeElement[];
    expect(times).toHaveLength(2);
    for (const time of times) {
      expect(time).toHaveAttribute("datetime", at);
      expect(time.textContent).toBe(clock);
      // It lives with the actions, which the stylesheet only reveals on hover
      // or focus, so it is never on the page at rest.
      expect(time.closest(".message__actions")).not.toBeNull();
    }

    expect(screen.getByRole("group", { name: `Reply actions, ${clock}` })).toBeInTheDocument();
    expect(screen.getByRole("group", { name: `Message actions, ${clock}` })).toBeInTheDocument();
  });
});
