import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { StudioRuntimeProvider } from "../../assistant/StudioRuntime";
import type { StudioContextValue } from "../../state/StudioContext";
import type { ChatMessage } from "../../types";
import { ThreadComposer } from "./ThreadComposer";

vi.mock("../../state/StudioContext", () => ({ useStudio: vi.fn() }));

import { useStudio } from "../../state/StudioContext";

function context(messages: ChatMessage[], overrides: Record<string, unknown> = {}) {
  return {
    settings: { base_url: "", api_key: "", model_name: "test-model", mcp_url: "", display_name: "" },
    llmHealth: { healthy: true, message: "" },
    brief: null,
    canvas: null,
    connectorSuggestions: [],
    presets: [],
    dismissConnectorSuggestion: vi.fn(),
    refreshConnectors: vi.fn(async () => {}),
    messages,
    streaming: false,
    sendMessage: vi.fn(async () => {}),
    regenerateFrom: vi.fn(async () => {}),
    editFrom: vi.fn(async () => {}),
    switchBranch: vi.fn(),
    respondToApproval: vi.fn(async () => {}),
    stopStreaming: vi.fn(),
    pushToast: vi.fn(),
    saveSettings: vi.fn(async () => {}),
    openPanel: vi.fn(),
    ...overrides,
  } as unknown as StudioContextValue;
}

const history: ChatMessage[] = [
  { id: "u-1", parentId: null, role: "user", content: "The first question" },
  { id: "a-1", parentId: "u-1", role: "assistant", content: "An answer" },
  { id: "u-2", parentId: "a-1", role: "user", content: "The latest question" },
  { id: "a-2", parentId: "u-2", role: "assistant", content: "Another answer" },
];

function renderComposer(overrides: Record<string, unknown> = {}) {
  vi.mocked(useStudio).mockReturnValue(context(history, overrides));
  render(
    <StudioRuntimeProvider>
      <ThreadComposer onCommand={() => {}} />
    </StudioRuntimeProvider>,
  );
  return screen.getByRole("textbox", { name: "Message the studio" }) as HTMLTextAreaElement;
}

function recalls(): string[] {
  return screen
    .queryAllByRole("status")
    .map((node) => node.textContent ?? "")
    .filter((text) => text.startsWith("Recalled your last message"));
}

describe("ThreadComposer recall", () => {
  it("recalls the message sent last on an empty draft, and says so once", () => {
    const input = renderComposer();

    fireEvent.keyDown(input, { key: "ArrowUp" });

    expect(input.value).toBe("The latest question");
    expect(recalls()).toHaveLength(1);
    expect(recalls()[0]).toContain("The latest question");
  });

  it("walks further back, then forward, then restores the draft", () => {
    const input = renderComposer();

    fireEvent.keyDown(input, { key: "ArrowUp" });
    expect(input.value).toBe("The latest question");

    fireEvent.keyDown(input, { key: "ArrowUp" });
    expect(input.value).toBe("The first question");

    fireEvent.keyDown(input, { key: "ArrowDown" });
    expect(input.value).toBe("The latest question");

    fireEvent.keyDown(input, { key: "ArrowDown" });
    expect(input.value).toBe("");
  });

  it("leaves a draft untouched when the caret is inside it", () => {
    const input = renderComposer();

    fireEvent.change(input, { target: { value: "a thought in progress" } });
    input.setSelectionRange(5, 5);
    fireEvent.keyDown(input, { key: "ArrowUp" });

    expect(input.value).toBe("a thought in progress");
    expect(recalls()).toHaveLength(0);
  });

  it("never recalls assistant text", () => {
    const input = renderComposer();

    fireEvent.keyDown(input, { key: "ArrowUp" });

    expect(input.value).not.toContain("Another answer");
  });

  it("still sends on Enter", () => {
    const sendMessage = vi.fn(async () => {});
    const input = renderComposer({ sendMessage });

    fireEvent.change(input, { target: { value: "Send this" } });
    fireEvent.keyDown(input, { key: "Enter" });

    expect(sendMessage).toHaveBeenCalledWith("Send this", expect.anything());
  });
});
