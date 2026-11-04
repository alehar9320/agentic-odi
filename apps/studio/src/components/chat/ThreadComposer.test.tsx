import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { StudioRuntimeProvider } from "../../assistant/StudioRuntime";
import type { StudioCommand } from "../../lib/commands";
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

function renderComposer(
  overrides: Record<string, unknown> = {},
  onCommand: (command: StudioCommand) => void = () => {},
) {
  vi.mocked(useStudio).mockReturnValue(context(history, overrides));
  render(
    <StudioRuntimeProvider>
      <ThreadComposer onCommand={onCommand} />
    </StudioRuntimeProvider>,
  );
  return screen.getByRole("textbox", { name: "Message the studio" }) as HTMLTextAreaElement;
}

/**
 * `fireEvent`'s `key` and `isComposing` init both land on the native event, so
 * this is the same event shape a real input method emits mid-composition.
 */
function composingKeyDown(
  input: HTMLTextAreaElement,
  init: { key: string; shiftKey?: boolean },
) {
  fireEvent.keyDown(input, { ...init, isComposing: true });
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

describe("ThreadComposer during IME composition", () => {
  it("leaves a composing Enter to the input method", () => {
    const onCommand = vi.fn();
    const sendMessage = vi.fn(async () => {});
    const input = renderComposer({ sendMessage }, onCommand);

    fireEvent.change(input, { target: { value: "/" } });
    composingKeyDown(input, { key: "Enter" });

    expect(onCommand).not.toHaveBeenCalled();
    expect(sendMessage).not.toHaveBeenCalled();
    expect(input.value).toBe("/");
  });

  it("treats the legacy keyCode 229 as composition too", () => {
    const onCommand = vi.fn();
    const sendMessage = vi.fn(async () => {});
    const input = renderComposer({ sendMessage }, onCommand);

    fireEvent.change(input, { target: { value: "/" } });
    // WebKit can commit a candidate with `isComposing` unset and keyCode 229.
    fireEvent.keyDown(input, { key: "Enter", keyCode: 229 });

    expect(onCommand).not.toHaveBeenCalled();
    expect(sendMessage).not.toHaveBeenCalled();
    expect(input.value).toBe("/");
  });

  it("does not move the palette highlight on a composing arrow", () => {
    const input = renderComposer();

    fireEvent.change(input, { target: { value: "/" } });
    composingKeyDown(input, { key: "ArrowDown" });

    expect(screen.getAllByRole("option")[0]).toHaveAttribute("aria-selected", "true");
  });

  it("does not dismiss the palette on a composing Escape", () => {
    const input = renderComposer();

    fireEvent.change(input, { target: { value: "/" } });
    composingKeyDown(input, { key: "Escape" });

    expect(screen.getByRole("listbox", { name: "Commands" })).toBeInTheDocument();
  });

  it("does not recall history on a composing arrow", () => {
    const input = renderComposer();

    composingKeyDown(input, { key: "ArrowUp" });

    expect(input.value).toBe("");
    expect(recalls()).toHaveLength(0);
  });

  it("runs the highlighted command on a plain Enter once composition ends", () => {
    const onCommand = vi.fn();
    const input = renderComposer({}, onCommand);

    fireEvent.change(input, { target: { value: "/status" } });
    fireEvent.keyDown(input, { key: "Enter" });

    expect(onCommand).toHaveBeenCalledWith(expect.objectContaining({ id: "status" }));
  });

  it("moves the highlight and closes on plain arrows and Escape", () => {
    const input = renderComposer();

    fireEvent.change(input, { target: { value: "/" } });
    fireEvent.keyDown(input, { key: "ArrowDown" });
    expect(screen.getAllByRole("option")[1]).toHaveAttribute("aria-selected", "true");

    fireEvent.keyDown(input, { key: "Escape" });
    expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
  });

  it("keeps Shift+Enter a newline and still sends a plain Enter", () => {
    const sendMessage = vi.fn(async () => {});
    const input = renderComposer({ sendMessage });

    fireEvent.change(input, { target: { value: "Send this" } });
    fireEvent.keyDown(input, { key: "Enter", shiftKey: true });
    expect(sendMessage).not.toHaveBeenCalled();

    fireEvent.keyDown(input, { key: "Enter" });
    expect(sendMessage).toHaveBeenCalledWith("Send this", expect.anything());
  });
});
