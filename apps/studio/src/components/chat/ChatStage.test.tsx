import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { StudioRuntimeProvider } from "../../assistant/StudioRuntime";
import type { ChatMessage } from "../../types";
import { ChatStage } from "./ChatStage";

const harness = vi.hoisted(() => ({
  state: {
    messages: [] as unknown[],
    streaming: false,
    thinkingPhase: null as string | null,
    toolActivity: [] as unknown[],
    offlineReplyFor: null as string | null,
    sendMessage: vi.fn<(text: string) => Promise<void>>(),
    regenerateFrom: vi.fn<(messageId: string | null) => Promise<void>>(),
    editFrom: vi.fn<(messageId: string | null, text: string) => Promise<void>>(),
    switchBranch: vi.fn(),
    respondToApproval: vi.fn<(approvalId: string, approved: boolean) => Promise<void>>(),
    stopStreaming: vi.fn(),
    openPanel: vi.fn(),
    closePanel: vi.fn(),
    clearChat: vi.fn(),
    pushNotice: vi.fn(),
    openSetup: vi.fn(),
    setupOpen: false,
    canvas: null as unknown,
    brief: null as unknown,
    settings: { base_url: "http://llm", api_key: "k", model_name: "m", mcp_url: "http://mcp" },
    mcpReachable: true,
    llmHealth: { healthy: true, message: "ok" },
    connectorSuggestions: [] as string[],
    presets: [] as unknown[],
    dismissConnectorSuggestion: vi.fn(),
    refreshConnectors: vi.fn(),
    pushToast: vi.fn(),
  },
}));

vi.mock("../../state/StudioContext", () => ({
  useStudio: () => harness.state,
}));

// The stage is rendered without the shell here, so the tour stays off; the
// onboarding flow itself has its own suite.
vi.mock("../../onboarding/context", () => ({
  useOnboarding: () => ({ enabled: false, openTour: vi.fn() }),
}));

const FAILED_TURN: ChatMessage[] = [
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
];

