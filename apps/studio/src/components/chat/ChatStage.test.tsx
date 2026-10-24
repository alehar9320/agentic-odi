import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

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
];

describe("ChatStage stream failures", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders the failure as an error surface instead of an empty chat", () => {
    const errorLog = vi.spyOn(console, "error").mockImplementation(() => {});
    harness.state.messages = FAILED_TURN;

    const { container } = render(<ChatStage />);

    expect(container.querySelector(".chat--empty")).toBeNull();
    expect(screen.getByRole("alert")).toHaveTextContent("The MCP server is unreachable.");
    expect(container.textContent).toContain("list the jobs");
    expect(container.textContent).toContain("req-1");
    expect(errorLog).not.toHaveBeenCalled();
  });

  it("keeps the composer usable after a failed turn so the question can be retried", () => {
    const errorLog = vi.spyOn(console, "error").mockImplementation(() => {});
    harness.state.messages = FAILED_TURN;

    render(<ChatStage />);

    expect(screen.getByRole("button", { name: /retry/i })).toBeInTheDocument();
    expect(screen.getByRole("textbox")).toBeInTheDocument();
    expect(errorLog).not.toHaveBeenCalled();
  });
});
