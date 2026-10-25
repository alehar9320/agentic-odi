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
    offlineReply: false,
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

  it("shows a latest-message control when the viewport is detached during a run", async () => {
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
    expect(screen.queryByRole("button", { name: "Latest message" })).toBeNull();
    Object.defineProperty(viewport, "scrollHeight", { configurable: true, value: 1200 });
    Object.defineProperty(viewport, "clientHeight", { configurable: true, value: 400 });
    Object.defineProperty(viewport, "scrollTop", { configurable: true, value: 800, writable: true });
    viewport.dispatchEvent(new Event("wheel", { bubbles: true }));
    fireEvent.scroll(viewport);

    viewport.scrollTop = 200;
    fireEvent.scroll(viewport);
    await waitFor(() => expect(screen.getByRole("button", { name: "Latest message" })).toBeInTheDocument());

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

    await waitFor(() => expect(screen.getByRole("button", { name: "Latest message" })).toBeInTheDocument());
    expect(viewport.scrollTop).toBe(200);
  });

  it("returns the viewport to the bottom when the latest-message control is selected", async () => {
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
    const latestButton = await screen.findByRole("button", { name: "Latest message" });

    fireEvent.click(latestButton);
    expect(scrollTo).toHaveBeenCalledWith({ top: 1200, behavior: "smooth" });
    await waitFor(() => expect(viewport.scrollTop).toBe(800));
    expect(screen.queryByRole("button", { name: "Latest message" })).toBeNull();
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

      const latestButton = await screen.findByRole("button", { name: "Latest message" });
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
});