describe("ChatStage", () => {
  afterEach(() => {
    harness.state.messages = [];
    harness.state.streaming = false;
    vi.restoreAllMocks();
  });

  it("shows a jump-to-latest control when the viewport is detached during a run", async () => {
    harness.state.messages = [
      { id: "u-1", parentId: null, role: "user", content: "An older question" },
      { id: "a-1", parentId: "u-1", role: "assistant", content: "An older answer" },
      { id: "u-2", parentId: "a-1", role: "user", content: "A new question" },
      { id: "a-2", parentId: "u-2", role: "assistant", content: "A live answer" },
    ];
    harness.state.streaming = true;
    const { container, rerender } = render(
      <StudioRuntimeProvider>
        <ChatStage />
      </StudioRuntimeProvider>,
    );

    const viewport = container.querySelector(".chat__scroll") as HTMLDivElement;
    expect(screen.queryByRole("button", { name: /latest/i })).toBeNull();
    Object.defineProperty(viewport, "scrollHeight", { configurable: true, value: 1200 });
    Object.defineProperty(viewport, "clientHeight", { configurable: true, value: 400 });
    Object.defineProperty(viewport, "scrollTop", { configurable: true, value: 800, writable: true });
    viewport.dispatchEvent(new Event("wheel", { bubbles: true }));
    fireEvent.scroll(viewport);

    viewport.scrollTop = 200;
    fireEvent.scroll(viewport);
    await waitFor(() =>
      expect(screen.getByRole("button", { name: /latest/i })).toBeInTheDocument(),
    );

    Object.defineProperty(viewport, "scrollHeight", { configurable: true, value: 1500 });
    harness.state.messages = [
      { id: "u-1", parentId: null, role: "user", content: "An older question" },
      { id: "a-1", parentId: "u-1", role: "assistant", content: "An older answer" },
      { id: "u-2", parentId: "a-1", role: "user", content: "A new question" },
      { id: "a-2", parentId: "u-2", role: "assistant", content: "A live answer with another streamed delta" },
    ];
    rerender(
      <StudioRuntimeProvider>
        <ChatStage />
      </StudioRuntimeProvider>,
    );

    await waitFor(() =>
      expect(screen.getByRole("button", { name: /latest/i })).toBeInTheDocument(),
    );
    expect(viewport.scrollTop).toBe(200);
  });

  it("counts the turns that arrived while the reader was scrolled up", async () => {
    harness.state.messages = [
      { id: "u-1", parentId: null, role: "user", content: "An older question" },
      { id: "a-1", parentId: "u-1", role: "assistant", content: "An older answer" },
      { id: "u-2", parentId: "a-1", role: "user", content: "A new question" },
      { id: "a-2", parentId: "u-2", role: "assistant", content: "A live answer" },
    ];
    harness.state.streaming = true;
    const { container, rerender } = render(
      <StudioRuntimeProvider>
        <ChatStage />
      </StudioRuntimeProvider>,
    );

    const viewport = container.querySelector(".chat__scroll") as HTMLDivElement;
    Object.defineProperty(viewport, "scrollHeight", { configurable: true, value: 1200 });
    Object.defineProperty(viewport, "clientHeight", { configurable: true, value: 400 });
    Object.defineProperty(viewport, "scrollTop", { configurable: true, value: 800, writable: true });
    viewport.dispatchEvent(new Event("wheel", { bubbles: true }));
    fireEvent.scroll(viewport);
    viewport.scrollTop = 200;
    fireEvent.scroll(viewport);

    // Two whole turns land while the reader is away: the count says two.
    harness.state.messages = [
      ...harness.state.messages,
      { id: "u-3", parentId: "a-2", role: "user", content: "Another question" },
      { id: "a-3", parentId: "u-3", role: "assistant", content: "Another answer" },
    ];
    rerender(
      <StudioRuntimeProvider>
        <ChatStage />
      </StudioRuntimeProvider>,
    );

    const pill = await screen.findByRole("button", { name: "2 new ↓" });
    expect(pill).toBeInTheDocument();
    // The polite region states the count once, in words.
    expect(screen.getByRole("status", { name: "New replies" })).toHaveTextContent("2 new messages");
  });

  it("does not inflate the count while one turn streams token by token", async () => {
    harness.state.messages = [
      { id: "u-1", parentId: null, role: "user", content: "An older question" },
      { id: "a-1", parentId: "u-1", role: "assistant", content: "An older answer" },
      { id: "u-2", parentId: "a-1", role: "user", content: "A new question" },
      { id: "a-2", parentId: "u-2", role: "assistant", content: "A live answer" },
    ];
    harness.state.streaming = true;
    const { container, rerender } = render(
      <StudioRuntimeProvider>
        <ChatStage />
      </StudioRuntimeProvider>,
    );

    const viewport = container.querySelector(".chat__scroll") as HTMLDivElement;
    Object.defineProperty(viewport, "scrollHeight", { configurable: true, value: 1200 });
    Object.defineProperty(viewport, "clientHeight", { configurable: true, value: 400 });
    Object.defineProperty(viewport, "scrollTop", { configurable: true, value: 800, writable: true });
    viewport.dispatchEvent(new Event("wheel", { bubbles: true }));
    fireEvent.scroll(viewport);
    viewport.scrollTop = 200;
    fireEvent.scroll(viewport);

    // One turn arrives, then grows: same message id, longer content.
    harness.state.messages = [
      ...harness.state.messages,
      { id: "u-3", parentId: "a-2", role: "user", content: "Another question" },
    ];
    rerender(
      <StudioRuntimeProvider>
        <ChatStage />
      </StudioRuntimeProvider>,
    );
    await screen.findByRole("button", { name: "1 new ↓" });

    harness.state.messages = [
      ...harness.state.messages,
      { id: "a-3", parentId: "u-3", role: "assistant", content: "Another answer, first delta" },
    ];
    rerender(
      <StudioRuntimeProvider>
        <ChatStage />
      </StudioRuntimeProvider>,
    );
    harness.state.messages = [
      ...harness.state.messages.slice(0, -1),
      { id: "a-3", parentId: "u-3", role: "assistant", content: "Another answer, first delta plus more" },
    ];
    rerender(
      <StudioRuntimeProvider>
        <ChatStage />
      </StudioRuntimeProvider>,
    );

    // The streamed turn is one arrival, not one per delta.
    const pill = await screen.findByRole("button", { name: "2 new ↓" });
    expect(pill).toBeInTheDocument();
  });

  it("clears the count when the reader returns to the bottom", async () => {
    harness.state.messages = [
      { id: "u-1", parentId: null, role: "user", content: "An older question" },
      { id: "a-1", parentId: "u-1", role: "assistant", content: "An older answer" },
      { id: "u-2", parentId: "a-1", role: "user", content: "A new question" },
      { id: "a-2", parentId: "u-2", role: "assistant", content: "A live answer" },
    ];
    harness.state.streaming = true;
    const { container, rerender } = render(
      <StudioRuntimeProvider>
        <ChatStage />
      </StudioRuntimeProvider>,
    );

    const viewport = container.querySelector(".chat__scroll") as HTMLDivElement;
    Object.defineProperty(viewport, "scrollHeight", { configurable: true, value: 1200 });
    Object.defineProperty(viewport, "clientHeight", { configurable: true, value: 400 });
    Object.defineProperty(viewport, "scrollTop", { configurable: true, value: 800, writable: true });
    viewport.dispatchEvent(new Event("wheel", { bubbles: true }));
    fireEvent.scroll(viewport);
    viewport.scrollTop = 200;
    fireEvent.scroll(viewport);

    harness.state.messages = [
      ...harness.state.messages,
      { id: "u-3", parentId: "a-2", role: "user", content: "Another question" },
    ];
    rerender(
      <StudioRuntimeProvider>
        <ChatStage />
      </StudioRuntimeProvider>,
    );
    await screen.findByRole("button", { name: "1 new ↓" });

    // Scrolling back to the bottom hides the pill and empties the announcement.
    viewport.scrollTop = 800;
    fireEvent.scroll(viewport);

    await waitFor(() =>
      expect(screen.queryByRole("button", { name: /latest/i })).toBeNull(),
    );
    expect(screen.getByRole("status", { name: "New replies" })).toHaveTextContent("");
  });

  it("returns the viewport to the bottom when the jump-to-latest control is selected", async () => {
    harness.state.messages = [
      { id: "u-1", parentId: null, role: "user", content: "An older question" },
      { id: "a-1", parentId: "u-1", role: "assistant", content: "An older answer" },
      { id: "u-2", parentId: "a-1", role: "user", content: "A new question" },
      { id: "a-2", parentId: "u-2", role: "assistant", content: "A live answer" },
    ];
    harness.state.streaming = true;
    const { container } = render(
      <StudioRuntimeProvider>
        <ChatStage />
      </StudioRuntimeProvider>,
    );

    const viewport = container.querySelector(".chat__scroll") as HTMLDivElement;
    Object.defineProperty(viewport, "scrollHeight", { configurable: true, value: 1200 });
    Object.defineProperty(viewport, "clientHeight", { configurable: true, value: 400 });
    Object.defineProperty(viewport, "scrollTop", { configurable: true, value: 0, writable: true });
    viewport.scrollTop = 800;
    viewport.dispatchEvent(new Event("wheel", { bubbles: true }));
    fireEvent.scroll(viewport);
    const scrollTo = vi.fn((options?: ScrollToOptions) => {
      viewport.scrollTop = Math.min(
        options?.top ?? 0,
        viewport.scrollHeight - viewport.clientHeight,
      );
      fireEvent.scroll(viewport);
    });
    Object.defineProperty(viewport, "scrollTo", { configurable: true, value: scrollTo });
    viewport.scrollTop = 200;
    fireEvent.scroll(viewport);
    const latestButton = await screen.findByRole("button", { name: /latest/i });

    fireEvent.click(latestButton);
    expect(scrollTo).toHaveBeenCalledWith({ top: 1200, behavior: "smooth" });
    await waitFor(() => expect(viewport.scrollTop).toBe(800));
    expect(screen.queryByRole("button", { name: /latest/i })).toBeNull();
  });

  it("returns to the live end without animating when reduced motion is preferred", async () => {
    const originalMatchMedia = window.matchMedia;
    Object.defineProperty(window, "matchMedia", {
      configurable: true,
      writable: true,
      value: (query: string) => ({
        matches: query.includes("prefers-reduced-motion"),
        media: query,
        onchange: null,
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        addListener: vi.fn(),
        removeListener: vi.fn(),
        dispatchEvent: vi.fn(() => false),
      }),
    });

    try {
      harness.state.messages = [
        { id: "u-1", parentId: null, role: "user", content: "An older question" },
        { id: "a-1", parentId: "u-1", role: "assistant", content: "An older answer" },
      ];
      const { container } = render(
        <StudioRuntimeProvider>
          <ChatStage />
        </StudioRuntimeProvider>,
      );

      const viewport = container.querySelector(".chat__scroll") as HTMLDivElement;
      Object.defineProperty(viewport, "scrollHeight", { configurable: true, value: 1200 });
      Object.defineProperty(viewport, "clientHeight", { configurable: true, value: 400 });
      Object.defineProperty(viewport, "scrollTop", { configurable: true, value: 800, writable: true });
      viewport.dispatchEvent(new Event("wheel", { bubbles: true }));
      fireEvent.scroll(viewport);
      const scrollTo = vi.fn();
      Object.defineProperty(viewport, "scrollTo", { configurable: true, value: scrollTo });
      viewport.scrollTop = 200;
      fireEvent.scroll(viewport);

      const latestButton = await screen.findByRole("button", { name: /latest/i });
      fireEvent.click(latestButton);

      expect(scrollTo).toHaveBeenCalledWith({ top: 1200, behavior: "auto" });
    } finally {
      Object.defineProperty(window, "matchMedia", {
        configurable: true,
        writable: true,
        value: originalMatchMedia,
      });
    }
  });

  it("lets a keyboard reader reach the pill and press it without stealing focus", async () => {
    harness.state.messages = [
      { id: "u-1", parentId: null, role: "user", content: "An older question" },
      { id: "a-1", parentId: "u-1", role: "assistant", content: "An older answer" },
      { id: "u-2", parentId: "a-1", role: "user", content: "A new question" },
      { id: "a-2", parentId: "u-2", role: "assistant", content: "A live answer" },
    ];
    harness.state.streaming = true;
    const { container } = render(
      <StudioRuntimeProvider>
        <ChatStage />
      </StudioRuntimeProvider>,
    );

    // A reader is typing in the composer when the pill appears.
    const textbox = screen.getByRole("textbox");
    textbox.focus();
    expect(textbox).toHaveFocus();

    const viewport = container.querySelector(".chat__scroll") as HTMLDivElement;
    Object.defineProperty(viewport, "scrollHeight", { configurable: true, value: 1200 });
    Object.defineProperty(viewport, "clientHeight", { configurable: true, value: 400 });
    Object.defineProperty(viewport, "scrollTop", { configurable: true, value: 800, writable: true });
    viewport.dispatchEvent(new Event("wheel", { bubbles: true }));
    fireEvent.scroll(viewport);
    const scrollTo = vi.fn();
    Object.defineProperty(viewport, "scrollTo", { configurable: true, value: scrollTo });
    viewport.scrollTop = 200;
    fireEvent.scroll(viewport);

    const pill = await screen.findByRole("button", { name: /latest/i });
    // Mounting the pill never moves focus away from where the reader was.
    expect(pill).not.toHaveFocus();
    expect(textbox).toHaveFocus();

    // It is a real button: focusable and pressable with the keyboard.
    pill.focus();
    expect(pill).toHaveFocus();
    fireEvent.keyDown(pill, { key: "Enter" });
    fireEvent.click(pill);
    expect(scrollTo).toHaveBeenCalled();
  });

  it("keeps the pill free of any pulse so reduced-motion users see a still control", async () => {
    // The pill's only motion is the scroll it triggers; it carries no
    // animation of its own, which is what the theme's reduced-motion block
    // would otherwise have to neutralise.
    const themeCss = await import("../../styles/theme.css?raw");
    const start = themeCss.default.indexOf(".chat__latest {");
    const block = themeCss.default.slice(start, themeCss.default.indexOf("}", start));
    expect(block).not.toMatch(/animation\s*:/);
  });

  it("renders the failure as an error surface instead of an empty chat", () => {
    const errorLog = vi.spyOn(console, "error").mockImplementation(() => {});
    harness.state.messages = FAILED_TURN;

    const { container } = render(
      <StudioRuntimeProvider>
        <ChatStage />
      </StudioRuntimeProvider>,
    );

    expect(container.querySelector(".chat--empty")).toBeNull();
    expect(screen.getByRole("alert")).toHaveTextContent("The MCP server is unreachable.");
    expect(container.textContent).toContain("list the jobs");
    expect(container.textContent).toContain("req-1");
    expect(errorLog).not.toHaveBeenCalled();
  });

  it("keeps the composer usable after a failed turn so the question can be retried", () => {
    const errorLog = vi.spyOn(console, "error").mockImplementation(() => {});
    harness.state.messages = FAILED_TURN;

    render(
      <StudioRuntimeProvider>
        <ChatStage />
      </StudioRuntimeProvider>,
    );

    expect(screen.getByRole("button", { name: /retry/i })).toBeInTheDocument();
    expect(screen.getByRole("textbox")).toBeInTheDocument();
    expect(errorLog).not.toHaveBeenCalled();
  });

  it("docks the records lens when the palette runs /records", () => {
    harness.state.openPanel.mockClear();

    render(
      <StudioRuntimeProvider>
        <ChatStage />
      </StudioRuntimeProvider>,
    );

    const input = screen.getByRole("textbox");
    fireEvent.change(input, { target: { value: "/records" } });
    fireEvent.keyDown(input, { key: "Enter" });

    expect(harness.state.openPanel).toHaveBeenCalledWith("records");
  });

  it("docks the decision brief when the palette runs /brief", () => {
    harness.state.openPanel.mockClear();

    render(
      <StudioRuntimeProvider>
        <ChatStage />
      </StudioRuntimeProvider>,
    );

    const input = screen.getByRole("textbox");
    fireEvent.change(input, { target: { value: "/brief" } });
    fireEvent.keyDown(input, { key: "Enter" });

    expect(harness.state.openPanel).toHaveBeenCalledWith("brief");
  });

  it("shows the sample loop on the empty stage, above the composer", () => {
    window.localStorage.clear();

    const { container } = render(
      <StudioRuntimeProvider>
        <ChatStage />
      </StudioRuntimeProvider>,
    );

    const strip = screen.getByLabelText("Sample loop, not your data");
    expect(strip).toBeInTheDocument();
    // It sits inside the welcome block, so it scrolls with the hero and never
    // covers the composer.
    expect(container.querySelector(".chat__welcome-inner .sample-loop")).not.toBeNull();
  });

  it("hands the composer focus and a placeholder without sending anything", () => {
    window.localStorage.clear();
    harness.state.sendMessage.mockClear();

    render(
      <StudioRuntimeProvider>
        <ChatStage />
      </StudioRuntimeProvider>,
    );

    fireEvent.click(screen.getByRole("button", { name: "Start with my own" }));

    const input = screen.getByRole("textbox") as HTMLTextAreaElement;
    expect(input).toHaveFocus();
    expect(input.placeholder).toBe("Paste a customer quote to begin.");
    expect(input.value).toBe("");
    expect(harness.state.sendMessage).not.toHaveBeenCalled();
  });

  it("drops the sample loop once the thread has a message", () => {
    window.localStorage.clear();
    harness.state.messages = [
      { id: "u-1", parentId: null, role: "user", content: "What should I chase?" },
      { id: "a-1", parentId: "u-1", role: "assistant", content: "Start with the job." },
    ];

    render(
      <StudioRuntimeProvider>
        <ChatStage />
      </StudioRuntimeProvider>,
    );

    expect(screen.queryByLabelText("Sample loop, not your data")).toBeNull();
  });

  it("stays out of the way while the introduction is open", () => {
    window.localStorage.clear();
    harness.state.setupOpen = true;

    try {
      render(
        <StudioRuntimeProvider>
          <ChatStage />
        </StudioRuntimeProvider>,
      );

      // One first impression at a time: the introduction speaks first, and the
      // sample waits for the stage to be otherwise empty.
      expect(screen.queryByLabelText("Sample loop, not your data")).toBeNull();
    } finally {
      harness.state.setupOpen = false;
    }
  });
});
