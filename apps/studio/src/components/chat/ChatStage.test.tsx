import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { ChatMessage } from "../../types";
import { ChatStage } from "./ChatStage";

const harness = vi.hoisted(() => ({
  state: {
    messages: [] as unknown[],
    streaming: false,
    thinkingPhase: null as string | null,
    offlineReply: false,
    setupOpen: false,
    canvas: null as unknown,
    brief: null as unknown,
    settings: { base_url: "", api_key: "", model_name: "m", mcp_url: "" },
    llmHealth: { healthy: true, message: "" },
    mcpReachable: true,
    sendMessage: vi.fn(),
    stopStreaming: vi.fn(),
    openPanel: vi.fn(),
    closePanel: vi.fn(),
    clearChat: vi.fn(),
    pushNotice: vi.fn(),
    pushToast: vi.fn(),
    openSetup: vi.fn(),
    connectorSuggestions: [] as string[],
    presets: [] as unknown[],
    dismissConnectorSuggestion: vi.fn(),
    refreshConnectors: vi.fn(),
  },
}));

vi.mock("../../state/StudioContext", () => ({
  useStudio: () => harness.state,
}));
vi.mock("./Hero", () => ({ Hero: () => <div data-testid="hero" /> }));
vi.mock("./OfflineNotice", () => ({ OfflineNotice: () => null }));
vi.mock("../setup/SetupConversation", () => ({
  SetupConversation: () => <div data-testid="setup" />,
}));

function setMessages(messages: ChatMessage[], streaming = false) {
  harness.state.messages = messages;
  harness.state.streaming = streaming;
}

function announcedText(container: HTMLElement): string {
  return Array.from(container.querySelectorAll('[role="status"][aria-live="polite"]'))
    .map((region) => region.textContent ?? "")
    .join("");
}

describe("ChatStage transcript", () => {
  beforeEach(() => {
    harness.state.streaming = false;
    harness.state.setupOpen = false;
    harness.state.messages = [] as unknown[];
    harness.state.stopStreaming = vi.fn();
  });

  it("exposes the transcript as a focusable, non-live log", () => {
    setMessages([{ role: "assistant", content: "Ready." }]);

    render(<ChatStage />);

    const log = screen.getByRole("log", { name: "Conversation transcript" });
    expect(log).toHaveAttribute("tabindex", "0");
    // Token-by-token announcements are replaced by one settled-turn announcer.
    expect(log).toHaveAttribute("aria-live", "off");
    expect(log).toHaveAttribute("aria-busy", "false");
  });

  it("marks the log busy while a reply streams", () => {
    setMessages([{ role: "assistant", content: "Partial" }], true);

    render(<ChatStage />);

    expect(screen.getByRole("log", { name: "Conversation transcript" })).toHaveAttribute(
      "aria-busy",
      "true",
    );
  });

  it("announces a settled reply once, as speech rather than Markdown", () => {
    setMessages([{ role: "user", content: "how are my outcomes" }]);
    const { container, rerender } = render(<ChatStage />);
    expect(announcedText(container)).not.toContain("Studio replied");

    setMessages([
      { role: "user", content: "how are my outcomes" },
      { role: "assistant", content: "**Scored** three outcomes." },
    ]);
    rerender(<ChatStage />);

    const spoken = announcedText(container);
    expect(spoken).toContain("Studio replied: Scored three outcomes.");
    expect(spoken).not.toContain("**");
  });

  it("does not re-read history when the stage remounts", () => {
    setMessages([{ role: "assistant", content: "An earlier answer." }]);

    const { container } = render(<ChatStage />);

    expect(announcedText(container)).not.toContain("An earlier answer.");
  });

  it("says nothing while the reply is still streaming", () => {
    setMessages([{ role: "assistant", content: "Still writing" }], true);

    const { container } = render(<ChatStage />);

    expect(announcedText(container)).not.toContain("Studio replied");
  });

  it("announces each new turn without repeating the previous one", () => {
    setMessages([{ role: "user", content: "first question" }]);
    const { container, rerender } = render(<ChatStage />);

    setMessages([
      { role: "user", content: "first question" },
      { role: "assistant", content: "First answer." },
    ]);
    rerender(<ChatStage />);
    expect(announcedText(container)).toContain("First answer.");

    setMessages([
      { role: "user", content: "first question" },
      { role: "assistant", content: "First answer." },
      { role: "assistant", content: "Second answer." },
    ]);
    rerender(<ChatStage />);

    const spoken = announcedText(container);
    expect(spoken).toContain("Second answer.");
    expect(spoken).not.toContain("First answer.");
  });

  it("offers a jump control when the reader scrolled back, and returns focus to the log", () => {
    setMessages([
      { role: "assistant", content: "A long answer." },
      { role: "assistant", content: "An even longer answer." },
    ]);

    const { container } = render(<ChatStage />);
    const log = screen.getByRole("log", { name: "Conversation transcript" }) as HTMLDivElement;
    Object.defineProperty(log, "scrollHeight", { value: 1000, configurable: true });
    Object.defineProperty(log, "clientHeight", { value: 400, configurable: true });
    Object.defineProperty(log, "scrollTop", { value: 0, writable: true, configurable: true });

    fireEvent.scroll(log);

    const jump = screen.getByRole("button", { name: /jump to latest/i });
    expect(jump).toBeInTheDocument();

    fireEvent.click(jump);

    expect(log.scrollTop).toBe(1000);
    expect(log).toHaveFocus();
    expect(
      screen.queryByRole("button", { name: /jump to latest/i }),
    ).not.toBeInTheDocument();
    expect(container.querySelector(".chat__scroll")).toBe(log);
  });

  it("keeps the jump control out of the way when the reader is at the bottom", () => {
    setMessages([{ role: "assistant", content: "Short answer." }]);

    render(<ChatStage />);

    expect(screen.queryByRole("button", { name: /jump to latest/i })).not.toBeInTheDocument();
  });
});

describe("ChatStage composer", () => {
  beforeEach(() => {
    harness.state.streaming = false;
    harness.state.messages = [] as unknown[];
    harness.state.stopStreaming = vi.fn();
  });

  it("stops the run with Escape while a reply streams", () => {
    setMessages([{ role: "assistant", content: "" }], true);
    render(<ChatStage />);

    fireEvent.keyDown(screen.getByLabelText("Message the studio"), { key: "Escape" });

    expect(harness.state.stopStreaming).toHaveBeenCalled();
  });

  it("lets Escape alone when nothing is streaming", () => {
    render(<ChatStage />);

    fireEvent.keyDown(screen.getByLabelText("Message the studio"), { key: "Escape" });

    expect(harness.state.stopStreaming).not.toHaveBeenCalled();
  });
});
